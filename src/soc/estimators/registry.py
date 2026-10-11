"""Estimator registry for E0 through E7.

E0, E1, and E2 are fully implemented.
E3 through E7 raise NotImplementedError at construction (scheduled for Phase 4).
"""

from typing import Dict, List, Type

from soc.estimators.base import Estimator, ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis


class _StubEstimator(Estimator):
    """Stub estimator raising NotImplementedError at construction."""

    def __init__(self, name: str, params: ParamSet):
        raise NotImplementedError(f"{name} is scheduled for Phase 4")

    def reset(self, soc0: float) -> None:
        pass

    def step(self, measurement: Any) -> Any:
        pass


def _create_stub(name: str) -> Type[Estimator]:
    """Create a stub estimator class that raises NotImplementedError upon instantiation."""
    class Stub(Estimator):
        def __init__(self, params: ParamSet):
            raise NotImplementedError(f"{name} is scheduled for Phase 4")

        def reset(self, soc0: float) -> None:
            pass

        def step(self, measurement: Any) -> Any:
            pass

    Stub.__name__ = f"{name}Stub"
    return Stub


ESTIMATOR_REGISTRY: Dict[str, Type[Estimator]] = {
    "E0": E0CoulombCounting,
    "E1": E1ExtendedKalmanFilter,
    "E2": E2EKFHysteresis,
    "E3": _create_stub("E3"),
    "E4": _create_stub("E4"),
    "E5": _create_stub("E5"),
    "E6": _create_stub("E6"),
    "E7": _create_stub("E7"),
}


def get_estimator(name: str, params: ParamSet) -> Estimator:
    """Instantiate an estimator by identifier from the registry.

    Args:
        name: Estimator name ('E0', 'E1', ..., 'E7').
        params: Estimator parameter package.

    Returns:
        Estimator instance conforming to Estimator Protocol.

    Raises:
        KeyError: If estimator name is not recognized.
        NotImplementedError: For E3 through E7.
    """
    if name not in ESTIMATOR_REGISTRY:
        raise KeyError(
            f"Unknown estimator '{name}'. Available: {list(ESTIMATOR_REGISTRY.keys())}"
        )
    cls = ESTIMATOR_REGISTRY[name]
    return cls(params)


def list_registered_estimators() -> List[str]:
    """Return list of all registered estimator identifiers."""
    return list(ESTIMATOR_REGISTRY.keys())
