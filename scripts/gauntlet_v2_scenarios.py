"""Gauntlet V2 Scenario Engine.

Implements Scenarios S-A, S-B, S-C, and S-F on DST (and later US06/FUDS)
under strict Rule R3 (unmodified current ground truth) and Stage V1 parameter set (calce_a123_v4.yaml).

Changes from V1:
- S-D (unknown start) is REMOVED (not testable on CALCE without mid-SOC rests).
- S-C has three partial windows with zero offset: 90->40%, 80->30%, 70->20%.
- S-B has 16 cases per temperature (80, 60, 40, 20% with offsets -10, -5, +5, +10 pp).
- S-F has 10 faults: current +-10, +-50 mA; voltage +-5, +-10 mV; capacity +-3%.
- Cross-cell set X: A1-007 parameters applied to A1-008 data at 20, 30, 40, 50 C (A1-008 own truth, own Q(T)).
- Evaluates against Rule R3:
    truth_soc = start_soc - (np.cumsum(unmodified_current * dt) / (3600.0 * q_c20))
"""

from dataclasses import dataclass, replace
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir
from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.models.plant import Measurement
from soc.models.cell_2rc import Cell2RCModel
from soc.models.tables import InterpolatedTable2D
from scripts.evaluate_calce import get_file_paths

# Rule R3 explicit guarantee line string
R3_GUARANTEE_LINE = "truth_soc = start_soc - (np.cumsum(unmodified_current * dt) / (3600.0 * q_c20))"

SOC_GRID = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]

# M(T) corrected half-gap values from Stage 1/V1 audit
M_AUDIT = {
    "A1-007": {20: 0.02701, 25: 0.01719, 30: 0.02436, 40: 0.02155, 50: 0.01988},
    "A1-008": {20: 0.02438, 25: 0.01568, 30: 0.02194, 40: 0.01917, 50: 0.01456},
}


def load_d8_table() -> pd.DataFrame:
    """Load D8 CV-taper anchor gap table."""
    return pd.read_csv(repo_root / "reports" / "diagnostics" / "d8_anchor_gap.csv")


@dataclass
class ScenarioDataSet:
    """Precomputed ground truth, cell data, and truth-driven model state trajectory."""
    temp_c: int
    cell_id: str
    profile: str
    time_s: np.ndarray
    dt_arr: np.ndarray
    current_a: np.ndarray
    voltage_v: np.ndarray
    temp_measured_c: np.ndarray
    truth_soc: np.ndarray
    cap_c20: float
    start_soc: float
    # Truth-driven model trajectories (internal states of estimator cell model)
    i1_truth: np.ndarray
    i2_truth: np.ndarray
    h_truth: np.ndarray
    v_model_truth: np.ndarray
    ocv_mono: np.ndarray


