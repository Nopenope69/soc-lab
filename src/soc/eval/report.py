"""Benchmark report generator producing GitHub Flavored Markdown reports."""

import math
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

from soc.assumptions.loader import PERCENT_FACTOR, load_assumptions
from soc.assumptions.schema import Assumptions
from soc.eval.model_checks import check_ocv_table_error_mv
from soc.harness.runner import RunResult

MANDATORY_HEADER = (
    "> Synthetic data. Software correctness and comparison only, not accuracy evidence."
)

UNIMPLEMENTED_ESTIMATORS = ["E3", "E4", "E5", "E6", "E7"]


def format_pp(val: float) -> str:
    """Format fractional error as percentage points, handling NaN and Inf."""
    if val is None or math.isnan(val):
        return "n/a"
    if math.isinf(val):
        return "never"
    return f"{val * PERCENT_FACTOR:.2f} pp"


def format_sec(val: float) -> str:
    """Format duration in seconds, handling NaN and Inf."""
    if val is None or math.isnan(val):
        return "n/a"
    if math.isinf(val):
        return "never"
    return f"{val:.1f} s"


def format_ms(val: float) -> str:
    """Format execution time in milliseconds."""
    if val is None or math.isnan(val):
        return "n/a"
    if math.isinf(val):
        return "never"
    return f"{val:.2f} ms"


def format_mv(val: float) -> str:
    """Format voltage in millivolts."""
    if val is None or math.isnan(val):
        return "n/a"
    if math.isinf(val):
        return "never"
    return f"{val * 1000:.2f} mV"


