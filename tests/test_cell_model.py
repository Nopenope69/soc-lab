"""Unit tests for the 2RC cell model, hysteresis dynamics, and table interpolation."""

import math
import pytest
import numpy as np

from soc.assumptions.loader import resolve_assumptions
from soc.models.cell_2rc import Cell2RCModel, CellState
from soc.models.tables import InterpolatedTable1D, InterpolatedTable2D


def test_table_interpolation_clamps_at_grid_edges():
    """Verify that table lookups strictly clamp at edges and never extrapolate."""
    x_grid = [0.0, 0.5, 1.0]
    y_vals = [2.5, 3.2, 3.65]
    table = InterpolatedTable1D(x_grid, y_vals)

    # Within grid
    assert table.lookup(0.5) == pytest.approx(3.2)
    # Below lower bound: clamps to y_vals[0]
    assert table.lookup(-0.5) == pytest.approx(2.5)
    assert table.lookup(-100.0) == pytest.approx(2.5)
    # Above upper bound: clamps to y_vals[-1]
    assert table.lookup(1.5) == pytest.approx(3.65)
    assert table.lookup(50.0) == pytest.approx(3.65)


def test_table_2d_clamps_at_grid_edges():
    """Verify that 2D (temp, soc) table clamps along both axes."""
    temps = [15.0, 25.0, 35.0]
    socs = [0.0, 0.5, 1.0]
    table_dict = {
        "15.0": [2.50, 3.20, 3.65],
        "25.0": [2.55, 3.25, 3.70],
        "35.0": [2.60, 3.30, 3.75],
    }
    table = InterpolatedTable2D(temps, socs, table_dict)

    # Inside
    assert table.lookup(0.5, 25.0) == pytest.approx(3.25)
    # Below temp: clamps to 15.0 C
    assert table.lookup(0.5, -10.0) == pytest.approx(3.20)
    # Above temp: clamps to 35.0 C
    assert table.lookup(0.5, 50.0) == pytest.approx(3.30)
    # Below SOC: clamps to soc=0.0 at 25.0 C
    assert table.lookup(-0.2, 25.0) == pytest.approx(2.55)
    # Above SOC: clamps to soc=1.0 at 25.0 C
    assert table.lookup(1.2, 25.0) == pytest.approx(3.70)


def test_constant_current_discharge_analytic_soc():
    """Verify constant-current discharge changes SOC by exactly I*dt/(3600*Q) per step."""
    soc0 = 0.80
    i_discharge = 50.0  # 50 A discharge (positive)
    dt = 2.0  # seconds
    capacity_ah = 100.0
    coulomb_eff = 0.998

    expected_delta = (1.0 * i_discharge * dt) / (3600.0 * capacity_ah)
    expected_soc1 = soc0 - expected_delta

    soc1 = Cell2RCModel.step_soc(
        soc=soc0,
        i_a=i_discharge,
        dt_s=dt,
        capacity_ah=capacity_ah,
        coulombic_efficiency=coulomb_eff,
    )
    assert soc1 == pytest.approx(expected_soc1, abs=1e-12)


def test_constant_current_charge_analytic_soc():
    """Verify charge current (negative) scales by coulombic efficiency eta."""
    soc0 = 0.50
    i_charge = -50.0  # 50 A charge (negative)
    dt = 2.0
    capacity_ah = 100.0
    coulomb_eff = 0.998

    # delta_soc = (eta * i * dt) / (3600 * Q)
    expected_delta = (coulomb_eff * i_charge * dt) / (3600.0 * capacity_ah)
    expected_soc1 = soc0 - expected_delta

    soc1 = Cell2RCModel.step_soc(
        soc=soc0,
        i_a=i_charge,
        dt_s=dt,
        capacity_ah=capacity_ah,
        coulombic_efficiency=coulomb_eff,
    )
    assert soc1 == pytest.approx(expected_soc1, abs=1e-12)
    # Cell must have gained charge
    assert soc1 > soc0


def test_rc_branch_current_step_response_analytic():
    """Verify RC branch current approaches applied current with stated time constant."""
    i_applied = 20.0
    tau = 15.0
    dt = 1.0
    i_rc = 0.0

    # Step forward 15 seconds (1 time constant)
    steps = int(tau / dt)
    for _ in range(steps):
        i_rc = Cell2RCModel.step_rc_current(i_rc=i_rc, i_a=i_applied, dt_s=dt, tau_s=tau)

    # Analytic solution for 1st-order step response at t = tau: i(tau) = I * (1 - e^-1)
    expected_i_rc = i_applied * (1.0 - math.exp(-1.0))
    assert i_rc == pytest.approx(expected_i_rc, rel=1e-3)


def test_hysteresis_exact_closed_form_match():
    """Verify that constant discharge and charge segments match closed form to 1e-9."""
    capacity_ah = 100.0
    gamma = 50.0
    coulomb_eff = 0.998
    dt_s = 1.0
    cap_as = 3600.0 * capacity_ah

    # 1. Constant discharge segment (50 A for 1500 steps from h0 = 0.0)
    i_dis = 50.0
    h = 0.0
    n_dis = 1500
    for _ in range(n_dis):
        h = Cell2RCModel.step_hysteresis(
            h=h,
            i_a=i_dis,
            dt_s=dt_s,
            capacity_ah=capacity_ah,
            gamma=gamma,
            coulombic_efficiency=coulomb_eff,
        )
        assert -1.0 <= h <= 1.0

    alpha_dis = (1.0 * i_dis * gamma * dt_s) / cap_as
    # Closed form from h0=0: h = -(1 - exp(-n * alpha))
    h_closed_dis = -(1.0 - math.exp(-n_dis * alpha_dis))
    assert abs(h - h_closed_dis) < 1e-9

    # 2. Constant charge segment (-30 A for 400 steps starting from h_closed_dis)
    i_chg = -30.0
    n_chg = 400
    h_start_chg = h
    for _ in range(n_chg):
        h = Cell2RCModel.step_hysteresis(
            h=h,
            i_a=i_chg,
            dt_s=dt_s,
            capacity_ah=capacity_ah,
            gamma=gamma,
            coulombic_efficiency=coulomb_eff,
        )
        assert -1.0 <= h <= 1.0

    alpha_chg = (coulomb_eff * abs(i_chg) * gamma * dt_s) / cap_as
    # Closed form: h = 1 - (1 - h_start) * exp(-n * alpha)
    h_closed_chg = 1.0 - (1.0 - h_start_chg) * math.exp(-n_chg * alpha_chg)
    assert abs(h - h_closed_chg) < 1e-9


def test_zero_current_leaves_hysteresis_unchanged():
    """Verify zero current leaves h completely unchanged (at rest)."""
    h_init = 0.42
    capacity_ah = 100.0
    gamma = 50.0
    coulomb_eff = 0.998

    # Apply 10 rest steps at i = 0
    h = h_init
    for _ in range(10):
        h = Cell2RCModel.step_hysteresis(
            h=h,
            i_a=0.0,
            dt_s=1.0,
            capacity_ah=capacity_ah,
            gamma=gamma,
            coulombic_efficiency=coulomb_eff,
        )
    assert h == pytest.approx(h_init)
