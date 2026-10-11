"""SOC Estimator interfaces, base types, implementations, and registry."""

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.registry import get_estimator, list_registered_estimators

__all__ = [
    "Estimator",
    "ParamSet",
    "SocEstimate",
    "E0CoulombCounting",
    "E1ExtendedKalmanFilter",
    "E2EKFHysteresis",
    "get_estimator",
    "list_registered_estimators",
]
