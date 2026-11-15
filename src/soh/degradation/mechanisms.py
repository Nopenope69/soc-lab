"""Calibrated electrochemical and empirical degradation mechanisms.

Models irreversible degradation processes (SEI growth, LLI, active material loss,
and independent resistance growth) as calibrated domain models, cleanly separated
from feature extraction, estimators, and reversible variations.
"""

from dataclasses import dataclass
import math
import numpy as np

from soh.common.units import celsius_to_kelvin

# Gas constant in J / (mol * K)
R_GAS = 8.314462618


@dataclass
class SeiKineticsConfig:
    """Calibrated parameters for solvent-diffusion limited SEI layer growth."""

    k_sei: float = 1e-12          # SEI kinetic rate constant [m^2 / s]
    activation_energy_j: float = 38000.0  # Activation energy [J / mol] (~0.39 eV)
    delta_sei_0: float = 5e-9     # Initial SEI film thickness at BOL [m]
    c_sei_conversion: float = 2.0e7  # Conversion factor from delta_sei to capacity fade [Ah / m]
    current_acceleration_beta: float = 0.2
    current_exponent_alpha: float = 0.5


class SeiKineticsModel:
    """Solvent diffusion-limited SEI growth degradation model.
    
    Governing ODE (diffusion-limited parabolic kinetics):
        d(delta_sei) / dt = (k_sei / (2 * delta_sei)) * exp(-E_a / (R_g * T)) * (1 + beta * |I|^alpha)
    """

    def __init__(self, config: SeiKineticsConfig = SeiKineticsConfig()):
        self.config = config

    def step_sei_growth(
        self,
        current_delta_m: float,
        current_a: float,
        temp_c: float,
        dt_s: float,
    ) -> float:
        """Step SEI film thickness forward by dt_s seconds."""
        t_k = celsius_to_kelvin(temp_c)
        arrhenius = math.exp(-self.config.activation_energy_j / (R_GAS * t_k))
        current_factor = 1.0 + self.config.current_acceleration_beta * (abs(current_a) ** self.config.current_exponent_alpha)
        
        # d(delta)/dt = k_sei / (2 * delta) * arrhenius * current_factor
        rate = (self.config.k_sei / (2.0 * max(1e-11, current_delta_m))) * arrhenius * current_factor
        new_delta = current_delta_m + rate * dt_s
        return max(self.config.delta_sei_0, new_delta)

    def delta_to_capacity_fade_ah(self, delta_m: float) -> float:
        """Calculate cumulative capacity loss [Ah] from SEI thickness change."""
        delta_increase = max(0.0, delta_m - self.config.delta_sei_0)
        return self.config.c_sei_conversion * delta_increase


@dataclass
class EmpiricalAgingConfig:
    """Calibrated empirical power-law degradation parameters with reference temperature scaling."""

    capacity_coeff_a: float = 0.00075
    capacity_exponent_z: float = 0.65
    capacity_ea_j: float = 28000.0
    resistance_coeff_b: float = 0.0012
    resistance_exponent_w: float = 0.70
    resistance_ea_j: float = 32000.0
    t_ref_c: float = 25.0


class EmpiricalDegradationModel:
    """Models capacity fade and resistance growth independently via power laws.
    
    Arrhenius temperature scaling is normalized to t_ref_c (25°C):
        k(T) = k_ref * exp( (-E_a / R) * (1/T - 1/T_ref) )
    This ensures that at 25°C, Arrhenius = 1.0, and high temperatures
    accelerate permanent degradation without uncalibrated magnitude distortion.
    """

    def __init__(self, config: EmpiricalAgingConfig = EmpiricalAgingConfig()):
        self.config = config

    def predict_capacity_retention(
        self,
        ah_throughput: float,
        avg_temp_c: float = 25.0,
    ) -> float:
        """Predict capacity retention SOH_C_bol (1.0 at BOL)."""
        if ah_throughput <= 0.0:
            return 1.0
        t_k = celsius_to_kelvin(avg_temp_c)
        t_ref_k = celsius_to_kelvin(self.config.t_ref_c)
        arrhenius = math.exp(-(self.config.capacity_ea_j / R_GAS) * (1.0 / t_k - 1.0 / t_ref_k))
        fade = self.config.capacity_coeff_a * (ah_throughput ** self.config.capacity_exponent_z) * arrhenius
        return max(0.0, min(1.0, 1.0 - fade))

    def predict_resistance_growth(
        self,
        ah_throughput: float,
        avg_temp_c: float = 25.0,
    ) -> float:
        """Predict resistance multiplier R_actual / R_bol (1.0 at BOL).
        
        Resistance SOH is the inverse: SOH_R = 1.0 / multiplier.
        """
        if ah_throughput <= 0.0:
            return 1.0
        t_k = celsius_to_kelvin(avg_temp_c)
        t_ref_k = celsius_to_kelvin(self.config.t_ref_c)
        arrhenius = math.exp(-(self.config.resistance_ea_j / R_GAS) * (1.0 / t_k - 1.0 / t_ref_k))
        growth = 1.0 + self.config.resistance_coeff_b * (ah_throughput ** self.config.resistance_exponent_w) * arrhenius
        return max(1.0, growth)
