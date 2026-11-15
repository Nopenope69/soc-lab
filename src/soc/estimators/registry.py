"""Estimator registry for E0 through E10.

Identifier classifications:
- Research Candidate:
  * E7v3 ('e7v3'): Primary research candidate. Confidence-aware composite EKF
    with observability-gated voltage feedback, RLS-driven R0 tracking, and Joseph-form covariance.
- Classical Baselines & Predecessors:
  * E0 ('E0'): Coulomb counting with capacity scaling and resting OCV recalibration anchors.
  * E1 ('E1'): Standard Extended Kalman Filter (Thevenin 2RC).
  * E2 ('E2'): Anchored EKF with hysteresis state.
  * E3 ('E3'): Unscented Kalman Filter.
  * E4 ('E4', 'e4v2'): EKF with Recursive Least Squares (RLS) parameter tracking.
  * E5 ('E5', 'e5v4'): Observability-gated EKF.
  * E6 ('E6'): RBC dual EKF.
  * e7v2: Intermediate composite filter.
  * d3: Innovation-gated EKF.
- Deprecated Aliases:
  * E7: Deprecated unversioned alias; raises NotImplementedError directing to 'e7v3'.
- Experimental Neural Hybrid Estimators (requires 'neural' extra):
  * E8 ('E8', 'e8'): Hybrid GRU residual estimator.
  * E8-LGBM ('E8-LGBM', 'e8-lgbm', 'e8_lgbm'): LightGBM residual estimator.
  * E9 ('E9', 'e9', 'e9_tcn_ukf'): Temporal Convolutional Network + UKF.
  * E10 ('E10', 'e10', 'e10_pinn_aekf'): Physics-Informed Neural Network + Adaptive EKF.
"""

from typing import Any, Callable, Dict, List, Type

from soc.estimators.base import Estimator, ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.e3_ukf import E3UnscentedKalmanFilter
from soc.estimators.e4_rls_r0 import E4RLSR0EKF
from soc.estimators.e5_observability_ekf import E5ObservabilityEKF
from soc.estimators.e6_rbc_dekf import E6RBCDEKF
from soc.estimators.e5v4 import E5V4ObservabilityEKF
from soc.estimators.e4v2_rls import E4V2RLSEKF
from soc.estimators.innovation_gating import D3InnovationGatedEKF
from soc.estimators.e7v2 import E7V2CompositeFilter
from soc.estimators.e7v3 import E7V3CompositeFilter


class _StubEstimator(Estimator):
    """Stub estimator raising NotImplementedError for deprecated or stubbed names."""

    def __init__(self, name: str, params: ParamSet):
        raise NotImplementedError(
            f"Estimator '{name}' is deprecated; use 'e7v3' (the research candidate) instead."
        )

    def reset(self, soc0: float) -> None:
        pass

    def step(self, measurement: Any) -> Any:
        pass


def _create_stub(name: str) -> Type[Estimator]:
    """Create a stub estimator class that raises NotImplementedError upon instantiation."""
    class Stub(Estimator):
        def __init__(self, params: ParamSet):
            raise NotImplementedError(
                f"Estimator '{name}' is deprecated; use 'e7v3' (the research candidate) instead."
            )

        def reset(self, soc0: float) -> None:
            pass

        def step(self, measurement: Any) -> Any:
            pass

    Stub.__name__ = f"{name}Stub"
    return Stub


def _load_e8_gru() -> Type[Estimator]:
    try:
        from soc.estimators.e8_residual_gru import E8ResidualGRUEstimator
        return E8ResidualGRUEstimator
    except ImportError as e:
        raise ImportError(
            "Estimator E8 (GRU) requires the 'neural' extra (torch). Install with: pip install 'soc-lab[neural]'"
        ) from e


