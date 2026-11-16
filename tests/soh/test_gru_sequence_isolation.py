"""Unit tests verifying GRU sequence history isolation per cell_id and reset paths."""

import numpy as np
import pytest

pytest.importorskip("torch")
from soh.common.contracts import CycleRecord
from soh.models.gru.gru_estimator import GruNetworkConfig, GruSohEstimator, GruTrainingConfig


def _make_dummy_cycle(cycle_index: int, temp_c: float = 25.0, cell_id: str = "CELL_A") -> CycleRecord:
    t = np.linspace(0, 100, 50)
    v = np.linspace(3.3, 3.0, 50)
    i = np.full_like(t, -1.0)
    temp = np.full_like(t, temp_c)
    return CycleRecord(
        cycle_index=cycle_index,
        time_s=t,
        voltage_v=v,
        current_a=i,
        temp_c=temp,
        metadata={"cell_id": cell_id},
        ah_throughput=float(cycle_index * 2.0),
        soh_c_bol_true=1.0 - 0.001 * cycle_index,
        soh_r_bol_true=1.0 + 0.001 * cycle_index,
    )


def test_gru_sequence_history_isolation():
    """Verify that multiple cells track sequence history in isolated buffers."""
    gru = GruSohEstimator(network_config=GruNetworkConfig(sequence_length=4, hidden_dim=8))

    # Feed cell A
    gru.predict_cycle(_make_dummy_cycle(0, cell_id="CELL_A"))
    gru.predict_cycle(_make_dummy_cycle(1, cell_id="CELL_A"))

    # Feed cell B
    gru.predict_cycle(_make_dummy_cycle(0, cell_id="CELL_B"))

    assert len(gru.history_by_cell["CELL_A"]) == 2
    assert len(gru.history_by_cell["CELL_B"]) == 1

    # Reset cell A only
    gru.reset("CELL_A")
    assert "CELL_A" not in gru.history_by_cell
    assert len(gru.history_by_cell["CELL_B"]) == 1

    # Global reset
    gru.reset()
    assert len(gru.history_by_cell) == 0
    assert len(gru.history_buffer) == 0
