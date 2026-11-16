"""Unit tests verifying that missing SOH_R labels are excluded from training rather than defaulted."""

import numpy as np
import pytest

from soh.common.contracts import CycleRecord
from soh.common.protocols import CellReferenceSpec
from soh.data.base_loader import SohBatteryData, SohDataset
from soh.data.synthetic_aging import SyntheticAgingGenerator
from soh.estimators.pulse_elastic_net import PulseElasticNetEstimator


def _create_partial_label_dataset(total_cycles: int = 10, r_labeled_cycles: int = 6) -> SohDataset:
    """Helper to generate a cohort where only some cycles have SOH_R labels."""
    spec = CellReferenceSpec(
        cell_id="TEST_PARTIAL_CELL",
        chemistry="LFP",
        nominal_capacity_ah=1.1,
        v_max=3.6,
        v_min=2.0,
        t_ref_c=25.0,
        nominal_resistance_ohm=0.015,
    )
    bdata = SohBatteryData(
        cell_id="TEST_PARTIAL_CELL",
        spec=spec,
        bol_capacity_ah=1.1,
        bol_resistance_ohm=0.015,
    )

    t_pts = np.linspace(0, 100, 100)
    # Step pulse in current: 0A for 10s, then 2A discharge for 30s, then 0A
    i_pts = np.zeros_like(t_pts)
    i_pts[(t_pts >= 10.0) & (t_pts <= 40.0)] = -2.0
    v_pts = 3.3 + 0.015 * i_pts + 0.005 * (1.0 - np.exp(-np.maximum(0.0, t_pts - 10.0) / 5.0)) * (i_pts != 0)
    temp_pts = np.full_like(t_pts, 25.0)

    for k in range(total_cycles):
        # SOH_C is always available
        soh_c = 1.0 - 0.001 * k
        # SOH_R is only available for first r_labeled_cycles
        soh_r = (1.0 - 0.002 * k) if k < r_labeled_cycles else None

        rec = CycleRecord(
            cycle_index=k,
            time_s=t_pts,
            voltage_v=v_pts,
            current_a=i_pts,
            temp_c=temp_pts,
            ah_throughput=k * 2.2,
            soh_c_bol_true=soh_c,
            soh_r_bol_true=soh_r,
        )
        bdata.cycles.append(rec)

    ds = SohDataset()
    ds.add_battery(bdata)
    return ds


def test_pulse_elasticnet_missing_soh_r_exclusion():
    """Verify PulseElasticNetEstimator excludes missing SOH_R labels without defaulting to 1.0."""
    ds = _create_partial_label_dataset(total_cycles=10, r_labeled_cycles=6)
    est = PulseElasticNetEstimator()
    est.fit(ds)

    assert est.n_samples_c == 10, f"Expected 10 SOH_C samples, got {est.n_samples_c}"
    assert est.n_samples_r == 6, f"Expected 6 SOH_R samples, got {est.n_samples_r}"
    assert est._is_r_fitted is True


def test_pulse_elasticnet_insufficient_soh_r_labels():
    """Verify PulseElasticNet leaves SOH_R unfitted when fewer than 5 SOH_R labels exist."""
    ds = _create_partial_label_dataset(total_cycles=10, r_labeled_cycles=3)
    est = PulseElasticNetEstimator()
    est.fit(ds)

    assert est.n_samples_c == 10
    assert est.n_samples_r == 3
    assert est._is_r_fitted is False

    # Prediction should still succeed for SOH_C, but SOH_R should be None
    pulse = ds.batteries["TEST_PARTIAL_CELL"].cycles[0]
    out = est.predict_cycle(pulse)
    assert out.soh_c is not None
    assert out.soh_r is None


def test_gru_missing_soh_r_exclusion():
    """Verify GruSohEstimator tracks independent SOH_C and SOH_R sample counts."""
    pytest.importorskip("torch")
    from soh.models.gru.gru_estimator import GruNetworkConfig, GruSohEstimator, GruTrainingConfig

    ds = _create_partial_label_dataset(total_cycles=10, r_labeled_cycles=6)
    cfg = GruTrainingConfig(epochs=2, batch_size=4)
    net_cfg = GruNetworkConfig(sequence_length=3, hidden_dim=8)
    gru = GruSohEstimator(config=cfg, network_config=net_cfg)
    gru.fit(ds)

    assert gru.n_samples_c == 10, f"Expected 10 SOH_C samples, got {gru.n_samples_c}"
    assert gru.n_samples_r == 6, f"Expected 6 SOH_R samples, got {gru.n_samples_r}"