def _load_e8_lgbm() -> Type[Estimator]:
    try:
        from soc.estimators.e8_residual_lgbm import E8ResidualLGBMEstimator, lgb
        if lgb is None:
            raise ImportError("lightgbm is not available")
        return E8ResidualLGBMEstimator
    except ImportError as e:
        raise ImportError(
            "Estimator E8-LGBM requires the 'neural' extra (lightgbm). Install with: pip install 'soc-lab[neural]'"
        ) from e


def _load_e9() -> Type[Estimator]:
    try:
        from soc.estimators.e9_tcn_ukf import E9TCNUKFEstimator
        return E9TCNUKFEstimator
    except ImportError as e:
        raise ImportError(
            "Estimator E9 (TCN-UKF) requires the 'neural' extra (torch). Install with: pip install 'soc-lab[neural]'"
        ) from e


def _load_e10() -> Type[Estimator]:
    try:
        from soc.estimators.e10_pinn_aekf import E10PINNAEKFEstimator
        return E10PINNAEKFEstimator
    except ImportError as e:
        raise ImportError(
            "Estimator E10 (PINN-AEKF) requires the 'neural' extra (torch). Install with: pip install 'soc-lab[neural]'"
        ) from e


_LAZY_LOADERS: Dict[str, Callable[[], Type[Estimator]]] = {
    "E8": _load_e8_gru,
    "e8": _load_e8_gru,
    "E8-LGBM": _load_e8_lgbm,
    "e8-lgbm": _load_e8_lgbm,
    "e8_lgbm": _load_e8_lgbm,
    "E9": _load_e9,
    "e9": _load_e9,
    "e9_tcn_ukf": _load_e9,
    "E10": _load_e10,
    "e10": _load_e10,
    "e10_pinn_aekf": _load_e10,
}


class _EstimatorRegistryDict(dict):
    """Registry dict supporting on-demand lazy loading of neural estimators."""

    def __getitem__(self, key: str) -> Type[Estimator]:
        if key in _LAZY_LOADERS:
            return _LAZY_LOADERS[key]()
        return super().__getitem__(key)

    def get(self, key: str, default=None) -> Any:
        if key in _LAZY_LOADERS:
            return _LAZY_LOADERS[key]()
        return super().get(key, default)


ESTIMATOR_REGISTRY: Dict[str, Type[Estimator]] = _EstimatorRegistryDict({
    "E0": E0CoulombCounting,
    "E1": E1ExtendedKalmanFilter,
    "E2": E2EKFHysteresis,
    "E3": E3UnscentedKalmanFilter,
    "E4": E4RLSR0EKF,
    "E5": E5ObservabilityEKF,
    "E6": E6RBCDEKF,
    "E7": _create_stub("E7"),
    "e5v4": E5V4ObservabilityEKF,
    "e4v2": E4V2RLSEKF,
    "d3": D3InnovationGatedEKF,
    "e7v2": E7V2CompositeFilter,
    "e7v3": E7V3CompositeFilter,
    # Keys for lazy neural estimators registered to enable key inspection
    "E8": None,  # type: ignore
    "e8": None,  # type: ignore
    "E8-LGBM": None,  # type: ignore
    "e8-lgbm": None,  # type: ignore
    "e8_lgbm": None,  # type: ignore
    "E9": None,  # type: ignore
    "e9": None,  # type: ignore
    "e9_tcn_ukf": None,  # type: ignore
    "E10": None,  # type: ignore
    "e10": None,  # type: ignore
    "e10_pinn_aekf": None,  # type: ignore
})


def get_estimator(name: str, params: ParamSet) -> Estimator:
    """Instantiate an estimator by identifier from the registry.

    Args:
        name: Estimator name (e.g. 'E0', 'E1', 'E2', 'e7v3', 'E8').
        params: Estimator parameter package.

    Returns:
        Estimator instance conforming to Estimator Protocol.

    Raises:
        KeyError: If estimator name is not recognized.
        NotImplementedError: For E7 stub.
        ImportError: If neural estimator requested without 'neural' extra.
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
