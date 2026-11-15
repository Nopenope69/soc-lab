"""Unit tests for degradation mechanisms and reversible temperature scaling."""

import math
import pytest

from soh.degradation import (
    EmpiricalAgingConfig,
    EmpiricalDegradationModel,
    ReversibleCorrectionConfig,
    SeiKineticsConfig,
    SeiKineticsModel,
    TemperatureReversibleCorrection,
)


def test_sei_growth_kinetics():
    """Verify diffusion-limited parabolic growth and monotonic behavior."""
    model = SeiKineticsModel(SeiKineticsConfig(delta_sei_0=5e-9))
    delta = 5e-9

    # Step through 1000s under charging at 25°C
    for _ in range(10):
        delta = model.step_sei_growth(
            current_delta_m=delta,
            current_a=-1.0,
            temp_c=25.0,
            dt_s=100.0,
        )

    assert delta > 5e-9
    fade_ah = model.delta_to_capacity_fade_ah(delta)
    assert fade_ah > 0.0


def test_empirical_degradation_independent_modeling():
    """Verify independent capacity fade and resistance growth models."""
    model = EmpiricalDegradationModel()

    # Zero throughput -> pristine state (SOH_C=1.0, R_mult=1.0)
    assert model.predict_capacity_retention(0.0) == 1.0
    assert model.predict_resistance_growth(0.0) == 1.0

    # With cycling throughput
    retention = model.predict_capacity_retention(1000.0, avg_temp_c=25.0)
    r_mult = model.predict_resistance_growth(1000.0, avg_temp_c=25.0)

    assert 0.0 < retention < 1.0
    assert r_mult > 1.0

    # High temperature accelerates degradation
    retention_hot = model.predict_capacity_retention(1000.0, avg_temp_c=45.0)
    r_mult_hot = model.predict_resistance_growth(1000.0, avg_temp_c=45.0)

    assert retention_hot < retention
    assert r_mult_hot > r_mult


def test_reversible_temperature_correction():
    """Verify Arrhenius temperature normalization of resistance."""
    corr = TemperatureReversibleCorrection(ReversibleCorrectionConfig(t_ref_c=25.0))

    # Resistance measured at reference temperature should remain unchanged
    r_ref = 0.020
    assert corr.normalize_resistance_to_t_ref(r_ref, 25.0) == pytest.approx(r_ref)

    # Hot cell (45°C) has lower resistance due to higher electrolyte conductivity
    r_hot = 0.015
    # Normalized to 25°C, the cold resistance should be higher than r_hot
    r_norm = corr.normalize_resistance_to_t_ref(r_hot, 45.0)
    assert r_norm > r_hot

    # Cold cell (0°C) has higher resistance
    r_cold = 0.035
    # Normalized to 25°C, the resistance should be lower than r_cold
    r_norm_cold = corr.normalize_resistance_to_t_ref(r_cold, 0.0)
    assert r_norm_cold < r_cold

    # Round trip test: predict at 45°C from reference, then normalize back
    r_pred_hot = corr.predict_resistance_at_temp(r_ref, 45.0)
    assert corr.normalize_resistance_to_t_ref(r_pred_hot, 45.0) == pytest.approx(r_ref)


def test_degradation_transition_benchmarks_and_units():
    """Verify calibrated physical degradation over 100, 500, and 1,000 equivalent full cycles (EFC)."""
    model = EmpiricalDegradationModel()
    nom_cap_ah = 2.30
    ah_per_efc = nom_cap_ah * 2.0  # 4.60 Ah per full charge-discharge cycle

    # 1. Benchmark at 100 EFC (460 Ah)
    ah_100 = 100 * ah_per_efc
    soh_c_100 = model.predict_capacity_retention(ah_100, avg_temp_c=25.0)
    r_growth_100 = model.predict_resistance_growth(ah_100, avg_temp_c=25.0)
    # Expected: 2% to 6% capacity fade, 5% to 15% resistance growth
    assert 0.94 <= soh_c_100 <= 0.98
    assert 1.05 <= r_growth_100 <= 1.15

    # 2. Benchmark at 500 EFC (2300 Ah)
    ah_500 = 500 * ah_per_efc
    soh_c_500 = model.predict_capacity_retention(ah_500, avg_temp_c=25.0)
    r_growth_500 = model.predict_resistance_growth(ah_500, avg_temp_c=25.0)
    # Expected: 8% to 15% capacity fade, 20% to 35% resistance growth
    assert 0.85 <= soh_c_500 <= 0.92
    assert 1.20 <= r_growth_500 <= 1.35

    # 3. Benchmark at 1,000 EFC (4600 Ah)
    ah_1000 = 1000 * ah_per_efc
    soh_c_1000 = model.predict_capacity_retention(ah_1000, avg_temp_c=25.0)
    r_growth_1000 = model.predict_resistance_growth(ah_1000, avg_temp_c=25.0)
    # Expected: 15% to 22% capacity fade (approaching 80% EOL), 35% to 55% resistance growth
    assert 0.78 <= soh_c_1000 <= 0.85
    assert 1.35 <= r_growth_1000 <= 1.55

    # 4. Degradation rate per Ah (alpha_deg) verification
    delta_soh = 1.0 - soh_c_1000
    alpha_deg_ah = delta_soh / ah_1000
    # Expected alpha_deg in Ah: 3e-5 to 5e-5 SOH / Ah
    assert 3.0e-5 <= alpha_deg_ah <= 5.0e-5

    # Converted to A*s units: alpha_deg_as = alpha_deg_ah / 3600
    alpha_deg_as = alpha_deg_ah / 3600.0
    assert 0.8e-8 <= alpha_deg_as <= 1.5e-8
