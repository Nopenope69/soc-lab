"""Scenario execution engine, identical measurement stream distribution, and metric logger."""

import csv
from dataclasses import dataclass, asdict
import math
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import warnings
import numpy as np

from soc.assumptions.loader import (
    DEFAULT_PERCENTILE_95,
    DEFAULT_PLATEAU_MAX,
    DEFAULT_PLATEAU_MIN,
    DEFAULT_WARMUP_COUNT,
    PERCENT_FACTOR,
    SECONDS_PER_DAY,
    count_assumption_statuses,
    derive_scenario_noise_seed,
    get_default_config_dir,
    get_git_commit_hash,
    load_assumptions,
)
from soc.assumptions.schema import Assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.registry import get_estimator
from soc.eval.metrics import (
    converge_time_2pct,
    converge_time_5pct,
    drift_24h,
    mae,
    max_abs_error,
    p95_error,
    plateau_rmse_20_80,
    post_reversal_error_60s,
    rmse,
)
from soc.harness.generator import DutyCycleGenerator
from soc.models.plant import Measurement, PlantSimulator, PlantTruthState


@dataclass
class RunResult:
    """Standardized record of estimator evaluation on a scenario."""

    scenario: str
    estimator: str
    variant: str  # "matched" or "mismatched"
    profile: str
    config_hash: str
    git_commit: str
    placeholder_count: int
    assumed_count: int
    temp_clamp_warnings: int
    rmse: float
    mae: float
    max_abs_error: float
    p95_error: float
    plateau_rmse_20_80: float
    converge_time_2pct: float
    converge_time_5pct: float
    drift_24h: float
    post_reversal_error_60s: float
    ms_per_step_mean: float
    ms_per_step_median: float
    voltage_residual_rmse: float
    mean_nis: float
    pass_all_bars: bool
    failed_bars: str


