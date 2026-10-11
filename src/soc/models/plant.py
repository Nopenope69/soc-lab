"""Plant forward simulator generating truth cell states and degraded sensor measurements.

Estimator treatment of dropped samples:
When `Measurement.dropout` is True, measurement fields `v`, `i`, and `temp_c` are NaN.
Estimators MUST treat dropped samples by executing only the time-update (predict) step
with zero current or held last current, and skip the measurement correction (update) step.

Timing convention:
- At sample k the plant applies current i_k to state x_k. The measurement carries
  v_k = terminal voltage at x_k under i_k, and i_k.
- Truth recorded at sample k is the state after the step, x_(k+1).
- Estimator.step(v_k, i_k, T_k, dt) must return the estimate of x_(k+1), so it updates
  on v_k using its prior for x_k, then propagates with i_k.
- Metrics compare estimate k with truth k, which now refer to the same instant.
"""

import warnings
from dataclasses import dataclass
from typing import Optional, Tuple
import math
import numpy as np

from soc.assumptions.schema import Assumptions
from soc.models.tables import InterpolatedTable2D
from soc.models.cell_2rc import Cell2RCModel, CellState


@dataclass(frozen=True)
class Measurement:
    """Estimator-facing sensor output carrying only observable signals and dropout flag."""

    v: float
    i: float
    temp_c: float
    dt: float
    dropout: bool


@dataclass(frozen=True)
class PlantTruthState:
    """True electrochemistry states (isolated from estimators)."""

    soc: float
    v_terminal: float
    i_true: float
    temp_c: float
    i1: float
    i2: float
    h: float


