"""Dual-state Multi-Estimator Fusion Engine.

Maintains separate capacity (SOH_C) and resistance (SOH_R) health states.
Integrates scalar and partial estimator observations, handles asynchronous updates,
prevents overconfidence on shared sensor data via Covariance Intersection,
and protects state integrity using Chi-squared innovation gating.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from soh.common.contracts import (
    CycleRecord,
    EstimationStatus,
    FeatureQualityRecord,
    QualificationStatus,
    SOHState,
    SohEstimate,
)
from soh.data.base_loader import SohDataset
from soh.estimators.base import SohEstimator
from soh.fusion.covariance import (
    covariance_intersection_scalar,
    enforce_positive_semidefinite,
)
from soh.fusion.gating import GatingResult, InnovationGater


@dataclass
class FusionConfig:
    """Configuration parameters for multi-estimator fusion."""

    process_noise_c: float = 1e-6          # Process noise variance on SOH_C per cycle
    process_noise_r: float = 1e-6          # Process noise variance on SOH_R per cycle
    initial_var_c: float = 1e-4            # Initial prior variance for SOH_C
    initial_var_r: float = 1e-4            # Initial prior variance for SOH_R
    initial_cov_cr: float = 0.0            # Initial cross-covariance
    throughput_deg_rate_c: float = 1.5e-5  # Capacity degradation rate per Ah throughput
    throughput_deg_rate_r: float = 2.0e-5  # Resistance degradation rate per Ah throughput
    significance_level: float = 0.01       # 99% confidence region for innovation gating
    min_eigenval: float = 1e-8             # Eigenvalue floor for numerical stability
    ci_objective: str = "balanced"         # Objective for scalar CI ('balanced', 'min_trace', 'equal')
    max_stale_cycles: int = 5              # Max cycle latency before rejecting observation
    soh_min: float = 0.05                  # Physical lower bound for SOH
    soh_max: float = 1.20                  # Physical upper bound for SOH


@dataclass
class FusionCycleLog:
    """Diagnostic audit record for a single fusion cycle."""

    cycle_index: int
    prior_state: np.ndarray
    prior_covariance: np.ndarray
    posterior_state: np.ndarray
    posterior_covariance: np.ndarray
    updated_sources: List[str]
    ci_weight_omega: Optional[float] = None
    gating_result: Optional[GatingResult] = None
    rejection_reasons: List[str] = field(default_factory=list)


class DualSohFusionTracker:
    """Multi-Estimator Kalman Fusion Engine with Covariance Intersection.
    
    Tracks state vector x = [SOH_C, SOH_R]^T and 2x2 error covariance P.
    """

    def __init__(
        self,
        config: Optional[FusionConfig] = None,
        ica_estimator: Optional[SohEstimator] = None,
        pulse_estimator: Optional[SohEstimator] = None,
    ):
        self.config = config or FusionConfig()
        self.ica_estimator = ica_estimator
        self.pulse_estimator = pulse_estimator
        self.gater = InnovationGater(
            significance_level=self.config.significance_level,
            min_eigenval=self.config.min_eigenval,
        )

        # Internal state vector [SOH_C, SOH_R]^T
        self.x = np.array([1.0, 1.0], dtype=float)
        # Covariance matrix P (2x2)
        self.P = np.array(
            [
                [self.config.initial_var_c, self.config.initial_cov_cr],
                [self.config.initial_cov_cr, self.config.initial_var_r],
            ],
            dtype=float,
        )
        self.P = enforce_positive_semidefinite(self.P, min_eigenval=self.config.min_eigenval)

        self.current_cycle_index: int = 0
        self.current_timestamp_s: float = 0.0
        self.last_ah_throughput: float = 0.0
        self.is_initialized: bool = True
        self.history: List[FusionCycleLog] = []

    def reset(
        self,
        initial_soh_c: float = 1.0,
        initial_soh_r: float = 1.0,
        initial_cov: Optional[np.ndarray] = None,
    ) -> None:
        """Reset filter to pristine state."""
        self.x = np.array([initial_soh_c, initial_soh_r], dtype=float)
        if initial_cov is not None:
            self.P = enforce_positive_semidefinite(initial_cov, min_eigenval=self.config.min_eigenval)
        else:
            p_init = np.array(
                [
                    [self.config.initial_var_c, self.config.initial_cov_cr],
                    [self.config.initial_cov_cr, self.config.initial_var_r],
                ],
                dtype=float,
            )
            self.P = enforce_positive_semidefinite(p_init, min_eigenval=self.config.min_eigenval)
        self.current_cycle_index = 0
        self.current_timestamp_s = 0.0
        self.last_ah_throughput = 0.0
        self.history.clear()
        self.is_c_qualified: bool = False
        self.is_r_qualified: bool = False
        self.qualification_status_c: QualificationStatus = QualificationStatus.UNVALIDATED
        self.qualification_status_r: QualificationStatus = QualificationStatus.UNVALIDATED

    def fit(self, dataset: SohDataset) -> "DualSohFusionTracker":
        """Learn degradation process rates and train sub-estimators."""
        # 1. Fit sub-estimators if provided
        if self.ica_estimator is not None:
            self.ica_estimator.fit(dataset)
        if self.pulse_estimator is not None:
            self.pulse_estimator.fit(dataset)

        # 2. Learn physical degradation transition rates from training cycles
        delta_ah_list: List[float] = []
        delta_soh_c_list: List[float] = []
        delta_soh_r_list: List[float] = []

        for cid, bdata in dataset.batteries.items():
            if len(bdata.cycles) >= 2:
                c_first = bdata.cycles[0]
                c_last = bdata.cycles[-1]
                if (
                    c_first.ah_throughput is not None
                    and c_last.ah_throughput is not None
                    and c_first.soh_c_bol_true is not None
                    and c_last.soh_c_bol_true is not None
                ):
                    d_ah = float(c_last.ah_throughput - c_first.ah_throughput)
                    d_c = float(c_first.soh_c_bol_true - c_last.soh_c_bol_true)
                    if d_ah > 0 and d_c >= 0:
                        delta_ah_list.append(d_ah)
                        delta_soh_c_list.append(d_c)

                    if (
                        c_first.soh_r_bol_true is not None
                        and c_last.soh_r_bol_true is not None
                    ):
                        d_r = float(c_first.soh_r_bol_true - c_last.soh_r_bol_true)
                        if d_r >= 0:
                            delta_soh_r_list.append(d_r)

        total_ah = sum(delta_ah_list)
        if total_ah > 0:
            if delta_soh_c_list:
                self.config.throughput_deg_rate_c = float(sum(delta_soh_c_list) / total_ah)
            if delta_soh_r_list and len(delta_soh_r_list) == len(delta_ah_list):
                self.config.throughput_deg_rate_r = float(sum(delta_soh_r_list) / total_ah)

        return self

    def predict_step(
        self,
        delta_ah: float = 0.0,
        dt_s: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Propagate state and covariance forward via physical degradation kinetics."""
        eff_delta_ah = max(0.0, float(delta_ah))

        # Irreversible physical degradation: x_k^- = x_{k-1} - alpha * delta_ah
        self.x[0] = self.x[0] - self.config.throughput_deg_rate_c * eff_delta_ah
        self.x[1] = self.x[1] - self.config.throughput_deg_rate_r * eff_delta_ah

        # Process noise covariance Q
        q_mat = np.diag([self.config.process_noise_c, self.config.process_noise_r])
        self.P = self.P + q_mat
        self.P = enforce_positive_semidefinite(self.P, min_eigenval=self.config.min_eigenval)

        return self.x.copy(), self.P.copy()

    def update_cycle(
        self,
        cycle: CycleRecord,
        est_ica: Optional[SohEstimate] = None,
        est_pulse: Optional[SohEstimate] = None,
    ) -> Tuple[SOHState, FusionCycleLog]:
        """Execute complete fusion cycle: propagate, fuse compatible estimators, gate, and update."""
        cycle_idx = cycle.cycle_index
        rejection_reasons: List[str] = []
        updated_sources: List[str] = []
        ci_omega: Optional[float] = None
        gating_res: Optional[GatingResult] = None

        # 1. Staleness check
        if cycle_idx < self.current_cycle_index:
            rejection_reasons.append(
                f"Out-of-order cycle {cycle_idx} (tracker at {self.current_cycle_index})"
            )
            # Retain current state without corruption
            return self.get_state(), FusionCycleLog(
                cycle_index=cycle_idx,
                prior_state=self.x.copy(),
                prior_covariance=self.P.copy(),
                posterior_state=self.x.copy(),
                posterior_covariance=self.P.copy(),
                updated_sources=[],
                rejection_reasons=rejection_reasons,
            )

        # 2. Compute throughput increment & predict step
        delta_ah = max(0.0, cycle.ah_throughput - self.last_ah_throughput)
        dt_s = float(cycle.time_s[-1] - cycle.time_s[0]) if len(cycle.time_s) > 1 else 0.0
        self.last_ah_throughput = cycle.ah_throughput
        self.current_cycle_index = cycle_idx
        self.current_timestamp_s += dt_s

        prior_x, prior_P = self.predict_step(delta_ah=delta_ah, dt_s=dt_s)

        # 3. If sub-estimators are attached and estimates not explicitly passed, compute them
        if est_ica is None and self.ica_estimator is not None:
            if hasattr(self.ica_estimator, "predict_cycle"):
                est_ica = self.ica_estimator.predict_cycle(cycle)  # type: ignore

        if est_pulse is None and self.pulse_estimator is not None:
            if hasattr(self.pulse_estimator, "predict_cycle"):
                est_pulse = self.pulse_estimator.predict_cycle(cycle)  # type: ignore

        # 4. Check eligibility and validity of candidate estimates
        ica_valid = (
            est_ica is not None
            and est_ica.status == EstimationStatus.VALID
            and est_ica.quality.is_eligible
            and est_ica.soh_c is not None
        )
        pulse_c_valid = (
            est_pulse is not None
            and est_pulse.status == EstimationStatus.VALID
            and est_pulse.quality.is_eligible
            and est_pulse.soh_c is not None
        )
        pulse_r_valid = (
            est_pulse is not None
            and est_pulse.status == EstimationStatus.VALID
            and est_pulse.quality.is_eligible
            and est_pulse.soh_r is not None
        )

        z: Optional[np.ndarray] = None
        R: Optional[np.ndarray] = None
        H: Optional[np.ndarray] = None

        # Case A: Both ICA and Pulse provide valid SOH_C
        if ica_valid and pulse_c_valid:
            assert est_ica is not None and est_pulse is not None
            assert est_ica.soh_c is not None and est_pulse.soh_c is not None

            var_ica_c = est_ica.variance_c if est_ica.variance_c and est_ica.variance_c > 0 else 1e-4
            var_pulse_c = est_pulse.variance_c if est_pulse.variance_c and est_pulse.variance_c > 0 else 1e-4

            # Fuse correlated SOH_C subspace via Covariance Intersection
            fused_c, fused_var_c, ci_omega = covariance_intersection_scalar(
                val1=est_ica.soh_c,
                var1=var_ica_c,
                val2=est_pulse.soh_c,
                var2=var_pulse_c,
                objective=self.config.ci_objective,
            )

            if pulse_r_valid and est_pulse.soh_r is not None:
                var_pulse_r = est_pulse.variance_r if est_pulse.variance_r and est_pulse.variance_r > 0 else 1e-4
                # Joint 2D observation: [fused_SOH_C, SOH_R]
                z = np.array([fused_c, est_pulse.soh_r], dtype=float)
                R = np.diag([fused_var_c, var_pulse_r])
                H = np.eye(2)
                updated_sources = ["ICA_CI", "PULSE_CI_R"]
            else:
                # Scalar observation: fused_SOH_C
                z = np.array([fused_c], dtype=float)
                R = np.array([[fused_var_c]], dtype=float)
                H = np.array([[1.0, 0.0]], dtype=float)
                updated_sources = ["ICA_PULSE_CI_C"]

        # Case B: Only ICA is valid
        elif ica_valid:
            assert est_ica is not None and est_ica.soh_c is not None
            var_ica_c = est_ica.variance_c if est_ica.variance_c and est_ica.variance_c > 0 else 1e-4
            z = np.array([est_ica.soh_c], dtype=float)
            R = np.array([[var_ica_c]], dtype=float)
            H = np.array([[1.0, 0.0]], dtype=float)
            updated_sources = ["ICA"]

        # Case C: Only Pulse is valid
        elif pulse_c_valid or pulse_r_valid:
            assert est_pulse is not None
            if pulse_c_valid and pulse_r_valid:
                assert est_pulse.soh_c is not None and est_pulse.soh_r is not None
                var_c = est_pulse.variance_c if est_pulse.variance_c and est_pulse.variance_c > 0 else 1e-4
                var_r = est_pulse.variance_r if est_pulse.variance_r and est_pulse.variance_r > 0 else 1e-4
                z = np.array([est_pulse.soh_c, est_pulse.soh_r], dtype=float)
                R = np.diag([var_c, var_r])
                H = np.eye(2)
                updated_sources = ["PULSE_DUAL"]
            elif pulse_c_valid:
                assert est_pulse.soh_c is not None
                var_c = est_pulse.variance_c if est_pulse.variance_c and est_pulse.variance_c > 0 else 1e-4
                z = np.array([est_pulse.soh_c], dtype=float)
                R = np.array([[var_c]], dtype=float)
                H = np.array([[1.0, 0.0]], dtype=float)
                updated_sources = ["PULSE_C"]
            else:
                assert est_pulse.soh_r is not None
                var_r = est_pulse.variance_r if est_pulse.variance_r and est_pulse.variance_r > 0 else 1e-4
                z = np.array([est_pulse.soh_r], dtype=float)
                R = np.array([[var_r]], dtype=float)
                H = np.array([[0.0, 1.0]], dtype=float)
                updated_sources = ["PULSE_R"]

        # Case D: Neither valid -> bypass measurement update
        else:
            if est_ica and not est_ica.quality.is_eligible:
                rejection_reasons.extend(est_ica.quality.failure_reasons)
            if est_pulse and not est_pulse.quality.is_eligible:
                rejection_reasons.extend(est_pulse.quality.failure_reasons)

        # 5. Perform Innovation Gating and Joseph-Form Kalman Update if observation exists
        if z is not None and R is not None and H is not None:
            gating_res = self.gater.evaluate(
                z=z,
                H=H,
                x_prior=self.x,
                P_prior=self.P,
                R=R,
            )

            if gating_res.is_accepted:
                # Innovation: y = z - H * x
                y = z - (H @ self.x)
                # Innovation covariance: S = H * P * H^T + R
                S = H @ self.P @ H.T + R
                S_psd = enforce_positive_semidefinite(S, min_eigenval=self.config.min_eigenval)

                # Kalman gain: K = P * H^T * S^(-1)
                K = self.P @ H.T @ np.linalg.inv(S_psd)

                # State update: x^+ = x^- + K * y
                self.x = self.x + (K @ y)

                # Joseph-form covariance update:
                # P^+ = (I - K * H) * P * (I - K * H)^T + K * R * K^T
                I_mat = np.eye(2)
                I_KH = I_mat - (K @ H)
                self.P = (I_KH @ self.P @ I_KH.T) + (K @ R @ K.T)

                # Update independent qualification statuses if sources are qualified
                if ica_valid and est_ica and getattr(est_ica, "qualification_status_c", None) == QualificationStatus.QUALIFIED:
                    self.is_c_qualified = True
                    self.qualification_status_c = QualificationStatus.QUALIFIED
                if pulse_c_valid and est_pulse and getattr(est_pulse, "qualification_status_c", None) == QualificationStatus.QUALIFIED:
                    self.is_c_qualified = True
                    self.qualification_status_c = QualificationStatus.QUALIFIED
                if pulse_r_valid and est_pulse and getattr(est_pulse, "qualification_status_r", None) == QualificationStatus.QUALIFIED:
                    self.is_r_qualified = True
                    self.qualification_status_r = QualificationStatus.QUALIFIED
            else:
                rejection_reasons.append(
                    gating_res.rejection_reason or "Innovation gate rejected observation."
                )
                updated_sources = []

        # 6. Enforce PSD and physical bounding
        self.P = enforce_positive_semidefinite(self.P, min_eigenval=self.config.min_eigenval)
        self.x = np.clip(self.x, self.config.soh_min, self.config.soh_max)

        log_entry = FusionCycleLog(
            cycle_index=cycle_idx,
            prior_state=prior_x,
            prior_covariance=prior_P,
            posterior_state=self.x.copy(),
            posterior_covariance=self.P.copy(),
            updated_sources=updated_sources,
            ci_weight_omega=ci_omega,
            gating_result=gating_res,
            rejection_reasons=rejection_reasons,
        )
        self.history.append(log_entry)

        return self.get_state(), log_entry

    def get_state(self) -> SOHState:
        """Return current estimated health state with independent qualification statuses."""
        return SOHState(
            soh_c_bol=float(self.x[0]),
            soh_c_rated=float(self.x[0]),
            soh_r_bol=float(self.x[1]),
            cycle_index=self.current_cycle_index,
            timestamp_s=self.current_timestamp_s,
            covariance=self.P.copy(),
            is_c_qualified=self.is_c_qualified,
            is_r_qualified=self.is_r_qualified,
            qualification_status_c=self.qualification_status_c,
            qualification_status_r=self.qualification_status_r,
        )
