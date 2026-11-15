"""Reversible variations and normalization models.

Separates reversible operational influences (electrolyte conductivity Arrhenius
temperature dependency, polarization relaxation) from permanent degradation.
"""

import math
from dataclasses import dataclass

from soh.common.units import celsius_to_kelvin
from soh.degradation.mechanisms import R_GAS


@dataclass
class ReversibleCorrectionConfig:
    """Activation energy parameters for electrolyte & charge-transfer conduction."""

    ea_conduction_j: float = 22000.0  # ~0.23 eV for typical Li-ion electrolytes
    t_ref_c: float = 25.0


class TemperatureReversibleCorrection:
    """Normalizes measured DC internal resistance to standard reference temperature."""

    def __init__(self, config: ReversibleCorrectionConfig = ReversibleCorrectionConfig()):
        self.config = config

    def normalize_resistance_to_t_ref(
        self,
        measured_r_ohm: float,
        measured_temp_c: float,
    ) -> float:
        """Scale resistance measured at T to equivalent resistance at T_ref.
        
        Using Arrhenius conductivity scaling:
            R(T_ref) = R(T) * exp( (E_a / R_g) * (1/T_ref - 1/T) )
        """
        if measured_r_ohm <= 0.0:
            raise ValueError("Measured resistance must be positive.")

        t_meas_k = celsius_to_kelvin(measured_temp_c)
        t_ref_k = celsius_to_kelvin(self.config.t_ref_c)

        # Higher T leads to lower R; to get R at T_ref (e.g. 25°C) from a hot cell (e.g. 45°C),
        # R(T_ref) should be higher than R(T_hot).
        exponent = (self.config.ea_conduction_j / R_GAS) * (1.0 / t_ref_k - 1.0 / t_meas_k)
        scale_factor = math.exp(exponent)
        return measured_r_ohm * scale_factor

    def predict_resistance_at_temp(
        self,
        reference_r_ohm: float,
        target_temp_c: float,
    ) -> float:
        """Predict expected resistance at arbitrary operating temperature given reference R."""
        if reference_r_ohm <= 0.0:
            raise ValueError("Reference resistance must be positive.")

        t_target_k = celsius_to_kelvin(target_temp_c)
        t_ref_k = celsius_to_kelvin(self.config.t_ref_c)

        exponent = (self.config.ea_conduction_j / R_GAS) * (1.0 / t_target_k - 1.0 / t_ref_k)
        scale_factor = math.exp(exponent)
        return reference_r_ohm * scale_factor
