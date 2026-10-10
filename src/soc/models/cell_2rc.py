"""2RC equivalent circuit battery cell model with one-state hysteresis.

Sign convention: Discharge current is positive (i > 0 discharges cell).
Hysteresis properties:
  - h is strictly bounded in [-1, 1].
  - Initial value is 0.
  - At zero current (i == 0), delta_h is 0, so h is unchanged at rest.
  - T9 tests RC relaxation only (i1 and i2 decay to 0 while h remains static).
"""

from dataclasses import dataclass
import math
from typing import Tuple


@dataclass
class CellState:
    """Internal state vector of the 2RC cell model."""

    soc: float
    i1: float
    i2: float
    h: float


class Cell2RCModel:
    """2RC equivalent circuit model with 1-state hysteresis."""

    @staticmethod
    def step_soc(
        soc: float,
        i_a: float,
        dt_s: float,
        capacity_ah: float,
        coulombic_efficiency: float,
    ) -> float:
        """Step SOC forward: z_{k+1} = z_k - (eta * dt / (3600 * Q)) * i_k."""
        # Discharge is positive: i_a > 0 -> eta = 1.0; Charge: i_a < 0 -> eta = coulombic_efficiency
        eta = coulombic_efficiency if i_a < 0 else float(1)
        # Coulomb capacity in As
        cap_as = capacity_ah * 3600
        delta_soc = (eta * i_a * dt_s) / cap_as
        return soc - delta_soc

    @staticmethod
    def step_rc_current(i_rc: float, i_a: float, dt_s: float, tau_s: float) -> float:
        """Step RC branch current: i_{j,k+1} = exp(-dt/tau)*i_j + (1 - exp(-dt/tau))*i."""
        decay = math.exp(-dt_s / tau_s)
        return decay * i_rc + (1 - decay) * i_a

    @staticmethod
    def step_hysteresis(
        h: float,
        i_a: float,
        dt_s: float,
        capacity_ah: float,
        gamma: float,
        coulombic_efficiency: float,
    ) -> float:
        """Step 1-state hysteresis: h_{k+1} = exp(-|...|)*h_k - (1 - exp(-|...|))*sgn(i_k)."""
        if i_a == 0:
            return h

        eta = coulombic_efficiency if i_a < 0 else float(1)
        cap_as = capacity_ah * 3600

        # Argument to exponential: |eta * i * gamma * dt / (3600 * Q)|
        arg = abs(eta * i_a * gamma * dt_s / cap_as)
        factor = math.exp(-arg)

        sgn_i = float(1) if i_a > 0 else float(-1)
        h_next = factor * h - (1 - factor) * sgn_i

        # Clamp strictly within [-1, 1]
        return min(max(h_next, float(-1)), float(1))

    @staticmethod
    def compute_terminal_voltage(
        ocv: float,
        h: float,
        i_a: float,
        i1: float,
        i2: float,
        r0: float,
        r1: float,
        r2: float,
        m_hysteresis: float,
    ) -> float:
        """Compute terminal voltage: v = OCV + M*h - R1*i1 - R2*i2 - R0*i."""
        return ocv + m_hysteresis * h - r1 * i1 - r2 * i2 - r0 * i_a
