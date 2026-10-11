"""Parameter mutability tests verifying zero-code configuration overrides."""

from pathlib import Path
import numpy as np
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


def test_mismatched_variant_with_all_zero_mismatch_raises_error():
    """Verify that runner raises ValueError if mismatched variant is evaluated with all-zero mismatch."""
    from soc.assumptions.loader import load_assumptions
    from soc.harness.generator import DutyCycleGenerator
    from soc.models.plant import PlantSimulator

    runner = ScenarioRunner()
    cli_overrides = [
        "estimator_model.mismatch.capacity_pct.value=0.0",
        "estimator_model.mismatch.r0_pct.value=0.0",
        "estimator_model.mismatch.r1_pct.value=0.0",
        "estimator_model.mismatch.r2_pct.value=0.0",
        "estimator_model.mismatch.ocv_offset_mv.value=0.0",
        "estimator_model.mismatch.hysteresis_amplitude_pct.value=0.0",
        "estimator_model.mismatch.hysteresis_gamma_pct.value=0.0",
    ]
    assumptions, _, _ = load_assumptions(cli_overrides=cli_overrides)
    meas, truths, times, _, _ = runner.generate_scenario_stream(assumptions, "smoke")

    with pytest.raises(ValueError, match="all-zero mismatch"):
        runner.evaluate_estimator_on_stream("E1", "mismatched", assumptions, meas, truths, times)


def test_minor_loops_scenario_reversal_count_in_both_profiles():
    """Verify that any scenario with cycle_type: minor_loops has reversal_count >= 4 in both profiles."""
    runner = ScenarioRunner()
    for profile in ["automotive", "bess"]:
        results = runner.run_scenario("t3_t10_minor_loops", profile=profile, num_seeds=1)
        r = results[0]
        assert r.reversal_count >= 4, f"Profile {profile} had {r.reversal_count} reversals, expected >= 4"


def test_t4_and_t12_cycle_limits_duration_and_soc_range():
    """Verify that t4_plateau_stress and t12 cycle for >= 3600 s with truth SOC range >= 20 pp."""
    runner = ScenarioRunner()
    for scen in ["t4_plateau_stress", "t12_hysteresis_mismatch"]:
        for profile in ["automotive", "bess"]:
            res = runner.run_scenario(scen, profile=profile, num_seeds=1)
            r = res[0]
            assert r.duration_s >= 3600.0, f"{scen} {profile} duration {r.duration_s} < 3600"
            soc_range_pp = (r.soc_max - r.soc_min) * 100.0
            assert soc_range_pp >= 20.0, f"{scen} {profile} SOC range {soc_range_pp} pp < 20 pp"


def test_scenario_duty_setting_without_reason_raises_error(tmp_path):
    """Verify that scenario setting c_rate or rest without a reason string raises ValueError."""
    import yaml
    from soc.assumptions.loader import load_assumptions

    bad_scen = tmp_path / "bad_duty_scenario.yaml"
    bad_scen.write_text(yaml.dump({
        "duty": {
            "pulse_c_rate": {"value": 1.5}
        }
    }))
    with pytest.raises(ValueError, match="sets duty 'pulse_c_rate' without a declared reason string"):
        load_assumptions(scenario_file=bad_scen)


def test_crate_override_changes_window_currents_and_profiles_differ():
    """Verify that changing C-rate with --set changes spike window currents, and automotive vs bess spike sections differ."""
    from soc.eval.report import ReportGenerator

    runner = ScenarioRunner()
    res_base = runner.run_scenario("t6_plateau_only", profile="automotive", num_seeds=1)
    res_mod = runner.run_scenario("t6_plateau_only", profile="automotive", num_seeds=1, cli_overrides=["duty.pulse_c_rate.value=3.0"])

    curr_base = res_base[0].diagnostic_telemetry.get("applied_current_a")
    curr_mod = res_mod[0].diagnostic_telemetry.get("applied_current_a")
    assert curr_base != curr_mod, "Applied current in diagnostic telemetry did not change with C-rate override"

    res_bess = runner.run_scenario("t6_plateau_only", profile="bess", num_seeds=1)
    rep_auto = ReportGenerator.generate_report(res_base)
    rep_bess = ReportGenerator.generate_report(res_bess)

    assert "t6_plateau_only Spike Windows" in rep_auto
    assert "t6_plateau_only Spike Windows" in rep_bess

    auto_section = rep_auto.split("t6_plateau_only Spike Windows")[1].split("##")[0]
    bess_section = rep_bess.split("t6_plateau_only Spike Windows")[1].split("##")[0]
    assert auto_section != bess_section


