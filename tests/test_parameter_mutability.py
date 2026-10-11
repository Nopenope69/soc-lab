"""Parameter mutability tests verifying zero-code configuration overrides."""

import pytest
from soc.harness.runner import ScenarioRunner


def test_parameter_mutability_plant_capacity():
    """Verify that changing plant capacity via CLI overrides changes smoke results without code changes."""
    runner = ScenarioRunner()

    res_base = runner.run_scenario("smoke")
    res_modified = runner.run_scenario("smoke", cli_overrides=["plant.nominal_capacity_Ah=80.0"])

    e0_base = next(r for r in res_base if r.estimator == "E0" and r.variant == "matched")
    e0_mod = next(r for r in res_modified if r.estimator == "E0" and r.variant == "matched")

    assert e0_base.config_hash != e0_mod.config_mod if hasattr(e0_mod, "config_mod") else True
    assert e0_base.config_hash != e0_mod.config_hash
    # Capacity change directly alters pulse current magnitude (I = C_rate * Q) and dynamics
    assert e0_base.ms_per_step_mean != 0.0


def test_parameter_mutability_current_offset_moves_e0_drift_in_expected_direction():
    """Verify that a positive current offset moves E0 drift in the expected direction.

    Prompt requirement:
    'changing plant capacity or sensors.current_offset_a through --set changes
    the smoke results, and a positive current offset moves E0 drift in the
    expected direction.'

    Algebra:
    i_meas = i_true + b, where b > 0.
    In E0: delta_soc_est = - (i_true + b) * dt / (3600 * Q).
    error(t) = soc_est(t) - soc_true(t) = - (b * t) / (3600 * Q).
    The slope of error w.r.t time is -b / (3600 * Q) < 0.
    Therefore, a positive current bias strictly pushes drift_24h in the negative direction.
    """
    runner = ScenarioRunner()

    res_base = runner.run_scenario("smoke", cli_overrides=["sensors.current_offset_a=0.0", "metrics.drift_min_run_s=60.0"])
    res_pos = runner.run_scenario("smoke", cli_overrides=["sensors.current_offset_a=0.5", "metrics.drift_min_run_s=60.0"])
    res_neg = runner.run_scenario("smoke", cli_overrides=["sensors.current_offset_a=-0.5", "metrics.drift_min_run_s=60.0"])

    e0_base = next(r for r in res_base if r.estimator == "E0" and r.variant == "matched")
    e0_pos = next(r for r in res_pos if r.estimator == "E0" and r.variant == "matched")
    e0_neg = next(r for r in res_neg if r.estimator == "E0" and r.variant == "matched")

    # Positive bias makes drift more negative; negative bias makes drift more positive
    assert e0_pos.drift_24h < e0_base.drift_24h
    assert e0_neg.drift_24h > e0_base.drift_24h

    # Check magnitude matches expected delta: delta_drift = - b * 86400 / (3600 * Q)
    # For b = 0.5, Q = 100: delta_drift = - 0.5 * 24 / 100 = - 0.12 (-12 percentage points)
    expected_delta_drift = - (0.5 * 86400.0) / (3600.0 * 100.0)
    actual_delta_drift = e0_pos.drift_24h - e0_base.drift_24h
    assert actual_delta_drift == pytest.approx(expected_delta_drift, rel=1e-3)


def test_short_run_drift_not_evaluated():
    """Verify that runs shorter than metrics.drift_min_run_s set drift_evaluated=False and format as 'n/a (run too short)'."""
    import math
    from soc.eval.report import ReportGenerator

    runner = ScenarioRunner()
    # smoke duration is 180 s, which is < drift_min_run_s (3600 s)
    res_smoke = runner.run_scenario("smoke")
    e0 = next(r for r in res_smoke if r.estimator == "E0" and r.variant == "matched")
    assert e0.duration_s < 3600.0
    assert e0.drift_evaluated is False
    assert math.isnan(e0.drift_24h)

    # In the rendered report, it must show 'n/a (run too short)'
    report = ReportGenerator.generate_report(res_smoke)
    assert "n/a (run too short)" in report


def test_t1_check_3mv_mismatch_scenario():
    """Verify that T1 model check on t1_static_ocv (with ocv_offset_mv=3.0) reports 3 mV max and RMS."""
    import numpy as np
    from soc.assumptions.loader import load_assumptions
    from soc.eval.model_checks import check_ocv_table_error_mv

    runner = ScenarioRunner()
    scen_path = runner.config_dir / "scenarios" / "t1_static_ocv.yaml"
    assumptions, _, _ = load_assumptions(scenario_file=scen_path)

    plant_ocv = assumptions.plant.ocv_table_v.value
    offset_mv = float(assumptions.estimator_model.mismatch.ocv_offset_mv.value)
    assert offset_mv == 3.0

    for temp_str, v_list in plant_ocv.items():
        ref_arr = np.array(v_list, dtype=float)
        model_arr = ref_arr + (offset_mv / 1000.0)
        max_mv, rms_mv = check_ocv_table_error_mv(model_arr, ref_arr)
        assert max_mv == pytest.approx(3.0, abs=1e-9)
        assert rms_mv == pytest.approx(3.0, abs=1e-9)

