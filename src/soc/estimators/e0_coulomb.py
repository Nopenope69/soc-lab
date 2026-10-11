"""E0: Coulomb counting estimator with full-charge and rest OCV anchoring.

Algorithm:
- Integrates current forward: z_{k+1} = z_k - (eta(i_k) * dt / (3600 * Q)) * i_k
- Full-charge anchor: triggers when v >= full_charge_voltage_threshold_v and
  |i| <= full_charge_current_threshold_a, setting SOC to full_charge_anchor_soc.
- Rest anchor: triggers when |i| <= rest_current_threshold_a for duration >=
  rest_duration_threshold_s and rest_anchor_enabled is True, setting SOC via
  OCV table inversion at the measured temperature.
- Dropouts: skips anchoring, propagates with last valid current, holds state.
"""

import math
from typing import Optional

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.models.cell_2rc import Cell2RCModel
from soc.models.plant import Measurement
from soc.models.tables import InterpolatedTable2D


class E0CoulombCounting(Estimator):
    """E0: Pure Coulomb integration with optional recalibration anchors."""

    def __init__(self, params: ParamSet):
        self.params = params
        self.soc = float(0)
        self.rest_timer_s = float(0)
        self.last_valid_i = float(0)
        self.last_valid_temp = float(self.params.temperatures_c[1])

        # Construct 2D table for OCV lookups and inversions
        self.ocv_table = InterpolatedTable2D(
            list(self.params.temperatures_c),
            list(self.params.soc_grid),
            self.params.ocv_table,
        )

    def reset(self, soc0: float) -> None:
        """Reset estimator internal state to initial SOC."""
        self.soc = min(max(float(soc0), float(0)), float(1))
        self.rest_timer_s = float(0)
        self.last_valid_i = float(0)

    def step(self, measurement: Measurement) -> SocEstimate:
        """Process measurement and return estimated SOC for post-step state x_(k+1)."""
        dt = measurement.dt

        # Handle dropouts
        if measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i):
            i_prop = self.last_valid_i
            self.soc = Cell2RCModel.step_soc(
                soc=self.soc,
                i_a=i_prop,
                dt_s=dt,
                capacity_ah=self.params.nominal_capacity_ah,
                coulombic_efficiency=self.params.coulombic_efficiency,
            )
            self.soc = min(max(self.soc, float(0)), float(1))
            return SocEstimate(
                soc=self.soc,
                soc_std=self.params.initial_soc_std,
                anchor_used=False,
            )

        # Valid measurement: update last valid inputs
        self.last_valid_i = measurement.i
        self.last_valid_temp = measurement.temp_c

        anchor_applied = False

        # 1. Full-charge anchor
        if self.params.anchor_enabled:
            v_thresh = self.params.full_charge_voltage_threshold_v
            i_thresh = self.params.full_charge_current_threshold_a
            if measurement.v >= v_thresh and abs(measurement.i) <= i_thresh:
                self.soc = float(self.params.full_charge_anchor_soc)
                anchor_applied = True
                self.rest_timer_s = float(0)

        # 2. Rest anchor
        if not anchor_applied and self.params.anchor_enabled and self.params.rest_anchor_enabled:
            if abs(measurement.i) <= self.params.rest_current_threshold_a:
                self.rest_timer_s += dt
                if self.rest_timer_s >= self.params.rest_duration_threshold_s:
                    inv_soc = self.ocv_table.invert_soc(measurement.v, measurement.temp_c)
                    self.soc = float(inv_soc)
                    anchor_applied = True
            else:
                self.rest_timer_s = float(0)

        # Step forward over dt with measurement.i
        self.soc = Cell2RCModel.step_soc(
            soc=self.soc,
            i_a=measurement.i,
            dt_s=dt,
            capacity_ah=self.params.nominal_capacity_ah,
            coulombic_efficiency=self.params.coulombic_efficiency,
        )
        self.soc = min(max(self.soc, float(0)), float(1))

        return SocEstimate(
            soc=self.soc,
            soc_std=self.params.initial_soc_std,
            anchor_used=anchor_applied,
        )
