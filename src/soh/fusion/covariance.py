"""Covariance Intersection and positive-semidefinite matrix utilities.

Implements conservative Covariance Intersection (CI) for fusing correlated state
estimates with unknown cross-covariances (Julier & Uhlmann, 1997), along with
numerical safeguards (symmetrization, eigenvalue flooring, Joseph-form updates).
"""

from typing import Optional, Tuple
import numpy as np
from scipy.optimize import minimize_scalar


def enforce_positive_semidefinite(
    matrix: np.ndarray,
    min_eigenval: float = 1e-8,
) -> np.ndarray:
    """Enforce symmetry and positive-definiteness on a covariance matrix.
    
    Performs eigenvalue decomposition, clamps negative and sub-threshold eigenvalues
    to min_eigenval, and reconstructs the symmetric matrix.
    """
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"Matrix must be 2D square, got shape {matrix.shape}")

    # Symmetrize
    sym = 0.5 * (matrix + matrix.T)
    # Eigendecomposition (Hermitian/symmetric solver)
    eigvals, eigvecs = np.linalg.eigh(sym)
    # Floor eigenvalues
    eigvals_clamped = np.maximum(eigvals, min_eigenval)
    # Reconstruct
    reconstructed = eigvecs @ np.diag(eigvals_clamped) @ eigvecs.T
    return 0.5 * (reconstructed + reconstructed.T)


def covariance_intersection_scalar(
    val1: float,
    var1: float,
    val2: float,
    var2: float,
    objective: str = "min_trace",
    omega: Optional[float] = None,
) -> Tuple[float, float, float]:
    """Fuse two scalar estimates via Covariance Intersection.

    Args:
        val1: Mean of estimate 1.
        var1: Variance of estimate 1 (> 0).
        val2: Mean of estimate 2.
        var2: Variance of estimate 2 (> 0).
        objective: Optimization criterion ('min_trace', 'balanced', 'equal').
        omega: Optional explicit weight in [0, 1]. If provided, overrides objective.

    Returns:
        (fused_val, fused_var, optimal_omega)
    """
    if var1 <= 0 or var2 <= 0:
        raise ValueError(f"Variances must be positive, got var1={var1}, var2={var2}")

    if omega is not None:
        w = float(np.clip(omega, 0.0, 1.0))
    elif objective in ("min_trace", "min_var"):
        # For scalar CI, P_CI(w) = 1 / (w/var1 + (1-w)/var2)
        # Monotonically increasing or decreasing in w.
        w = 1.0 if var1 <= var2 else 0.0
    elif objective == "balanced":
        # Balanced weighting inversely proportional to variances
        w = float(var2 / (var1 + var2))
    elif objective == "equal":
        w = 0.5
    else:
        raise ValueError(f"Unknown scalar CI objective: '{objective}'. Use 'min_trace', 'balanced', or 'equal'.")

    # Degenerate boundary cases
    if w >= 1.0 - 1e-7:
        return float(val1), float(var1), 1.0
    if w <= 1e-7:
        return float(val2), float(var2), 0.0

    inv_var = (w / var1) + ((1.0 - w) / var2)
    fused_var = float(1.0 / inv_var)
    fused_val = float(fused_var * ((w * val1 / var1) + ((1.0 - w) * val2 / var2)))

    return fused_val, fused_var, w


def covariance_intersection_vector(
    x1: np.ndarray,
    p1: np.ndarray,
    x2: np.ndarray,
    p2: np.ndarray,
    objective: str = "det",
    omega: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Fuse two multivariate Gaussian estimates via Covariance Intersection.

    P_CI(w)^(-1) = w * P1^(-1) + (1 - w) * P2^(-1)
    x_CI(w) = P_CI(w) * [w * P1^(-1) * x1 + (1 - w) * P2^(-1) * x2]

    Args:
        x1: State vector 1 (n,)
        p1: Covariance matrix 1 (n, n)
        x2: State vector 2 (n,)
        p2: Covariance matrix 2 (n, n)
        objective: 'det' (minimize determinant / volume) or 'trace' (minimize trace / total variance).
        omega: Optional explicit weight in [0, 1].

    Returns:
        (fused_x, fused_p, optimal_omega)
    """
    p1_psd = enforce_positive_semidefinite(p1)
    p2_psd = enforce_positive_semidefinite(p2)

    inv_p1 = np.linalg.inv(p1_psd)
    inv_p2 = np.linalg.inv(p2_psd)

    if omega is not None:
        w_opt = float(np.clip(omega, 0.0, 1.0))
    else:
        def cost_func(w: float) -> float:
            inv_p_ci = w * inv_p1 + (1.0 - w) * inv_p2
            p_ci = np.linalg.inv(inv_p_ci)
            if objective == "det":
                return float(np.linalg.det(p_ci))
            elif objective == "trace":
                return float(np.trace(p_ci))
            else:
                raise ValueError(f"Unknown objective: {objective}")

        res = minimize_scalar(cost_func, bounds=(0.0, 1.0), method="bounded")
        w_opt = float(res.x)

    if w_opt >= 1.0 - 1e-7:
        return x1.copy(), p1_psd.copy(), 1.0
    if w_opt <= 1e-7:
        return x2.copy(), p2_psd.copy(), 0.0

    inv_p_fused = w_opt * inv_p1 + (1.0 - w_opt) * inv_p2
    p_fused = np.linalg.inv(inv_p_fused)
    x_fused = p_fused @ (w_opt * (inv_p1 @ x1) + (1.0 - w_opt) * (inv_p2 @ x2))

    p_fused = enforce_positive_semidefinite(p_fused)
    return x_fused, p_fused, w_opt
