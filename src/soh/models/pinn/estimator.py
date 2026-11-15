"""Physics-Informed Neural Network (PINN) Estimator for SOH_C and SOH_R.

Implements the SohEstimator interface with support for:
- Full Physics-Informed Neural Network (PINN) training
- Controlled ablation modes (no_physics, no_operating_conditions, empirical, mechanistic)
- Heteroscedastic + Monte Carlo Dropout uncertainty intervals
- Leave-One-Battery-Out cross-validation compatibility
"""

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple
import numpy as np
import torch
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
from soh.degradation.mechanisms import (
    EmpiricalAgingConfig,
    EmpiricalDegradationModel,
    SeiKineticsConfig,
    SeiKineticsModel,
)
from soh.estimators.base import SohEstimator
from soh.models.pinn.losses import LossWeights, PinnLossFunction
from soh.models.pinn.network import BatteryDegradationPINN, NetworkConfig
from soh.models.pinn.sei_kinetics import (
    LithiumPlatingModule,
    LossOfActiveMaterialModule,
    MultiComponentResistanceParameters,
    SeiGrowthMechanism,
    SeiKineticsParameters,
    SeiKineticsPhysics,
)


@dataclass
class PinnTrainingConfig:
    """Hyperparameters for training the BatteryDegradationPINN estimator."""

    epochs: int = 150
    learning_rate: float = 3.0e-3
    weight_decay: float = 1.0e-4
    batch_size: int = 64
    mode: str = "pinn"  # "pinn", "pure_mlp", "no_physics", "no_operating_conditions", "no_monotonicity", "pinn_reaction", "empirical", "mechanistic"
    mc_samples: int = 25
    seed: int = 42


