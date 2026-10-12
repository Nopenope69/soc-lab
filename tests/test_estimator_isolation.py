"""Isolation tests enforcing strict architectural boundary for estimators.

Estimators must accept only Measurement and estimator-side configuration (ParamSet).
They cannot access the plant object, truth state, hidden electrochemical states,
or injected sensor noise parameters.
dt is sourced strictly from measurement.dt and never assumed.
"""

import inspect
from typing import get_type_hints
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.e5_observability_ekf import E5ObservabilityEKF
from soc.estimators.e6_rbc_dekf import E6RBCDEKF
from soc.models.plant import Measurement


@pytest.fixture
def estimator_params() -> ParamSet:
    assumptions, _, _ = load_assumptions()
    return ParamSet.from_assumptions(assumptions)


def test_estimator_step_signature_accepts_only_measurement():
    """Verify that Estimator.step takes strictly (self, measurement: Measurement)."""
    for cls in [E0CoulombCounting, E1ExtendedKalmanFilter, E2EKFHysteresis, E5ObservabilityEKF, E6RBCDEKF]:
        hints = get_type_hints(cls.step)
        params = list(inspect.signature(cls.step).parameters.keys())

        # Parameters must be strictly ['self', 'measurement']
        assert params == ["self", "measurement"], (
            f"{cls.__name__}.step has non-isolated parameter list: {params}"
        )
        assert hints.get("measurement") is Measurement, (
            f"{cls.__name__}.step argument 'measurement' is not typed as Measurement"
        )
        assert hints.get("return") is SocEstimate, (
            f"{cls.__name__}.step does not return SocEstimate"
        )


def test_estimator_constructor_signature_accepts_only_paramset():
    """Verify that estimator constructor takes strictly (self, params: ParamSet)."""
    for cls in [E0CoulombCounting, E1ExtendedKalmanFilter, E2EKFHysteresis, E5ObservabilityEKF, E6RBCDEKF]:
        params = list(inspect.signature(cls.__init__).parameters.keys())
        assert params == ["self", "params"], (
            f"{cls.__name__}.__init__ has non-isolated parameter list: {params}"
        )


def test_estimators_step_with_stripped_measurement(estimator_params):
    """Verify that estimators execute successfully with a bare Measurement object.

    No plant object, truth, or noise realization parameters can be required.
    """
    stripped_meas = Measurement(
        v=3.28,
        i=25.0,
        temp_c=25.0,
        dt=0.5,  # Non-standard dt to ensure dt is read from meas.dt
        dropout=False,
    )

    for cls in [E0CoulombCounting, E1ExtendedKalmanFilter, E2EKFHysteresis, E5ObservabilityEKF, E6RBCDEKF]:
        est = cls(estimator_params)
        est.reset(0.80)
        out = est.step(stripped_meas)

        assert isinstance(out, SocEstimate)
        assert 0.0 <= out.soc <= 1.0
        assert out.soc_std >= 0.0
