"""Diagnostics, ablation tracking, and gradient auditing for battery PINN.

Implements:
1. Loss and gradient vector tracking during training
2. Relative gradient contribution and cosine similarity between data and physics gradients
3. Monotonicity violation rate and magnitude tracking
4. Multi-seed sensitivity sweeps over physics loss weights
5. Long-horizon early-life extrapolation benchmarks (10%, 25%, 50% training)
6. Multi-stage nonlinear aging evaluation (passivation, steady wear, knee-point rollover)
7. Kinetic model mismatch benchmarking
8. Temperature and operating profile transfer evaluation
9. Conformal uncertainty calibration and stratified coverage auditing
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from soh.common.contracts import (
    EstimationStatus,
    FeatureQualityRecord,
    SohEstimate,
)
from soh.data.base_loader import SohBatteryData, SohDataset
from soh.degradation.mechanisms import (
    EmpiricalDegradationModel,
    SeiKineticsModel,
)
from soh.models.pinn.estimator import (
    PinnSohEstimator,
    PinnTrainingConfig,
)
from soh.models.pinn.losses import (
    LossWeights,
    PinnLossFunction,
)
from soh.models.pinn.network import (
    BatteryDegradationPINN,
    NetworkConfig,
)
from soh.models.pinn.sei_kinetics import (
    SeiGrowthMechanism,
    SeiKineticsParameters,
    SeiKineticsPhysics,
)


@dataclass
class GradientEpochRecord:
    """Detailed loss and gradient diagnostics at an individual training epoch."""

    epoch: int
    loss_data_c: float
    loss_data_r: float
    loss_phys: float
    loss_mono: float
    loss_lli: float
    loss_total: float
    grad_norm_data: float
    grad_norm_phys: float
    grad_norm_mono: float
    grad_norm_lli: float
    grad_norm_total: float
    relative_phys_grad_pct: float
    cosine_sim_data_phys: float
    monotonicity_violations: int
    monotonicity_violation_rate: float
    monotonicity_max_violation: float


@dataclass
class PinnDiagnosticHistory:
    """Historical trace of loss magnitudes and gradient metrics during training."""

    records: List[GradientEpochRecord] = field(default_factory=list)
    initial_grad_ratio: float = 0.0
    final_grad_ratio: float = 0.0
    mean_cosine_sim: float = 0.0
    mean_relative_phys_grad_pct: float = 0.0
    total_monotonicity_violations: int = 0


@dataclass
class PhysicsWeightSweepResult:
    """Multi-seed evaluation of model performance under varying physics loss weight lambda_phys."""

    lambda_phys: float
    seeds: List[int]
    rmse_mean: float
    rmse_std: float
    mae_mean: float
    mae_std: float
    max_err_mean: float
    max_err_std: float
    picp_mean: float
    picp_std: float
    winkler_mean: float
    winkler_std: float
    relative_phys_grad_pct: float
    monotonicity_violation_rate: float


@dataclass
class ExtrapolationResult:
    """Evaluation metrics for early-life training on unseen future cycles."""

    train_fraction: float  # e.g. 0.10, 0.25, 0.50
    model_type: str        # "pure_mlp", "full_pinn"
    seeds: List[int]
    rmse_mean: float
    rmse_std: float
    mae_mean: float
    mae_std: float
    max_err_mean: float
    max_err_std: float
    picp_mean: float
    picp_std: float


@dataclass
class KineticMismatchResult:
    """Evaluation metrics for matched vs mismatched kinetic models."""

    data_mechanism: str
    model_type: str
    seeds: List[int]
    rmse_mean: float
    rmse_std: float
    mae_mean: float
    mae_std: float
    picp_mean: float
    picp_std: float
    winkler_mean: float
    winkler_std: float


def extract_dataset_tensors(
    dataset: SohDataset,
    spec_nominal_capacity_ah: float = 2.30,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Convert SohDataset cycles into PyTorch training tensors [x, y_c, y_r]."""
    x_list: List[np.ndarray] = []
    yc_list: List[float] = []
    yr_list: List[float] = []

    for cid, bdata in dataset.batteries.items():
        nom_cap = bdata.spec.nominal_capacity_ah
        for cycle in bdata.cycles:
            if cycle.soh_c_bol_true is None:
                continue

            duration = float(cycle.time_s[-1] - cycle.time_s[0]) if len(cycle.time_s) > 1 else 3600.0
            t_s = max(60.0, float(cycle.cycle_index + 1) * duration)

            if hasattr(cycle, "ah_throughput") and cycle.ah_throughput is not None and cycle.ah_throughput > 0.0:
                ah_thru = float(cycle.ah_throughput)
            else:
                ah_thru = float(cycle.cycle_index) * nom_cap * 2.0

            temp_c = float(np.mean(cycle.temp_c)) if len(cycle.temp_c) > 0 else 25.0
            temp_k = float(temp_c + 273.15)
            current_a = float(np.mean(np.abs(cycle.current_a))) if len(cycle.current_a) > 0 else 1.0
            soc_avg = float(cycle.metadata.get("soc_avg", 0.50)) if hasattr(cycle, "metadata") and cycle.metadata else 0.50

            feat = np.array([t_s, ah_thru, temp_k, current_a, soc_avg], dtype=np.float32)
            x_list.append(feat)
            yc_list.append(float(cycle.soh_c_bol_true))
            true_r = float(cycle.soh_r_bol_true) if cycle.soh_r_bol_true is not None else 1.0
            yr_list.append(true_r)

    x_arr = np.vstack(x_list)
    yc_arr = np.array(yc_list, dtype=np.float32).reshape(-1, 1)
    yr_arr = np.array(yr_list, dtype=np.float32).reshape(-1, 1)

    x_tensor = torch.tensor(x_arr, dtype=torch.float32, requires_grad=True)
    yc_tensor = torch.tensor(yc_arr, dtype=torch.float32)
    yr_tensor = torch.tensor(yr_arr, dtype=torch.float32)

    return x_tensor, yc_tensor, yr_tensor


