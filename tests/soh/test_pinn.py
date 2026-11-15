"""Comprehensive unit tests for Physics-Informed Neural Network (PINN) degradation modeling."""

import copy
import math
import numpy as np
import pytest
import torch

from soh.common.contracts import CycleRecord, EstimationStatus
from soh.data.synthetic_aging import SyntheticAgingGenerator
from soh.models.pinn.estimator import PinnSohEstimator, PinnTrainingConfig
from soh.models.pinn.losses import LossWeights, PinnLossFunction
from soh.models.pinn.network import BatteryDegradationPINN, NetworkConfig
from soh.models.pinn.sei_kinetics import (
    LithiumPlatingModule,
    LithiumPlatingParameters,
    LossOfActiveMaterialModule,
    LamParameters,
    SeiKineticsParameters,
    SeiKineticsPhysics,
)


def test_sei_kinetics_physics_and_arrhenius():
    """Verify diffusion-limited parabolic rate and reference temperature normalization."""
    params = SeiKineticsParameters(
        k_sei=1.5e-16,
        activation_energy_j=38000.0,
        t_ref_k=298.15,
        delta_sei_0=5e-9,
    )
    physics = SeiKineticsPhysics(params)

    # 1. At 25°C (298.15 K), Arrhenius factor must be exactly 1.0
    arrh_25 = physics.arrhenius_factor(298.15)
    assert abs(arrh_25 - 1.0) < 1e-6

    # 2. At 45°C (318.15 K), Arrhenius factor must be > 1.0 (accelerated degradation)
    arrh_45 = physics.arrhenius_factor(318.15)
    assert arrh_45 > 1.0
    # Expected factor ~ exp(-38000/8.314 * (1/318.15 - 1/298.15)) ~ exp(0.96) ~ 2.62
    assert 2.0 < arrh_45 < 3.5

    # 3. Growth rate decreases with increasing film thickness (diffusion limitation ~ 1 / delta)
    rate_thin = physics.sei_growth_rate(delta_sei_m=10e-9, temp_k=298.15)
    rate_thick = physics.sei_growth_rate(delta_sei_m=40e-9, temp_k=298.15)
    assert rate_thin > rate_thick
    assert abs((rate_thin / rate_thick) - 4.0) < 1e-3

    # 4. SOH_C and SOH_R conversion
    soh_c, soh_r = physics.delta_to_soh(delta_sei_m=10e-9)
    assert 0.0 < soh_c < 1.0
    assert 0.0 < soh_r < 1.0


def test_modular_lithium_plating_and_lam():
    """Verify experimental plating and active material loss modules operate modularly."""
    plating = LithiumPlatingModule(LithiumPlatingParameters(t_threshold_c=15.0, c_rate_threshold=1.0))
    lam = LossOfActiveMaterialModule(LamParameters(k_lam=1e-5))

    # At 25°C and 1C, no plating occurs
    rate_normal = plating.evaluate_plating_rate(temp_c=25.0, charge_current_a=2.30)
    assert rate_normal == 0.0

    # At 5°C (< 15°C) and 2C (> 1C), plating occurs
    rate_cold = plating.evaluate_plating_rate(temp_c=5.0, charge_current_a=4.60)
    assert rate_cold > 0.0

    # LAM grows monotonically with cycle count
    lam_10 = lam.evaluate_lam_fade(cycle_index=10, delta_soc=0.8)
    lam_100 = lam.evaluate_lam_fade(cycle_index=100, delta_soc=0.8)
    assert 0.0 < lam_10 < lam_100 <= 0.40


def test_battery_degradation_pinn_autograd_derivatives():
    """Verify PyTorch autograd can differentiate SEI thickness and SOH_C."""
    net = BatteryDegradationPINN()
    net.eval()

    # Inputs: [t_s, ah_thru, temp_k, current_a, soc]
    x = torch.tensor([[3600.0, 5.0, 298.15, 1.0, 0.50]], requires_grad=True)
    delta_sei_m, soh_c, soh_r, lv_c, lv_r = net(x)

    assert delta_sei_m.shape == (1, 1)
    assert soh_c.shape == (1, 1)
    assert soh_r.shape == (1, 1)

    # Differentiate delta_sei with respect to time (t_s)
    grads = torch.autograd.grad(
        outputs=delta_sei_m,
        inputs=x,
        grad_outputs=torch.ones_like(delta_sei_m),
        create_graph=True,
    )[0]

    d_delta_dt = grads[0, 0].item()
    assert not math.isnan(d_delta_dt)
    assert not math.isinf(d_delta_dt)


