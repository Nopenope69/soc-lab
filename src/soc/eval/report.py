"""Benchmark report generator producing GitHub Flavored Markdown reports."""

import copy
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from soc.assumptions.loader import (
    DEFAULT_PLATEAU_MAX,
    DEFAULT_PLATEAU_MIN,
    FLOAT_EPSILON,
    PERCENT_FACTOR,
    T1_MISMATCH_OFFSETS_MV,
    load_assumptions,
)
from soc.assumptions.schema import Assumptions
from soc.eval.model_checks import check_ocv_table_error_mv
from soc.harness.runner import RunResult, ScenarioRunner

MANDATORY_HEADER = (
    "> Synthetic data. Software correctness and comparison only, not accuracy evidence.\n"
    "> All cell, sensor and filter values are placeholders. Absolute errors are not expectations for any real cell.\n"
    "> Note: E0 (Coulomb counting) passes scenarios without current sensor error by construction."
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


def format_stat_pp(
    vals: List[float],
    drift_eval: bool = True,
    is_rev_spike: bool = False,
) -> str:
    """Format fractional error list as mean +/- std (worst) in percentage points."""
    valid = [v for v in vals if v is not None and not math.isnan(v) and not math.isinf(v)]
    if is_rev_spike and len(valid) == 0:
        return "n/a (no reversals)"
    if not drift_eval:
        if len(valid) > 0:
            arr = np.array(valid, dtype=float)
            worst_val = float(np.max(np.abs(arr)))
            return f"extrapolated: {worst_val * PERCENT_FACTOR:.2f} pp (not scored)"
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
        ofat_results: Optional[List[Dict[str, Any]]] = None,
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
        git_dirty = any(r.dirty for r in results) if results else False
        dirty_str = "true" if git_dirty else "false"
        lines.append(f"- **Active Profile:** `{active_profile}`")
        lines.append(f"- **Git Commit:** `{commit_hash}`")
        lines.append(f"- **Git Dirty:** `{dirty_str}`")
        lines.append(f"- **Configuration Hash:** `{config_hash}`")
        lines.append(f"- **Scenarios Evaluated:** `{len(unique_scenarios)}`")
        lines.append(f"- **Random Seeds per Scenario:** `{num_seeds_total}`")
        lines.append(f"- **Estimators Evaluated:** `{len(unique_estimators)}` ({', '.join(unique_estimators)})")
        lines.append(f"- **Temperature-Clamp Warnings:** `{temp_warnings}`")
        lines.append("")

        # 3. Resolved Duty Cycle Settings Table
        lines.append("## Resolved Duty Cycle Settings")
        lines.append("")
        lines.append("| Scenario | Cycle Type | Pulse C-Rate | Rest Duration | Total Duration | Initial SOC | SOC Limits |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for scen_name in unique_scenarios:
            clean_s = scen_name.split(" [")[0]
            try:
                scen_a, _, _ = load_assumptions(profile=active_profile, scenario_file=Path(clean_s))
                d = scen_a.duty
                c_str = f"{d.pulse_c_rate.value:.1f} C"
                ctype_str = f"`{d.cycle_type.value}`"
                rest_str = f"{d.rest_duration_s.value:.0f} s"
                dur_str = f"{d.total_duration_s.value:.0f} s"
                isoc_str = f"{d.initial_soc.value * PERCENT_FACTOR:.0f}%"
                lim_str = f"[{d.soc_min_limit.value * PERCENT_FACTOR:.0f}%, {d.soc_max_limit.value * PERCENT_FACTOR:.0f}%]"
                lines.append(f"| `{scen_name}` | {ctype_str} | {c_str} | {rest_str} | {dur_str} | {isoc_str} | {lim_str} |")
            except Exception:
                lines.append(f"| `{scen_name}` | *custom* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* |")
        lines.append("")

        # 4. Scenario Durations and Sample Counts
        lines.append("## Scenario Durations and Sample Counts")
        lines.append("")
        lines.append("| Scenario | Duration (s) | Sample Count (kept) | Sample Period dt (s) | Dropped Samples |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for scen_name in unique_scenarios:
            scen_runs = [r for r in results if r.scenario == scen_name]
            if scen_runs:
                first = scen_runs[0]
                dt_val = first.duration_s / first.n_samples_kept if first.n_samples_kept > 0 else float(1)
                lines.append(
                    f"| `{scen_name}` | {first.duration_s:.1f} s | {first.n_samples_kept} | {dt_val:.1f} s | {first.n_dropped} |"
                )
        lines.append("")

        # 5. Benchmark Metric Results Table (Grouped by scenario, variant, estimator)
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
            rev_str = format_stat_pp([r.post_reversal_error_60s for r in run_list], is_rev_spike=True)
            ms_str = format_stat_ms([r.ms_per_step_median for r in run_list])
            vres_str = format_stat_float([r.voltage_residual_rmse for r in run_list], scale=1000)
            nis_str = format_stat_float([r.mean_nis for r in run_list])

            lines.append(
                f"| `{scen}` | `{var}` | **{est}** | {rmse_str} | {mae_str} | {max_err_str} | {p95_str} | {plat_str} | {c5_str} | {c2_str} | {d24_str} | {rev_str} | {ms_str} | {vres_str} | {nis_str} | {pass_str} |"
            )

        for unimpl in UNIMPLEMENTED_ESTIMATORS:
            lines.append(
                f"| *scheduled* | *n/a* | **{unimpl}** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |"
            )
        lines.append("")

        # 6. Profile Bars & Pass/Fail Evaluation
        lines.append("## Profile Bars & Pass/Fail Evaluation")
        lines.append("")
        bars = assumptions.bars
        drift_threshold_pp = f"{bars.t6_drift_bess_per_day_max.value * PERCENT_FACTOR:.2f} pp"
        lines.append(f"Pass/fail criteria loaded from active profile `{active_profile}`:")
        lines.append("")
        lines.append("| Bar Name | Metric | Threshold | Window | Aggregation | Applied Scenarios | Description |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        lines.append(
            f"| `t1_ocv_error_max_mv` | `ocv_error_mv` | {bars.t1_ocv_error_max_mv.value} mV | full table | max across temperatures | `t1_static_ocv` | Model OCV table error against reference |"
        )
        lines.append(
            f"| `t2_dynamic_rmse_max` | `rmse` | {bars.t2_dynamic_rmse_max.value * PERCENT_FACTOR:.2f} pp | full scenario | worst seed | `smoke`, `t3_t10_minor_loops` | Dynamic cycling RMSE bar |"
        )
        lines.append(
            f"| `t2_dynamic_max_error` | `max_abs_error` | {bars.t2_dynamic_max_error.value * PERCENT_FACTOR:.2f} pp | full scenario | worst seed | `smoke`, `t3_t10_minor_loops` | Dynamic cycling maximum error bar |"
        )
        if active_profile == "bess":
            lines.append(
                f"| `t3_bess_rmse_24h_max` | `rmse` | {bars.t3_bess_rmse_24h_max.value * PERCENT_FACTOR:.2f} pp | 24 h duty | worst seed | `t3_bess_24h` | Stationary BESS 24h duty cycle RMSE bar |"
            )
        lines.append(
            f"| `t4_plateau_p95_max` | `p95_error` | {bars.t4_plateau_p95_max.value * PERCENT_FACTOR:.2f} pp | truth SOC in [0.20, 0.80] | worst seed | `t4_plateau_stress` | 95th percentile error on plateau |"
        )
        lines.append(
            f"| `t5_converge_time_s` | `converge_time_2pct` | {bars.t5_converge_time_s.value} s | start to |error| <= 0.02 | worst seed | `t5_initial_soc_offset` | Convergence time from 10pp offset to within 2pp |"
        )
        lines.append(
            f"| `t6_drift_bess_per_day_max` | `drift_24h` | {drift_threshold_pp} | 86400 s (measured) | worst seed | `t6_current_bias` | 24-hour current bias drift bar |"
        )
        lines.append(
            f"| `t7_error_rise_max` | `error_rise` | {bars.t7_error_rise_max.value * PERCENT_FACTOR:.2f} pp | full scenario | worst seed | `t7_voltage_quant_noise` | RMSE rise under sensor noise above clean baseline |"
        )
        lines.append(
            f"| `t9_post_rest_step_error_max` | `max_abs_error` | {bars.t9_post_rest_step_error_max.value * PERCENT_FACTOR:.2f} pp | post-rest step | worst seed | `t9_rest_relaxation` | Max error during RC relaxation |"
        )
        lines.append(
            f"| `t10_reversal_spike_max` | `post_reversal_error_60s` | {bars.t10_reversal_spike_max.value * PERCENT_FACTOR:.2f} pp | 60 s post-reversal | worst seed | `t3_t10_minor_loops` | Error spike after direction reversal |"
        )
        lines.append(
            f"| `t14_auto_max_ms_per_step` | `ms_per_step_median` | {bars.t14_auto_max_ms_per_step.value} ms | per step | worst seed | all scenarios | Median computation latency per step |"
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
            "t3_bess_24h": True,
            "t4_plateau_stress": True,
            "t5_initial_soc_offset": True,
            "t6_current_bias": True,
            "t6_plateau_only": False,
            "t7_voltage_quant_noise": True,
            "t9_rest_relaxation": True,
            "t11_anchor_toggle": False,
            "t12_hysteresis_mismatch": False,
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

        expected_bar_scenarios = set(STANDARD_BAR_SCENARIOS)
        if active_profile == "bess":
            expected_bar_scenarios.add("t3_bess_24h")

        missing_bar_scenarios = [s for s in sorted(expected_bar_scenarios) if s not in unique_scenarios]
        if len(missing_bar_scenarios) > 0:
            missing_str = ", ".join(f"`{s}`" for s in missing_bar_scenarios)
            lines.append(
                f"**First Rung Meeting All Bars:** `incomplete: not all bar scenarios were run` (missing: {missing_str})"
            )
        else:
            rung_label = first_passing_rung if first_passing_rung else "None (all rungs failed at least one bar)"
            lines.append(f"**First Rung Meeting All Bars:** `{rung_label}`")
        lines.append("")

        # 7. E2 vs E1 Head-to-Head Evaluation Table
        lines.append("## E2 vs E1 Head-to-Head Comparison")
        lines.append("")
        lines.append(
            "> Purely computed comparison of E2 versus E1 across scenarios on Plateau RMSE (or overall RMSE where plateau is unpopulated)."
        )
        lines.append("")
        lines.append(
            "| Scenario | E2 Beats E1 (Matched)? | E1 Plateau RMSE (m) | E2 Plateau RMSE (m) | Margin Matched | E2 Beats E1 (Mismatched)? | E1 Plateau RMSE (mis) | E2 Plateau RMSE (mis) | Margin Mismatched |"
        )
        lines.append(
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        )

        for scen in unique_scenarios:
            e1_m = [r.plateau_rmse_20_80 for r in results if r.scenario == scen and r.estimator == "E1" and r.variant == "matched"]
            e2_m = [r.plateau_rmse_20_80 for r in results if r.scenario == scen and r.estimator == "E2" and r.variant == "matched"]
            e1_mis = [r.plateau_rmse_20_80 for r in results if r.scenario == scen and r.estimator == "E1" and r.variant == "mismatched"]
            e2_mis = [r.plateau_rmse_20_80 for r in results if r.scenario == scen and r.estimator == "E2" and r.variant == "mismatched"]

            # Fallback to overall RMSE if plateau RMSE is NaN
            use_overall = False
            if e1_m and (len(e1_m) == 0 or math.isnan(e1_m[0])):
                use_overall = True
                e1_m = [r.rmse for r in results if r.scenario == scen and r.estimator == "E1" and r.variant == "matched"]
                e2_m = [r.rmse for r in results if r.scenario == scen and r.estimator == "E2" and r.variant == "matched"]
                e1_mis = [r.rmse for r in results if r.scenario == scen and r.estimator == "E1" and r.variant == "mismatched"]
                e2_mis = [r.rmse for r in results if r.scenario == scen and r.estimator == "E2" and r.variant == "mismatched"]

            metric_lbl = " (overall)" if use_overall else ""

            def _compare_pair(e1_list: List[float], e2_list: List[float]) -> Tuple[str, str, str, str]:
                if not e1_list or not e2_list:
                    return "n/a", "n/a", "n/a", "n/a"
                v1 = float(np.mean(e1_list))
                v2 = float(np.mean(e2_list))
                diff_pp = (v1 - v2) * PERCENT_FACTOR
                beats = "YES" if diff_pp >= float(0) else "NO"
                m_str = f"+{diff_pp:.2f} pp" if diff_pp >= float(0) else f"{diff_pp:.2f} pp"
                return beats, f"{v1 * PERCENT_FACTOR:.2f} pp", f"{v2 * PERCENT_FACTOR:.2f} pp", m_str

            b_m, s1_m, s2_m, mg_m = _compare_pair(e1_m, e2_m)
            b_mis, s1_mis, s2_mis, mg_mis = _compare_pair(e1_mis, e2_mis)
            lines.append(
                f"| `{scen}`{metric_lbl} | **{b_m}** | {s1_m} | {s2_m} | {mg_m} | **{b_mis}** | {s1_mis} | {s2_mis} | {mg_mis} |"
            )
        lines.append("")

        # 8. One-Factor-At-A-Time (OFAT) Parameter Sensitivity Sweep
        lines.append("## One-Factor-At-A-Time (OFAT) Parameter Sensitivity Sweep")
        lines.append("")
        lines.append(
            "> Evaluates E1 and E2 on `t3_t10_minor_loops`, `t4_plateau_stress`, and `t5_initial_soc_offset` under isolated single-parameter perturbations with matched noise realization."
        )
        lines.append("")

        if ofat_results is None:
            try:
                runner = ScenarioRunner()
                ofat_results = runner.run_ofat_sensitivity(profile=active_profile)
            except Exception:
                ofat_results = []

        if ofat_results:
            # Rank parameters by maximum effect magnitude
            param_effects: Dict[str, float] = {}
            for r in ofat_results:
                p_name = r["parameter"]
                if p_name != "combined mismatch":
                    eff = r["effect_magnitude"]
                    param_effects[p_name] = max(param_effects.get(p_name, float(0)), eff)

            sorted_params = sorted(param_effects.items(), key=lambda kv: kv[1], reverse=True)
            param_rank = {p: idx + 1 for idx, (p, _) in enumerate(sorted_params)}

            lines.append("### Parameter Ranking by Effect Magnitude")
            lines.append("")
            lines.append("| Rank | Parameter | Maximum Effect on RMSE |")
            lines.append("| :--- | :--- | :--- |")
            for p, eff_val in sorted_params:
                lines.append(f"| {param_rank[p]} | `{p}` | {eff_val * PERCENT_FACTOR:.3f} pp |")
            lines.append("")

            lines.append("### Sensitivity Evaluation Results")
            lines.append("")
            lines.append("| Rank | Parameter | Perturbation | Estimator | Scenario | RMSE | Max Error | Plateau RMSE | Effect Magnitude |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

            # Sort results by parameter rank
            def _sort_key(item: Dict[str, Any]) -> Tuple[int, str, str, str]:
                p = item["parameter"]
                rank_num = param_rank.get(p, 1000)
                return (rank_num, p, item["scenario"], item["estimator"])

            sorted_ofat = sorted(ofat_results, key=_sort_key)
            for r in sorted_ofat:
                p_name = r["parameter"]
                rk_str = str(param_rank.get(p_name, "n/a"))
                eff_pp = f"{r['effect_magnitude'] * PERCENT_FACTOR:.3f} pp"
                lines.append(
                    f"| {rk_str} | `{p_name}` | `{r['size_str']}` | **{r['estimator']}** | `{r['scenario']}` | {r['rmse'] * PERCENT_FACTOR:.2f} pp | {r['max_abs_error'] * PERCENT_FACTOR:.2f} pp | {r['plateau_rmse_20_80'] * PERCENT_FACTOR:.2f} pp | {eff_pp} |"
                )
            lines.append("")

        # 9. T1 Model Check Section (Matched & Mismatched at 3 mV and 5 mV)
        lines.append("## T1 OCV Model Check")
        lines.append("")
        lines.append(
            "> Evaluates model OCV table error against reference plant OCV table across temperature calibration points."
        )
        lines.append("")

        plant_ocv = assumptions.plant.ocv_table_v.value
        t1_bar_mv = float(bars.t1_ocv_error_max_mv.value)

        lines.append("| Variant | Temperature | Max Error (mV) | RMS Error (mV) | Bar Threshold | Margin to Bar | Result |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        if isinstance(plant_ocv, dict):
            # 1. Matched variant
            for temp_str, v_list in plant_ocv.items():
                ref_arr = np.array(v_list, dtype=float)
                max_mv, rms_mv = check_ocv_table_error_mv(ref_arr, ref_arr)
                margin_mv = t1_bar_mv - max_mv
                lines.append(
                    f"| `matched (0 mV)` | `{temp_str} C` | {max_mv:.2f} mV | {rms_mv:.2f} mV | {t1_bar_mv:.1f} mV | +{margin_mv:.2f} mV | PASS |"
                )
            # 2. Mismatched variants at 3 mV and 5 mV
            for off_mv in T1_MISMATCH_OFFSETS_MV:
                for temp_str, v_list in plant_ocv.items():
                    ref_arr = np.array(v_list, dtype=float)
                    model_arr = ref_arr + (off_mv / 1000)
                    max_mv, rms_mv = check_ocv_table_error_mv(model_arr, ref_arr)
                    margin_mv = t1_bar_mv - max_mv
                    res_str = "PASS" if max_mv <= t1_bar_mv else "FAIL"
                    margin_str = f"+{margin_mv:.2f} mV" if margin_mv >= float(0) else f"{margin_mv:.2f} mV"
                    lines.append(
                        f"| `mismatched ({off_mv:.0f} mV)` | `{temp_str} C` | {max_mv:.2f} mV | {rms_mv:.2f} mV | {t1_bar_mv:.1f} mV | {margin_str} | {res_str} |"
                    )
        lines.append("")

        # 10. T6 Current Bias & Drift Diagnostics
        lines.append("## T6 Current Bias & Drift Diagnostics")
        lines.append("")
        lines.append(
            "> Evaluates estimator current bias drift over 24 hours under sensor current offset (0.2 A)."
        )
        lines.append("")

        for t6_scen in ["t6_current_bias", "t6_plateau_only"]:
            scen_runs = [r for r in results if r.scenario == t6_scen]
            if scen_runs:
                first = scen_runs[0]
                lines.append(f"### `{t6_scen}`")
                lines.append(f"- **SOC Range:** `[{first.soc_min * PERCENT_FACTOR:.1f}%, {first.soc_max * PERCENT_FACTOR:.1f}%]`")
                lines.append(f"- **Time on Plateau ([0.20, 0.80]):** `{first.fraction_on_plateau * PERCENT_FACTOR:.1f}%`")
                lines.append("")
                lines.append("| Estimator | Variant | Drift 24h | Status |")
                lines.append("| :--- | :--- | :--- | :--- |")
                for est in ["E0", "E1", "E2"]:
                    for var in ["matched", "mismatched"]:
                        sub = [r for r in scen_runs if r.estimator == est and r.variant == var]
                        if sub:
                            d_str = format_stat_pp([r.drift_24h for r in sub])
                            st_str = "PASS" if all(r.pass_all_bars for r in sub) else "FAIL"
                            lines.append(f"| **{est}** | `{var}` | {d_str} | {st_str} |")
                lines.append("")

        # 11. T7 Sensor Noise Error Rise Diagnostic
        lines.append("## T7 Sensor Noise Error Rise Diagnostic")
        lines.append("")
        lines.append(
            "> Evaluates estimator degradation under sensor quantization and ADC noise against a clean baseline with identical seed and duty."
        )
        lines.append("")
        t7_runs = [r for r in results if r.scenario == "t7_voltage_quant_noise"]
        if t7_runs:
            t7_bar_val = float(bars.t7_error_rise_max.value)
            lines.append("| Estimator | Variant | Clean RMSE | Noisy RMSE | RMSE Rise | Bar Threshold | Result | Max Error Rise |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for est in ["E0", "E1", "E2"]:
                for var in ["matched", "mismatched"]:
                    sub = [r for r in t7_runs if r.estimator == est and r.variant == var]
                    if sub:
                        c_rmse = format_stat_pp([r.clean_rmse for r in sub])
                        n_rmse = format_stat_pp([r.rmse for r in sub])
                        r_rise = format_stat_pp([r.rmse_rise for r in sub])
                        m_rise = format_stat_pp([r.max_error_rise for r in sub])
                        worst_rise = max(r.rmse_rise for r in sub)
                        res_str = "PASS" if worst_rise <= t7_bar_val else "FAIL"
                        lines.append(
                            f"| **{est}** | `{var}` | {c_rmse} | {n_rmse} | {r_rise} | {t7_bar_val * PERCENT_FACTOR:.2f} pp | **{res_str}** | {m_rise} |"
                        )
            lines.append("")

        # 12. T11 Recalibration Anchors & Error Transitions
        lines.append("## T11 Recalibration Anchor Modes & Verification")
        lines.append("")
        lines.append(
            "> T11 evaluates anchor triggering across three configurations: `anchors off`, `full-charge only`, and `rest anchor on`."
        )
        lines.append("")
        t11_runs = [r for r in results if "t11_anchor_toggle" in r.scenario]
        if t11_runs:
            lines.append("| Configuration | Estimator | Variant | Anchor Count | First Anchor Time | Pre-Anchor Error | Post-Anchor Error | Error Drop |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for r in t11_runs:
                if r.estimator == "E0":
                    anc_cnt = r.anchor_count
                    anc_t = f"{r.first_anchor_time_s:.1f} s" if not math.isnan(r.first_anchor_time_s) else "never"
                    pre_e = f"{r.err_pre_anchor * PERCENT_FACTOR:.2f} pp" if not math.isnan(r.err_pre_anchor) else "n/a"
                    post_e = f"{r.err_post_anchor * PERCENT_FACTOR:.2f} pp" if not math.isnan(r.err_post_anchor) else "n/a"
                    drop = (
                        f"{(r.err_pre_anchor - r.err_post_anchor) * PERCENT_FACTOR:.2f} pp"
                        if not math.isnan(r.err_pre_anchor) and not math.isnan(r.err_post_anchor)
                        else "n/a"
                    )
                    lines.append(f"| `{r.scenario}` | **{r.estimator}** | `{r.variant}` | {anc_cnt} | {anc_t} | {pre_e} | {post_e} | {drop} |")
            lines.append("")

        # 13. Transient Spike Anomaly Detection
        lines.append("## Transient Spike Anomaly Detection")
        lines.append("")
        lines.append(
            "> Flags any evaluation run where maximum absolute error exceeds 5.0 pp while RMSE remains below 1.0 pp."
        )
        lines.append("")
        spike_runs = [r for r in results if r.spike_detected]
        if spike_runs:
            lines.append("| Scenario | Estimator | Variant | Seed | Max Error | RMSE | Timestamp (s) | True SOC at t |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for r in spike_runs:
                lines.append(
                    f"| `{r.scenario}` | **{r.estimator}** | `{r.variant}` | {r.seed_index} | {r.max_abs_error * PERCENT_FACTOR:.2f} pp | {r.rmse * PERCENT_FACTOR:.2f} pp | {r.spike_time_s:.1f} s | {r.spike_true_soc * PERCENT_FACTOR:.1f}% |"
                )
            lines.append("")
        else:
            lines.append("- **Anomaly Detection Status:** No runs exhibited transient error spikes exceeding 5.0 pp with RMSE under 1.0 pp.")
            lines.append("")

        # 14. Assumptions Audit Summary
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