def prepare_scenario_data_v2(
    temp_c: int,
    profile: str = "DST",
    cell_id: str = "A1-007",
    profile_name: str = "calce_a123_v4",
) -> ScenarioDataSet:
    """Prepare dataset, ground truth, and truth-driven state trajectories adhering strictly to Rule R3."""
    raw_dir = get_raw_dir(repo_root)
    d8_df = load_d8_table()
    row = d8_df[d8_df["Temp (C)"] == temp_c]

    ocv_p, dyn_p = get_file_paths(raw_dir, temp_c, cell_id)
    ocv = load_ocv_file(ocv_p, float(temp_c), cell_id)

    # Determine cell-specific Q(T) and start SOC = 1 - CV_taper_gap(T)
    if len(row) > 0:
        gap_pp = float(row.iloc[0]["Delta SOC Gap (pp)"])
        start_soc = 1.0 - (gap_pp / 100.0)
        if cell_id == "A1-007":
            cap_c20 = float(row.iloc[0]["C/20 Cap (Ah)"])
        else:
            cap_c20 = float(ocv.c20_capacity_ah)
    else:
        gap_pp = 0.0
        start_soc = 1.0
        cap_c20 = float(ocv.c20_capacity_ah)

    # Monotonized symmetric OCV for the cell
    dis_soc, dis_v = ocv.discharge_soc, ocv.discharge_v
    chg_soc, chg_v = ocv.charge_soc, ocv.charge_v
    if ocv.excluded_soc_range is not None:
        low, high = ocv.excluded_soc_range
        mask_dis = (dis_soc < low) | (dis_soc > high)
        dis_soc, dis_v = dis_soc[mask_dis], dis_v[mask_dis]
    idx_dis = np.argsort(dis_soc)
    idx_chg = np.argsort(chg_soc)
    v_dis_grid = np.interp(SOC_GRID, dis_soc[idx_dis], dis_v[idx_dis])
    v_chg_grid = np.interp(SOC_GRID, chg_soc[idx_chg], chg_v[idx_chg])
    v_ocv_base = 0.5 * (v_dis_grid + v_chg_grid)
    v_ocv_mono = np.copy(v_ocv_base)
    if v_ocv_mono[0] < 2.0:
        v_ocv_mono[0] = 2.0
    for i in range(len(v_ocv_mono) - 1):
        if v_ocv_mono[i + 1] <= v_ocv_mono[i]:
            v_ocv_mono[i + 1] = v_ocv_mono[i] + 0.001

    cyc = load_dynamic_cycle(dyn_p, float(temp_c), cell_id, profile, cap_c20)
    time_s = cyc.time_s
    n = len(time_s)
    dt_arr = np.diff(time_s, prepend=time_s[0])
    current_a = cyc.current_a
    voltage_v = cyc.voltage_v
    temp_meas = cyc.temperature_measured_c

    # RULE R3 GROUND TRUTH INTEGRATION:
    # Guaranteed script line: truth_soc = start_soc - (np.cumsum(unmodified_current * dt) / (3600.0 * q_c20))
    unmodified_current = current_a
    truth_soc = start_soc - (np.cumsum(unmodified_current * dt_arr) / (3600.0 * cap_c20))

    # Load frozen plant model parameters (calce_a123_v4)
    assumptions, _, _ = load_assumptions(profile=profile_name)
    params = ParamSet.from_assumptions(assumptions, matched=True)
    temps_p = list(params.temperatures_c)
    socs_p = list(params.soc_grid)
    r0_tab = InterpolatedTable2D(temps_p, socs_p, params.r0_table)
    r1_tab = InterpolatedTable2D(temps_p, socs_p, params.r1_table)
    tau1_tab = InterpolatedTable2D(temps_p, socs_p, params.tau1_table)
    r2_tab = InterpolatedTable2D(temps_p, socs_p, params.r2_table)
    tau2_tab = InterpolatedTable2D(temps_p, socs_p, params.tau2_table)
    ocv_tab = InterpolatedTable2D(temps_p, socs_p, params.ocv_table)

    m_val = M_AUDIT["A1-007"].get(temp_c, params.hysteresis_amplitude_v)
    gamma = params.hysteresis_gamma  # 50.0 in calce_a123_v4.yaml
    eta = params.coulombic_efficiency

    # Simulate truth-driven cell model to provide exact prior RC and hysteresis states
    i1_truth = np.zeros(n, dtype=float)
    i2_truth = np.zeros(n, dtype=float)
    h_truth = np.zeros(n, dtype=float)
    v_model_truth = np.zeros(n, dtype=float)

    i1, i2, h = 0.0, 0.0, 0.0
    for k in range(n):
        dt = float(dt_arr[k]) if k > 0 else 1.0
        cur_t = float(temp_meas[k])
        cur_i = float(current_a[k])
        cur_z = float(truth_soc[k])

        r0 = r0_tab.lookup(cur_z, cur_t)
        r1 = r1_tab.lookup(cur_z, cur_t)
        r2 = r2_tab.lookup(cur_z, cur_t)
        tau1 = tau1_tab.lookup(cur_z, cur_t)
        tau2 = tau2_tab.lookup(cur_z, cur_t)
        ocv_v = ocv_tab.lookup(cur_z, cur_t)

        v_model_truth[k] = ocv_v + m_val * h - r1 * i1 - r2 * i2 - r0 * cur_i
        i1_truth[k] = i1
        i2_truth[k] = i2
        h_truth[k] = h

        i1 = Cell2RCModel.step_rc_current(i1, cur_i, dt, tau1)
        i2 = Cell2RCModel.step_rc_current(i2, cur_i, dt, tau2)
        h = Cell2RCModel.step_hysteresis(h, cur_i, dt, cap_c20, gamma, eta)

    return ScenarioDataSet(
        temp_c=temp_c,
        cell_id=cell_id,
        profile=profile,
        time_s=time_s,
        dt_arr=dt_arr,
        current_a=current_a,
        voltage_v=voltage_v,
        temp_measured_c=temp_meas,
        truth_soc=truth_soc,
        cap_c20=cap_c20,
        start_soc=start_soc,
        i1_truth=i1_truth,
        i2_truth=i2_truth,
        h_truth=h_truth,
        v_model_truth=v_model_truth,
        ocv_mono=v_ocv_mono,
    )


