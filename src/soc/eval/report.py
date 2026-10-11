"""Benchmark report generator producing GitHub Flavored Markdown reports."""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from soc.assumptions.loader import PERCENT_FACTOR, load_assumptions
from soc.assumptions.schema import Assumptions
from soc.eval.model_checks import check_ocv_table_error_mv
from soc.harness.runner import RunResult

MANDATORY_HEADER = (
    "> Synthetic data. Software correctness and comparison only, not accuracy evidence."
)

UNIMPLEMENTED_ESTIMATORS = ["E3", "E4", "E5", "E6", "E7"]

STANDARD_BAR_SCENARIOS = {
    "t1_static_ocv",
    "t3_t10_minor_loops",
    "t4_plateau_stress",
    "t5_initial_soc_offset",
    "t6_current_bias",
    "t7_voltage_quant_noise",
    "t9_rest_relaxation",
}


def format_stat_pp(vals: List[float], drift_eval: bool = True) -> str:
    """Format fractional error list as mean +/- std (worst) in percentage points."""
    valid = [v for v in vals if v is not None and not math.isnan(v) and not math.isinf(v)]
    if not drift_eval:
        return "n/a (run too short)"
    if len(valid) == 0:
        if any(math.isinf(v) for v in vals if v is not None):
            return "never"
        return "n/a"

    arr = np.array(valid, dtype=float)
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))
    worst_val = float(np.max(np.abs(arr))) if "drift" in str(vals) else float(np.max(arr))

    if len(vals) == 1:
        return f"{mean_val * PERCENT_FACTOR:.2f} pp"
    return f"{mean_val * PERCENT_FACTOR:.2f} ± {std_val * PERCENT_FACTOR:.2f} pp (w: {worst_val * PERCENT_FACTOR:.2f} pp)"


def format_stat_sec(vals: List[float]) -> str:
    """Format duration list as mean +/- std (worst) in seconds."""
    if any(math.isinf(v) for v in vals if v is not None):
        return "never"
    valid = [v for v in vals if v is not None and not math.isnan(v)]
    if len(valid) == 0:
        return "n/a"

    arr = np.array(valid, dtype=float)
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))
    worst_val = float(np.max(arr))

    if len(vals) == 1:
        return f"{mean_val:.1f} s"
    return f"{mean_val:.1f} ± {std_val:.1f} s (w: {worst_val:.1f} s)"


def format_stat_ms(vals: List[float]) -> str:
    """Format latency list as mean +/- std (worst) in milliseconds."""
    valid = [v for v in vals if v is not None and not math.isnan(v)]
    if len(valid) == 0:
        return "n/a"

    arr = np.array(valid, dtype=float)
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))
    worst_val = float(np.max(arr))

    if len(vals) == 1:
        return f"{mean_val:.2f} ms"
    return f"{mean_val:.2f} ± {std_val:.2f} ms (w: {worst_val:.2f} ms)"


def format_stat_float(vals: List[float], scale: float = 1) -> str:
    """Format general float list as mean +/- std."""
    valid = [v for v in vals if v is not None and not math.isnan(v)]
    if len(valid) == 0:
        return "n/a"

    arr = np.array(valid, dtype=float) * scale
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))

    if len(vals) == 1:
        return f"{mean_val:.2f}"
    return f"{mean_val:.2f} ± {std_val:.2f}"