class PinnSohEstimator(SohEstimator):
    """SOH Estimator driven by Physics-Informed Neural Networks and degradation kinetics."""

    def __init__(
        self,
        config: Optional[PinnTrainingConfig] = None,
        network_config: Optional[NetworkConfig] = None,
        kinetics_params: Optional[SeiKineticsParameters] = None,
        loss_weights: Optional[LossWeights] = None,
    ):
        self.config = config or PinnTrainingConfig()
        self.network_config = network_config or NetworkConfig()
        self.kinetics_params = kinetics_params or SeiKineticsParameters()
        self.loss_weights = loss_weights or LossWeights()

        # Modular physical degradation engines
        self.physics = SeiKineticsPhysics(self.kinetics_params)
        self.plating_module = LithiumPlatingModule()
        self.lam_module = LossOfActiveMaterialModule()

        # Classical reference baselines for ablation modes
        self.empirical_model = EmpiricalDegradationModel()
        self.mechanistic_model = SeiKineticsModel()

        # PyTorch Neural Network
        torch.manual_seed(self.config.seed)
        self.model = BatteryDegradationPINN(self.network_config)
        self.loss_fn = PinnLossFunction(
            kinetics_params=self.kinetics_params,
            weights=self.loss_weights,
        )

        self.is_fitted = False
        self.training_history: List[Dict[str, float]] = []
        self.conformal_scale_c: float = 1.96
        self.conformal_scale_r: float = 1.96

    def _extract_cycle_features(
        self, cycle: CycleRecord, spec_nominal_capacity_ah: float = 2.30
    ) -> Optional[np.ndarray]:
        """Extract physical input vector [t_s, ah_throughput, temp_k, current_a, soc]."""
        # Time duration and cumulative time
        duration = float(cycle.time_s[-1] - cycle.time_s[0]) if len(cycle.time_s) > 1 else 3600.0
        t_s = max(60.0, float(cycle.cycle_index + 1) * duration)

        # Cumulative throughput in Ah
        if hasattr(cycle, "ah_throughput") and cycle.ah_throughput is not None and cycle.ah_throughput > 0.0:
            ah_thru = float(cycle.ah_throughput)
        else:
            ah_thru = float(cycle.cycle_index) * spec_nominal_capacity_ah * 2.0

        # Operating temperature
        temp_c = float(np.mean(cycle.temp_c)) if len(cycle.temp_c) > 0 else 25.0
        if temp_c < -40.0 or temp_c > 85.0:
            return None  # Unphysical temperature
        temp_k = celsius_to_kelvin(temp_c)

        # Operating current and SOC
        current_a = float(np.mean(np.abs(cycle.current_a))) if len(cycle.current_a) > 0 else 1.0
        soc_avg = float(cycle.metadata.get("soc_avg", 0.50)) if hasattr(cycle, "metadata") and cycle.metadata else 0.50

        if self.config.mode == "no_operating_conditions":
            # Ablation mode: zero out temperature, current, and SOC variations
            temp_k = 298.15
            current_a = 0.0
            soc_avg = 0.50

        return np.array([t_s, ah_thru, temp_k, current_a, soc_avg], dtype=np.float32)

    def fit(self, dataset: SohDataset) -> "PinnSohEstimator":
        """Train PINN or calibrate reference model across cohort dataset."""
        if self.config.mode in ("empirical", "mechanistic"):
            self.is_fitted = True
            return self

        # Collect training cycles across all batteries
        x_list: List[np.ndarray] = []
        yc_list: List[float] = []
        yr_list: List[float] = []

        for cid, bdata in dataset.batteries.items():
            nom_cap = bdata.spec.nominal_capacity_ah
            for cycle in bdata.cycles:
                if cycle.soh_c_bol_true is None:
                    continue
                feat = self._extract_cycle_features(cycle, spec_nominal_capacity_ah=nom_cap)
                if feat is None:
                    continue
                x_list.append(feat)
                yc_list.append(float(cycle.soh_c_bol_true))
                true_r = float(cycle.soh_r_bol_true) if cycle.soh_r_bol_true is not None else 1.0
                yr_list.append(true_r)

        if len(x_list) < 2:
            raise ValueError(f"Insufficient training cycles for PINN: {len(x_list)}")

        x_arr = np.vstack(x_list)
        yc_arr = np.array(yc_list, dtype=np.float32).reshape(-1, 1)
        yr_arr = np.array(yr_list, dtype=np.float32).reshape(-1, 1)

        x_tensor = torch.tensor(x_arr, dtype=torch.float32, requires_grad=True)
        yc_tensor = torch.tensor(yc_arr, dtype=torch.float32)
        yr_tensor = torch.tensor(yr_arr, dtype=torch.float32)

        optimizer = optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        # Determine active loss components based on ablation mode
        is_pure_mlp = self.config.mode in ("pure_mlp", "no_physics")
        enable_phys = (not is_pure_mlp) and (self.config.mode != "no_physics")
        enable_mono = (not is_pure_mlp) and (self.config.mode != "no_monotonicity")
        enable_lli = not is_pure_mlp
        phys_mech = (
            SeiGrowthMechanism.REACTION_LIMITED
            if self.config.mode == "pinn_reaction"
            else SeiGrowthMechanism.SOLVENT_DIFFUSION_LIMITED
        )

        self.model.train()
        n_samples = len(x_arr)
        batch_size = min(self.config.batch_size, n_samples)

        for epoch in range(self.config.epochs):
            # Mini-batch or full-batch training
            indices = torch.randperm(n_samples)
            epoch_loss = 0.0

            for start_idx in range(0, n_samples, batch_size):
                batch_idx = indices[start_idx : start_idx + batch_size]
                bx = x_tensor[batch_idx].clone().detach().requires_grad_(True)
                byc = yc_tensor[batch_idx]
                byr = yr_tensor[batch_idx]

                optimizer.zero_grad()
                delta_m, sc, sr, lv_c, lv_r = self.model(bx)

                loss, metrics = self.loss_fn(
                    x_inputs=bx,
                    delta_sei_m=delta_m,
                    soh_c_pred=sc,
                    soh_r_pred=sr,
                    log_var_c=lv_c,
                    log_var_r=lv_r,
                    y_c_true=byc,
                    y_r_true=byr,
                    enable_physics=enable_phys,
                    enable_monotonicity=enable_mono,
                    enable_lli=enable_lli,
                    physics_mechanism=phys_mech,
                )

                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=2.0)
                optimizer.step()
                epoch_loss += loss.item()

            if (epoch + 1) % 50 == 0 or epoch == self.config.epochs - 1:
                self.training_history.append({"epoch": epoch + 1, "loss": epoch_loss})

        self.model.eval()
        self.is_fitted = True
        return self

    def predict_cycle(self, cycle: CycleRecord) -> SohEstimate:
        """Estimate SOH_C and SOH_R for a complete cycle record."""
        feat = self._extract_cycle_features(cycle)
        timestamp = float(cycle.metadata.get("timestamp_start", 0.0)) if hasattr(cycle, "metadata") and cycle.metadata else 0.0

        if feat is None:
            return SohEstimate(
                status=EstimationStatus.INSUFFICIENT_INFORMATION,
                quality=FeatureQualityRecord(
                    is_eligible=False, failure_reasons=["Cycle operating conditions unphysical or missing"]
                ),
            )

        temp_c = float(np.mean(cycle.temp_c)) if len(cycle.temp_c) > 0 else 25.0

        if self.config.mode == "empirical":
            ah_thru = float(feat[1])
            sc = self.empirical_model.predict_capacity_retention(ah_thru, avg_temp_c=temp_c)
            sr = self.empirical_model.predict_resistance_growth(ah_thru, avg_temp_c=temp_c)
            sr_ret = 1.0 / max(1.0, sr)
            return SohEstimate(
                status=EstimationStatus.VALID,
                soh_c=float(sc),
                soh_r=float(sr_ret),
                variance_c=1e-4,
                variance_r=1e-4,
                quality=FeatureQualityRecord(is_eligible=True),
                confidence_interval_95_c=(sc - 0.02, sc + 0.02),
                confidence_interval_95_r=(sr_ret - 0.02, sr_ret + 0.02),
            )

        if self.config.mode == "mechanistic":
            t_s = float(feat[0])
            delta_est = self.kinetics_params.delta_sei_0 + math.sqrt(
                max(0.0, 2.0 * self.kinetics_params.k_sei * t_s)
            )
            sc, sr = self.physics.delta_to_soh(delta_est)
            return SohEstimate(
                status=EstimationStatus.VALID,
                soh_c=float(sc),
                soh_r=float(sr),
                variance_c=1e-4,
                variance_r=1e-4,
                quality=FeatureQualityRecord(is_eligible=True),
                confidence_interval_95_c=(sc - 0.02, sc + 0.02),
                confidence_interval_95_r=(sr - 0.02, sr + 0.02),
            )

        # PINN and Neural Network inference
        x_tensor = torch.tensor(feat.reshape(1, -1), dtype=torch.float32)
        mean_c, std_c, mean_r, std_r = self.model.predict_with_uncertainty(
            x_tensor, num_mc_samples=self.config.mc_samples
        )

        sc = float(mean_c.item())
        vc = float((std_c.item()) ** 2)
        sr = float(mean_r.item())
        vr = float((std_r.item()) ** 2)

        ci_c = (max(0.0, sc - self.conformal_scale_c * std_c.item()), min(1.0, sc + self.conformal_scale_c * std_c.item()))
        ci_r = (max(0.0, sr - self.conformal_scale_r * std_r.item()), min(1.0, sr + self.conformal_scale_r * std_r.item()))

        return SohEstimate(
            status=EstimationStatus.VALID,
            soh_c=sc,
            soh_r=sr,
            variance_c=vc,
            variance_r=vr,
            confidence_interval_95_c=ci_c,
            confidence_interval_95_r=ci_r,
            quality=FeatureQualityRecord(
                is_eligible=True,
                temperature_drift_c_per_s=0.01,
                fit_rmse_mv=0.005,
            ),
        )

    def predict_window(
        self,
        window: PartialWindow,
        features: Optional[Dict[str, float]] = None,
    ) -> SohEstimate:
        """Estimate SOH from partial charging telemetry window."""
        temp_c = float(np.mean(window.temp_c)) if len(window.temp_c) > 0 else 25.0
        t_s = float(window.duration_s)
        current_a = float(np.mean(window.current_a)) if len(window.current_a) > 0 else 1.0
        soc_avg = 0.50

        # Ah throughput in this window
        ah_thru = abs(current_a) * (t_s / 3600.0)

        feat = np.array([t_s, ah_thru, celsius_to_kelvin(temp_c), current_a, soc_avg], dtype=np.float32)
        x_tensor = torch.tensor(feat.reshape(1, -1), dtype=torch.float32)

        mean_c, std_c, mean_r, std_r = self.model.predict_with_uncertainty(
            x_tensor, num_mc_samples=self.config.mc_samples
        )

        sc = float(mean_c.item())
        sr = float(mean_r.item())
        vc = float((std_c.item()) ** 2)
        vr = float((std_r.item()) ** 2)

        return SohEstimate(
            status=EstimationStatus.VALID,
            soh_c=sc,
            soh_r=sr,
            variance_c=vc,
            variance_r=vr,
            confidence_interval_95_c=(sc - self.conformal_scale_c * std_c.item(), sc + self.conformal_scale_c * std_c.item()),
            confidence_interval_95_r=(sr - self.conformal_scale_r * std_r.item(), sr + self.conformal_scale_r * std_r.item()),
            quality=FeatureQualityRecord(is_eligible=True),
        )

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
            for cycle in bdata.cycles:
                if cycle.soh_c_bol_true is None:
                    continue
                feat = self._extract_cycle_features(cycle, spec_nominal_capacity_ah=bdata.spec.nominal_capacity_ah)
                if feat is None:
                    continue

                x_t = torch.tensor(feat.reshape(1, -1), dtype=torch.float32)
                mean_c, std_c, mean_r, std_r = self.model.predict_with_uncertainty(
                    x_t, num_mc_samples=self.config.mc_samples
                )

                err_c = abs(float(cycle.soh_c_bol_true) - float(mean_c.item()))
                denom_c = max(1e-6, float(std_c.item()))
                scores_c.append(err_c / denom_c)

                if cycle.soh_r_bol_true is not None:
                    err_r = abs(float(cycle.soh_r_bol_true) - float(mean_r.item()))
                    denom_r = max(1e-6, float(std_r.item()))
                    scores_r.append(err_r / denom_r)

        if scores_c:
            n_c = len(scores_c)
            q_level = min(1.0, target_coverage * (1.0 + 1.0 / n_c))
            self.conformal_scale_c = float(np.quantile(scores_c, q_level))

        if scores_r:
            n_r = len(scores_r)
            q_level_r = min(1.0, target_coverage * (1.0 + 1.0 / n_r))
            self.conformal_scale_r = float(np.quantile(scores_r, q_level_r))

        return self.conformal_scale_c, self.conformal_scale_r

    def update_state(
        self,
        current_state: SOHState,
        estimate: SohEstimate,
        dt_s: float = 0.0,
    ) -> SOHState:
        """Update discrete health state tracking with estimate."""
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

    @staticmethod
    def evaluate_stratified_uncertainty(
        y_true: List[float],
        y_pred: List[float],
        ci_bounds: List[Tuple[float, float]],
    ) -> Dict[str, Dict[str, float]]:
        """Stratify prediction interval calibration into BOL (>95%), Mid (85-95%), and Degraded (<85%)."""
        yt = np.array(y_true, dtype=float)
        yp = np.array(y_pred, dtype=float)
        lb = np.array([c[0] for c in ci_bounds], dtype=float)
        ub = np.array([c[1] for c in ci_bounds], dtype=float)

        strata = {
            "bol_above_95": yt > 0.95,
            "mid_life_85_to_95": (yt >= 0.85) & (yt <= 0.95),
            "degraded_below_85": yt < 0.85,
        }

        results = {}
        for s_name, mask in strata.items():
            if not np.any(mask):
                results[s_name] = {"count": 0, "picp": 0.0, "mpiw": 0.0, "winkler": 0.0}
                continue
            s_yt = yt[mask]
            s_lb = lb[mask]
            s_ub = ub[mask]

            coverage = np.mean((s_yt >= s_lb) & (s_yt <= s_ub))
            mpiw = np.mean(s_ub - s_lb)
            alpha = 0.05
            width = s_ub - s_lb
            below = np.maximum(0.0, s_lb - s_yt)
            above = np.maximum(0.0, s_yt - s_ub)
            winkler = np.mean(width + (2.0 / alpha) * below + (2.0 / alpha) * above)

            results[s_name] = {
                "count": int(np.sum(mask)),
                "picp": float(coverage),
                "mpiw": float(mpiw),
                "winkler": float(winkler),
            }
        return results