def init_estimator_state(
    estimator: Estimator,
    soc0: float,
    i1: float = 0.0,
    i2: float = 0.0,
    h: float = 0.0,
) -> None:
    """Reset estimator and initialize RC and hysteresis states if present in state vector."""
    estimator.reset(soc0)
    if hasattr(estimator, "x") and isinstance(estimator.x, np.ndarray):
        if len(estimator.x) >= 3:
            estimator.x[1] = float(i1)
            estimator.x[2] = float(i2)
        if len(estimator.x) >= 4:
            estimator.x[3] = float(h)


def run_stream_slice(
    estimator: Estimator,
    data: ScenarioDataSet,
    start_idx: int,
    end_idx: int,
    i_bias: float = 0.0,
    v_offset: float = 0.0,
) -> np.ndarray:
    """Feed measurement stream to estimator with optional sensor fault injection."""
    n_slice = end_idx - start_idx
    soc_est = np.zeros(n_slice, dtype=float)

    for step_idx, k in enumerate(range(start_idx, end_idx)):
        dt = float(data.dt_arr[k]) if k > 0 else 1.0
        v_in = float(data.voltage_v[k]) + v_offset
        i_in = float(data.current_a[k]) + i_bias
        meas = Measurement(
            v=v_in,
            i=i_in,
            temp_c=float(data.temp_measured_c[k]),
            dt=dt,
            dropout=False,
        )
        out = estimator.step(meas)
        soc_est[step_idx] = out.soc

    return soc_est