def record_loss_and_gradient_diagnostics(
    dataset: SohDataset,
    epochs: int = 150,
    learning_rate: float = 3e-3,
    loss_weights: Optional[LossWeights] = None,
    kinetics_params: Optional[SeiKineticsParameters] = None,
    seed: int = 42,
    record_interval: int = 25,
) -> PinnDiagnosticHistory:
    """Train PINN while computing gradient norms, cosine similarities, and violation rates."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    weights = loss_weights or LossWeights(lambda_physics=0.01, lambda_monotonicity=0.01, lambda_lli=0.05)
    params = kinetics_params or SeiKineticsParameters()

    x_tensor, yc_tensor, yr_tensor = extract_dataset_tensors(dataset)
    n_samples = len(x_tensor)

    model = BatteryDegradationPINN()
    loss_fn = PinnLossFunction(kinetics_params=params, weights=weights)
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)

    history = PinnDiagnosticHistory()
    cos_sims: List[float] = []
    rel_phys_grads: List[float] = []
    total_violations = 0

    trunk_params = list(model.trunk.parameters())

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()

        bx = x_tensor.clone().detach().requires_grad_(True)
        delta_m, sc, sr, lv_c, lv_r = model(bx)

        # 1. Data losses
        loss_data_c = loss_fn.heteroscedastic_nll(yc_tensor, sc, lv_c)
        loss_data_r = loss_fn.heteroscedastic_nll(yr_tensor, sr, lv_r)
        loss_data = weights.lambda_data_c * loss_data_c + weights.lambda_data_r * loss_data_r

        # 2. Physical residual loss
        loss_phys_raw = loss_fn.compute_physics_residual(bx, delta_m)
        loss_phys = weights.lambda_physics * loss_phys_raw

        # 3. Monotonicity loss
        loss_mono_raw = loss_fn.compute_monotonicity_loss(bx, sc)
        loss_mono = weights.lambda_monotonicity * loss_mono_raw

        # 4. LLI coupling loss
        loss_lli_raw = loss_fn.compute_lli_loss(delta_m, sc)
        loss_lli = weights.lambda_lli * loss_lli_raw

        # Total combined loss
        loss_total = loss_data + loss_phys + loss_mono + loss_lli

        # Monotonicity violation check on current outputs
        grads_mono = torch.autograd.grad(
            outputs=sc,
            inputs=bx,
            grad_outputs=torch.ones_like(sc),
            create_graph=False,
            retain_graph=True,
            only_inputs=True,
        )[0]
        d_sohc_dah = grads_mono[:, 1:2]
        pos_violations = (d_sohc_dah > 0.0).sum().item()
        violation_rate = float(pos_violations) / float(n_samples)
        max_violation = float(torch.clamp(d_sohc_dah, min=0.0).max().item())
        total_violations += int(pos_violations)

        # Evaluate diagnostic gradients at sampled intervals
        should_record = (epoch == 0) or ((epoch + 1) % record_interval == 0) or (epoch == epochs - 1)

        if should_record:
            # Gradients with respect to trunk parameters
            g_data_tensors = torch.autograd.grad(loss_data, trunk_params, retain_graph=True, allow_unused=True)
            g_phys_tensors = torch.autograd.grad(loss_phys, trunk_params, retain_graph=True, allow_unused=True)
            g_mono_tensors = torch.autograd.grad(loss_mono, trunk_params, retain_graph=True, allow_unused=True)
            g_lli_tensors = torch.autograd.grad(loss_lli, trunk_params, retain_graph=True, allow_unused=True)

            g_data = torch.cat([g.contiguous().view(-1) for g in g_data_tensors if g is not None])
            g_phys = torch.cat([g.contiguous().view(-1) for g in g_phys_tensors if g is not None])
            g_mono = torch.cat([g.contiguous().view(-1) for g in g_mono_tensors if g is not None])
            g_lli = torch.cat([g.contiguous().view(-1) for g in g_lli_tensors if g is not None])

            norm_data = float(torch.norm(g_data).item())
            norm_phys = float(torch.norm(g_phys).item())
            norm_mono = float(torch.norm(g_mono).item())
            norm_lli = float(torch.norm(g_lli).item())

            sum_norms = norm_data + norm_phys + norm_mono + norm_lli
            rel_phys_pct = (norm_phys / max(1e-9, sum_norms)) * 100.0
            rel_phys_grads.append(rel_phys_pct)

            # Cosine similarity between data and physics gradients
            dot_dp = float(torch.dot(g_data, g_phys).item())
            cos_dp = dot_dp / max(1e-9, norm_data * norm_phys)
            cos_sims.append(cos_dp)

            rec = GradientEpochRecord(
                epoch=epoch + 1,
                loss_data_c=float(loss_data_c.item()),
                loss_data_r=float(loss_data_r.item()),
                loss_phys=float(loss_phys_raw.item()),
                loss_mono=float(loss_mono_raw.item()),
                loss_lli=float(loss_lli_raw.item()),
                loss_total=float(loss_total.item()),
                grad_norm_data=norm_data,
                grad_norm_phys=norm_phys,
                grad_norm_mono=norm_mono,
                grad_norm_lli=norm_lli,
                grad_norm_total=sum_norms,
                relative_phys_grad_pct=rel_phys_pct,
                cosine_sim_data_phys=cos_dp,
                monotonicity_violations=pos_violations,
                monotonicity_violation_rate=violation_rate,
                monotonicity_max_violation=max_violation,
            )
            history.records.append(rec)

        loss_total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
        optimizer.step()

    if history.records:
        history.initial_grad_ratio = history.records[0].relative_phys_grad_pct
        history.final_grad_ratio = history.records[-1].relative_phys_grad_pct
    history.mean_cosine_sim = float(np.mean(cos_sims)) if cos_sims else 0.0
    history.mean_relative_phys_grad_pct = float(np.mean(rel_phys_grads)) if rel_phys_grads else 0.0
    history.total_monotonicity_violations = total_violations

    return history


def evaluate_lobo_pinn(
    dataset: SohDataset,
    mode: str = "pinn",
    loss_weights: Optional[LossWeights] = None,
    kinetics_params: Optional[SeiKineticsParameters] = None,
    seed: int = 42,
    epochs: int = 100,
) -> Tuple[float, float, float, float, float, float]:
    """Evaluate Leave-One-Battery-Out cross-validation for a specific PINN configuration.
    
    Returns:
        (mae_pct, rmse_pct, max_err_pct, picp_pct, mpiw, winkler)
    """
    cids = sorted(list(dataset.batteries.keys()))
    if len(cids) < 2:
        raise ValueError("Need at least 2 batteries for LOBO")

    errors: List[float] = []
    y_true_all: List[float] = []
    y_pred_all: List[float] = []
    ci_all: List[Tuple[float, float]] = []

    for test_cid in cids:
        train_ds = SohDataset()
        for cid, bdata in dataset.batteries.items():
            if cid != test_cid:
                train_ds.add_battery(bdata)

        cfg = PinnTrainingConfig(epochs=epochs, seed=seed, mode=mode)
        est = PinnSohEstimator(
            config=cfg,
            loss_weights=loss_weights,
            kinetics_params=kinetics_params,
        )
        est.fit(train_ds)

        test_battery = dataset.batteries[test_cid]
        for cycle in test_battery.cycles:
            if cycle.soh_c_bol_true is None:
                continue
            pred = est.predict_cycle(cycle)
            if pred.status != EstimationStatus.VALID or pred.soh_c is None:
                continue

            yt = float(cycle.soh_c_bol_true)
            yp = float(pred.soh_c)
            errors.append(abs(yt - yp))
            y_true_all.append(yt)
            y_pred_all.append(yp)
            ci = pred.confidence_interval_95_c or (yp - 0.02, yp + 0.02)
            ci_all.append(ci)

    err_arr = np.array(errors, dtype=float)
    mae_pct = float(np.mean(err_arr)) * 100.0
    rmse_pct = float(np.sqrt(np.mean(err_arr ** 2))) * 100.0
    max_err_pct = float(np.max(err_arr)) * 100.0

    yt_arr = np.array(y_true_all, dtype=float)
    lb_arr = np.array([c[0] for c in ci_all], dtype=float)
    ub_arr = np.array([c[1] for c in ci_all], dtype=float)

    picp = float(np.mean((yt_arr >= lb_arr) & (yt_arr <= ub_arr))) * 100.0
    mpiw = float(np.mean(ub_arr - lb_arr))
    alpha = 0.05
    width = ub_arr - lb_arr
    below = np.maximum(0.0, lb_arr - yt_arr)
    above = np.maximum(0.0, yt_arr - ub_arr)
    winkler = float(np.mean(width + (2.0 / alpha) * below + (2.0 / alpha) * above))

    return mae_pct, rmse_pct, max_err_pct, picp, mpiw, winkler


def sweep_physics_weights_multiseed(
    dataset: SohDataset,
    lambda_phys_list: Sequence[float] = (0.0, 1e-4, 1e-3, 1e-2, 1e-1, 1.0, 5.0),
    seeds: Sequence[int] = (42, 123, 456, 789, 1011),
    epochs: int = 80,
) -> List[PhysicsWeightSweepResult]:
    """Perform multi-seed parameter sweep across physics loss weights."""
    results: List[PhysicsWeightSweepResult] = []

    for l_phys in lambda_phys_list:
        rmses, maes, max_errs, picps, winklers = [], [], [], [], []
        rel_grads = []
        violation_rates = []

        for s in seeds:
            mode = "pure_mlp" if l_phys == 0.0 else "pinn"
            weights = LossWeights(
                lambda_physics=l_phys,
                lambda_monotonicity=0.01 if l_phys > 0.0 else 0.0,
                lambda_lli=0.05 if l_phys > 0.0 else 0.0,
            )

            # Get LOBO metrics
            mae, rmse, max_err, picp, mpiw, winkler = evaluate_lobo_pinn(
                dataset=dataset,
                mode=mode,
                loss_weights=weights,
                seed=s,
                epochs=epochs,
            )
            rmses.append(rmse)
            maes.append(mae)
            max_errs.append(max_err)
            picps.append(picp)
            winklers.append(winkler)

            # Measure gradient ratio and violation rate on full cohort
            diag = record_loss_and_gradient_diagnostics(
                dataset=dataset,
                epochs=epochs,
                loss_weights=weights,
                seed=s,
                record_interval=epochs,
            )
            rel_grads.append(diag.mean_relative_phys_grad_pct)
            if diag.records:
                violation_rates.append(diag.records[-1].monotonicity_violation_rate)
            else:
                violation_rates.append(0.0)

        res = PhysicsWeightSweepResult(
            lambda_phys=float(l_phys),
            seeds=list(seeds),
            rmse_mean=float(np.mean(rmses)),
            rmse_std=float(np.std(rmses)),
            mae_mean=float(np.mean(maes)),
            mae_std=float(np.std(maes)),
            max_err_mean=float(np.mean(max_errs)),
            max_err_std=float(np.std(max_errs)),
            picp_mean=float(np.mean(picps)),
            picp_std=float(np.std(picps)),
            winkler_mean=float(np.mean(winklers)),
            winkler_std=float(np.std(winklers)),
            relative_phys_grad_pct=float(np.mean(rel_grads)),
            monotonicity_violation_rate=float(np.mean(violation_rates)),
        )
        results.append(res)

    return results


def run_long_horizon_extrapolation(
    battery_data: SohBatteryData,
    train_fractions: Sequence[float] = (0.10, 0.25, 0.50),
    seeds: Sequence[int] = (42, 123, 456, 789, 1011),
    epochs: int = 100,
) -> List[ExtrapolationResult]:
    """Train on early life and evaluate strictly on unseen future cycles."""
    total_cycles = len(battery_data.cycles)
    results: List[ExtrapolationResult] = []

    for frac in train_fractions:
        n_train = max(2, int(total_cycles * frac))
        train_cycles = battery_data.cycles[:n_train]
        test_cycles = battery_data.cycles[n_train:]

        train_battery = SohBatteryData(
            cell_id=f"{battery_data.cell_id}_train",
            spec=battery_data.spec,
            bol_capacity_ah=battery_data.bol_capacity_ah,
            bol_resistance_ohm=battery_data.bol_resistance_ohm,
            cycles=train_cycles,
        )
        train_ds = SohDataset()
        train_ds.add_battery(train_battery)

        for model_type in ("pure_mlp", "full_pinn"):
            mode = "pure_mlp" if model_type == "pure_mlp" else "pinn"
            rmses, maes, max_errs, picps = [], [], [], []

            for s in seeds:
                cfg = PinnTrainingConfig(epochs=epochs, seed=s, mode=mode)
                weights = LossWeights(
                    lambda_physics=0.01 if mode == "pinn" else 0.0,
                    lambda_monotonicity=0.01 if mode == "pinn" else 0.0,
                    lambda_lli=0.05 if mode == "pinn" else 0.0,
                )
                est = PinnSohEstimator(config=cfg, loss_weights=weights)
                est.fit(train_ds)

                step_errors = []
                covered = []
                for cyc in test_cycles:
                    if cyc.soh_c_bol_true is None:
                        continue
                    pred = est.predict_cycle(cyc)
                    if pred.status != EstimationStatus.VALID or pred.soh_c is None:
                        continue
                    yt = float(cyc.soh_c_bol_true)
                    yp = float(pred.soh_c)
                    err = abs(yt - yp)
                    step_errors.append(err)
                    ci = pred.confidence_interval_95_c or (yp - 0.02, yp + 0.02)
                    covered.append(1.0 if ci[0] <= yt <= ci[1] else 0.0)

                if step_errors:
                    err_arr = np.array(step_errors, dtype=float)
                    rmses.append(float(np.sqrt(np.mean(err_arr ** 2))) * 100.0)
                    maes.append(float(np.mean(err_arr)) * 100.0)
                    max_errs.append(float(np.max(err_arr)) * 100.0)
                    picps.append(float(np.mean(covered)) * 100.0)

            results.append(
                ExtrapolationResult(
                    train_fraction=frac,
                    model_type=model_type,
                    seeds=list(seeds),
                    rmse_mean=float(np.mean(rmses)),
                    rmse_std=float(np.std(rmses)),
                    mae_mean=float(np.mean(maes)),
                    mae_std=float(np.std(maes)),
                    max_err_mean=float(np.mean(max_errs)),
                    max_err_std=float(np.std(max_errs)),
                    picp_mean=float(np.mean(picps)),
                    picp_std=float(np.std(picps)),
                )
            )

    return results


def run_nonlinear_stage_benchmark(
    dataset: SohDataset,
    seeds: Sequence[int] = (42, 123, 456, 789, 1011),
    epochs: int = 100,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Evaluate 6 models across 3 distinct degradation stages on non-power-law data:
    
    Stage 1: Early Passivation (cycles 0-5)
    Stage 2: Steady-State Cycling (cycles 5-30)
    Stage 3: Knee-Point Rollover (cycles 30-50)
    """
    models_to_test = [
        "constant_mean",
        "empirical_power_law",
        "mechanistic_sei",
        "pure_mlp",
        "full_pinn",
        "pinn_no_physics",
    ]

    stages = {
        "early_passivation_0_to_5": (0, 5),
        "steady_cycling_5_to_30": (5, 30),
        "knee_rollover_30_to_50": (30, 50),
        "full_lifecycle_0_to_50": (0, 50),
    }

    # Aggregate predictions across seeds
    stage_errors: Dict[str, Dict[str, List[float]]] = {
        s: {m: [] for m in models_to_test} for s in stages
    }

    # Pre-calculate constant mean from all cycles
    all_y_train = []
    for b in dataset.batteries.values():
        for c in b.cycles:
            if c.soh_c_bol_true is not None:
                all_y_train.append(float(c.soh_c_bol_true))
    const_mean = float(np.mean(all_y_train))

    # Classical baselines
    emp_model = EmpiricalDegradationModel()
    phys_engine = SeiKineticsPhysics()

    for m in models_to_test:
        if m in ("constant_mean", "empirical_power_law", "mechanistic_sei"):
            for b in dataset.batteries.values():
                for c in b.cycles:
                    if c.soh_c_bol_true is None:
                        continue
                    yt = float(c.soh_c_bol_true)
                    k = c.cycle_index
                    ah = float(c.ah_throughput or k * 4.6)
                    tc = float(np.mean(c.temp_c)) if len(c.temp_c) > 0 else 25.0
                    tk = float(tc + 273.15)
                    ts = max(60.0, float(k + 1) * 3600.0)

                    if m == "constant_mean":
                        yp = const_mean
                    elif m == "empirical_power_law":
                        yp = float(emp_model.predict_capacity_retention(ah, avg_temp_c=tc))
                    else:
                        arrh = phys_engine.arrhenius_factor(tk)
                        op = phys_engine.operating_condition_factor(current_a=1.0, soc=0.5)
                        delta_t = math.sqrt(phys_engine.params.delta_sei_0 ** 2 + phys_engine.params.k_sei_diffusion * arrh * op * ts)
                        sc_phys, _ = phys_engine.delta_to_soh(delta_t, cycle_count=k, temp_k=tk)
                        yp = float(sc_phys)

                    err = abs(yt - yp)
                    for s_name, (c_start, c_end) in stages.items():
                        if c_start <= k < c_end:
                            stage_errors[s_name][m].append(err)
        else:
            # Neural models across seeds
            mode = "pure_mlp" if m == "pure_mlp" else ("no_physics" if m == "pinn_no_physics" else "pinn")
            for s in seeds:
                cfg = PinnTrainingConfig(epochs=epochs, seed=s, mode=mode)
                est = PinnSohEstimator(config=cfg)
                est.fit(dataset)

                for b in dataset.batteries.values():
                    for c in b.cycles:
                        if c.soh_c_bol_true is None:
                            continue
                        yt = float(c.soh_c_bol_true)
                        k = c.cycle_index
                        pred = est.predict_cycle(c)
                        if pred.status != EstimationStatus.VALID or pred.soh_c is None:
                            continue
                        yp = float(pred.soh_c)
                        err = abs(yt - yp)
                        for s_name, (c_start, c_end) in stages.items():
                            if c_start <= k < c_end:
                                stage_errors[s_name][m].append(err)

    # Compute summary metrics
    summary: Dict[str, Dict[str, Dict[str, float]]] = {}
    for s_name in stages:
        summary[s_name] = {}
        for m in models_to_test:
            arr = np.array(stage_errors[s_name][m], dtype=float)
            summary[s_name][m] = {
                "rmse_pct": float(np.sqrt(np.mean(arr ** 2))) * 100.0,
                "mae_pct": float(np.mean(arr)) * 100.0,
                "max_err_pct": float(np.max(arr)) * 100.0,
            }

    return summary


