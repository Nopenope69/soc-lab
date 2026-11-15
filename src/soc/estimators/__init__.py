"""SOC Estimator interfaces, base types, implementations, and registry."""

from typing import TYPE_CHECKING, List

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.e3_ukf import E3UnscentedKalmanFilter
from soc.estimators.e4_rls_r0 import E4RLSR0EKF
from soc.estimators.e4v2_rls import E4V2RLSEKF
from soc.estimators.e5_observability_ekf import E5ObservabilityEKF
from soc.estimators.e5v4 import E5V4ObservabilityEKF
from soc.estimators.e6_rbc_dekf import E6RBCDEKF
from soc.estimators.innovation_gating import D3InnovationGatedEKF
from soc.estimators.e7v2 import E7V2CompositeFilter
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.estimators.registry import get_estimator, list_registered_estimators

if TYPE_CHECKING:
    from soc.estimators.e8_residual_gru import E8ResidualGRUEstimator
    from soc.estimators.e8_residual_lgbm import E8ResidualLGBMEstimator
    from soc.estimators.e9_tcn_ukf import E9TCNUKFEstimator
    from soc.estimators.e10_pinn_aekf import E10PINNAEKFEstimator


def __getattr__(name: str):
    if name == "E8ResidualGRUEstimator":
        try:
            from soc.estimators.e8_residual_gru import E8ResidualGRUEstimator
            return E8ResidualGRUEstimator
        except ImportError as e:
            raise ImportError(
                "E8ResidualGRUEstimator requires the 'neural' extra (torch). Install with: pip install 'soc-lab[neural]'"
            ) from e
    if name == "E8ResidualLGBMEstimator":
        try:
            from soc.estimators.e8_residual_lgbm import E8ResidualLGBMEstimator, lgb
            if lgb is None:
                raise ImportError("lightgbm is not available")
            return E8ResidualLGBMEstimator
        except ImportError as e:
            raise ImportError(
                "E8ResidualLGBMEstimator requires the 'neural' extra (lightgbm). Install with: pip install 'soc-lab[neural]'"
            ) from e
    if name == "E9TCNUKFEstimator":
        try:
            from soc.estimators.e9_tcn_ukf import E9TCNUKFEstimator
            return E9TCNUKFEstimator
        except ImportError as e:
            raise ImportError(
                "E9TCNUKFEstimator requires the 'neural' extra (torch). Install with: pip install 'soc-lab[neural]'"
            ) from e
    if name == "E10PINNAEKFEstimator":
        try:
            from soc.estimators.e10_pinn_aekf import E10PINNAEKFEstimator
            return E10PINNAEKFEstimator
        except ImportError as e:
            raise ImportError(
                "E10PINNAEKFEstimator requires the 'neural' extra (torch). Install with: pip install 'soc-lab[neural]'"
            ) from e
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Estimator",
    "ParamSet",
    "SocEstimate",
    "E0CoulombCounting",
    "E1ExtendedKalmanFilter",
    "E2EKFHysteresis",
    "E3UnscentedKalmanFilter",
    "E4RLSR0EKF",
    "E4V2RLSEKF",
    "E5ObservabilityEKF",
    "E5V4ObservabilityEKF",
    "E6RBCDEKF",
    "D3InnovationGatedEKF",
    "E7V2CompositeFilter",
    "E7V3CompositeFilter",
    "E8ResidualGRUEstimator",
    "E8ResidualLGBMEstimator",
    "E9TCNUKFEstimator",
    "E10PINNAEKFEstimator",
    "get_estimator",
    "list_registered_estimators",
]
