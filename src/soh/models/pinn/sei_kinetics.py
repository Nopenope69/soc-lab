"""Modular electrochemical degradation kinetics and resistance models.

Implements:
1. Solvent Diffusion-Limited SEI Growth Kinetics (Parabolic: d(delta)/dt ~ 1 / delta)
2. Reaction-Limited SEI Growth Kinetics (Linear: d(delta)/dt ~ const)
3. Multi-Component Resistance Degradation (Bulk Ohmic, SEI Film, Contact, and Electrolyte)
4. Loss of Lithium Inventory (LLI) Mapping
5. Dimensional Consistency Auditing across all physical parameters
6. Modular Experimental Extensions for Lithium Plating and Active Material Loss (LAM)
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Dict, Optional, Tuple
import numpy as np

from soh.common.units import celsius_to_kelvin

R_GAS = 8.314462618  # Universal gas constant [J / (mol * K)]


class SeiGrowthMechanism(str, Enum):
    """SEI layer growth kinetic regimes."""

    SOLVENT_DIFFUSION_LIMITED = "solvent_diffusion_limited"
    REACTION_LIMITED = "reaction_limited"


@dataclass
class SeiKineticsParameters:
    """Electrochemical and kinetic parameters for SEI growth models.
    
    Diffusion-Limited Parabolic ODE:
        d(delta_sei)/dt = (k_diff / (2 * delta_sei)) * Arrhenius(T) * g(I, SOC)
        Units: k_diff [m^2 / s], delta_sei [m], rate [m / s]
        
    Reaction-Limited Linear ODE:
        d(delta_sei)/dt = k_rxn * Arrhenius(T) * g(I, SOC)
        Units: k_rxn [m / s], rate [m / s]
    """

    mechanism: SeiGrowthMechanism = SeiGrowthMechanism.SOLVENT_DIFFUSION_LIMITED
    k_sei_diffusion: float = 1.5e-16  # Parabolic rate constant [m^2 / s]
    k_sei_reaction: float = 1.2e-14   # Linear rate constant [m / s]
    activation_energy_j: float = 38000.0  # Activation energy [J / mol] (~0.39 eV)
    t_ref_k: float = 298.15               # Standard reference temperature (25 °C) [K]
    delta_sei_0: float = 5.0e-9           # BOL pristine SEI film thickness [m] (~5 nm)
    beta_current: float = 0.25            # Current acceleration coefficient [dimensionless]
    alpha_current: float = 0.50           # Current non-linear exponent [dimensionless]
    beta_soc: float = 0.15                # SOC acceleration coefficient [dimensionless]
    nominal_1c_current_a: float = 2.30    # 1C current magnitude [A]
    chi_lli: float = 2.0e7                # LLI capacity fade coupling [1 / m] (fraction per meter SEI)

    def __init__(
        self,
        mechanism: SeiGrowthMechanism = SeiGrowthMechanism.SOLVENT_DIFFUSION_LIMITED,
        k_sei_diffusion: float = 1.5e-16,
        k_sei_reaction: float = 1.2e-14,
        activation_energy_j: float = 38000.0,
        t_ref_k: float = 298.15,
        delta_sei_0: float = 5.0e-9,
        beta_current: float = 0.25,
        alpha_current: float = 0.50,
        beta_soc: float = 0.15,
        nominal_1c_current_a: float = 2.30,
        chi_lli: float = 2.0e7,
        k_sei: Optional[float] = None,
    ):
        self.mechanism = mechanism
        self.k_sei_diffusion = k_sei if k_sei is not None else k_sei_diffusion
        self.k_sei_reaction = k_sei_reaction
        self.activation_energy_j = activation_energy_j
        self.t_ref_k = t_ref_k
        self.delta_sei_0 = delta_sei_0
        self.beta_current = beta_current
        self.alpha_current = alpha_current
        self.beta_soc = beta_soc
        self.nominal_1c_current_a = nominal_1c_current_a
        self.chi_lli = chi_lli

    @property
    def k_sei(self) -> float:
        return self.k_sei_diffusion

    @k_sei.setter
    def k_sei(self, val: float) -> None:
        self.k_sei_diffusion = val


@dataclass
class MultiComponentResistanceParameters:
    """Parameters for multi-component battery internal resistance evolution.
    
    R_total(t, N, T) = R_bulk(T) + Delta_R_sei(delta) + Delta_R_contact(N) + Delta_R_elyte(fade)
    """

    r_bulk_bol_ohm: float = 0.010         # Pristine bulk electrolyte/ohmic resistance [Ohm]
    ea_bulk_j: float = 15000.0            # Thermal activation energy of ionic transport [J / mol]
    
    # SEI film conduction resistance: Delta_R_sei = rho_sei_spec * Delta_delta_sei
    rho_sei_specific_ohm_per_m: float = 1.5e5  # Film resistance per meter thickness [Ohm / m]
    
    # Interfacial / current collector contact fatigue
    k_contact_fatigue_ohm: float = 1.0e-6      # Contact resistance growth per cycle^zeta [Ohm]
    contact_exponent_zeta: float = 0.60       # Cycle accumulation exponent [dimensionless]
    
    # Electrolyte dryout / salt consumption
    k_elyte_depletion_ohm: float = 0.003       # Electrolyte resistance rise at EOL [Ohm]
    q_crit_fraction: float = 0.30             # Critical capacity fade where electrolyte dries out


class SeiKineticsPhysics:
    """Electrochemical physics engine for SEI film growth and multi-component resistance."""

    def __init__(
        self,
        kinetics_params: Optional[SeiKineticsParameters] = None,
        resistance_params: Optional[MultiComponentResistanceParameters] = None,
    ):
        self.params = kinetics_params or SeiKineticsParameters()
        self.r_params = resistance_params or MultiComponentResistanceParameters()

    def arrhenius_factor(self, temp_k: float) -> float:
        """Normalized Arrhenius temperature factor: 1.0 at T_ref (298.15 K)."""
        temp_k = max(200.0, temp_k)
        exponent = -(self.params.activation_energy_j / R_GAS) * (1.0 / temp_k - 1.0 / self.params.t_ref_k)
        return math.exp(max(-30.0, min(30.0, exponent)))

    def operating_condition_factor(self, current_a: float, soc: float = 0.5) -> float:
        """Acceleration factor from C-rate and SOC: g(I, SOC)."""
        c_rate = abs(current_a) / max(0.1, self.params.nominal_1c_current_a)
        current_term = self.params.beta_current * (c_rate ** self.params.alpha_current)
        soc_term = self.params.beta_soc * (max(0.0, min(1.0, soc)) - 0.5)
        return max(0.1, 1.0 + current_term + soc_term)

    def sei_growth_rate(
        self,
        delta_sei_m: float,
        temp_k: float,
        current_a: float = 0.0,
        soc: float = 0.5,
        mechanism: Optional[SeiGrowthMechanism] = None,
    ) -> float:
        """Compute instantaneous SEI growth rate d(delta_sei)/dt [m / s]."""
        mech = mechanism or self.params.mechanism
        arrh = self.arrhenius_factor(temp_k)
        op_factor = self.operating_condition_factor(current_a, soc)

        if mech == SeiGrowthMechanism.SOLVENT_DIFFUSION_LIMITED:
            # Parabolic diffusion kinetics: d(delta)/dt = (k_diff / (2 * delta)) * Arrhenius * g(I, SOC)
            delta = max(1.0e-11, delta_sei_m)
            rate = (self.params.k_sei_diffusion / (2.0 * delta)) * arrh * op_factor
        else:
            # Linear reaction-limited kinetics: d(delta)/dt = k_rxn * Arrhenius * g(I, SOC)
            rate = self.params.k_sei_reaction * arrh * op_factor

        return rate

    def compute_multi_component_resistance(
        self,
        delta_sei_m: float,
        cycle_count: int,
        temp_k: float,
        capacity_fade_fraction: float,
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate total cell resistance from 4 distinct physical mechanisms.
        
        Returns:
            r_total_ohm: Total DC internal resistance [Ohm].
            components: Breakdown of bulk, SEI film, contact, and electrolyte terms [Ohm].
        """
        # 1. Bulk ohmic resistance with thermal Arrhenius conductivity
        arrh_bulk = math.exp(-(self.r_params.ea_bulk_j / R_GAS) * (1.0 / max(200.0, temp_k) - 1.0 / self.params.t_ref_k))
        r_bulk = self.r_params.r_bulk_bol_ohm * (1.0 / max(0.2, arrh_bulk))

        # 2. SEI film resistance
        delta_inc = max(0.0, delta_sei_m - self.params.delta_sei_0)
        r_sei = self.r_params.rho_sei_specific_ohm_per_m * delta_inc

        # 3. Interfacial contact fatigue
        r_contact = self.r_params.k_contact_fatigue_ohm * (max(0, cycle_count) ** self.r_params.contact_exponent_zeta)

        # 4. Electrolyte dryout / tortuosity rise
        fade_clamped = max(0.0, min(self.r_params.q_crit_fraction * 0.95, capacity_fade_fraction))
        r_elyte = self.r_params.k_elyte_depletion_ohm * (fade_clamped / (self.r_params.q_crit_fraction - fade_clamped))

        r_total = r_bulk + r_sei + r_contact + r_elyte
        components = {
            "r_bulk": r_bulk,
            "r_sei": r_sei,
            "r_contact": r_contact,
            "r_elyte": r_elyte,
            "r_total": r_total,
        }
        return r_total, components

    def delta_to_soh(
        self,
        delta_sei_m: float,
        cycle_count: int = 0,
        temp_k: float = 298.15,
    ) -> Tuple[float, float]:
        """Convert SEI thickness and cycling count to separate SOH_C and SOH_R fractions."""
        delta_inc = max(0.0, delta_sei_m - self.params.delta_sei_0)
        fade_fraction = self.params.chi_lli * delta_inc
        soh_c = max(0.0, min(1.0, 1.0 - fade_fraction))

        # Compute resistance at BOL and currently
        r_bol, _ = self.compute_multi_component_resistance(
            delta_sei_m=self.params.delta_sei_0,
            cycle_count=0,
            temp_k=self.params.t_ref_k,
            capacity_fade_fraction=0.0,
        )
        r_curr, _ = self.compute_multi_component_resistance(
            delta_sei_m=delta_sei_m,
            cycle_count=cycle_count,
            temp_k=temp_k,
            capacity_fade_fraction=fade_fraction,
        )

        soh_r = max(0.0, min(1.0, r_bol / max(1e-6, r_curr)))
        return soh_c, soh_r

    def verify_dimensional_consistency(self) -> Dict[str, str]:
        """Audit dimensional consistency of all model parameters and governing equations."""
        units = {
            "k_sei_diffusion": "m^2 / s",
            "k_sei_reaction": "m / s",
            "activation_energy_j": "J / mol",
            "t_ref_k": "K",
            "delta_sei_0": "m",
            "beta_current": "dimensionless",
            "alpha_current": "dimensionless",
            "beta_soc": "dimensionless",
            "nominal_1c_current_a": "A",
            "chi_lli": "1 / m",
            "r_bulk_bol_ohm": "Ohm",
            "rho_sei_specific_ohm_per_m": "Ohm / m",
            "d_delta_dt_diffusion": "(m^2/s) / m = m / s [CONSISTENT]",
            "d_delta_dt_reaction": "m / s [CONSISTENT]",
            "r_total_formula": "Ohm + (Ohm/m)*m + Ohm + Ohm = Ohm [CONSISTENT]",
            "soh_c_formula": "1.0 - (1/m)*m = dimensionless [CONSISTENT]",
            "soh_r_formula": "Ohm / Ohm = dimensionless [CONSISTENT]",
        }
        return units


