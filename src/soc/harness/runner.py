import copy
import csv
from dataclasses import dataclass, asdict
import math
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import warnings
import numpy as np

from soc.assumptions.loader import (
    DEFAULT_DRIFT_MIN_RUN_S,
    DEFAULT_METRIC_WARMUP_S,
    DEFAULT_PERCENTILE_95,
    DEFAULT_PLATEAU_FRACTION_MIN,
    DEFAULT_PLATEAU_MAX,
    DEFAULT_PLATEAU_MIN,
    DEFAULT_TIE_BAND_PP,
    DEFAULT_WARMUP_COUNT,
    OFAT_SWEEP_CONFIGS,
    PERCENT_FACTOR,
    SECONDS_PER_DAY,
    T11_REST_DUTY_DISCHARGE_CURRENT_A,
    T11_REST_DUTY_DISCHARGE_S,
    T11_REST_DUTY_INITIAL_SOC,
    T11_REST_DUTY_OFFSET,
    T11_REST_DUTY_REST_S,
    TRANSIENT_SPIKE_MAX_ERR_THRESHOLD,
    TRANSIENT_SPIKE_RMSE_THRESHOLD,
    count_assumption_statuses,
    derive_scenario_noise_seed,
    get_default_config_dir,
    get_git_commit_hash,
    is_git_dirty,
    load_assumptions,
)
from soc.assumptions.schema import Assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.registry import get_estimator
from soc.eval.metrics import (
    converge_time_2pct,
    converge_time_5pct,
    detect_reversals,
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
    noise_seed: int
    seed_index: int
    duration_s: float
    n_samples_kept: int
    n_dropped: int
    drift_evaluated: bool
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
    dirty: bool = False
    reversal_count: int = 0
    error_rise: float = float("nan")
    anchor_count: int = 0
    samples_anchored: int = 0
    first_anchor_time_s: float = float("nan")
    err_pre_anchor: float = float("nan")
    err_post_anchor: float = float("nan")
    clean_rmse: float = float("nan")
    signed_rmse_rise: float = float("nan")
    rmse_rise: float = float("nan")
    clean_max_error: float = float("nan")
    max_error_rise: float = float("nan")
    max_abs_error_post_warmup: float = float("nan")
    soc_min: float = float("nan")
    soc_max: float = float("nan")
    fraction_on_plateau: float = float("nan")
    spike_detected: bool = False
    spike_time_s: float = float("nan")
    spike_true_soc: float = float("nan")
    spike_error: float = float("nan")
    mean_signed_error: float = float("nan")
    truth_soc_min: float = float("nan")
    truth_soc_max: float = float("nan")
    is_invalid_extreme: bool = False


class ScenarioRunner:
    """Runner generating shared measurement streams and executing estimator benchmarks."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or get_default_config_dir()

    def generate_scenario_stream(
        self,
        assumptions: Assumptions,
        scenario_name: str,
        seed_index: int = 0,
    ) -> Tuple[List[Measurement], List[PlantTruthState], List[float], int, int]:
        """Generate single reproducible measurement and truth stream for scenario and seed.

        Noise seed derived from (run_seed, scenario_hash, seed_index).
        Returns: (measurements, truths, cumulative_times, temp_warning_count, noise_seed).
        """
        run_seed = int(assumptions.run.random_seed.value)
        noise_seed = derive_scenario_noise_seed(run_seed, scenario_name, seed_index)
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
        return measurements, truths, times, temp_warnings, noise_seed

    def evaluate_estimator_on_stream(
        self,
        estimator_name: str,
        variant: str,
        assumptions: Assumptions,
        measurements: List[Measurement],
        truths: List[PlantTruthState],
        times: List[float],
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, Any]]:
        """Run single estimator over measurement stream with timing and error filtering."""
        is_matched = variant == "matched"
        if not is_matched:
            mism = assumptions.estimator_model.mismatch
            mism_fields = [
                "capacity_pct",
                "r0_pct",
                "r1_pct",
                "r2_pct",
                "ocv_offset_mv",
                "hysteresis_amplitude_pct",
                "hysteresis_gamma_pct",
            ]
            if all(float(getattr(mism, f).value) == float(0) for f in mism_fields):
                raise ValueError("Mismatched variant evaluated with all-zero mismatch configuration.")

        params = ParamSet.from_assumptions(assumptions, matched=is_matched)
        estimator = get_estimator(estimator_name, params)

        init_soc = float(assumptions.duty.initial_soc.value)
        init_offset = float(assumptions.filter.initial_soc_offset.value)
        estimator.reset(init_soc + init_offset)

        step_durations_ms: List[float] = []
        estimates: List[SocEstimate] = []
        held_estimates: List[float] = []
        curr_est = init_soc + init_offset

        anchor_cnt = 0
        samples_anchored = 0
        in_anchor = False
        first_anc_time = float("nan")
        err_pre = float("nan")
        err_post = float("nan")

        for k, meas in enumerate(measurements):
            t_start = time.perf_counter()
            out = estimator.step(meas)
            t_end = time.perf_counter()
            step_durations_ms.append((t_end - t_start) * 1000)
            estimates.append(out)

            prev_est = curr_est
            if not meas.dropout:
                curr_est = out.soc
            held_estimates.append(curr_est)

            if out.anchor_used:
                samples_anchored += 1
                if not in_anchor:
                    anchor_cnt += 1
                    in_anchor = True
                    if math.isnan(first_anc_time):
                        first_anc_time = times[k]
                        prev_truth = truths[k - 1].soc if k > 0 else truths[0].soc
                        err_pre = abs(prev_est - prev_truth)
                        err_post = abs(out.soc - truths[k].soc)
            else:
                in_anchor = False

        kept_indices = [idx for idx, m in enumerate(measurements) if not m.dropout]
        if len(kept_indices) == 0:
            kept_indices = list(range(len(measurements)))

        kept_times = np.array([times[k] for k in kept_indices], dtype=float)
        kept_truth = np.array([truths[k].soc for k in kept_indices], dtype=float)
        kept_est = np.array([held_estimates[k] for k in kept_indices], dtype=float)
        kept_currents = np.array([truths[k].i_true for k in kept_indices], dtype=float)

        duration_s = times[-1] if len(times) > 0 else float(0)
        n_samples_kept = len(kept_indices)
        n_dropped = len(measurements) - n_samples_kept

        # Check drift min run duration requirement
        drift_min_s = (
            float(assumptions.metrics.drift_min_run_s.value)
            if (assumptions.metrics is not None and hasattr(assumptions.metrics, "drift_min_run_s"))
            else DEFAULT_DRIFT_MIN_RUN_S
        )
        drift_evaluated = duration_s >= drift_min_s
        d24 = (
            drift_24h(kept_truth, kept_est, kept_times, seconds_per_day=SECONDS_PER_DAY)
            if drift_evaluated
            else float("nan")
        )

        # Metric calculations
        th_2pct = float(assumptions.filter.convergence_threshold_2pct.value)
        th_5pct = float(assumptions.filter.convergence_threshold_5pct.value)
        deadband = float(assumptions.filter.reversal_min_current_a.value)

        # Reversals detection
        reversal_indices = detect_reversals(kept_currents, deadband=deadband)
        reversal_cnt = len(reversal_indices)
        post_rev_err = (
            post_reversal_error_60s(
                kept_truth, kept_est, kept_times, kept_currents, deadband=deadband
            )
            if reversal_cnt > 0
            else float("nan")
        )

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
            "drift_24h": d24,
            "post_reversal_error_60s": post_rev_err,
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

        # SOC range and fraction on plateau ([0.20, 0.80])
        soc_min_val = float(np.min(kept_truth)) if len(kept_truth) > 0 else float("nan")
        soc_max_val = float(np.max(kept_truth)) if len(kept_truth) > 0 else float("nan")
        on_plat = (kept_truth >= DEFAULT_PLATEAU_MIN) & (kept_truth <= DEFAULT_PLATEAU_MAX)
        frac_plat = float(np.mean(on_plat)) if len(kept_truth) > 0 else float("nan")

        # Transient spike anomaly detection: max_abs_error > 5.0 pp and rmse < 1.0 pp
        abs_errs = np.abs(kept_est - kept_truth)
        spike_det = False
        spk_t = float("nan")
        spk_soc = float("nan")
        spk_err = float("nan")
        if (
            metrics["max_abs_error"] > TRANSIENT_SPIKE_MAX_ERR_THRESHOLD
            and metrics["rmse"] < TRANSIENT_SPIKE_RMSE_THRESHOLD
            and len(abs_errs) > 0
        ):
            max_idx = int(np.argmax(abs_errs))
            spike_det = True
            spk_t = float(kept_times[max_idx])
            spk_soc = float(kept_truth[max_idx])
            spk_err = float(abs_errs[max_idx])

        # Warmup handling for max_abs_error_post_warmup
        warmup_s = (
            float(assumptions.run.metric_warmup_s.value)
            if (assumptions.run is not None and hasattr(assumptions.run, "metric_warmup_s") and assumptions.run.metric_warmup_s is not None)
            else DEFAULT_METRIC_WARMUP_S
        )
        post_warmup_idx = [idx for idx, k in enumerate(kept_indices) if times[k] > warmup_s]
        if post_warmup_idx:
            pw_truth = kept_truth[post_warmup_idx]
            pw_est = kept_est[post_warmup_idx]
            max_err_post_warmup = max_abs_error(pw_truth, pw_est)
        else:
            max_err_post_warmup = metrics["max_abs_error"]

        mean_signed_err = float(np.mean(kept_est - kept_truth)) if len(kept_truth) > 0 else float("nan")
        allow_extremes = (
            bool(assumptions.duty.allow_extremes.value)
            if (assumptions.duty is not None and hasattr(assumptions.duty, "allow_extremes") and assumptions.duty.allow_extremes is not None)
            else False
        )
        is_invalid_extreme = False
        if not allow_extremes:
            if soc_min_val <= float(0) or soc_max_val >= float(1):
                is_invalid_extreme = True

        meta = {
            "duration_s": duration_s,
            "n_samples_kept": n_samples_kept,
            "n_dropped": n_dropped,
            "drift_evaluated": drift_evaluated,
            "reversal_count": reversal_cnt,
            "anchor_count": anchor_cnt,
            "samples_anchored": samples_anchored,
            "first_anchor_time_s": first_anc_time,
            "err_pre_anchor": err_pre,
            "err_post_anchor": err_post,
            "max_abs_error_post_warmup": max_err_post_warmup,
            "soc_min": soc_min_val,
            "soc_max": soc_max_val,
            "fraction_on_plateau": frac_plat,
            "spike_detected": spike_det,
            "spike_time_s": spk_t,
            "spike_true_soc": spk_soc,
            "spike_error": spk_err,
            "mean_signed_error": mean_signed_err,
            "truth_soc_min": soc_min_val,
            "truth_soc_max": soc_max_val,
            "is_invalid_extreme": is_invalid_extreme,
        }
        return metrics, diag, meta

    def check_pass_bars(
        self,
        scenario_name: str,
        metrics: Dict[str, float],
        assumptions: Assumptions,
        drift_evaluated: bool = True,
        reversal_count: int = 0,
        error_rise: float = float("nan"),
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

        # T3 BESS 24h error
        if scenario_name in ["t3_bess_24h"]:
            t3_rmse_max = float(bars.t3_bess_rmse_24h_max.value)
            if metrics["rmse"] > t3_rmse_max:
                failed.append("t3_bess_rmse_24h_max")

        # T4 Plateau stress
        if scenario_name in ["t4_plateau_stress"]:
            t4_max = float(bars.t4_plateau_p95_max.value)
            if metrics["p95_error"] > t4_max:
                failed.append("t4_plateau_p95_max")

        # T5 Convergence time (uses converge_time_2pct per plan)
        if scenario_name in ["t5_initial_soc_offset"]:
            t5_max_s = float(bars.t5_converge_time_s.value)
            if metrics["converge_time_2pct"] > t5_max_s:
                failed.append("t5_converge_time_s")

        # T6 Current bias drift (only if duration meets drift_min_run_s)
        if scenario_name in ["t6_current_bias"] and drift_evaluated:
            t6_drift_max = float(bars.t6_drift_bess_per_day_max.value)
            if abs(metrics["drift_24h"]) > t6_drift_max:
                failed.append("t6_drift_bess_per_day_max")

        # T7 Voltage quantisation noise error rise (compared against clean baseline)
        if scenario_name in ["t7_voltage_quant_noise"]:
            t7_rise_max = float(bars.t7_error_rise_max.value)
            if not math.isnan(error_rise) and error_rise > t7_rise_max:
                failed.append("t7_error_rise_max")

        # T9 Post rest step error
        if scenario_name in ["t9_rest_relaxation"]:
            t9_post_max = float(bars.t9_post_rest_step_error_max.value)
            if metrics["max_abs_error"] > t9_post_max:
                failed.append("t9_post_rest_step_error_max")

        # T10 Reversal spike (only if reversal_count > 0)
        if scenario_name in ["t3_t10_minor_loops"] and reversal_count > 0:
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
        num_seeds: Optional[int] = None,
    ) -> List[RunResult]:
        """Execute scenario benchmark across estimators, variants, and random seeds."""
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
        dirty = is_git_dirty()
        status_counts = count_assumption_statuses(raw_dict)
        profile_label = profile or "automotive"

        if num_seeds is not None:
            n_seeds = num_seeds
        elif assumptions.run.num_seeds is not None:
            n_seeds = int(assumptions.run.num_seeds.value)
        else:
            n_seeds = 1

        results: List[RunResult] = []

        if scen_clean == "t11_anchor_toggle":
            anchor_modes = [
                ("anchors off", False, False),
                ("full-charge only", True, False),
                ("rest anchor only", False, True),
            ]
        else:
            anchor_modes = [
                (
                    None,
                    bool(assumptions.soc_definition.anchor_enabled.value),
                    bool(assumptions.soc_definition.rest_anchor_enabled.value),
                )
            ]

        for s_idx in range(n_seeds):
            # Generate single shared measurement stream for (scenario, s_idx)
            measurements, truths, times, temp_warnings, noise_seed = self.generate_scenario_stream(
                assumptions, scen_clean, seed_index=s_idx
            )

            clean_meas, clean_truths, clean_times = None, None, None
            if scen_clean == "t7_voltage_quant_noise":
                clean_assump = copy.deepcopy(assumptions)
                clean_assump.sensors.current_noise_sigma_a.value = float(0)
                clean_assump.sensors.voltage_noise_sigma_v.value = float(0)
                clean_assump.sensors.voltage_quantisation_v.value = float(0)
                clean_assump.sensors.dropout_rate.value = float(0)
                clean_assump.sensors.temperature_noise_sigma_c.value = float(0)
                clean_meas, clean_truths, clean_times, _, _ = self.generate_scenario_stream(
                    clean_assump, scen_clean, seed_index=s_idx
                )

            for mode_label, anchor_en, rest_en in anchor_modes:
                mode_assumptions = copy.deepcopy(assumptions)
                mode_assumptions.soc_definition.anchor_enabled.value = anchor_en
                mode_assumptions.soc_definition.rest_anchor_enabled.value = rest_en
                display_scenario = f"t11_anchor_toggle [{mode_label}]" if mode_label else scen_clean

                if mode_label == "rest anchor only":
                    rest_assump = copy.deepcopy(assumptions)
                    rest_assump.plant.initial_soc.value = T11_REST_DUTY_INITIAL_SOC
                    rest_assump.duty.initial_soc.value = T11_REST_DUTY_INITIAL_SOC
                    rest_assump.filter.initial_soc_offset.value = T11_REST_DUTY_OFFSET
                    rest_assump.soc_definition.anchor_enabled.value = True
                    rest_assump.soc_definition.full_charge_anchor_enabled.value = False
                    rest_assump.soc_definition.rest_anchor_enabled.value = True

                    mode_assumptions = rest_assump
                    dt_val = float(rest_assump.sensors.sample_period_s.value)
                    n_dischg = int(T11_REST_DUTY_DISCHARGE_S / dt_val)
                    n_rest = int(T11_REST_DUTY_REST_S / dt_val)
                    rest_steps = []
                    amb_t = float(rest_assump.duty.ambient_temperature_c.value)
                    for _ in range(n_dischg):
                        rest_steps.append((T11_REST_DUTY_DISCHARGE_CURRENT_A, amb_t, dt_val))
                    for _ in range(n_rest):
                        rest_steps.append((float(0), amb_t, dt_val))

                    plant_rest = PlantSimulator(rest_assump, rng=np.random.default_rng(noise_seed))
                    plant_rest.reset(T11_REST_DUTY_INITIAL_SOC)

                    active_meas = []
                    active_truths = []
                    active_times = []
                    t_acc = float(0)
                    for i_a, tc, dt_s in rest_steps:
                        m, tr = plant_rest.step(i_a, tc, dt_s)
                        t_acc += dt_s
                        active_meas.append(m)
                        active_truths.append(tr)
                        active_times.append(t_acc)
                else:
                    active_meas = measurements
                    active_truths = truths
                    active_times = times

                for variant in active_variants:
                    for est_name in active_estimators:
                        metrics, diag, meta = self.evaluate_estimator_on_stream(
                            estimator_name=est_name,
                            variant=variant,
                            assumptions=mode_assumptions,
                            measurements=active_meas,
                            truths=active_truths,
                            times=active_times,
                        )

                        clean_r = float("nan")
                        noisy_r = metrics["rmse"]
                        signed_r_rise = float("nan")
                        r_rise = float("nan")
                        clean_m = float("nan")
                        noisy_m = metrics["max_abs_error"]
                        signed_m_rise = float("nan")
                        m_rise = float("nan")
                        if clean_meas is not None:
                            clean_metrics, _, _ = self.evaluate_estimator_on_stream(
                                estimator_name=est_name,
                                variant=variant,
                                assumptions=clean_assump,
                                measurements=clean_meas,
                                truths=clean_truths,
                                times=clean_times,
                            )
                            clean_r = clean_metrics["rmse"]
                            signed_r_rise = noisy_r - clean_r
                            r_rise = max(float(0), signed_r_rise)
                            clean_m = clean_metrics["max_abs_error"]
                            signed_m_rise = noisy_m - clean_m
                            m_rise = max(float(0), signed_m_rise)

                        passed, failed_list = self.check_pass_bars(
                            scen_clean,
                            metrics,
                            mode_assumptions,
                            drift_evaluated=meta["drift_evaluated"],
                            reversal_count=meta["reversal_count"],
                            error_rise=r_rise,
                        )
                        res = RunResult(
                            scenario=display_scenario,
                            estimator=est_name,
                            variant=variant,
                            profile=profile_label,
                            config_hash=config_hash,
                            git_commit=commit,
                            noise_seed=noise_seed,
                            seed_index=s_idx,
                            duration_s=meta["duration_s"],
                            n_samples_kept=meta["n_samples_kept"],
                            n_dropped=meta["n_dropped"],
                            drift_evaluated=meta["drift_evaluated"],
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
                            pass_all_bars=passed and not meta["is_invalid_extreme"],
                            failed_bars="INVALID: cell empty or full" if meta["is_invalid_extreme"] else ";".join(failed_list),
                            dirty=dirty,
                            reversal_count=meta["reversal_count"],
                            error_rise=r_rise,
                            anchor_count=meta["anchor_count"],
                            samples_anchored=meta["samples_anchored"],
                            first_anchor_time_s=meta["first_anchor_time_s"],
                            err_pre_anchor=meta["err_pre_anchor"],
                            err_post_anchor=meta["err_post_anchor"],
                            clean_rmse=clean_r,
                            signed_rmse_rise=signed_r_rise,
                            rmse_rise=r_rise,
                            clean_max_error=clean_m,
                            max_error_rise=m_rise,
                            max_abs_error_post_warmup=meta["max_abs_error_post_warmup"],
                            soc_min=meta["soc_min"],
                            soc_max=meta["soc_max"],
                            fraction_on_plateau=meta["fraction_on_plateau"],
                            spike_detected=meta["spike_detected"],
                            spike_time_s=meta["spike_time_s"],
                            spike_true_soc=meta["spike_true_soc"],
                            spike_error=meta["spike_error"],
                            mean_signed_error=meta["mean_signed_error"],
                            truth_soc_min=meta["truth_soc_min"],
                            truth_soc_max=meta["truth_soc_max"],
                            is_invalid_extreme=meta["is_invalid_extreme"],
                        )
                        results.append(res)

        return results

    def run_all_scenarios(
        self,
        profile: Optional[str] = None,
        cli_overrides: Optional[List[str]] = None,
        estimators: Optional[List[str]] = None,
        variants: Optional[List[str]] = None,
        num_seeds: Optional[int] = None,
    ) -> List[RunResult]:
        """Execute full test suite across all standard scenarios."""
        standard_scenarios = [
            "t1_static_ocv",
            "t3_t10_minor_loops",
            "t4_plateau_stress",
            "t5_initial_soc_offset",
            "t6_current_bias",
            "t6_plateau_only",
            "t7_voltage_quant_noise",
            "t9_rest_relaxation",
            "t11_anchor_toggle",
            "t12_hysteresis_mismatch",
        ]
        if profile == "bess":
            # BESS profile includes dedicated 24h stationary storage scenario
            standard_scenarios.insert(2, "t3_bess_24h")

        all_res: List[RunResult] = []
        for scen in standard_scenarios:
            scen_results = self.run_scenario(
                scenario_name=scen,
                profile=profile,
                cli_overrides=cli_overrides,
                estimators=estimators,
                variants=variants,
                num_seeds=num_seeds,
            )
            all_res.extend(scen_results)
        return all_res

    def run_ofat_sensitivity(
        self, profile: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Run One-Factor-At-A-Time (OFAT) parameter sensitivity sweep.

        Evaluates E1 and E2 across t3_t10_minor_loops, t4_plateau_stress, and t5_initial_soc_offset
        under matched noise realization for each isolated parameter perturbation.
        """
        scenarios = ["t3_t10_minor_loops", "t4_plateau_stress", "t5_initial_soc_offset"]
        all_ofat_results: List[Dict[str, Any]] = []

        mism_fields = [
            "capacity_pct",
            "r0_pct",
            "r1_pct",
            "r2_pct",
            "tau1_pct",
            "tau2_pct",
            "ocv_offset_mv",
            "hysteresis_amplitude_pct",
            "hysteresis_gamma_pct",
        ]

        for scen in scenarios:
            scen_path = self.config_dir / "scenarios" / f"{scen}.yaml"
            base_assumptions, _, _ = load_assumptions(
                profile=profile, scenario_file=scen_path
            )
            meas, truths, times, _, _ = self.generate_scenario_stream(
                base_assumptions, scen, seed_index=0
            )

            # Base matched reference
            matched_metrics: Dict[str, Dict[str, float]] = {}
            for est_name in ["E1", "E2"]:
                m_metrics, _, _ = self.evaluate_estimator_on_stream(
                    estimator_name=est_name,
                    variant="matched",
                    assumptions=base_assumptions,
                    measurements=meas,
                    truths=truths,
                    times=times,
                )
                matched_metrics[est_name] = m_metrics

            # Combined default mismatch run
            for est_name in ["E1", "E2"]:
                comb_metrics, _, _ = self.evaluate_estimator_on_stream(
                    estimator_name=est_name,
                    variant="mismatched",
                    assumptions=base_assumptions,
                    measurements=meas,
                    truths=truths,
                    times=times,
                )
                eff = abs(comb_metrics["rmse"] - matched_metrics[est_name]["rmse"])
                all_ofat_results.append({
                    "scenario": scen,
                    "estimator": est_name,
                    "parameter": "combined mismatch",
                    "sign": "+/-",
                    "size_str": "combined",
                    "rmse": comb_metrics["rmse"],
                    "max_abs_error": comb_metrics["max_abs_error"],
                    "plateau_rmse_20_80": comb_metrics["plateau_rmse_20_80"],
                    "effect_magnitude": eff,
                })

            # Isolated OFAT perturbations
            for field, param_name, sign_str, delta_val, delta_str in OFAT_SWEEP_CONFIGS:
                ofat_assump = copy.deepcopy(base_assumptions)
                for mf in mism_fields:
                    setattr(getattr(ofat_assump.estimator_model.mismatch, mf), "value", float(0))
                setattr(getattr(ofat_assump.estimator_model.mismatch, field), "value", float(delta_val))

                for est_name in ["E1", "E2"]:
                    pert_metrics, _, _ = self.evaluate_estimator_on_stream(
                        estimator_name=est_name,
                        variant="mismatched",
                        assumptions=ofat_assump,
                        measurements=meas,
                        truths=truths,
                        times=times,
                    )
                    eff = abs(pert_metrics["rmse"] - matched_metrics[est_name]["rmse"])
                    all_ofat_results.append({
                        "scenario": scen,
                        "estimator": est_name,
                        "parameter": param_name,
                        "sign": sign_str,
                        "size_str": delta_str,
                        "rmse": pert_metrics["rmse"],
                        "max_abs_error": pert_metrics["max_abs_error"],
                        "plateau_rmse_20_80": pert_metrics["plateau_rmse_20_80"],
                        "effect_magnitude": eff,
                    })

        return all_ofat_results

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
