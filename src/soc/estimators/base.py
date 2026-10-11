"""Base types and Protocol for SOC estimators.

Timing convention:
- At sample k the plant applies current i_k to state x_k. The measurement carries
  v_k = terminal voltage at x_k under i_k, and i_k.
- Truth recorded at sample k is the state after the step, x_(k+1).
- Estimator.step(v_k, i_k, T_k, dt) must return the estimate of x_(k+1), so it updates
  on v_k using its prior for x_k, then propagates with i_k.
- Metrics compare estimate k with truth k, which now refer to the same instant.

Dropped sample handling:
When a sample is dropped (`dropout=True`), measurement fields `v`, `i`, and `temp_c`
are NaN. Estimators must perform only the time-update (predict) step with zero current
or held last current, and skip the measurement correction (update) step.
"""

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from soc.assumptions.schema import Assumptions
from soc.models.plant import Measurement


@dataclass(frozen=True)
class ParamSet:
    """Estimator-facing parameter package derived solely from estimator_model assumptions.

    Estimators receive this and have no access to the plant object, truth state,
    or noise parameters.
    """

    nominal_capacity_ah: float
    coulombic_efficiency: float
    soc_grid: tuple
    temperatures_c: tuple
    ocv_table: dict
    r0_table: dict
    r1_table: dict
    tau1_table: dict
    r2_table: dict
    tau2_table: dict
    hysteresis_amplitude_v: float
    hysteresis_gamma: float


@dataclass(frozen=True)
class SocEstimate:
    """Estimated SOC output from a single step."""

    soc: float
    voltage_residual: Optional[float] = None
    nis: Optional[float] = None


@runtime_checkable
class Estimator(Protocol):
    """Protocol that all SOC estimators (E0 through E7) must satisfy.

    Timing convention:
    - At sample k the plant applies current i_k to state x_k. The measurement
      carries v_k = terminal voltage at x_k under i_k, and i_k.
    - Truth recorded at sample k is the state after the step, x_(k+1).
    - Estimator.step(v_k, i_k, T_k, dt) must return the estimate of x_(k+1),
      so it updates on v_k using its prior for x_k, then propagates with i_k.
    - Metrics compare estimate k with truth k, which now refer to the same instant.
    """

    def reset(self, soc0: float) -> None:
        """Reset estimator state to initial SOC."""
        ...

    def step(
        self,
        measurement: Measurement,
    ) -> SocEstimate:
        """Process incoming measurement and return estimate of x_(k+1).

        Args:
            measurement: Measurement carrying (v_k, i_k, temp_c_k, dt_k, dropout).

        Returns:
            SocEstimate for post-step state x_(k+1).
        """
        ...