def test_pinn_loss_function_residuals():
    """Verify physics residual, monotonicity penalty, and LLI coupling losses."""
    loss_fn = PinnLossFunction()
    x = torch.tensor(
        [
            [1000.0, 2.0, 298.15, 1.0, 0.50],
            [5000.0, 10.0, 318.15, 2.0, 0.60],
        ],
        requires_grad=True,
    )

    net = BatteryDegradationPINN()
    delta_m, sc, sr, lv_c, lv_r = net(x)

    y_c = torch.tensor([[0.98], [0.95]])
    y_r = torch.tensor([[0.99], [0.96]])

    total_loss, metrics = loss_fn(
        x_inputs=x,
        delta_sei_m=delta_m,
        soh_c_pred=sc,
        soh_r_pred=sr,
        log_var_c=lv_c,
        log_var_r=lv_r,
        y_c_true=y_c,
        y_r_true=y_r,
        enable_physics=True,
    )

    assert not math.isnan(total_loss.item())
    assert not math.isinf(total_loss.item())
    assert "loss_physics" in metrics
    assert "loss_mono" in metrics
    assert "loss_lli" in metrics
    assert metrics["loss_physics"] >= 0.0


def test_pinn_estimator_fit_and_uncertainty():
    """Verify PinnSohEstimator trains, predicts valid SOH_C/R, and provides calibrated intervals."""
    # Generate a lightweight 2-cell synthetic cohort
    synth_gen = SyntheticAgingGenerator(seed=42)
    b1 = synth_gen.generate_battery("CELL_A", num_cycles=10, temp_c=25.0)
    b2 = synth_gen.generate_battery("CELL_B", num_cycles=10, temp_c=35.0)

    from soh.data.base_loader import SohDataset
    ds = SohDataset()
    ds.add_battery(b1)
    ds.add_battery(b2)

    estimator = PinnSohEstimator(
        config=PinnTrainingConfig(epochs=30, batch_size=16, mc_samples=10, seed=123),
    )
    estimator.fit(ds)
    assert estimator.is_fitted

    # Predict on a test cycle
    test_cycle = b1.cycles[5]
    est = estimator.predict_cycle(test_cycle)

    assert est.status == EstimationStatus.VALID
    assert est.soh_c is not None and 0.5 < est.soh_c < 1.05
    assert est.soh_r is not None and 0.5 < est.soh_r < 1.05
    assert est.confidence_interval_95_c is not None
    lb_c, ub_c = est.confidence_interval_95_c
    assert lb_c < est.soh_c < ub_c


def test_pinn_estimator_ablation_modes():
    """Verify controlled ablation modes (no_physics, no_operating_conditions, empirical)."""
    synth_gen = SyntheticAgingGenerator(seed=10)
    b1 = synth_gen.generate_battery("CELL_T1", num_cycles=8, temp_c=25.0)
    b2 = synth_gen.generate_battery("CELL_T2", num_cycles=8, temp_c=25.0)

    from soh.data.base_loader import SohDataset
    ds = SohDataset()
    ds.add_battery(b1)
    ds.add_battery(b2)

    # 1. No-physics ablation (pure MLP)
    est_no_phys = PinnSohEstimator(
        config=PinnTrainingConfig(epochs=10, mode="no_physics", seed=42)
    )
    est_no_phys.fit(ds)
    res_no_phys = est_no_phys.predict_cycle(b1.cycles[2])
    assert res_no_phys.status == EstimationStatus.VALID

    # 2. No-operating-conditions ablation
    est_no_ops = PinnSohEstimator(
        config=PinnTrainingConfig(epochs=10, mode="no_operating_conditions", seed=42)
    )
    est_no_ops.fit(ds)
    res_no_ops = est_no_ops.predict_cycle(b1.cycles[2])
    assert res_no_ops.status == EstimationStatus.VALID

    # 3. Empirical power-law mode
    est_emp = PinnSohEstimator(config=PinnTrainingConfig(mode="empirical"))
    est_emp.fit(ds)
    res_emp = est_emp.predict_cycle(b1.cycles[2])
    assert res_emp.status == EstimationStatus.VALID