def run_kinetic_mismatch_benchmark(
    dataset_diff: SohDataset,
    dataset_rxn: SohDataset,
    seeds: Sequence[int] = (42, 123, 456, 789, 1011),
    epochs: int = 80,
) -> List[KineticMismatchResult]:
    """Produce complete benchmark for matched vs mismatched kinetic models."""
    results: List[KineticMismatchResult] = []

    configs = [
        ("diffusion", "matched_diffusion", "pinn", SeiGrowthMechanism.SOLVENT_DIFFUSION_LIMITED, dataset_diff),
        ("diffusion", "mismatched_reaction", "pinn_reaction", SeiGrowthMechanism.REACTION_LIMITED, dataset_diff),
        ("diffusion", "pure_mlp", "pure_mlp", None, dataset_diff),
        ("reaction", "matched_reaction", "pinn_reaction", SeiGrowthMechanism.REACTION_LIMITED, dataset_rxn),
        ("reaction", "mismatched_diffusion", "pinn", SeiGrowthMechanism.SOLVENT_DIFFUSION_LIMITED, dataset_rxn),
        ("reaction", "pure_mlp", "pure_mlp", None, dataset_rxn),
    ]

    for data_mech, model_name, mode, phys_mech, ds in configs:
        rmses, maes, picps, winklers = [], [], [], []
        for s in seeds:
            params = SeiKineticsParameters(mechanism=phys_mech) if phys_mech else None
            weights = LossWeights(
                lambda_physics=0.01 if mode != "pure_mlp" else 0.0,
                lambda_monotonicity=0.01 if mode != "pure_mlp" else 0.0,
                lambda_lli=0.05 if mode != "pure_mlp" else 0.0,
            )
            mae, rmse, max_err, picp, mpiw, winkler = evaluate_lobo_pinn(
                dataset=ds,
                mode=mode,
                loss_weights=weights,
                kinetics_params=params,
                seed=s,
                epochs=epochs,
            )
            rmses.append(rmse)
            maes.append(mae)
            picps.append(picp)
            winklers.append(winkler)

        results.append(
            KineticMismatchResult(
                data_mechanism=data_mech,
                model_type=model_name,
                seeds=list(seeds),
                rmse_mean=float(np.mean(rmses)),
                rmse_std=float(np.std(rmses)),
                mae_mean=float(np.mean(maes)),
                mae_std=float(np.std(maes)),
                picp_mean=float(np.mean(picps)),
                picp_std=float(np.std(picps)),
                winkler_mean=float(np.mean(winklers)),
                winkler_std=float(np.std(winklers)),
            )
        )

    return results


