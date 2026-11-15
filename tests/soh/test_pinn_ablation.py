"""Unit tests for Phase 5.1 Physics Validation, Dimensional Consistency, and Model Ablation."""

import math
import numpy as np
import pytest
import torch

from soh.data.base_loader import SohDataset
from soh.data.synthetic_aging import NonlinearAgingGenerator
from soh.models.pinn.estimator import PinnSohEstimator, PinnTrainingConfig
from soh.models.pinn.losses import LossWeights, PinnLossFunction
from soh.models.pinn.network import BatteryDegradationPINN
from soh.models.pinn.sei_kinetics import (
    MultiComponentResistanceParameters,
    SeiGrowthMechanism,
    SeiKineticsParameters,
    SeiKineticsPhysics,
)


def test_dimensional_consistency_audit():
    """Verify dimensional consistency across all degradation and resistance equations."""
    physics = SeiKineticsPhysics()
    units = physics.verify_dimensional_consistency()

    assert "[CONSISTENT]" in units["d_delta_dt_diffusion"]
    assert "[CONSISTENT]" in units["d_delta_dt_reaction"]
    assert "[CONSISTENT]" in units["r_total_formula"]
    assert "[CONSISTENT]" in units["soh_c_formula"]
    assert "[CONSISTENT]" in units["soh_r_formula"]


def test_multi_component_resistance_breakdown():
    """Verify resistance is decomposed into bulk, SEI, contact, and electrolyte components."""
    physics = SeiKineticsPhysics()

    # BOL state: pristine resistance
    r_bol, comp_bol = physics.compute_multi_component_resistance(
        delta_sei_m=5e-9, cycle_count=0, temp_k=298.15, capacity_fade_fraction=0.0
    )
    assert abs(comp_bol["r_bulk"] - 0.010) < 1e-5
    assert comp_bol["r_sei"] == 0.0
    assert comp_bol["r_contact"] == 0.0
    assert comp_bol["r_elyte"] == 0.0
    assert abs(r_bol - 0.010) < 1e-5

    # Aged state: 50 nm SEI (+45 nm), 500 cycles, 20% capacity fade
    r_aged, comp_aged = physics.compute_multi_component_resistance(
        delta_sei_m=50e-9, cycle_count=500, temp_k=298.15, capacity_fade_fraction=0.20
    )
    assert comp_aged["r_sei"] > 0.0  # 1.5e5 * 45e-9 = 0.00675 Ohm
    assert comp_aged["r_contact"] > 0.0  # Contact wear
    assert comp_aged["r_elyte"] > 0.0  # Electrolyte dryout
    assert r_aged > r_bol

    # SOH_R correctly decreases with degradation
    soh_c, soh_r = physics.delta_to_soh(delta_sei_m=50e-9, cycle_count=500, temp_k=298.15)
    assert 0.0 < soh_r < 1.0
    assert 0.0 < soh_c < 1.0


def test_matched_vs_mismatched_sei_physics():
    """Verify diffusion-limited (parabolic) vs reaction-limited (linear) ODE behaviors."""
    p_diff = SeiKineticsParameters(mechanism=SeiGrowthMechanism.SOLVENT_DIFFUSION_LIMITED)
    p_rxn = SeiKineticsParameters(mechanism=SeiGrowthMechanism.REACTION_LIMITED)

    phys_diff = SeiKineticsPhysics(p_diff)
    phys_rxn = SeiKineticsPhysics(p_rxn)

    # Diffusion rate scales inversely with thickness (parabolic slowing)
    rate_diff_thin = phys_diff.sei_growth_rate(delta_sei_m=10e-9, temp_k=298.15)
    rate_diff_thick = phys_diff.sei_growth_rate(delta_sei_m=40e-9, temp_k=298.15)
    assert rate_diff_thin > rate_diff_thick
    assert abs((rate_diff_thin / rate_diff_thick) - 4.0) < 1e-3

    # Reaction rate is independent of thickness (linear constant rate)
    rate_rxn_thin = phys_rxn.sei_growth_rate(delta_sei_m=10e-9, temp_k=298.15)
    rate_rxn_thick = phys_rxn.sei_growth_rate(delta_sei_m=40e-9, temp_k=298.15)
    assert abs(rate_rxn_thin - rate_rxn_thick) < 1e-18


def test_independent_nonlinear_aging_generator():
    """Verify NonlinearAgingGenerator produces non-power-law multi-stage trajectory."""
    gen = NonlinearAgingGenerator(seed=123)
    b = gen.generate_battery("NONLINEAR_TEST", num_cycles=50, temp_c=25.0)

    assert len(b.cycles) == 50
    caps = [c.soh_c_bol_true for c in b.cycles]

    # Degradation must be monotonic
    for i in range(1, len(caps)):
        assert caps[i] <= caps[i - 1]

    # Verify presence of knee-point acceleration (slope steepens near cycle 35-45)
    early_slope = caps[5] - caps[20]  # Fade over 15 mid-life cycles
    knee_slope = caps[35] - caps[50] if len(caps) > 50 else caps[30] - caps[45]  # Fade over 15 late cycles
    assert knee_slope > early_slope  # Acceleration after knee-point!


def test_stratified_uncertainty_metrics():
    """Verify SOH-stratified uncertainty evaluation across BOL, Mid-life, and Degraded."""
    yt = [0.98, 0.96, 0.90, 0.88, 0.82, 0.79]
    yp = [0.97, 0.95, 0.89, 0.87, 0.81, 0.78]
    ci = [(0.95, 0.99), (0.93, 0.97), (0.87, 0.91), (0.85, 0.89), (0.79, 0.83), (0.76, 0.80)]

    strat = PinnSohEstimator.evaluate_stratified_uncertainty(yt, yp, ci)

    assert "bol_above_95" in strat
    assert "mid_life_85_to_95" in strat
    assert "degraded_below_85" in strat

    assert strat["bol_above_95"]["count"] == 2
    assert strat["mid_life_85_to_95"]["count"] == 2
    assert strat["degraded_below_85"]["count"] == 2

    # All targets are within bounds -> 100% PICP
    assert strat["bol_above_95"]["picp"] == 1.0
    assert strat["mid_life_85_to_95"]["picp"] == 1.0
    assert strat["degraded_below_85"]["picp"] == 1.0


def test_controlled_pinn_ablation_modes_initialization():
    """Verify all 5 ablation modes configure active loss components correctly."""
    gen = NonlinearAgingGenerator(seed=42)
    b = gen.generate_battery("ABL_CELL", num_cycles=10)
    ds = SohDataset()
    ds.add_battery(b)

    modes = ["pure_mlp", "pinn", "no_operating_conditions", "no_monotonicity", "pinn_reaction"]
    for m in modes:
        est = PinnSohEstimator(config=PinnTrainingConfig(epochs=5, mode=m, seed=42))
        est.fit(ds)
        assert est.is_fitted
        res = est.predict_cycle(b.cycles[2])
        assert res.soh_c is not None and 0.5 < res.soh_c < 1.05
