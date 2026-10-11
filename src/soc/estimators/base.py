"""Base types and Protocol for SOC estimators.

Timing convention:
- At sample k the plant applies current i_k to state x_k. The measurement carries
  v_k = terminal voltage at x_k under i_k, and i_k.
- Truth recorded at sample k is the state after the step, x_(k+1).
- Estimator.step(measurement) must return the estimate of x_(k+1), so it updates
  on v_k using its prior for x_k, then propagates with i_k over measurement.dt.
- Metrics compare estimate k with truth k, which now refer to the same instant.

Dropped sample handling:
When a sample is dropped (`dropout=True`), measurement fields `v`, `i`, and `temp_c`
are NaN. Estimators must skip the measurement correction (update) step, propagate
with the last valid current and temperature, and hold.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Tuple, runtime_checkable

from soc.assumptions.schema import Assumptions
from soc.assumptions.derived import get_effective_estimator_parameters
from soc.models.plant import Measurement


@dataclass(frozen=True)
class ParamSet:
    """Estimator-facing parameter package derived solely from estimator-side configuration.

    Estimators receive this and have no access to the plant object, truth state,
    hidden electrochemical states, or injected sensor noise parameters.
    """

    nominal_capacity_ah: float
    coulombic_efficiency: float
    soc_grid: Tuple[float, ...]
    temperatures_c: Tuple[float, ...]
    ocv_table: Dict[str, Any]
    r0_table: Dict[str, Any]
    r1_table: Dict[str, Any]
    tau1_table: Dict[str, Any]
    r2_table: Dict[str, Any]
    tau2_table: Dict[str, Any]
    hysteresis_amplitude_v: float
    hysteresis_gamma: float

    # Filter tunings
    initial_soc_std: float
    initial_rc_current_std_a: float
    initial_hysteresis_std: float
    process_noise_q_soc: float
    process_noise_q_rc: float
    process_noise_q_hysteresis: float
    measurement_noise_r_v: float

    # Anchoring policies
    anchor_enabled: bool
    rest_anchor_enabled: bool
    rest_current_threshold_a: float
    rest_duration_threshold_s: float
    full_charge_voltage_threshold_v: float
    full_charge_current_threshold_a: float
    full_charge_anchor_soc: float

    @classmethod
    def from_assumptions(cls, assumptions: Assumptions, matched: bool = True) -> "ParamSet":
        """Construct estimator parameter set from resolved assumptions."""
        eff = get_effective_estimator_parameters(assumptions, matched=matched)
        f_cfg = assumptions.filter
        s_cfg = assumptions.soc_definition

        return cls(
            nominal_capacity_ah=float(eff["nominal_capacity_Ah"]),
            coulombic_efficiency=float(eff["coulombic_efficiency"]),
            soc_grid=tuple(float(x) for x in eff["soc_grid"]),
            temperatures_c=tuple(float(t) for t in eff["temperatures_c"]),
            ocv_table=eff["ocv_table_v"],
            r0_table=eff["r0_table_ohm"],
            r1_table=eff["r1_table_ohm"],
            tau1_table=eff["tau1_table_s"],
            r2_table=eff["r2_table_ohm"],
            tau2_table=eff["tau2_table_s"],
            hysteresis_amplitude_v=float(eff["hysteresis_amplitude_v"]),
            hysteresis_gamma=float(eff["hysteresis_gamma"]),
            initial_soc_std=float(f_cfg.initial_soc_std.value),
            initial_rc_current_std_a=float(f_cfg.initial_rc_current_std_a.value),
            initial_hysteresis_std=float(f_cfg.initial_hysteresis_std.value),
            process_noise_q_soc=float(f_cfg.process_noise_q_soc.value),
            process_noise_q_rc=float(f_cfg.process_noise_q_rc.value),
            process_noise_q_hysteresis=float(f_cfg.process_noise_q_hysteresis.value),
            measurement_noise_r_v=float(f_cfg.measurement_noise_r_v.value),
            anchor_enabled=bool(s_cfg.anchor_enabled.value),
            rest_anchor_enabled=bool(s_cfg.rest_anchor_enabled.value),
            rest_current_threshold_a=float(s_cfg.rest_current_threshold_a.value),
            rest_duration_threshold_s=float(s_cfg.rest_duration_threshold_s.value),
            full_charge_voltage_threshold_v=float(s_cfg.full_charge_voltage_threshold_v.value),
            full_charge_current_threshold_a=float(s_cfg.full_charge_current_threshold_a.value),
            full_charge_anchor_soc=float(s_cfg.full_charge_anchor_soc.value),
        )


@dataclass(frozen=True)
class SocEstimate:
    """Estimated SOC output from a single step."""

    soc: float
    soc_std: float
    anchor_used: bool
    voltage_residual: Optional[float] = None
    innovation_variance: Optional[float] = None


@runtime_checkable
class Estimator(Protocol):
    """Protocol that all SOC estimators (E0 through E7) must satisfy."""

    def reset(self, soc0: float) -> None:
        """Reset estimator state to initial SOC."""
        ...

    def step(
        self,
        measurement: Measurement,
    ) -> SocEstimate:
        """Process incoming measurement and return estimate of post-step state x_(k+1)."""
        ...