def run_temperature_transfer_benchmark(
    dataset: SohDataset,
    seeds: Sequence[int] = (42, 123, 456, 789, 1011),
    epochs: int = 100,
) -> Dict[str, Dict[str, float]]:
    """Leave-one-temperature-out cross-validation:
    
    1. Train on 25°C & 45°C -> Evaluate on unseen Cold 15°C
    2. Train on 15°C & 25°C -> Evaluate on unseen Hot 45°C
    """
    tests = {
        "unseen_cold_15c": 15.0,
        "unseen_hot_45c": 45.0,
    }

    results: Dict[str, Dict[str, float]] = {}

    for test_name, held_out_temp in tests.items():
        train_ds = SohDataset()
        test_ds = SohDataset()

        for cid, bdata in dataset.batteries.items():
            # Check cell temperature from metadata or average temp
            avg_temp = float(np.mean(bdata.cycles[0].temp_c)) if bdata.cycles else 25.0
            if abs(avg_temp - held_out_temp) < 2.0:
                test_ds.add_battery(bdata)
            else:
                train_ds.add_battery(bdata)

        if not test_ds.batteries or not train_ds.batteries:
            continue

        for m_type in ("pure_mlp", "full_pinn"):
            mode = "pure_mlp" if m_type == "pure_mlp" else "pinn"
            rmses, maes, picps = [], [], []

            for s in seeds:
                cfg = PinnTrainingConfig(epochs=epochs, seed=s, mode=mode)
                weights = LossWeights(
                    lambda_physics=0.01 if mode == "pinn" else 0.0,
                    lambda_monotonicity=0.01 if mode == "pinn" else 0.0,
                    lambda_lli=0.05 if mode == "pinn" else 0.0,
                )
                est = PinnSohEstimator(config=cfg, loss_weights=weights)
                est.fit(train_ds)

                step_errors = []
                covered = []
                for b in test_ds.batteries.values():
                    for c in b.cycles:
                        if c.soh_c_bol_true is None:
                            continue
                        pred = est.predict_cycle(c)
                        if pred.status != EstimationStatus.VALID or pred.soh_c is None:
                            continue
                        yt = float(c.soh_c_bol_true)
                        yp = float(pred.soh_c)
                        step_errors.append(abs(yt - yp))
                        ci = pred.confidence_interval_95_c or (yp - 0.02, yp + 0.02)
                        covered.append(1.0 if ci[0] <= yt <= ci[1] else 0.0)

                if step_errors:
                    err_arr = np.array(step_errors, dtype=float)
                    rmses.append(float(np.sqrt(np.mean(err_arr ** 2))) * 100.0)
                    maes.append(float(np.mean(err_arr)) * 100.0)
                    picps.append(float(np.mean(covered)) * 100.0)

            key_prefix = f"{test_name}_{m_type}"
            results[key_prefix] = {
                "rmse_mean": float(np.mean(rmses)),
                "rmse_std": float(np.std(rmses)),
                "mae_mean": float(np.mean(maes)),
                "mae_std": float(np.std(maes)),
                "picp_mean": float(np.mean(picps)),
                "picp_std": float(np.std(picps)),
            }

    return results
