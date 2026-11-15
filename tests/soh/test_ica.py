"""Unit tests for Incremental Capacity Analysis (ICA) feature extraction."""

import numpy as np
import pytest

from soh.features.ica import IcaConfig, IcaFeatureExtractor


def test_ica_feature_extraction_clean_peak():
    """Verify IcaFeatureExtractor detects peak, computes peak height, area, and shift."""
    # Synthesize CC charging: constant current I = -1.0 A
    # Voltage rises from 3.10V to 3.55V with an inflection plateau at 3.34V
    t = np.linspace(0, 3600, 300)
    i = np.full_like(t, -1.0)
    temp = np.full_like(t, 25.0)

    # Synthesize CC charging at 1.0A for 3600s
    t = np.linspace(0, 3600, 300)
    i = np.full_like(t, -1.0)
    temp = np.full_like(t, 25.0)

    # Normalized charge q in [0, 1]
    q = t / 3600.0
    # Invert the electrochemical plateau: around q ~ 0.45, voltage rises very slowly (plateau)
    # causing dQ/dV = 1 / (dV/dQ) to have a sharp peak
    # A gentle cubic inflection around q = 0.45 produces a realistic voltage plateau and ICA peak:
    v = 3.10 + 0.30 * q + 0.25 * ((q - 0.45) ** 3)
    # Add a tiny sensor noise (0.5 mV)
    v += np.random.default_rng(42).normal(0, 0.0005, len(v))

    extractor = IcaFeatureExtractor(IcaConfig(voltage_grid_step_v=0.002, min_peak_prominence=0.1, min_peak_height=0.2))
    ica_feats, quality = extractor.extract_from_charge_segment(t, v, i, temp)

    assert quality.is_eligible
    assert ica_feats is not None
    assert 3.20 < ica_feats.peak_voltage_v < 3.40
    assert ica_feats.peak_height_ah_per_v > 0.5
    assert ica_feats.peak_area_ah > 0.05
    assert quality.snr_db is not None


def test_ica_rejection_low_voltage_span():
    """Verify ICA rejects segments with insufficient voltage window."""
    t = np.linspace(0, 100, 50)
    i = np.full_like(t, -1.0)
    v = np.linspace(3.30, 3.32, 50)  # only 20 mV span (< 150 mV threshold)
    temp = np.full_like(t, 25.0)

    extractor = IcaFeatureExtractor(IcaConfig(min_voltage_span_v=0.15))
    ica_feats, quality = extractor.extract_from_charge_segment(t, v, i, temp)

    assert not quality.is_eligible
    assert ica_feats is None
    assert any("voltage span" in r.lower() for r in quality.failure_reasons)


def test_ica_rejection_thermal_drift():
    """Verify ICA rejects charging segments during violent thermal transients."""
    t = np.linspace(0, 1000, 200)
    i = np.full_like(t, -1.0)
    v = np.linspace(3.10, 3.50, 200)
    temp = np.linspace(25.0, 35.0, 200)  # 10°C thermal drift > 4°C limit

    extractor = IcaFeatureExtractor(IcaConfig(max_temp_drift_c=4.0))
    ica_feats, quality = extractor.extract_from_charge_segment(t, v, i, temp)

    assert not quality.is_eligible
    assert any("temperature drift" in r.lower() for r in quality.failure_reasons)