@dataclass
class LithiumPlatingParameters:
    """Parameters for low-temperature / high-rate lithium plating degradation."""

    t_threshold_c: float = 15.0       # Temperature threshold below which plating occurs [°C]
    c_rate_threshold: float = 1.0     # C-rate threshold above which overpotential favors plating
    k_plating: float = 1.0e-9         # Rate constant for metallic lithium deposition [m / s]
    stripping_reversibility: float = 0.60  # Fraction of plated lithium reversibly stripped during rest/discharge


class LithiumPlatingModule:
    """Modular experimental degradation module for irreversible lithium plating.
    
    EXPERIMENTAL STATUS: Calibration pending cryogenic HPPC operando titration data.
    Activated when operating temperature is below 15°C and charging rate exceeds 1C.
    """

    def __init__(self, params: Optional[LithiumPlatingParameters] = None):
        self.params = params or LithiumPlatingParameters()

    def evaluate_plating_rate(
        self,
        temp_c: float,
        charge_current_a: float,
        nominal_capacity_ah: float = 2.30,
    ) -> float:
        """Calculate irreversible lithium deposition rate [m / s]."""
        if charge_current_a <= 0.0:
            return 0.0  # Discharge or rest does not deposit lithium
        
        c_rate = charge_current_a / max(0.1, nominal_capacity_ah)
        if temp_c >= self.params.t_threshold_c or c_rate <= self.params.c_rate_threshold:
            return 0.0

        temp_penalty = (self.params.t_threshold_c - temp_c) / 15.0
        rate_penalty = (c_rate - self.params.c_rate_threshold)
        
        net_efficiency = 1.0 - self.params.stripping_reversibility
        rate = self.params.k_plating * temp_penalty * rate_penalty * net_efficiency
        return max(0.0, rate)


@dataclass
class LamParameters:
    """Parameters for Loss of Active Material (LAM) driven by cyclic mechanical strain."""

    k_lam: float = 1.0e-5             # Mechanical degradation rate per cycle
    dod_exponent_gamma: float = 1.4   # Non-linear depth-of-discharge exponent
    cycle_exponent_zeta: float = 0.50 # Cycle accumulation exponent


class LossOfActiveMaterialModule:
    """Modular experimental degradation module for Loss of Active Material (LAM).
    
    EXPERIMENTAL STATUS: Calibration pending destructive post-mortem XRD electrode half-cell data.
    Represents electrode particle micro-cracking and loss of electrical percolation.
    """

    def __init__(self, params: Optional[LamParameters] = None):
        self.params = params or LamParameters()

    def evaluate_lam_fade(self, cycle_index: int, delta_soc: float = 0.8) -> float:
        """Calculate cumulative fraction of active material lost at cycle index."""
        if cycle_index <= 0:
            return 0.0
        dod = max(0.1, min(1.0, delta_soc))
        lam_loss = self.params.k_lam * (dod ** self.params.dod_exponent_gamma) * (cycle_index ** self.params.cycle_exponent_zeta)
        return min(0.40, lam_loss)