def evaluate_estimator_v2(
    estimator_factory: Callable[[ParamSet], Estimator],
    base_params: ParamSet,
    data: ScenarioDataSet,
) -> Dict[str, Any]:
    """Run full Gauntlet V2 scenario evaluation (S-A, S-B, S-C, S-F) for a single temperature."""
    n = len(data.time_s)

    # Pure Coulomb counting E0 uses temperature-scheduled Q(T)
    est_probe = estimator_factory(base_params)
    from soc.estimators.e0_coulomb import E0CoulombCounting
    if isinstance(est_probe, E0CoulombCounting):
        eval_params = replace(base_params, nominal_capacity_ah=data.cap_c20)
    else:
        eval_params = base_params

    # -----------------------------------------------------------------
    # S-A: Matched full profile from truth start
    # -----------------------------------------------------------------
    est_sa = estimator_factory(eval_params)
    init_estimator_state(est_sa, data.truth_soc[0], 0.0, 0.0, 0.0)
    soc_sa = run_stream_slice(est_sa, data, 0, n)
    err_sa_pp = (soc_sa - data.truth_soc) * 100.0
    rmse_sa_pp = float(np.sqrt(np.mean(err_sa_pp ** 2)))
    max_err_sa_pp = float(np.max(np.abs(err_sa_pp)))

    # -----------------------------------------------------------------
    # S-B: Mid-plateau windows with initial offsets
    # Starts at truth SOC 80, 60, 40, 20% with offsets -10, -5, +5, +10 pp (16 cases)
    # -----------------------------------------------------------------
    sb_target_socs = [0.80, 0.60, 0.40, 0.20]
    sb_offsets_pp = [-10.0, -5.0, +5.0, +10.0]
    sb_rmse_list = []
    sb_cases = []

    for z_target in sb_target_socs:
        cross_idx = np.where(data.truth_soc <= z_target)[0]
        if len(cross_idx) == 0:
            continue
        k0 = int(cross_idx[0])

        for off_pp in sb_offsets_pp:
            off_frac = off_pp / 100.0
            z_init = min(max(float(data.truth_soc[k0] + off_frac), 0.0), 1.0)
            est_sb = estimator_factory(eval_params)
            init_estimator_state(
                est_sb,
                soc0=z_init,
                i1=data.i1_truth[k0],
                i2=data.i2_truth[k0],
                h=data.h_truth[k0],
            )
            soc_sb = run_stream_slice(est_sb, data, k0, n)
            truth_window = data.truth_soc[k0:]
            err_sb_pp = (soc_sb - truth_window) * 100.0
            rmse_sb = float(np.sqrt(np.mean(err_sb_pp ** 2)))
            sb_rmse_list.append(rmse_sb)
            sb_cases.append({
                "target_soc": z_target,
                "offset_pp": off_pp,
                "rmse_pp": rmse_sb,
            })

    # -----------------------------------------------------------------
    # S-C: Partial windows with zero offset
    # 90->40%, 80->30%, 70->20% (3 cases)
    # -----------------------------------------------------------------
    sc_windows = [(0.90, 0.40), (0.80, 0.30), (0.70, 0.20)]
    sc_rmse_list = []
    sc_cases = []

    for z_start, z_end in sc_windows:
        idx_start = np.where(data.truth_soc <= z_start)[0]
        idx_end = np.where(data.truth_soc <= z_end)[0]
        if len(idx_start) == 0 or len(idx_end) == 0:
            continue
        k_s = int(idx_start[0])
        k_e = int(idx_end[0])
        if k_e <= k_s:
            continue

        est_sc = estimator_factory(eval_params)
        init_estimator_state(
            est_sc,
            soc0=data.truth_soc[k_s],
            i1=data.i1_truth[k_s],
            i2=data.i2_truth[k_s],
            h=data.h_truth[k_s],
        )
        soc_sc = run_stream_slice(est_sc, data, k_s, k_e)
        truth_window = data.truth_soc[k_s:k_e]
        err_sc_pp = (soc_sc - truth_window) * 100.0
        rmse_sc = float(np.sqrt(np.mean(err_sc_pp ** 2)))
        sc_rmse_list.append(rmse_sc)
        sc_cases.append({
            "window": f"{int(z_start*100)}->{int(z_end*100)}",
            "rmse_pp": rmse_sc,
        })

    # Composite S-B and S-C metric (19 total cases: 16 in S-B, 3 in S-C)
    sbc_all_rmses = sb_rmse_list + sc_rmse_list
    sbc_mean_rmse_pp = float(np.mean(sbc_all_rmses))

    # -----------------------------------------------------------------
    # S-F: Faults from known start (10 cases)
    # Current bias +-10, +-50 mA; Voltage offset +-5, +-10 mV; Capacity +-3%
    # -----------------------------------------------------------------
    sf_cases = []
    sf_rmse_list = []
    sf_max_err_list = []

    # Current biases
    for i_b in [-0.050, -0.010, +0.010, +0.050]:
        est_sf = estimator_factory(eval_params)
        init_estimator_state(est_sf, data.truth_soc[0], 0.0, 0.0, 0.0)
        soc_sf = run_stream_slice(est_sf, data, 0, n, i_bias=i_b)
        err = (soc_sf - data.truth_soc) * 100.0
        r = float(np.sqrt(np.mean(err ** 2)))
        m = float(np.max(np.abs(err)))
        sf_rmse_list.append(r)
        sf_max_err_list.append(m)
        sf_cases.append({"type": "current_bias", "val": i_b, "rmse_pp": r, "max_err_pp": m})

    # Voltage offsets
    for v_off in [-0.010, -0.005, +0.005, +0.010]:
        est_sf = estimator_factory(eval_params)
        init_estimator_state(est_sf, data.truth_soc[0], 0.0, 0.0, 0.0)
        soc_sf = run_stream_slice(est_sf, data, 0, n, v_offset=v_off)
        err = (soc_sf - data.truth_soc) * 100.0
        r = float(np.sqrt(np.mean(err ** 2)))
        m = float(np.max(np.abs(err)))
        sf_rmse_list.append(r)
        sf_max_err_list.append(m)
        sf_cases.append({"type": "voltage_offset", "val": v_off, "rmse_pp": r, "max_err_pp": m})

    # Capacity errors (+- 3%)
    for cap_err_ratio in [-0.03, +0.03]:
        p_cap = replace(eval_params, nominal_capacity_ah=eval_params.nominal_capacity_ah * (1.0 + cap_err_ratio))
        est_sf = estimator_factory(p_cap)
        init_estimator_state(est_sf, data.truth_soc[0], 0.0, 0.0, 0.0)
        soc_sf = run_stream_slice(est_sf, data, 0, n)
        err = (soc_sf - data.truth_soc) * 100.0
        r = float(np.sqrt(np.mean(err ** 2)))
        m = float(np.max(np.abs(err)))
        sf_rmse_list.append(r)
        sf_max_err_list.append(m)
        sf_cases.append({"type": "capacity_err", "val": cap_err_ratio, "rmse_pp": r, "max_err_pp": m})

    mean_rmse_sf_pp = float(np.mean(sf_rmse_list))
    worst_case_sf_pp = float(np.max(sf_max_err_list))

    return {
        "sa_rmse_pp": rmse_sa_pp,
        "sa_max_err_pp": max_err_sa_pp,
        "sb_mean_rmse_pp": float(np.mean(sb_rmse_list)),
        "sb_cases": sb_cases,
        "sb_rmses": sb_rmse_list,
        "sc_mean_rmse_pp": float(np.mean(sc_rmse_list)),
        "sc_cases": sc_cases,
        "sc_rmses": sc_rmse_list,
        "sbc_mean_rmse_pp": sbc_mean_rmse_pp,
        "sbc_all_rmses": sbc_all_rmses,
        "sf_mean_rmse_pp": mean_rmse_sf_pp,
        "sf_worst_err_pp": worst_case_sf_pp,
        "sf_cases": sf_cases,
    }