class PlantSimulator:
    """Forward battery plant simulator with physical 2RC dynamics and sensor noise."""

    def __init__(
        self,
        assumptions: Assumptions,
        rng: Optional[np.random.Generator] = None,
    ):
        self.assumptions = assumptions
        self.plant_cfg = assumptions.plant
        self.sensors_cfg = assumptions.sensors

        if rng is None:
            seed_val = int(assumptions.run.random_seed.value)
            self.rng = np.random.default_rng(seed_val)
        else:
            self.rng = rng

        # Construct interpolated tables for plant parameters
        temps = self.plant_cfg.temperatures_c.value
        socs = self.plant_cfg.soc_grid.value

        self.ocv_table = InterpolatedTable2D(temps, socs, self.plant_cfg.ocv_table_v.value)
        self.r0_table = InterpolatedTable2D(temps, socs, self.plant_cfg.r0_table_ohm.value)
        self.r1_table = InterpolatedTable2D(temps, socs, self.plant_cfg.r1_table_ohm.value)
        self.tau1_table = InterpolatedTable2D(temps, socs, self.plant_cfg.tau1_table_s.value)
        self.r2_table = InterpolatedTable2D(temps, socs, self.plant_cfg.r2_table_ohm.value)
        self.tau2_table = InterpolatedTable2D(temps, socs, self.plant_cfg.tau2_table_s.value)

        # Initialize internal state
        init_soc = float(self.plant_cfg.initial_soc.value)
        self.state = CellState(soc=init_soc, i1=float(0), i2=float(0), h=float(0))

    def reset(self, soc0: Optional[float] = None) -> None:
        """Reset internal plant state to starting condition."""
        start_soc = soc0 if soc0 is not None else float(self.plant_cfg.initial_soc.value)
        self.state = CellState(soc=start_soc, i1=float(0), i2=float(0), h=float(0))

    def step(
        self, i_true_a: float, temp_c: float, dt_s: float
    ) -> Tuple[Measurement, PlantTruthState]:
        """Advance plant by dt seconds under applied true current, returning (meas, truth)."""
        t_min = float(self.plant_cfg.temperatures_c.value[0])
        t_max = float(self.plant_cfg.temperatures_c.value[-1])
        if temp_c < t_min or temp_c > t_max:
            warnings.warn(
                f"Temperature {temp_c} C is outside calibration range [{t_min}, {t_max}] C; values are clamped.",
                UserWarning,
                stacklevel=2,
            )

        cap_ah = float(self.plant_cfg.nominal_capacity_Ah.value)
        coulomb_eff = float(self.plant_cfg.coulombic_efficiency.value)
        gamma = float(self.plant_cfg.hysteresis_gamma.value)
        m_hyst = float(self.plant_cfg.hysteresis_amplitude_v.value)

        # Lookup temperature/SOC-dependent parameters at current state
        r0 = self.r0_table.lookup(self.state.soc, temp_c)
        r1 = self.r1_table.lookup(self.state.soc, temp_c)
        tau1 = self.tau1_table.lookup(self.state.soc, temp_c)
        r2 = self.r2_table.lookup(self.state.soc, temp_c)
        tau2 = self.tau2_table.lookup(self.state.soc, temp_c)
        ocv = self.ocv_table.lookup(self.state.soc, temp_c)

        # Compute true terminal voltage at start of step
        v_true = Cell2RCModel.compute_terminal_voltage(
            ocv=ocv,
            h=self.state.h,
            i_a=i_true_a,
            i1=self.state.i1,
            i2=self.state.i2,
            r0=r0,
            r1=r1,
            r2=r2,
            m_hysteresis=m_hyst,
        )

        # Update physical internal state
        next_soc = Cell2RCModel.step_soc(
            soc=self.state.soc,
            i_a=i_true_a,
            dt_s=dt_s,
            capacity_ah=cap_ah,
            coulombic_efficiency=coulomb_eff,
        )
        next_i1 = Cell2RCModel.step_rc_current(
            i_rc=self.state.i1,
            i_a=i_true_a,
            dt_s=dt_s,
            tau_s=tau1,
        )
        next_i2 = Cell2RCModel.step_rc_current(
            i_rc=self.state.i2,
            i_a=i_true_a,
            dt_s=dt_s,
            tau_s=tau2,
        )
        next_h = Cell2RCModel.step_hysteresis(
            h=self.state.h,
            i_a=i_true_a,
            dt_s=dt_s,
            capacity_ah=cap_ah,
            gamma=gamma,
            coulombic_efficiency=coulomb_eff,
        )
        self.state = CellState(soc=next_soc, i1=next_i1, i2=next_i2, h=next_h)

        truth_record = PlantTruthState(
            soc=next_soc,
            v_terminal=v_true,
            i_true=i_true_a,
            temp_c=temp_c,
            i1=next_i1,
            i2=next_i2,
            h=next_h,
        )

        # Generate degraded sensor measurements
        dropout_rate = float(self.sensors_cfg.dropout_rate.value)
        if dropout_rate > 0 and self.rng.random() < dropout_rate:
            meas = Measurement(
                v=float("nan"),
                i=float("nan"),
                temp_c=float("nan"),
                dt=dt_s,
                dropout=True,
            )
            return meas, truth_record

        # Current sensor degradation
        i_bias = float(self.sensors_cfg.current_offset_a.value)
        i_gain = float(self.sensors_cfg.current_gain_error.value)
        i_sigma = float(self.sensors_cfg.current_noise_sigma_a.value)
        i_noise = float(self.rng.normal(0, i_sigma)) if i_sigma > 0 else float(0)
        i_meas = (i_true_a + i_bias) * (1 + i_gain) + i_noise

        # Voltage sensor degradation
        v_sigma = float(self.sensors_cfg.voltage_noise_sigma_v.value)
        v_noise = float(self.rng.normal(0, v_sigma)) if v_sigma > 0 else float(0)
        v_noisy = v_true + v_noise

        v_quant = float(self.sensors_cfg.voltage_quantisation_v.value)
        if v_quant > 0:
            v_meas = round(v_noisy / v_quant) * v_quant
        else:
            v_meas = v_noisy

        # Temperature sensor degradation
        t_sigma = float(self.sensors_cfg.temperature_noise_sigma_c.value)
        t_noise = float(self.rng.normal(0, t_sigma)) if t_sigma > 0 else float(0)
        t_meas = temp_c + t_noise

        meas = Measurement(
            v=float(v_meas),
            i=float(i_meas),
            temp_c=float(t_meas),
            dt=dt_s,
            dropout=False,
        )
        return meas, truth_record