def test_pinn_shuffled_label_negative_control():
    """Verify negative control: shuffled targets degrade prediction quality."""
    synth_gen = SyntheticAgingGenerator(seed=99)
    b1 = synth_gen.generate_battery("CELL_SHUFFLE", num_cycles=40, temp_c=35.0)

    from soh.data.base_loader import SohDataset
    ds = SohDataset()
    ds.add_battery(b1)

    # Fit normal model
    est_normal = PinnSohEstimator(config=PinnTrainingConfig(epochs=60, seed=1))
    est_normal.fit(ds)

    # Fit shuffled target model
    ds_shuffled = SohDataset()
    b_shuf = copy.deepcopy(b1)
    c_vals = [c.soh_c_bol_true for c in b_shuf.cycles if c.soh_c_bol_true is not None]
    np.random.seed(42)
    np.random.shuffle(c_vals)

    idx = 0
    for c in b_shuf.cycles:
        if c.soh_c_bol_true is not None:
            c.soh_c_bol_true = c_vals[idx]
            idx += 1
    ds_shuffled.add_battery(b_shuf)

    est_shuf = PinnSohEstimator(config=PinnTrainingConfig(epochs=60, seed=1))
    est_shuf.fit(ds_shuffled)

    # Shuffled model should have worse fit error on true un-shuffled data
    errors_normal = []
    errors_shuf = []
    for c in b1.cycles:
        if c.soh_c_bol_true is not None:
            pred_n = est_normal.predict_cycle(c).soh_c
            pred_s = est_shuf.predict_cycle(c).soh_c
            errors_normal.append((pred_n - c.soh_c_bol_true) ** 2)
            errors_shuf.append((pred_s - c.soh_c_bol_true) ** 2)

    rmse_normal = math.sqrt(np.mean(errors_normal))
    rmse_shuf = math.sqrt(np.mean(errors_shuf))

    # Shuffled model must have higher or equal error than correctly trained model
    assert rmse_shuf >= rmse_normal


def test_pybamm_simulation_generation_and_pinn_eval():
    """Verify PyBaMM simulation cohort generation and evaluation with PINN."""
    from soh.data.pybamm_simulator import PybammDegradationSimulator, PybammSimulationConfig
    from soh.benchmarks.split_runner import GroupedBatteryEvaluator

    sim = PybammDegradationSimulator()
    # 2 small simulation cells with 3 cycles each for fast test execution
    b1 = sim.simulate_cell("PYBAMM_T1", PybammSimulationConfig(num_cycles=3, ambient_temp_c=25.0, c_rate=1.0))
    b2 = sim.simulate_cell("PYBAMM_T2", PybammSimulationConfig(num_cycles=3, ambient_temp_c=35.0, c_rate=1.0))

    from soh.data.base_loader import SohDataset
    ds = SohDataset()
    ds.add_battery(b1)
    ds.add_battery(b2)

    assert len(ds.cell_ids) == 2
    assert len(b1.cycles) == 3
    assert b1.cycles[0].soh_c_bol_true is not None

    # Evaluate via GroupedBatteryEvaluator LOBO
    evaluator = GroupedBatteryEvaluator()
    res = evaluator.run_lobo_cv(
        dataset=ds,
        estimator_factory=lambda: PinnSohEstimator(
            config=PinnTrainingConfig(epochs=15, batch_size=8, seed=42)
        ),
    )

    assert "PYBAMM_T1" in res.per_cell
    assert "PYBAMM_T2" in res.per_cell
    assert res.aggregate_metrics_c is not None
    assert res.aggregate_metrics_c.rmse >= 0.0

