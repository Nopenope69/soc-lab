"""Unit tests for pulse segmentation, 2-RC parameter fitting, and identifiability checks."""

import numpy as np
import pytest

from soh.features.pulse_ecm import (
    Ecm2RcFitter,
    PulseRecord,
    PulseSegmenter,
)


def test_pulse_segmentation_clean_square_wave():
    """Verify PulseSegmenter correctly isolates a pulse and post-pulse relaxation."""
    # 0 to 10s: rest (I=0), 10 to 20s: pulse (I=2A discharge), 20 to 40s: relax (I=0)
    t = np.linspace(0, 40, 400)
    i = np.zeros_like(t)
    i[(t >= 10.0) & (t < 20.0)] = 2.0  # 2A discharge
    v = np.full_like(t, 3.30)
    v[(t >= 10.0) & (t < 20.0)] = 3.20  # voltage drop
    temp = np.full_like(t, 25.0)

    segmenter = PulseSegmenter(min_pulse_current_a=1.0, min_pulse_duration_s=5.0, min_relax_duration_s=10.0)
    pulses = segmenter.detect_pulses(t, v, i, temp)

    assert len(pulses) == 1
    p = pulses[0]
    assert p.pulse_duration_s == pytest.approx(10.0, abs=0.5)
    assert p.relax_duration_s >= 10.0
    assert p.i_amplitude_a == pytest.approx(2.0, abs=0.1)


def test_ecm_2rc_fitting_and_identifiability():
    """Verify Ecm2RcFitter recovers true 2-RC parameters from synthesized pulse."""
    # Known ground truth parameters
    r0_true = 0.020
    r1_true = 0.010
    tau1_true = 4.0
    r2_true = 0.015
    tau2_true = 25.0
    vocv_true = 3.35
    i_pulse = 2.0  # 2A discharge

    # Simulate 10s pulse + 30s relaxation
    t_pulse = np.linspace(0, 10, 100)
    v_pulse = (
        vocv_true
        - i_pulse * r0_true
        - i_pulse * r1_true * (1.0 - np.exp(-t_pulse / tau1_true))
        - i_pulse * r2_true * (1.0 - np.exp(-t_pulse / tau2_true))
    )

    t_relax = np.linspace(0, 30, 150)
    v1_end = i_pulse * r1_true * (1.0 - np.exp(-10.0 / tau1_true))
    v2_end = i_pulse * r2_true * (1.0 - np.exp(-10.0 / tau2_true))
    v_relax = vocv_true - v1_end * np.exp(-t_relax / tau1_true) - v2_end * np.exp(-t_relax / tau2_true)

    pulse_rec = PulseRecord(
        pulse_id="test_p",
        cycle_index=1,
        t_pulse_s=t_pulse,
        v_pulse_v=v_pulse,
        i_pulse_a=np.full_like(t_pulse, i_pulse),
        t_relax_s=t_relax,
        v_relax_v=v_relax,
        i_relax_a=np.zeros_like(t_relax),
        temp_c=25.0,
        i_amplitude_a=i_pulse,
        pulse_duration_s=10.0,
        relax_duration_s=30.0,
    )

    fitter = Ecm2RcFitter()
    params, quality = fitter.fit_pulse(pulse_rec)

    assert quality.is_eligible
    assert params is not None
    assert params.fit_rmse_mv < 1.0  # < 1mV fit error
    assert params.r0_ohm == pytest.approx(r0_true, rel=0.10)
    assert params.r_total_ohm == pytest.approx(r0_true + r1_true + r2_true, rel=0.10)
    assert params.is_identifiable


def test_ecm_2rc_fitting_variable_current():
    """Verify Ecm2RcFitter handles variable current pulses via recursive state-space forward model."""
    r0_true = 0.020
    r1_true = 0.010
    tau1_true = 4.0
    r2_true = 0.015
    tau2_true = 25.0
    vocv_true = 3.35

    # 10s pulse with 20% current ripple: I(t) = 2.0 + 0.4 * sin(2*pi*t/2.5)
    t_pulse = np.linspace(0, 10, 100)
    i_pulse = 2.0 + 0.4 * np.sin(2.0 * np.pi * t_pulse / 2.5)

    # Simulate true physical response using recursive state-space integration
    v_pulse = np.zeros_like(t_pulse)
    v1 = 0.0
    v2 = 0.0
    v_pulse[0] = vocv_true - i_pulse[0] * r0_true

    for k in range(1, len(t_pulse)):
        dt = t_pulse[k] - t_pulse[k - 1]
        a1 = np.exp(-dt / tau1_true)
        a2 = np.exp(-dt / tau2_true)
        # Discharge current drops voltage
        v1 = v1 * a1 - i_pulse[k] * r1_true * (1.0 - a1)
        v2 = v2 * a2 - i_pulse[k] * r2_true * (1.0 - a2)
        v_pulse[k] = vocv_true - i_pulse[k] * r0_true + v1 + v2

    t_relax = np.linspace(0, 30, 150)
    i_relax = np.zeros_like(t_relax)
    v_relax = np.zeros_like(t_relax)
    for k in range(len(t_relax)):
        tr = t_relax[k]
        v_relax[k] = vocv_true + v1 * np.exp(-tr / tau1_true) + v2 * np.exp(-tr / tau2_true)

    pulse_rec = PulseRecord(
        pulse_id="var_p",
        cycle_index=2,
        t_pulse_s=t_pulse,
        v_pulse_v=v_pulse,
        i_pulse_a=-i_pulse,  # Sign convention: discharge negative
        t_relax_s=t_relax,
        v_relax_v=v_relax,
        i_relax_a=i_relax,
        temp_c=25.0,
        i_amplitude_a=-float(np.mean(i_pulse)),
        pulse_duration_s=10.0,
        relax_duration_s=30.0,
    )

    fitter = Ecm2RcFitter()
    params, quality = fitter.fit_pulse(pulse_rec)

    assert quality.is_eligible
    assert quality.current_stability_cv is not None
    assert quality.current_stability_cv > 0.05  # Detected significant current variation
    assert params is not None
    assert params.fit_rmse_mv < 2.0  # High fidelity fit even under variable current
    assert params.r0_ohm == pytest.approx(r0_true, rel=0.15)
    assert params.r_total_ohm == pytest.approx(r0_true + r1_true + r2_true, rel=0.15)
