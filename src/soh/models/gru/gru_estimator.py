"""Gated Recurrent Unit (GRU) neural network estimator for battery degradation.

Implements a sequence-aware recurrent model for tracking cumulative SOH_C and SOH_R
degradation dynamics across cycling history, with heteroscedastic uncertainty heads
and conformal prediction calibration.
"""

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from soh.common.contracts import (
    CycleRecord,
    EstimationStatus,
    FeatureQualityRecord,
    PartialWindow,
    SOHState,
    SohEstimate,
)
from soh.common.units import celsius_to_kelvin
from soh.data.base_loader import SohBatteryData, SohDataset
from soh.estimators.base import SohEstimator


@dataclass
class GruNetworkConfig:
    """Hyperparameters for GRU degradation network."""

    input_dim: int = 5          # [t_s, ah_throughput, temp_k, current_a, soc]
    hidden_dim: int = 32
    num_layers: int = 1
    dropout_rate: float = 0.05
    sequence_length: int = 5     # Rolling historical cycle window length
    input_scales: Tuple[float, ...] = (1.0e-6, 1.0e-3, 0.02, 0.4348, 1.0)
    input_shifts: Tuple[float, ...] = (0.0, 0.0, -298.15, 0.0, -0.5)


class BatteryDegradationGRU(nn.Module):
    """PyTorch recurrent network for sequence-aware degradation tracking."""

    def __init__(self, config: Optional[GruNetworkConfig] = None):
        super().__init__()
        self.config = config or GruNetworkConfig()

        self.register_buffer("scales", torch.tensor(self.config.input_scales, dtype=torch.float32))
        self.register_buffer("shifts", torch.tensor(self.config.input_shifts, dtype=torch.float32))

        self.gru = nn.GRU(
            input_size=self.config.input_dim,
            hidden_size=self.config.hidden_dim,
            num_layers=self.config.num_layers,
            batch_first=True,
            dropout=self.config.dropout_rate if self.config.num_layers > 1 else 0.0,
        )

        self.dropout = nn.Dropout(p=self.config.dropout_rate)

        # Output heads
        self.head_c = nn.Sequential(
            nn.Linear(self.config.hidden_dim, 16),
            nn.SiLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )
        self.head_r = nn.Sequential(
            nn.Linear(self.config.hidden_dim, 16),
            nn.SiLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )
        self.head_log_var_c = nn.Sequential(
            nn.Linear(self.config.hidden_dim, 16),
            nn.SiLU(),
            nn.Linear(16, 1),
        )
        self.head_log_var_r = nn.Sequential(
            nn.Linear(self.config.hidden_dim, 16),
            nn.SiLU(),
            nn.Linear(16, 1),
        )

        # Initialize biases to realistic pristine BOL health (~0.98)
        nn.init.constant_(self.head_c[2].bias, 3.8)
        nn.init.constant_(self.head_r[2].bias, 3.8)
        nn.init.constant_(self.head_log_var_c[2].bias, -6.0)
        nn.init.constant_(self.head_log_var_r[2].bias, -6.0)

    def normalize_input(self, x: torch.Tensor) -> torch.Tensor:
        """Scale and shift input telemetry features."""
        return (x + self.shifts) * self.scales

    def forward(
        self,
        x_seq: torch.Tensor,
        hidden: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Forward pass through recurrent trunk.
        
        Args:
            x_seq: Tensor of shape (batch, seq_len, input_dim).
        Returns:
            (soh_c, soh_r, log_var_c, log_var_r, next_hidden)
        """
        x_norm = self.normalize_input(x_seq)
        out, next_hidden = self.gru(x_norm, hidden)
        last_hidden = self.dropout(out[:, -1, :])

        sc = self.head_c(last_hidden)
        sr = self.head_r(last_hidden)
        lv_c = self.head_log_var_c(last_hidden)
        lv_r = self.head_log_var_r(last_hidden)

        return sc, sr, lv_c, lv_r, next_hidden


@dataclass
class GruTrainingConfig:
    """Hyperparameters for GruSohEstimator training."""

    epochs: int = 100
    learning_rate: float = 3.0e-3
    weight_decay: float = 1.0e-4
    batch_size: int = 32
    mc_samples: int = 20
    seed: int = 42


class GruSohEstimator(SohEstimator):
    """Sequence-aware SOH Estimator powered by GRU recurrent dynamics."""

    def __init__(
        self,
        config: Optional[GruTrainingConfig] = None,
        network_config: Optional[GruNetworkConfig] = None,
    ):
        self.config = config or GruTrainingConfig()
        self.network_config = network_config or GruNetworkConfig()

        torch.manual_seed(self.config.seed)
        np.random.seed(self.config.seed)

        self.model = BatteryDegradationGRU(self.network_config)
        self.is_fitted = False
        self.n_samples_c: int = 0
        self.n_samples_r: int = 0
        self.conformal_scale_c: float = 1.96
        self.conformal_scale_r: float = 1.96
        self.history_by_cell: Dict[str, List[np.ndarray]] = {}
        self.history_buffer: List[np.ndarray] = []

    def reset(self, cell_id: Optional[str] = None) -> None:
        """Reset sequence history buffer for a specific cell or all cells."""
        if cell_id is not None:
            self.history_by_cell.pop(cell_id, None)
        else:
            self.history_by_cell.clear()
            self.history_buffer.clear()

    def _extract_cycle_features(
        self, cycle: CycleRecord, spec_nominal_capacity_ah: float = 2.30
    ) -> Optional[np.ndarray]:
        """Extract physical feature vector [t_s, ah_throughput, temp_k, current_a, soc]."""
        duration = float(cycle.time_s[-1] - cycle.time_s[0]) if len(cycle.time_s) > 1 else 3600.0
        t_s = max(60.0, float(cycle.cycle_index + 1) * duration)

        if hasattr(cycle, "ah_throughput") and cycle.ah_throughput is not None and cycle.ah_throughput > 0.0:
            ah_thru = float(cycle.ah_throughput)
        else:
            ah_thru = float(cycle.cycle_index) * spec_nominal_capacity_ah * 2.0

        temp_c = float(np.mean(cycle.temp_c)) if len(cycle.temp_c) > 0 else 25.0
        temp_k = celsius_to_kelvin(temp_c)
        current_a = float(np.mean(np.abs(cycle.current_a))) if len(cycle.current_a) > 0 else 1.0
        soc_avg = float(cycle.metadata.get("soc_avg", 0.50)) if hasattr(cycle, "metadata") and cycle.metadata else 0.50

        return np.array([t_s, ah_thru, temp_k, current_a, soc_avg], dtype=np.float32)

    def fit(self, dataset: SohDataset) -> "GruSohEstimator":
        """Train GRU model across sequence cycles from all cohort batteries."""
        seq_len = self.network_config.sequence_length
        sequences: List[np.ndarray] = []
        yc_list: List[float] = []
        yr_list: List[float] = []
        r_mask_list: List[float] = []

        for cid, bdata in dataset.batteries.items():
            nom_cap = bdata.spec.nominal_capacity_ah
            feats = []
            targets_c = []
            targets_r = []
            has_r = []

            for cycle in bdata.cycles:
                if cycle.soh_c_bol_true is None:
                    continue
                feat = self._extract_cycle_features(cycle, spec_nominal_capacity_ah=nom_cap)
                if feat is None:
                    continue
                feats.append(feat)
                targets_c.append(float(cycle.soh_c_bol_true))
                if cycle.soh_r_bol_true is not None:
                    targets_r.append(float(cycle.soh_r_bol_true))
                    has_r.append(True)
                else:
                    # Exclude missing SOH_R labels from SOH_R loss
                    targets_r.append(0.0)
                    has_r.append(False)

            n_cycles = len(feats)
            if n_cycles == 0:
                continue

            # Build sequence windows
            for i in range(n_cycles):
                if i < seq_len - 1:
                    pad_count = seq_len - 1 - i
                    pad = [feats[0]] * pad_count
                    window = np.vstack(pad + feats[: i + 1])
                else:
                    window = np.vstack(feats[i - seq_len + 1 : i + 1])

                sequences.append(window)
                yc_list.append(targets_c[i])
                yr_list.append(targets_r[i])
                r_mask_list.append(1.0 if has_r[i] else 0.0)

        if len(sequences) < 2:
            raise ValueError(f"Insufficient sequence cycles for GRU: {len(sequences)}")

        self.n_samples_c = len(yc_list)
        self.n_samples_r = int(sum(r_mask_list))

        x_seq_arr = np.array(sequences, dtype=np.float32)
        yc_arr = np.array(yc_list, dtype=np.float32).reshape(-1, 1)
        yr_arr = np.array(yr_list, dtype=np.float32).reshape(-1, 1)
        rmask_arr = np.array(r_mask_list, dtype=np.float32).reshape(-1, 1)

        x_tensor = torch.tensor(x_seq_arr, dtype=torch.float32)
        yc_tensor = torch.tensor(yc_arr, dtype=torch.float32)
        yr_tensor = torch.tensor(yr_arr, dtype=torch.float32)
        rmask_tensor = torch.tensor(rmask_arr, dtype=torch.float32)

        optimizer = optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        n_samples = len(x_seq_arr)
        batch_size = min(self.config.batch_size, n_samples)
        self.model.train()

        for epoch in range(self.config.epochs):
            indices = torch.randperm(n_samples)
            for start_idx in range(0, n_samples, batch_size):
                b_idx = indices[start_idx : start_idx + batch_size]
                bx = x_tensor[b_idx]
                byc = yc_tensor[b_idx]
                byr = yr_tensor[b_idx]
                bmask_r = rmask_tensor[b_idx]

                optimizer.zero_grad()
                sc, sr, lv_c, lv_r, _ = self.model(bx)

                # Anchored heteroscedastic loss for SOH_C
                diff_c = (byc - sc) ** 2
                clamped_lvc = torch.clamp(lv_c, min=-12.0, max=0.0)
                loss_c = torch.mean(diff_c + 0.02 * (0.5 * torch.exp(-clamped_lvc) * diff_c + 0.5 * clamped_lvc))

                # Masked heteroscedastic loss for SOH_R (exclude missing labels)
                if bmask_r.sum() > 0:
                    diff_r = (byr - sr) ** 2
                    clamped_lvr = torch.clamp(lv_r, min=-12.0, max=0.0)
                    loss_r_elem = diff_r + 0.02 * (0.5 * torch.exp(-clamped_lvr) * diff_r + 0.5 * clamped_lvr)
                    loss_r = torch.sum(loss_r_elem * bmask_r) / torch.clamp(bmask_r.sum(), min=1.0)
                else:
                    loss_r = 0.0 * torch.sum(sr)

                loss = loss_c + loss_r
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=2.0)
                optimizer.step()

        self.model.eval()
        self.is_fitted = True
        return self

    def calibrate_conformal(
        self,
        calibration_dataset: SohDataset,
        target_coverage: float = 0.95,
    ) -> Tuple[float, float]:
        """Calibrate uncertainty scaling factors using non-conformity scores on independent calibration data."""
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before calibration.")

        scores_c: List[float] = []
        scores_r: List[float] = []

        for cid, bdata in calibration_dataset.batteries.items():
            self.reset(cid)  # Reset cell sequence buffer
            for cycle in bdata.cycles:
                if cycle.soh_c_bol_true is None:
                    continue
                est = self.predict_cycle(cycle, cell_id=cid)
                if est.status != EstimationStatus.VALID or est.soh_c is None:
                    continue

                sc = float(est.soh_c)
                std_c = math.sqrt(est.variance_c) if est.variance_c else 0.01
                err_c = abs(float(cycle.soh_c_bol_true) - sc)
                scores_c.append(err_c / max(1e-6, std_c))

                if cycle.soh_r_bol_true is not None and est.soh_r is not None:
                    sr = float(est.soh_r)
                    std_r = math.sqrt(est.variance_r) if est.variance_r else 0.01
                    err_r = abs(float(cycle.soh_r_bol_true) - sr)
                    scores_r.append(err_r / max(1e-6, std_r))

        if scores_c:
            n_c = len(scores_c)
            q_level = min(1.0, target_coverage * (1.0 + 1.0 / n_c))
            self.conformal_scale_c = float(np.quantile(scores_c, q_level))

        if scores_r:
            n_r = len(scores_r)
            q_level_r = min(1.0, target_coverage * (1.0 + 1.0 / n_r))
            self.conformal_scale_r = float(np.quantile(scores_r, q_level_r))

        return self.conformal_scale_c, self.conformal_scale_r

    def predict_cycle(self, cycle: CycleRecord, cell_id: Optional[str] = None) -> SohEstimate:
        """Estimate SOH from sequential cycle record with per-cell history isolation."""
        feat = self._extract_cycle_features(cycle)
        if feat is None:
            return SohEstimate(
                status=EstimationStatus.INSUFFICIENT_INFORMATION,
                quality=FeatureQualityRecord(
                    is_eligible=False, failure_reasons=["Operating conditions unphysical"]
                ),
            )

        # Isolate history per cell_id
        cid = cell_id
        if cid is None and hasattr(cycle, "metadata") and cycle.metadata:
            cid = cycle.metadata.get("cell_id")
        if cid is None:
            cid = "__default__"

        if cid not in self.history_by_cell:
            self.history_by_cell[cid] = []

        buf = self.history_by_cell[cid]
        buf.append(feat)
        self.history_buffer = buf

        seq_len = self.network_config.sequence_length

        if len(buf) < seq_len:
            pad = [buf[0]] * (seq_len - len(buf))
            seq_window = np.vstack(pad + buf)
        else:
            seq_window = np.vstack(buf[-seq_len:])

        x_seq_tensor = torch.tensor(seq_window.reshape(1, seq_len, -1), dtype=torch.float32)

        # Monte Carlo Dropout inference
        self.model.train()  # Enable dropout
        c_preds: List[float] = []
        r_preds: List[float] = []
        c_vars: List[float] = []
        r_vars: List[float] = []

        with torch.no_grad():
            for _ in range(self.config.mc_samples):
                sc, sr, lv_c, lv_r, _ = self.model(x_seq_tensor)
                c_preds.append(float(sc.item()))
                r_preds.append(float(sr.item()))
                c_vars.append(float(torch.exp(lv_c).item()))
                r_vars.append(float(torch.exp(lv_r).item()))

        self.model.eval()

        mean_c = float(np.mean(c_preds))
        mean_r = float(np.mean(r_preds))

        # Total variance = aleatoric + epistemic
        total_var_c = float(np.mean(c_vars) + np.var(c_preds))
        total_var_r = float(np.mean(r_vars) + np.var(r_preds))

        std_c = math.sqrt(max(1e-8, total_var_c))
        std_r = math.sqrt(max(1e-8, total_var_r))

        ci_c = (max(0.0, mean_c - self.conformal_scale_c * std_c), min(1.20, mean_c + self.conformal_scale_c * std_c))
        ci_r = (max(0.0, mean_r - self.conformal_scale_r * std_r), min(1.50, mean_r + self.conformal_scale_r * std_r))

        return SohEstimate(
            status=EstimationStatus.VALID,
            soh_c=mean_c,
            soh_r=mean_r,
            variance_c=total_var_c,
            variance_r=total_var_r,
            confidence_interval_95_c=ci_c,
            confidence_interval_95_r=ci_r,
            quality=FeatureQualityRecord(is_eligible=True),
        )

    def predict_window(
        self,
        window: PartialWindow,
        features: Optional[Dict[str, float]] = None,
    ) -> SohEstimate:
        """Estimate SOH from partial telemetry window."""
        temp_c = float(np.mean(window.temp_c)) if len(window.temp_c) > 0 else 25.0
        t_s = float(window.duration_s)
        current_a = float(np.mean(window.current_a)) if len(window.current_a) > 0 else 1.0
        soc_avg = 0.50
        ah_thru = abs(current_a) * (t_s / 3600.0)

        feat = np.array([t_s, ah_thru, celsius_to_kelvin(temp_c), current_a, soc_avg], dtype=np.float32)
        seq_len = self.network_config.sequence_length
        seq_window = np.vstack([feat] * seq_len)
        x_seq_tensor = torch.tensor(seq_window.reshape(1, seq_len, -1), dtype=torch.float32)

        with torch.no_grad():
            sc, sr, lv_c, lv_r, _ = self.model(x_seq_tensor)

        mean_c = float(sc.item())
        mean_r = float(sr.item())
        var_c = float(torch.exp(lv_c).item())
        var_r = float(torch.exp(lv_r).item())

        std_c = math.sqrt(max(1e-8, var_c))
        std_r = math.sqrt(max(1e-8, var_r))

        ci_c = (max(0.0, mean_c - self.conformal_scale_c * std_c), min(1.0, mean_c + self.conformal_scale_c * std_c))
        ci_r = (max(0.0, mean_r - self.conformal_scale_r * std_r), min(1.0, mean_r + self.conformal_scale_r * std_r))

        return SohEstimate(
            status=EstimationStatus.VALID,
            soh_c=mean_c,
            soh_r=mean_r,
            variance_c=var_c,
            variance_r=var_r,
            confidence_interval_95_c=ci_c,
            confidence_interval_95_r=ci_r,
            quality=FeatureQualityRecord(is_eligible=True),
        )

    def update_state(
        self,
        current_state: SOHState,
        estimate: SohEstimate,
        dt_s: float = 0.0,
    ) -> SOHState:
        """Update state tracking with GRU estimate."""
        if estimate.status != EstimationStatus.VALID:
            return current_state

        new_c = estimate.soh_c if estimate.soh_c is not None else current_state.soh_c
        new_r = estimate.soh_r if estimate.soh_r is not None else current_state.soh_r
        ts = estimate.timestamp if hasattr(estimate, "timestamp") and estimate.timestamp is not None else current_state.timestamp

        return SOHState(
            timestamp=ts,
            soh_c=new_c,
            soh_r=new_r,
            soh_c_var=estimate.variance_c if estimate.variance_c is not None else current_state.soh_c_var,
            soh_r_var=estimate.variance_r if estimate.variance_r is not None else current_state.soh_r_var,
            cov_cr=current_state.cov_cr,
        )