class ScenarioRunner:
    """Runner generating shared measurement streams and executing estimator benchmarks."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or get_default_config_dir()

    def generate_scenario_stream(
        self,
        assumptions: Assumptions,
        scenario_name: str,
    ) -> Tuple[List[Measurement], List[PlantTruthState], List[float], int]:
        """Generate single reproducible measurement and truth stream for scenario.

        Noise seed derived from (run_seed, scenario_hash).
        Returns: (measurements, truths, cumulative_times, temp_warning_count).
        """
        run_seed = int(assumptions.run.random_seed.value)
        noise_seed = derive_scenario_noise_seed(run_seed, scenario_name)
        rng = np.random.default_rng(noise_seed)

        duty_steps = DutyCycleGenerator.generate(assumptions)
        plant = PlantSimulator(assumptions, rng=rng)

        init_soc = float(assumptions.duty.initial_soc.value)
        plant.reset(init_soc)

        measurements: List[Measurement] = []
        truths: List[PlantTruthState] = []
        times: List[float] = []
        t_curr = float(0)

        with warnings.catch_warnings(record=True) as recorded_warnings:
            warnings.simplefilter("always")
            for step in duty_steps:
                meas, truth = plant.step(step.i_app, step.temp_c, step.dt)
                t_curr = t_curr + step.dt
                measurements.append(meas)
                truths.append(truth)
                times.append(t_curr)

        temp_warnings = sum(
            1 for w in recorded_warnings if "Temperature" in str(w.message)
        )
        return measurements, truths, times, temp_warnings

    def evaluate_estimator_on_stream(
        self,
        estimator_name: str,
        variant: str,
        assumptions: Assumptions,
        measurements: List[Measurement],
        truths: List[PlantTruthState],
        times: List[float],
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Run single estimator over measurement stream with timing and error filtering."""
        is_matched = variant == "matched"
        params = ParamSet.from_assumptions(assumptions, matched=is_matched)
        estimator = get_estimator(estimator_name, params)

        init_soc = float(assumptions.duty.initial_soc.value)
        init_offset = float(assumptions.filter.initial_soc_offset.value)
        estimator.reset(init_soc + init_offset)

        step_durations_ms: List[float] = []
        estimates: List[SocEstimate] = []

        for meas in measurements:
            t_start = time.perf_counter()
            out = estimator.step(meas)
            t_end = time.perf_counter()
            step_durations_ms.append((t_end - t_start) * 1000)
            estimates.append(out)

        # Dropped samples handling: hold last valid estimate and exclude dropped steps
        held_estimates: List[float] = []
        curr_est = init_soc + init_offset
        for meas, est in zip(measurements, estimates):
            if not meas.dropout:
                curr_est = est.soc
            held_estimates.append(curr_est)

        kept_indices = [idx for idx, m in enumerate(measurements) if not m.dropout]
        if len(kept_indices) == 0:
            kept_indices = list(range(len(measurements)))

        kept_times = np.array([times[k] for k in kept_indices], dtype=float)
        kept_truth = np.array([truths[k].soc for k in kept_indices], dtype=float)
        kept_est = np.array([held_estimates[k] for k in kept_indices], dtype=float)
        kept_currents = np.array([truths[k].i_true for k in kept_indices], dtype=float)

        # Metric calculations
        th_2pct = float(assumptions.filter.convergence_threshold_2pct.value)
        th_5pct = float(assumptions.filter.convergence_threshold_5pct.value)
        deadband = float(assumptions.filter.reversal_min_current_a.value)

        # Warm-up handling for timing
        warmup = (
            int(assumptions.run.warmup_steps.value)
            if assumptions.run.warmup_steps is not None
            else DEFAULT_WARMUP_COUNT
        )
        timed_durations = (
            step_durations_ms[warmup:]
            if len(step_durations_ms) > warmup
            else step_durations_ms
        )

        metrics = {
            "rmse": rmse(kept_truth, kept_est),
            "mae": mae(kept_truth, kept_est),
            "max_abs_error": max_abs_error(kept_truth, kept_est),
            "p95_error": p95_error(kept_truth, kept_est, percentile=DEFAULT_PERCENTILE_95),
            "plateau_rmse_20_80": plateau_rmse_20_80(
                kept_truth, kept_est, soc_min=DEFAULT_PLATEAU_MIN, soc_max=DEFAULT_PLATEAU_MAX
            ),
            "converge_time_2pct": converge_time_2pct(kept_truth, kept_est, kept_times, threshold=th_2pct),
            "converge_time_5pct": converge_time_5pct(kept_truth, kept_est, kept_times, threshold=th_5pct),
            "drift_24h": drift_24h(kept_truth, kept_est, kept_times, seconds_per_day=SECONDS_PER_DAY),
            "post_reversal_error_60s": post_reversal_error_60s(
                kept_truth, kept_est, kept_times, kept_currents, deadband=deadband
            ),
            "ms_per_step_mean": float(np.mean(timed_durations)) if timed_durations else float(0),
            "ms_per_step_median": float(np.median(timed_durations)) if timed_durations else float(0),
        }

        # Diagnostics (residuals and NIS)
        res_list = [e.voltage_residual for e in estimates if e.voltage_residual is not None]
        nis_list = [
            (e.voltage_residual ** 2) / e.innovation_variance
            for e in estimates
            if e.voltage_residual is not None
            and e.innovation_variance is not None
            and e.innovation_variance > float(0)
        ]

        diag = {
            "voltage_residual_rmse": (
                math.sqrt(float(np.mean(np.square(res_list)))) if res_list else float("nan")
            ),
            "mean_nis": float(np.mean(nis_list)) if nis_list else float("nan"),
        }
        return metrics, diag

    def check_pass_bars(
        self,
        scenario_name: str,
        metrics: Dict[str, float],
        assumptions: Assumptions,
    ) -> Tuple[bool, List[str]]:
        """Evaluate applicable pass/fail bars from active profile for scenario."""
        bars = assumptions.bars
        failed: List[str] = []

        # T2 Dynamic error
        if scenario_name in ["smoke", "t3_t10_minor_loops"]:
            t2_rmse_max = float(bars.t2_dynamic_rmse_max.value)
            t2_max_err = float(bars.t2_dynamic_max_error.value)
            if metrics["rmse"] > t2_rmse_max:
                failed.append("t2_dynamic_rmse_max")
            if metrics["max_abs_error"] > t2_max_err:
                failed.append("t2_dynamic_max_error")

        # T4 Plateau stress
        if scenario_name in ["t4_plateau_stress"]:
            t4_max = float(bars.t4_plateau_p95_max.value)
            if metrics["p95_error"] > t4_max:
                failed.append("t4_plateau_p95_max")

        # T5 Convergence time
        if scenario_name in ["t5_initial_soc_offset"]:
            t5_max_s = float(bars.t5_converge_time_s.value)
            if metrics["converge_time_5pct"] > t5_max_s:
                failed.append("t5_converge_time_s")

        # T6 Current bias drift
        if scenario_name in ["t6_current_bias"]:
            t6_drift_max = float(bars.t6_drift_bess_per_day_max.value)
            if abs(metrics["drift_24h"]) > t6_drift_max:
                failed.append("t6_drift_bess_per_day_max")

        # T7 Voltage quantisation noise
        if scenario_name in ["t7_voltage_quant_noise"]:
            t7_rise_max = float(bars.t7_error_rise_max.value)
            if metrics["max_abs_error"] > t7_rise_max:
                failed.append("t7_error_rise_max")

        # T9 Post rest step error
        if scenario_name in ["t9_rest_relaxation"]:
            t9_post_max = float(bars.t9_post_rest_step_error_max.value)
            if metrics["max_abs_error"] > t9_post_max:
                failed.append("t9_post_rest_step_error_max")

        # T10 Reversal spike
        if scenario_name in ["t3_t10_minor_loops"]:
            t10_spike_max = float(bars.t10_reversal_spike_max.value)
            if metrics["post_reversal_error_60s"] > t10_spike_max:
                failed.append("t10_reversal_spike_max")

        # T14 Execution speed
        t14_ms_max = float(bars.t14_auto_max_ms_per_step.value)
        if metrics["ms_per_step_median"] > t14_ms_max:
            failed.append("t14_auto_max_ms_per_step")

        return len(failed) == 0, failed

    def run_scenario(
        self,
        scenario_name: str,
        profile: Optional[str] = None,
        cli_overrides: Optional[List[str]] = None,
        estimators: Optional[List[str]] = None,
        variants: Optional[List[str]] = None,
    ) -> List[RunResult]:
        """Execute a full scenario benchmark across estimators and variants."""
        active_estimators = estimators or ["E0", "E1", "E2"]
        active_variants = variants or ["matched", "mismatched"]

        scen_p = Path(scenario_name)
        if scen_p.exists():
            scen_path = scen_p
            scen_clean = scen_p.stem
        else:
            scen_clean = scenario_name
            scen_path = self.config_dir / "scenarios" / f"{scenario_name}.yaml"

        assumptions, raw_dict, config_hash = load_assumptions(
            profile=profile, scenario_file=scen_path, cli_overrides=cli_overrides
        )
        commit = get_git_commit_hash()
        status_counts = count_assumption_statuses(raw_dict)
        profile_label = profile or "automotive"

        # Generate single shared measurement stream for scenario
        measurements, truths, times, temp_warnings = self.generate_scenario_stream(
            assumptions, scen_clean
        )

        results: List[RunResult] = []

        for variant in active_variants:
            for est_name in active_estimators:
                metrics, diag = self.evaluate_estimator_on_stream(
                    estimator_name=est_name,
                    variant=variant,
                    assumptions=assumptions,
                    measurements=measurements,
                    truths=truths,
                    times=times,
                )
                passed, failed_list = self.check_pass_bars(
                    scen_clean, metrics, assumptions
                )
                res = RunResult(
                    scenario=scen_clean,
                    estimator=est_name,
                    variant=variant,
                    profile=profile_label,
                    config_hash=config_hash,
                    git_commit=commit,
                    placeholder_count=status_counts["placeholder"],
                    assumed_count=status_counts["assumed"],
                    temp_clamp_warnings=temp_warnings,
                    rmse=metrics["rmse"],
                    mae=metrics["mae"],
                    max_abs_error=metrics["max_abs_error"],
                    p95_error=metrics["p95_error"],
                    plateau_rmse_20_80=metrics["plateau_rmse_20_80"],
                    converge_time_2pct=metrics["converge_time_2pct"],
                    converge_time_5pct=metrics["converge_time_5pct"],
                    drift_24h=metrics["drift_24h"],
                    post_reversal_error_60s=metrics["post_reversal_error_60s"],
                    ms_per_step_mean=metrics["ms_per_step_mean"],
                    ms_per_step_median=metrics["ms_per_step_median"],
                    voltage_residual_rmse=diag["voltage_residual_rmse"],
                    mean_nis=diag["mean_nis"],
                    pass_all_bars=passed,
                    failed_bars=";".join(failed_list),
                )
                results.append(res)

        return results

    @staticmethod
    def save_results_to_csv(results: List[RunResult], output_path: Path) -> None:
        """Write benchmark run results to CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if len(results) == 0:
            return

        fieldnames = list(asdict(results[0]).keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow(asdict(r))