def format_float(val: float) -> str:
    """Format general float."""
    if val is None or math.isnan(val):
        return "n/a"
    if math.isinf(val):
        return "never"
    return f"{val:.3f}"


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
        temp_warnings = first_res.temp_clamp_warnings if first_res else 0

        # Load assumptions if not provided
        if assumptions is None:
            assumptions, _, _ = load_assumptions(profile=active_profile)

        # 2. Executive Metadata
        lines.append("## Executive Metadata")
        lines.append("")
        lines.append(f"- **Active Profile:** `{active_profile}`")
        lines.append(f"- **Git Commit:** `{commit_hash}`")
        lines.append(f"- **Configuration Hash:** `{config_hash}`")
        lines.append(f"- **Temperature-Clamp Warnings:** `{temp_warnings}`")
        lines.append("")

        # 3. Benchmark Metric Results Table
        lines.append("## Benchmark Metric Results")
        lines.append("")
        lines.append(
            "| Scenario | Variant | Estimator | RMSE | MAE | Max Err | P95 Err | Plateau RMSE | Conv 5% | Conv 2% | Drift 24h | Rev Spike | ms/step (med) | V Res (mV) | NIS | Pass All |"
        )
        lines.append(
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        )

        for r in results:
            pass_str = "PASS" if r.pass_all_bars else f"FAIL ({r.failed_bars})"
            v_res_str = (
                f"{r.voltage_residual_rmse * 1000:.2f}"
                if not math.isnan(r.voltage_residual_rmse)
                else "n/a"
            )
            nis_str = (
                f"{r.mean_nis:.2f}" if not math.isnan(r.mean_nis) else "n/a"
            )
            lines.append(
                f"| `{r.scenario}` | `{r.variant}` | **{r.estimator}** | {format_pp(r.rmse)} | {format_pp(r.mae)} | {format_pp(r.max_abs_error)} | {format_pp(r.p95_error)} | {format_pp(r.plateau_rmse_20_80)} | {format_sec(r.converge_time_5pct)} | {format_sec(r.converge_time_2pct)} | {format_pp(r.drift_24h)} | {format_pp(r.post_reversal_error_60s)} | {format_ms(r.ms_per_step_median)} | {v_res_str} | {nis_str} | {pass_str} |"
            )

        # List unimplemented estimators
        for unimpl in UNIMPLEMENTED_ESTIMATORS:
            lines.append(
                f"| *scheduled* | *n/a* | **{unimpl}** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |"
            )
        lines.append("")

        # 4. Profile Bars & Pass/Fail Matrix
        lines.append("## Profile Bars & Pass/Fail Evaluation")
        lines.append("")
        bars = assumptions.bars
        lines.append(f"Pass/fail criteria loaded from active profile `{active_profile}`:")
        lines.append("")
        lines.append("| Bar Name | Threshold | Applied Scenarios | Description |")
        lines.append("| :--- | :--- | :--- | :--- |")
        lines.append(
            f"| `t1_ocv_error_max_mv` | {bars.t1_ocv_error_max_mv.value} mV | `t1_static_ocv` | Model OCV table error against reference |"
        )
        lines.append(
            f"| `t2_dynamic_rmse_max` | {format_pp(bars.t2_dynamic_rmse_max.value)} | `smoke`, `t3_t10_minor_loops` | Dynamic cycling RMSE bar |"
        )
        lines.append(
            f"| `t2_dynamic_max_error` | {format_pp(bars.t2_dynamic_max_error.value)} | `smoke`, `t3_t10_minor_loops` | Dynamic cycling maximum error bar |"
        )
        lines.append(
            f"| `t4_plateau_p95_max` | {format_pp(bars.t4_plateau_p95_max.value)} | `t4_plateau_stress` | 95th percentile error on plateau |"
        )
        lines.append(
            f"| `t5_converge_time_s` | {bars.t5_converge_time_s.value} s | `t5_initial_soc_offset` | Convergence time from 10pp offset |"
        )
        lines.append(
            f"| `t6_drift_bess_per_day_max` | {format_pp(bars.t6_drift_bess_per_day_max.value)} | `t6_current_bias` | 24-hour current bias drift bar |"
        )
        lines.append(
            f"| `t7_error_rise_max` | {format_pp(bars.t7_error_rise_max.value)} | `t7_voltage_quant_noise` | Max error rise under sensor noise |"
        )
        lines.append(
            f"| `t9_post_rest_step_error_max` | {format_pp(bars.t9_post_rest_step_error_max.value)} | `t9_rest_relaxation` | Max error during RC relaxation |"
        )
        lines.append(
            f"| `t10_reversal_spike_max` | {format_pp(bars.t10_reversal_spike_max.value)} | `t3_t10_minor_loops` | Error spike after direction reversal |"
        )
        lines.append(
            f"| `t14_auto_max_ms_per_step` | {bars.t14_auto_max_ms_per_step.value} ms | all scenarios | Median computation latency per step |"
        )
        lines.append("")

        # Pass/fail matrix per estimator per scenario
        estimators_present = sorted(list(set(r.estimator for r in results)))
        scenarios_present = sorted(list(set(r.scenario for r in results)))

        lines.append("### Pass / Fail Matrix")
        lines.append("")
        lines.append(
            f"| Estimator | Variant | " + " | ".join(f"`{s}`" for s in scenarios_present) + " | Overall |"
        )
        lines.append(
            f"| :--- | :--- | " + " | ".join(":---" for _ in scenarios_present) + " | :--- |"
        )

        first_passing_rung = None
        for est_name in ["E0", "E1", "E2"]:
            for var_name in ["matched", "mismatched"]:
                matching_rows = [
                    r for r in results if r.estimator == est_name and r.variant == var_name
                ]
                if not matching_rows:
                    continue

                row_statuses = []
                all_passed = True
                for scen in scenarios_present:
                    scen_matches = [r for r in matching_rows if r.scenario == scen]
                    if scen_matches:
                        is_p = scen_matches[0].pass_all_bars
                        row_statuses.append("PASS" if is_p else "FAIL")
                        if not is_p:
                            all_passed = False
                    else:
                        row_statuses.append("n/a")

                overall_str = "**PASS**" if all_passed else "FAIL"
                lines.append(
                    f"| **{est_name}** | `{var_name}` | "
                    + " | ".join(row_statuses)
                    + f" | {overall_str} |"
                )

                if all_passed and first_passing_rung is None:
                    first_passing_rung = f"{est_name} ({var_name})"

        lines.append("")
        rung_label = first_passing_rung if first_passing_rung else "None (all rungs failed at least one bar)"
        lines.append(f"**First Rung Meeting All Bars:** `{rung_label}`")
        lines.append("")

        # 5. T1 Model Check Section
        lines.append("## T1 OCV Model Check")
        lines.append("")
        lines.append(
            "> Evaluates model OCV table error against reference plant OCV table across temperature calibration points."
        )
        lines.append("")

        # Evaluate OCV error between plant and mismatched estimator_model
        plant_ocv = assumptions.plant.ocv_table_v.value
        mismatch_offset_mv = float(assumptions.estimator_model.mismatch.ocv_offset_mv.value)
        t1_bar_mv = float(bars.t1_ocv_error_max_mv.value)

        lines.append("| Temperature | Max Error (mV) | RMS Error (mV) | Bar Threshold | Result |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")

        all_t1_pass = True
        if isinstance(plant_ocv, dict):
            for temp_str, v_list in plant_ocv.items():
                ref_arr = np.array(v_list, dtype=float)
                # Model after mismatch
                model_arr = ref_arr + (mismatch_offset_mv / 1000)
                max_mv, rms_mv = check_ocv_table_error_mv(model_arr, ref_arr)
                t1_pass = max_mv <= t1_bar_mv
                if not t1_pass:
                    all_t1_pass = False
                res_str = "PASS" if t1_pass else "FAIL"
                lines.append(
                    f"| `{temp_str} C` | {max_mv:.2f} mV | {rms_mv:.2f} mV | {t1_bar_mv:.1f} mV | {res_str} |"
                )
        lines.append("")

        # 6. Diagnostic Observations
        lines.append("## Diagnostic Observations")
        lines.append("")
        # Compare E1 and E2 plateau RMSE
        e1_plat = [r.plateau_rmse_20_80 for r in results if r.estimator == "E1"]
        e2_plat = [r.plateau_rmse_20_80 for r in results if r.estimator == "E2"]
        hyst_amp = float(assumptions.plant.hysteresis_amplitude_v.value)
        if e1_plat and e2_plat and hyst_amp > float(0):
            mean_e1 = float(np.mean(e1_plat))
            mean_e2 = float(np.mean(e2_plat))
            if mean_e2 > mean_e1:
                lines.append(
                    f"> **[DIAGNOSTIC WARNING]** Plant hysteresis is active ({hyst_amp*1000:.1f} mV), but E2 plateau RMSE ({mean_e2*PERCENT_FACTOR:.2f} pp) did not outperform E1 ({mean_e1*PERCENT_FACTOR:.2f} pp)."
                )
            else:
                lines.append(
                    f"- **Hysteresis Performance:** With plant hysteresis active ({hyst_amp*1000:.1f} mV), E2 achieved plateau RMSE {mean_e2*PERCENT_FACTOR:.2f} pp vs E1 {mean_e1*PERCENT_FACTOR:.2f} pp."
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
