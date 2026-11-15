"""Innovation gating and outlier rejection for multi-sensor Kalman updates.

Computes Mahalanobis innovation distances against theoretical Chi-squared distribution
thresholds to detect and reject sensor glitches, thermal transients, or unmodeled dynamics
before they corrupt the battery health state.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from scipy.stats import chi2

from soh.fusion.covariance import enforce_positive_semidefinite


@dataclass
class GatingResult:
    """Diagnostic outcome of innovation gating check."""

    is_accepted: bool
    mahalanobis_dist_sq: float
    threshold: float
    degrees_of_freedom: int
    p_value: float
    rejection_reason: Optional[str] = None


class InnovationGater:
    """Chi-squared innovation gate for scalar and multivariate measurement updates."""

    def __init__(
        self,
        significance_level: float = 0.01,  # 99% confidence acceptance region
        min_eigenval: float = 1e-9,
    ):
        if not (0.0 < significance_level < 1.0):
            raise ValueError(f"significance_level must be in (0, 1), got {significance_level}")
        self.significance_level = significance_level
        self.min_eigenval = min_eigenval

    def evaluate(
        self,
        z: np.ndarray,
        H: np.ndarray,
        x_prior: np.ndarray,
        P_prior: np.ndarray,
        R: np.ndarray,
        custom_threshold: Optional[float] = None,
    ) -> GatingResult:
        """Evaluate whether observation z passes innovation gating.

        Args:
            z: Measurement vector (m,)
            H: Observation matrix (m, n)
            x_prior: Prior state vector (n,)
            P_prior: Prior state covariance (n, n)
            R: Measurement noise covariance (m, m)
            custom_threshold: Optional threshold override.

        Returns:
            GatingResult with acceptance flag and diagnostic metrics.
        """
        z_vec = np.atleast_1d(z).astype(float)
        x_vec = np.atleast_1d(x_prior).astype(float)
        m = len(z_vec)
        n = len(x_vec)

        H_mat = np.atleast_2d(H).astype(float)
        if H_mat.shape != (m, n):
            raise ValueError(f"H shape {H_mat.shape} must match (m={m}, n={n})")

        P_mat = np.atleast_2d(P_prior).astype(float)
        R_mat = np.atleast_2d(R).astype(float)

        # Innovation: y = z - H * x
        innovation = z_vec - (H_mat @ x_vec)

        # Innovation covariance: S = H * P * H^T + R
        S = H_mat @ P_mat @ H_mat.T + R_mat
        S_psd = enforce_positive_semidefinite(S, min_eigenval=self.min_eigenval)

        # Mahalanobis distance squared: d_M^2 = y^T * S^(-1) * y
        try:
            inv_S = np.linalg.inv(S_psd)
            d_m2 = float(innovation.T @ inv_S @ innovation)
        except np.linalg.LinAlgError:
            return GatingResult(
                is_accepted=False,
                mahalanobis_dist_sq=float("inf"),
                threshold=0.0,
                degrees_of_freedom=m,
                p_value=0.0,
                rejection_reason="Singular innovation covariance matrix S",
            )

        threshold = (
            custom_threshold
            if custom_threshold is not None
            else float(chi2.ppf(1.0 - self.significance_level, df=m))
        )

        p_val = float(1.0 - chi2.cdf(d_m2, df=m))
        is_accepted = bool(d_m2 <= threshold)

        reason = None
        if not is_accepted:
            reason = (
                f"Innovation outlier: d_M^2={d_m2:.3f} exceeded Chi2({m}) "
                f"threshold {threshold:.3f} (p={p_val:.4e})"
            )

        return GatingResult(
            is_accepted=is_accepted,
            mahalanobis_dist_sq=d_m2,
            threshold=threshold,
            degrees_of_freedom=m,
            p_value=p_val,
            rejection_reason=reason,
        )