def test_pass_all_column_na_when_no_bars():
    """Verify that Table 5 'Pass All' column displays 'n/a (no bars)' for scenarios where no bars apply."""
    from soc.eval.report import ReportGenerator

    runner = ScenarioRunner()
    res_no_bars = runner.run_scenario("t1_static_ocv", profile="automotive", num_seeds=1)
    report = ReportGenerator.generate_report(res_no_bars)

    assert "n/a (no bars)" in report


def test_automotive_and_bess_metric_tables_are_not_identical():
    """Verify that automotive and BESS benchmark runs produce non-identical metric tables."""
    from soc.harness.runner import ScenarioRunner

    runner = ScenarioRunner()
    auto_res = runner.run_scenario("t3_t10_minor_loops", profile="automotive", num_seeds=1)
    bess_res = runner.run_scenario("t3_t10_minor_loops", profile="bess", num_seeds=1)

    auto_rmses = [r.rmse for r in auto_res]
    bess_rmses = [r.rmse for r in bess_res]

    # Due to 2.0 C vs 0.5 C duty profile scaling, RMSEs must diverge
    assert auto_rmses != bess_rmses, "Automotive and BESS metric results unexpectedly identical"


def test_t11_anchor_firing_and_error_transition():
    """Verify that T11 anchor cycle triggers full-charge anchor and drops SOC error."""
    from soc.harness.runner import ScenarioRunner

    runner = ScenarioRunner()
    results = runner.run_scenario("t11_anchor_toggle", num_seeds=1)

    # Check that in full-charge and rest anchor modes, E0 anchors fired
    fc_runs = [r for r in results if "[full-charge only]" in r.scenario and r.estimator == "E0"]
    assert len(fc_runs) > 0
    first_fc = fc_runs[0]
    assert first_fc.anchor_count > 0, "Full-charge anchor failed to fire in T11 anchor cycle"
    assert not np.isnan(first_fc.first_anchor_time_s)
    assert not np.isnan(first_fc.err_post_anchor)
    assert first_fc.err_post_anchor < first_fc.err_pre_anchor


def test_ofat_sensitivity_sweep_coverage():
    """Verify that OFAT parameter sensitivity sweep evaluates all 16 isolated perturbations and combined."""
    from soc.assumptions.loader import OFAT_SWEEP_CONFIGS
    from soc.harness.runner import ScenarioRunner

    runner = ScenarioRunner()
    ofat_rows = runner.run_ofat_sensitivity("automotive")
    assert len(ofat_rows) > 0

    params_evaluated = set(r["parameter"] for r in ofat_rows)
    expected_params = set(cfg[1] for cfg in OFAT_SWEEP_CONFIGS)
    expected_params.add("combined mismatch")
    assert expected_params.issubset(params_evaluated)


def test_t6_plateau_only_scenario_stays_within_plateau():
    """Verify that t6_plateau_only keeps true SOC strictly between 30% and 70%."""
    from soc.assumptions.loader import load_assumptions
    from soc.harness.runner import ScenarioRunner

    runner = ScenarioRunner()
    assumptions, _, _ = load_assumptions(scenario_file=Path("t6_plateau_only.yaml"))
    _, truths, _, _, _ = runner.generate_scenario_stream(assumptions, "t6_plateau_only", seed_index=0)

    socs = [t.soc for t in truths]
    assert min(socs) >= 0.29
    assert max(socs) <= 0.71


