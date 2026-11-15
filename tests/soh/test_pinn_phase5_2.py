"""Unit tests for Phase 5.2 PINN diagnostics, extrapolation, and validation."""

import math
import numpy as np
import pytest
import torch

from soh.data.synthetic_aging import NonlinearAgingGenerator, SyntheticAgingGenerator
from soh.models.pinn.diagnostics import (
    record_loss_and_gradient_diagnostics,
    run_kinetic_mismatch_benchmark,
    run_long_horizon_extrapolation,
    run_nonlinear_stage_benchmark,
    run_temperature_transfer_benchmark,
    sweep_physics_weights_multiseed,
)
from soh.models.pinn.estimator import PinnSohEstimator, PinnTrainingConfig
from soh.models.pinn.losses import LossWeights


def test_loss_and_gradient_diagnostics():
    """Verify that loss and gradient diagnostics record valid metrics and cosine similarities."""
    gen = NonlinearAgingGenerator(seed=42)
    cohort = gen.generate_cohort(
        conditions=[("CELL_1", 25.0), ("CELL_2", 35.0)],
        num_cycles=10,
    )

    diag = record_loss_and_gradient_diagnostics(
        dataset=cohort,
        epochs=10,
        loss_weights=LossWeights(lambda_physics=0.01, lambda_monotonicity=0.01),
        seed=42,
        record_interval=5,
    )

    assert len(diag.records) >= 2
    rec = diag.records[-1]

    # Verify all metrics are valid finite numbers
    assert math.isfinite(rec.loss_total)
    assert math.isfinite(rec.loss_data_c)
    assert rec.loss_phys >= 0.0
    assert rec.grad_norm_data >= 0.0
    assert rec.grad_norm_phys >= 0.0
    assert 0.0 <= rec.relative_phys_grad_pct <= 100.0
    assert -1.01 <= rec.cosine_sim_data_phys <= 1.01
    assert 0.0 <= rec.monotonicity_violation_rate <= 1.0


def test_sweep_physics_weights_multiseed():
    """Verify physics loss weight sensitivity sweep executes across multiple seeds."""
    gen = NonlinearAgingGenerator(seed=42)
    cohort = gen.generate_cohort(
        conditions=[("CELL_A", 25.0), ("CELL_B", 35.0)],
        num_cycles=8,
    )

    results = sweep_physics_weights_multiseed(
        dataset=cohort,
        lambda_phys_list=[0.0, 0.01],
        seeds=[42, 123],
        epochs=15,
    )

    assert len(results) == 2
    for res in results:
        assert res.rmse_mean >= 0.0
        assert res.mae_mean >= 0.0
        assert 0.0 <= res.picp_mean <= 100.0
        assert len(res.seeds) == 2


def test_conformal_uncertainty_calibration():
    """Verify that conformal calibration scales prediction intervals correctly."""
    gen = NonlinearAgingGenerator(seed=42)
    train_cohort = gen.generate_cohort(conditions=[("CELL_TRAIN_1", 25.0), ("CELL_TRAIN_2", 35.0)], num_cycles=10)
    cal_cohort = gen.generate_cohort(conditions=[("CELL_CAL", 25.0)], num_cycles=10)

    est = PinnSohEstimator(config=PinnTrainingConfig(epochs=20, seed=42, mode="pinn"))
    est.fit(train_cohort)

    # Initial conformal scale should be default 1.96
    assert est.conformal_scale_c == 1.96

    # Calibrate on independent calibration battery
    scale_c, scale_r = est.calibrate_conformal(cal_cohort, target_coverage=0.95)
    assert scale_c > 0.0
    assert est.conformal_scale_c == scale_c

    # Prediction interval should reflect calibrated scaling
    test_cycle = cal_cohort.batteries["CELL_CAL"].cycles[0]
    pred = est.predict_cycle(test_cycle)
    ci = pred.confidence_interval_95_c
    assert ci is not None
    assert ci[0] < ci[1]


def test_long_horizon_extrapolation():
    """Verify that early-life training accurately evaluates on unseen future cycles."""
    gen = NonlinearAgingGenerator(seed=42)
    battery = gen.generate_battery("CELL_LONG", num_cycles=20, temp_c=25.0)

    results = run_long_horizon_extrapolation(
        battery_data=battery,
        train_fractions=[0.25, 0.50],
        seeds=[42, 123],
        epochs=20,
    )

    assert len(results) == 4  # 2 fractions x 2 models (pure_mlp, full_pinn)
    for res in results:
        assert res.rmse_mean >= 0.0
        assert res.max_err_mean >= 0.0
        assert 0.0 <= res.picp_mean <= 100.0


def test_nonlinear_stage_benchmark():
    """Verify that multi-stage degradation benchmarking stratifies errors across life stages."""
    gen = NonlinearAgingGenerator(seed=42)
    cohort = gen.generate_cohort(conditions=[("CELL_NL", 25.0)], num_cycles=35)

    summary = run_nonlinear_stage_benchmark(
        dataset=cohort,
        seeds=[42],
        epochs=15,
    )

    assert "early_passivation_0_to_5" in summary
    assert "steady_cycling_5_to_30" in summary
    assert "full_lifecycle_0_to_50" in summary

    for stage_name, models in summary.items():
        assert "constant_mean" in models
        assert "empirical_power_law" in models
        assert "pure_mlp" in models
        assert "full_pinn" in models
        for m_name, metrics in models.items():
            assert metrics["rmse_pct"] >= 0.0
            assert metrics["mae_pct"] >= 0.0


def test_temperature_transfer_benchmark():
    """Verify leave-one-temperature-out cross-validation runs cleanly."""
    gen = NonlinearAgingGenerator(seed=42)
    cohort = gen.generate_cohort(
        conditions=[
            ("CELL_15C", 15.0),
            ("CELL_25C", 25.0),
            ("CELL_45C", 45.0),
        ],
        num_cycles=10,
    )

    results = run_temperature_transfer_benchmark(
        dataset=cohort,
        seeds=[42],
        epochs=15,
    )

    assert len(results) >= 2
    for k, metrics in results.items():
        assert metrics["rmse_mean"] >= 0.0
        assert 0.0 <= metrics["picp_mean"] <= 100.0
