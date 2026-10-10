"""Tests for the assumptions loader hierarchy, overrides, status auditing, and derived quantities."""

import pytest
from pathlib import Path

from soc.assumptions.loader import (
    load_assumptions,
    resolve_assumptions,
    count_assumption_statuses,
    compute_config_hash,
)
from soc.assumptions.derived import (
    compute_derived_quantities,
    get_coulomb_capacity_as,
    get_derived_capacitances,
    derive_scenario_seed,
)


def test_profile_override_automotive():
    """Verify that profiles/automotive.yaml overrides base values."""
    base_assumptions = resolve_assumptions()
    auto_assumptions = resolve_assumptions(profile="automotive")

    assert auto_assumptions.duty.cycle_type.value == "dynamic_fuds"
    assert auto_assumptions.duty.pulse_c_rate.value == 2.0
    assert auto_assumptions.bars.t5_converge_time_s.value == 60.0
    # Plant nominal capacity remains from base
    assert auto_assumptions.plant.nominal_capacity_Ah.value == base_assumptions.plant.nominal_capacity_Ah.value


def test_profile_override_bess():
    """Verify that profiles/bess.yaml overrides base values."""
    bess_assumptions = resolve_assumptions(profile="bess")

    assert bess_assumptions.duty.cycle_type.value == "minor_loops"
    assert bess_assumptions.duty.pulse_c_rate.value == 0.5
    assert bess_assumptions.bars.t5_converge_time_s.value == 900.0


def test_cli_overrides_applied_last():
    """Verify that CLI --set overrides win over base and profile."""
    # Override capacity and sensor bias
    cli_overrides = [
        "plant.nominal_capacity_Ah=120.0",
        "sensors.current_offset_a.value=0.25",
    ]
    assumptions = resolve_assumptions(profile="automotive", cli_overrides=cli_overrides)

    assert assumptions.plant.nominal_capacity_Ah.value == 120.0
    assert assumptions.sensors.current_offset_a.value == 0.25
    # Still retains automotive profile overrides
    assert assumptions.duty.cycle_type.value == "dynamic_fuds"


def test_cli_override_out_of_bounds_rejected():
    """Verify that an invalid CLI override value outside bounds is caught and rejected."""
    cli_overrides = ["plant.nominal_capacity_Ah=999.0"]  # Upper bound is 500.0
    with pytest.raises(ValueError, match="outside declared bounds"):
        resolve_assumptions(cli_overrides=cli_overrides)


def test_config_hash_is_deterministic():
    """Verify that hashing identical configs produces identical SHA-256 digests."""
    _, raw1, hash1 = load_assumptions()
    _, raw2, hash2 = load_assumptions()
    assert hash1 == hash2

    # A changed value produces a different hash
    _, raw_mod, hash_mod = load_assumptions(cli_overrides=["plant.nominal_capacity_Ah=105.0"])
    assert hash1 != hash_mod


def test_count_assumption_statuses():
    """Verify that placeholder and assumed parameters are counted correctly."""
    assumptions, raw_dict, _ = load_assumptions()
    counts = count_assumption_statuses(raw_dict)
    assert counts["placeholder"] > 0
    assert counts["assumed"] > 0
    # The sum of all counts should be equal to the number of assumption entries
    total_entries = sum(counts.values())
    assert total_entries >= 40


def test_derived_quantities_computation():
    """Verify that derived capacitances and Coulomb capacity are computed dynamically in one place."""
    assumptions = resolve_assumptions()
    derived = compute_derived_quantities(assumptions)

    assert "capacity_As" in derived
    expected_as = 100.0 * 3600
    assert derived["capacity_As"] == pytest.approx(expected_as)

    # Check capacitance for 25.0 C: C1 = tau1 / R1 = 15.0 / 0.0006 = 25000 Farads
    c1_25 = derived["c1_farad"]["25.0"]
    assert c1_25 == pytest.approx(15.0 / 0.0006)

    # Check capacitance for 25.0 C: C2 = tau2 / R2 = 60.0 / 0.0009 = 66666.67 Farads
    c2_25 = derived["c2_farad"]["25.0"]
    assert c2_25 == pytest.approx(60.0 / 0.0009)


def test_derive_scenario_seed_is_reproducible():
    """Verify deterministic seed generation from master seed and scenario hash."""
    seed1 = derive_scenario_seed(42, "abcd1234ef567890abcd1234ef567890")
    seed2 = derive_scenario_seed(42, "abcd1234ef567890abcd1234ef567890")
    assert seed1 == seed2

    seed3 = derive_scenario_seed(42, "ffff0000ef567890abcd1234ef567890")
    assert seed1 != seed3


def test_estimator_model_defaults_to_copy_of_plant_when_not_set():
    """Verify that estimator_model defaults to plant parameters when mismatch is zero."""
    from soc.assumptions.derived import get_effective_estimator_parameters

    assumptions = resolve_assumptions()
    est_params = get_effective_estimator_parameters(assumptions)

    assert est_params["nominal_capacity_Ah"] == assumptions.plant.nominal_capacity_Ah.value
    assert est_params["coulombic_efficiency"] == assumptions.plant.coulombic_efficiency.value
    assert est_params["r0_table_ohm"] == assumptions.plant.r0_table_ohm.value
    assert est_params["r1_table_ohm"] == assumptions.plant.r1_table_ohm.value
    assert est_params["tau1_table_s"] == assumptions.plant.tau1_table_s.value
    assert est_params["hysteresis_amplitude_v"] == assumptions.plant.hysteresis_amplitude_v.value


def test_mismatch_block_scales_estimator_params_and_leaves_plant_unchanged():
    """Verify that mismatch scales estimator parameters and leaves plant untouched."""
    from soc.assumptions.derived import get_effective_estimator_parameters

    cli_overrides = [
        "estimator_model.mismatch.capacity_pct.value=10.0",
        "estimator_model.mismatch.r0_pct.value=-10.0",
        "estimator_model.mismatch.ocv_offset_mv.value=5.0",
    ]
    assumptions = resolve_assumptions(cli_overrides=cli_overrides)
    est_params = get_effective_estimator_parameters(assumptions)

    # Estimator parameters must be scaled
    # 100 Ah + 10% = 110 Ah
    assert est_params["nominal_capacity_Ah"] == pytest.approx(110.0)
    # R0 at 25.0 C: 0.0010 - 10% = 0.0009
    assert est_params["r0_table_ohm"]["25.0"] == pytest.approx(0.0009)
    # OCV at 25.0 C first point: 2.500 V + 5 mV (0.005 V) = 2.505 V
    assert est_params["ocv_table_v"]["25.0"][0] == pytest.approx(2.505)

    # Plant parameters MUST remain strictly unchanged
    assert assumptions.plant.nominal_capacity_Ah.value == 100.0
    assert assumptions.plant.r0_table_ohm.value["25.0"] == 0.0010
    assert assumptions.plant.ocv_table_v.value["25.0"][0] == 2.500

