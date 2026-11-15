"""Unit tests for SOH data loaders, synthetic aging generation, and window extraction."""

import numpy as np
import pytest

pytest.importorskip("pandas")
from soh.data import (
    CalceAgingDataLoader,
    PartialChargeWindowExtractor,
    SohBatteryData,
    SohDataset,
    SyntheticAgingGenerator,
)


def test_synthetic_aging_cohort_generation():
    """Verify synthetic aging generator produces physically valid degradation and ground truths."""
    generator = SyntheticAgingGenerator(seed=123)
    cohort = generator.generate_cohort(cell_ids=["CELL_1", "CELL_2"], num_cycles=20)

    assert len(cohort.cell_ids) == 2
    assert "CELL_1" in cohort.batteries
    assert "CELL_2" in cohort.batteries

    b1 = cohort.batteries["CELL_1"]
    assert b1.cycle_count == 20
    assert b1.bol_capacity_ah is not None and b1.bol_capacity_ah > 0
    assert b1.bol_resistance_ohm is not None and b1.bol_resistance_ohm > 0

    # First cycle should have SOH_C_bol = 1.0
    c0 = b1.cycles[0]
    assert c0.soh_c_bol_true == pytest.approx(1.0, abs=1e-4)
    assert c0.soh_r_bol_true == pytest.approx(1.0, abs=1e-4)

    # Last cycle should show degradation
    c_last = b1.cycles[-1]
    assert c_last.soh_c_bol_true < 1.0
    assert c_last.soh_r_bol_true < 1.0  # Resistance grew, so SOH_R < 1.0

    # Randomized session test
    cohort_rand = generator.generate_cohort(
        cell_ids=["R1"], num_cycles=5, randomize_sessions=True
    )
    b_rand = cohort_rand.batteries["R1"]
    durations = [c.time_s[-1] - c.time_s[0] for c in b_rand.cycles]
    assert len(set(np.round(durations, 1))) > 1


def test_dataset_grouped_split():
    """Verify grouped split strictly isolates physical batteries without leakage."""
    generator = SyntheticAgingGenerator(seed=456)
    cohort = generator.generate_cohort(cell_ids=["B1", "B2", "B3", "B4"], num_cycles=10)

    train_ds, test_ds = cohort.split_by_battery(train_cell_ids=["B1", "B2", "B3"], test_cell_ids=["B4"])

    assert train_ds.cell_ids == ["B1", "B2", "B3"]
    assert test_ds.cell_ids == ["B4"]

    # Ensure no intersection between battery cohorts
    assert set(train_ds.cell_ids).isdisjoint(set(test_ds.cell_ids))


def test_partial_charge_window_extractor():
    """Verify charging window segmentation and eligibility checking."""
    generator = SyntheticAgingGenerator(seed=789)
    bdata = generator.generate_battery("B_TEST", num_cycles=5)
    c0 = bdata.cycles[0]

    extractor = PartialChargeWindowExtractor(min_duration_s=10.0)
    windows = extractor.extract_windows_from_cycle(c0, nominal_capacity_ah=bdata.spec.nominal_capacity_ah)

    assert len(windows) >= 1
    win, is_eligible = windows[0]
    assert win.duration_s >= 10.0
    assert win.is_charging
    assert win.ah_charged > 0.0
    assert isinstance(is_eligible, (bool, np.bool_))