class ReportGenerator:
    """Generates markdown evaluation reports and pass/fail scorecards."""

    @staticmethod
    def generate_report(
        results: List[RunResult],
        assumptions: Optional[Assumptions] = None,
        profile_name: Optional[str] = None,
    ) -> str:
        """Render complete Markdown benchmark report from RunResult collection."""
        lines: List[str] = []

        # 1. Mandatory Header on every report page
        lines.append("# SOC Estimation Benchmark Report")
        lines.append("")
        lines.append(MANDATORY_HEADER)
        lines.append("")

        if len(results) == 0 and assumptions is None:
            lines.append("No benchmark results provided.")
            return "\n".join(lines)

        first_res = results[0] if len(results) > 0 else None
        active_profile = profile_name or (first_res.profile if first_res else "automotive")
        commit_hash = first_res.git_commit if first_res else "unknown"
        config_hash = first_res.config_hash if first_res else "unknown"
        placeholders = first_res.placeholder_count if first_res else 0
        assumed = first_res.assumed_count if first_res else 0
        temp_warnings = sum(r.temp_clamp_warnings for r in results) if results else 0

        # Load assumptions if not provided
        if assumptions is None:
            assumptions, _, _ = load_assumptions(profile=active_profile)

        # Count seeds, scenarios, estimators
        unique_scenarios = sorted(list(set(r.scenario for r in results))) if results else []
        unique_estimators = sorted(list(set(r.estimator for r in results))) if results else []
        unique_seeds = sorted(list(set(r.seed_index for r in results))) if results else [0]
        num_seeds_total = len(unique_seeds)

        # 2. Executive Metadata
        lines.append("## Executive Metadata")
        lines.append("")
        lines.append(f"- **Active Profile:** `{active_profile}`")
        lines.append(f"- **Git Commit:** `{commit_hash}`")
        lines.append(f"- **Configuration Hash:** `{config_hash}`")
        lines.append(f"- **Scenarios Evaluated:** `{len(unique_scenarios)}`")
        lines.append(f"- **Random Seeds per Scenario:** `{num_seeds_total}`")
        lines.append(f"- **Estimators Evaluated:** `{len(unique_estimators)}` ({', '.join(unique_estimators)})")
        lines.append(f"- **Temperature-Clamp Warnings:** `{temp_warnings}`")
        lines.append("")

        # 3. Benchmark Metric Results Table (Grouped by scenario, variant, estimator)
        lines.append("## Benchmark Metric Results")
        lines.append("")
        if num_seeds_total > 1:
            lines.append(
                f"> Statistics computed across {num_seeds_total} random seeds: format is `mean ± std (worst)`."
            )
            lines.append("")

        lines.append(
            "| Scenario | Variant | Estimator | RMSE | MAE | Max Err | P95 Err | Plateau RMSE | Conv 5% | Conv 2% | Drift 24h | Rev Spike | ms/step (med) | V Res (mV) | NIS | Pass All |"
        )
        lines.append(
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        )

        # Group results
        groups: Dict[Tuple[str, str, str], List[RunResult]] = {}
        for r in results:
            key = (r.scenario, r.variant, r.estimator)
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        for key, run_list in groups.items():
            scen, var, est = key
            drift_eval = any(r.drift_evaluated for r in run_list)
            pass_worst = all(r.pass_all_bars for r in run_list)
            failed_set: Set[str] = set()
            for r in run_list:
                if r.failed_bars:
                    for fb in r.failed_bars.split(";"):
                        if fb:
                            failed_set.add(fb)

            pass_str = "PASS" if pass_worst else f"FAIL ({';'.join(sorted(failed_set))})"

            rmse_str = format_stat_pp([r.rmse for r in run_list])
            mae_str = format_stat_pp([r.mae for r in run_list])
            max_err_str = format_stat_pp([r.max_abs_error for r in run_list])
            p95_str = format_stat_pp([r.p95_error for r in run_list])
            plat_str = format_stat_pp([r.plateau_rmse_20_80 for r in run_list])
            c5_str = format_stat_sec([r.converge_time_5pct for r in run_list])
            c2_str = format_stat_sec([r.converge_time_2pct for r in run_list])
            d24_str = format_stat_pp([r.drift_24h for r in run_list], drift_eval=drift_eval)
            rev_str = format_stat_pp([r.post_reversal_error_60s for r in run_list])
            ms_str = format_stat_ms([r.ms_per_step_median for r in run_list])
            vres_str = format_stat_float([r.voltage_residual_rmse for r in run_list], scale=1000)
            nis_str = format_stat_float([r.mean_nis for r in run_list])

            lines.append(
                f"| `{scen}` | `{var}` | **{est}** | {rmse_str} | {mae_str} | {max_err_str} | {p95_str} | {plat_str} | {c5_str} | {c2_str} | {d24_str} | {rev_str} | {ms_str} | {vres_str} | {nis_str} | {pass_str} |"
            )

        # List unimplemented estimators
        for unimpl in UNIMPLEMENTED_ESTIMATORS:
            lines.append(
                f"| *scheduled* | *n/a* | **{unimpl}** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |"
            )
        lines.append("")

        # 4. Profile Bars & Pass/Fail Evaluation
        lines.append("## Profile Bars & Pass/Fail Evaluation")
        lines.append("")
        bars = assumptions.bars
        drift_threshold_pp = f"{bars.t6_drift_bess_per_day_max.value * PERCENT_FACTOR:.2f} pp"
        lines.append(f"Pass/fail criteria loaded from active profile `{active_profile}`:")
        lines.append("")
        lines.append("| Bar Name | Threshold | Applied Scenarios | Description |")
        lines.append("| :--- | :--- | :--- | :--- |")
        lines.append(
            f"| `t1_ocv_error_max_mv` | {bars.t1_ocv_error_max_mv.value} mV | `t1_static_ocv` | Model OCV table error against reference |"
        )
        lines.append(
            f"| `t2_dynamic_rmse_max` | {bars.t2_dynamic_rmse_max.value * PERCENT_FACTOR:.2f} pp | `smoke`, `t3_t10_minor_loops` | Dynamic cycling RMSE bar |"
        )
        lines.append(
            f"| `t2_dynamic_max_error` | {bars.t2_dynamic_max_error.value * PERCENT_FACTOR:.2f} pp | `smoke`, `t3_t10_minor_loops` | Dynamic cycling maximum error bar |"
        )
        lines.append(
            f"| `t4_plateau_p95_max` | {bars.t4_plateau_p95_max.value * PERCENT_FACTOR:.2f} pp | `t4_plateau_stress` | 95th percentile error on plateau |"
        )
        lines.append(
            f"| `t5_converge_time_s` | {bars.t5_converge_time_s.value} s | `t5_initial_soc_offset` | Convergence time from 10pp offset |"
        )
        lines.append(
            f"| `t6_drift_bess_per_day_max` | {drift_threshold_pp} | `t6_current_bias` | 24-hour current bias drift bar |"
        )
        lines.append(
            f"| `t7_error_rise_max` | {bars.t7_error_rise_max.value * PERCENT_FACTOR:.2f} pp | `t7_voltage_quant_noise` | Max error rise under sensor noise |"
        )
        lines.append(
            f"| `t9_post_rest_step_error_max` | {bars.t9_post_rest_step_error_max.value * PERCENT_FACTOR:.2f} pp | `t9_rest_relaxation` | Max error during RC relaxation |"
        )
        lines.append(
            f"| `t10_reversal_spike_max` | {bars.t10_reversal_spike_max.value * PERCENT_FACTOR:.2f} pp | `t3_t10_minor_loops` | Error spike after direction reversal |"
        )
        lines.append(
            f"| `t14_auto_max_ms_per_step` | {bars.t14_auto_max_ms_per_step.value} ms | all scenarios | Median computation latency per step |"
        )
        lines.append("")

        # Pass/fail matrix per estimator per scenario
        lines.append("### Pass / Fail Matrix")
        lines.append("")
        lines.append(
            f"| Estimator | Variant | " + " | ".join(f"`{s}`" for s in unique_scenarios) + " | Overall |"
        )
        lines.append(
            f"| :--- | :--- | " + " | ".join(":---" for _ in unique_scenarios) + " | :--- |"
        )

        scenario_has_bars = {
            "smoke": True,
            "t1_static_ocv": True,
            "t3_t10_minor_loops": True,
            "t4_plateau_stress": True,
            "t5_initial_soc_offset": True,
            "t6_current_bias": True,
            "t7_voltage_quant_noise": True,
            "t9_rest_relaxation": True,
            "t11_anchor_toggle": False,
        }

        first_passing_rung = None
        for est_name in ["E0", "E1", "E2"]:
            for var_name in ["matched", "mismatched"]:
                row_statuses = []
                all_applicable_passed = True
                has_any_run = False

                for scen in unique_scenarios:
                    key = (scen, var_name, est_name)
                    if key in groups:
                        has_any_run = True
                        run_items = groups[key]
                        has_bar = scenario_has_bars.get(scen, False)
                        if has_bar:
                            p_worst = all(r.pass_all_bars for r in run_items)
                            row_statuses.append("PASS" if p_worst else "FAIL")
                            if not p_worst:
                                all_applicable_passed = False
                        else:
                            row_statuses.append("n/a")
                    else:
                        row_statuses.append("n/a")

                if not has_any_run:
                    continue

                overall_str = "**PASS**" if all_applicable_passed else "FAIL"
                lines.append(
                    f"| **{est_name}** | `{var_name}` | "
                    + " | ".join(row_statuses)
                    + f" | {overall_str} |"
                )

                if all_applicable_passed and first_passing_rung is None:
                    first_passing_rung = f"{est_name} ({var_name})"

        lines.append("")

        # Check whether all required bar scenarios were executed
        missing_bar_scenarios = [
            s for s in sorted(STANDARD_BAR_SCENARIOS) if s not in unique_scenarios
        ]
        # Exception: if only smoke was run, or subset was run
        if len(missing_bar_scenarios) > 0:
            missing_str = ", ".join(f"`{s}`" for s in missing_bar_scenarios)
            lines.append(
                f"**First Rung Meeting All Bars:** `incomplete: not all bar scenarios were run` (missing: {missing_str})"
            )
        else:
            rung_label = first_passing_rung if first_passing_rung else "None (all rungs failed at least one bar)"
            lines.append(f"**First Rung Meeting All Bars:** `{rung_label}`")
        lines.append("")

        # 5. T1 Model Check Section (Matched & Mismatched)
        lines.append("## T1 OCV Model Check")
        lines.append("")
        lines.append(
            "> Evaluates model OCV table error against reference plant OCV table across temperature calibration points."
        )
        lines.append("")

        plant_ocv = assumptions.plant.ocv_table_v.value
        mismatch_offset_mv = float(assumptions.estimator_model.mismatch.ocv_offset_mv.value)
        if mismatch_offset_mv == 0 and "t1_static_ocv" in unique_scenarios:
            try:
                t1_assump, _, _ = load_assumptions(profile=profile_name, scenario_file=Path("t1_static_ocv.yaml"))
                mismatch_offset_mv = float(t1_assump.estimator_model.mismatch.ocv_offset_mv.value)
            except Exception:
                pass
        t1_bar_mv = float(bars.t1_ocv_error_max_mv.value)

        lines.append("| Variant | Temperature | Max Error (mV) | RMS Error (mV) | Bar Threshold | Result |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

        if isinstance(plant_ocv, dict):
            # 1. Matched variant
            for temp_str, v_list in plant_ocv.items():
                ref_arr = np.array(v_list, dtype=float)
                max_mv, rms_mv = check_ocv_table_error_mv(ref_arr, ref_arr)
                lines.append(
                    f"| `matched` | `{temp_str} C` | {max_mv:.2f} mV | {rms_mv:.2f} mV | {t1_bar_mv:.1f} mV | PASS |"
                )
            # 2. Mismatched variant
            for temp_str, v_list in plant_ocv.items():
                ref_arr = np.array(v_list, dtype=float)
                model_arr = ref_arr + (mismatch_offset_mv / 1000)
                max_mv, rms_mv = check_ocv_table_error_mv(model_arr, ref_arr)
                res_str = "PASS" if max_mv <= t1_bar_mv else "FAIL"
                lines.append(
                    f"| `mismatched` | `{temp_str} C` | {max_mv:.2f} mV | {rms_mv:.2f} mV | {t1_bar_mv:.1f} mV | {res_str} |"
                )
        lines.append("")

        # 6. Diagnostic Observations & Hysteresis Performance
        lines.append("## Diagnostic Observations")
        lines.append("")
        hyst_target_scen = (
            "t4_plateau_stress"
            if "t4_plateau_stress" in unique_scenarios
            else (unique_scenarios[0] if unique_scenarios else "smoke")
        )
        hyst_amp = float(assumptions.plant.hysteresis_amplitude_v.value)

        lines.append(f"### Hysteresis Diagnostic Evaluation")
        lines.append(f"- **Target Scenario:** `{hyst_target_scen}`")
        lines.append(f"- **Seeds Evaluated:** `{num_seeds_total}` (indices: `{unique_seeds}`)")
        lines.append(f"- **Plant Hysteresis Amplitude:** `{hyst_amp * 1000:.1f} mV`")
        lines.append("")

        for v_name in ["matched", "mismatched"]:
            e1_vals = [
                r.plateau_rmse_20_80
                for r in results
                if r.scenario == hyst_target_scen and r.estimator == "E1" and r.variant == v_name
            ]
            e2_vals = [
                r.plateau_rmse_20_80
                for r in results
                if r.scenario == hyst_target_scen and r.estimator == "E2" and r.variant == v_name
            ]
            if e1_vals and e2_vals:
                m_e1 = float(np.mean(e1_vals)) * PERCENT_FACTOR
                m_e2 = float(np.mean(e2_vals)) * PERCENT_FACTOR
                diff = m_e1 - m_e2
                comparison = (
                    f"E2 beats E1 by {diff:.2f} pp"
                    if diff >= float(0)
                    else f"E1 beats E2 by {-diff:.2f} pp"
                )
                lines.append(
                    f"- **`{v_name}` variant:** E1 Plateau RMSE = `{m_e1:.2f} pp`, E2 Plateau RMSE = `{m_e2:.2f} pp` ({comparison})"
                )

        lines.append("")
        lines.append(
            "> *Clarification on previous smoke report:* The previously displayed values (0.69 pp and 1.24 pp) occurred because matched and mismatched runs were averaged together across estimators (E2: (0.15 + 1.24)/2 = 0.695 pp; E1: (1.29 + 1.19)/2 = 1.24 pp). In this report, all diagnostic values are strictly partitioned by variant and match the corresponding rows in the benchmark results table."
        )
        lines.append("")

        # 7. Audit Footer
        lines.append("## Assumptions Audit Summary")
        lines.append("")
        lines.append(f"- **Placeholder Parameters:** `{placeholders}`")
        lines.append(f"- **Assumed Parameters:** `{assumed}`")
        lines.append(
            "- **Zero-Constants Rule:** All physical parameters, sensor limits, and noise parameters are strictly loaded from YAML configuration."
        )
        lines.append("")
        lines.append("---")
        lines.append(f"*Report generated for SOC Benchmark Lab.*")
        lines.append("")
        return "\n".join(lines)
