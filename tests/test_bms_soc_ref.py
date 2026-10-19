"""Unit and verification tests for deliverable/bms_soc_ref.py.

Verifications:
1. AST import hygiene: strictly zero imports from soc.*, pydantic, yaml, numpy, scipy.
2. Bitwise/numerical precision agreement with repo E7V3CompositeFilter on DST (max |dSOC| <= 1e-9).
3. Confidence-aware reset behavior.
4. Per-step execution runtime limit (<= 5 ms).
"""

import ast
from dataclasses import replace
import math
from pathlib import Path
import sys
import time

import pytest
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from deliverable.bms_soc_ref import BmsSocEstimatorRef, BmsSocParameters
from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.models.plant import Measurement
from scripts.gauntlet_v3_scenarios import prepare_scenario_data_v3

ref_file = repo_root / "deliverable" / "bms_soc_ref.py"


def test_bms_soc_ref_has_zero_forbidden_imports():
    """Verify that bms_soc_ref.py imports ONLY standard library and zero soc.* or third-party packages."""
    assert ref_file.exists(), f"Deliverable file {ref_file} does not exist"

    with open(ref_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(ref_file))

    forbidden_prefixes = ["soc", "numpy", "scipy", "pandas", "yaml", "pydantic", "torch", "sklearn"]
    allowed_stdlib = {"bisect", "dataclasses", "math", "typing"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                assert mod in allowed_stdlib, f"Forbidden import found: {alias.name}"
                for forb in forbidden_prefixes:
                    assert not alias.name.startswith(forb), f"Forbidden import found: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                assert mod in allowed_stdlib, f"Forbidden from-import found: {node.module}"
                for forb in forbidden_prefixes:
                    assert not node.module.startswith(forb), f"Forbidden from-import found: {node.module}"


def test_bms_soc_ref_confidence_aware_reset():
    """Verify reset(soc0, soc_std) properly initializes state and covariance."""
    est = BmsSocEstimatorRef()

    # Known start (0.5 pp)
    est.reset(0.85, soc_std=0.005)
    assert est.x[0] == pytest.approx(0.85)
    assert est.p[0][0] == pytest.approx(0.005 ** 2)

    # Unknown start (10 pp)
    est.reset(0.50, soc_std=0.10)
    assert est.x[0] == pytest.approx(0.50)
    assert est.p[0][0] == pytest.approx(0.10 ** 2)

    # Default reset
    est.reset(0.70)
    assert est.x[0] == pytest.approx(0.70)
    assert est.p[0][0] == pytest.approx(0.10 ** 2)


def test_bms_soc_ref_agreement_with_repo_e7v3_on_dst():
    """Verify numerical equivalence between BmsSocEstimatorRef and repo E7V3CompositeFilter.

    Stage V6 criteria:
    - Single-step agreement: <= 1e-4 pp (1.0e-6 fractional SOC).
    - Final SOC on full DST (25k steps): <= 1e-3 pp (1.0e-5 fractional SOC).
    - Max trajectory discrepancy: <= 0.05 pp (5.0e-4 fractional SOC) due to 25k-step float accumulation.
    """
    sc = prepare_scenario_data_v3(20, profile="DST", cell_id="A1-007")

    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)
    frozen_params = replace(
        base_params,
        process_noise_q_soc=2.0e-09,
        process_noise_q_rc=1.1198164932559382e-05,
        process_noise_q_hysteresis=0.00017150882346504795,
        measurement_noise_r_v=0.0008610323423725228,
        e4_rls_forgetting_factor=0.9990,
        e5_slope_ref=0.20,
        e5_cap_plateau=2.0e-05,
        e5_cap_knee=0.01,
        e5_sigma_ocv_model_v=0.02,
    )

    repo_est = E7V3CompositeFilter(frozen_params)
    ref_est = BmsSocEstimatorRef()

    # 1. Single-step agreement test across various operating conditions
    max_single_step = 0.0
    for k in range(min(500, len(sc.time_s))):
        dt = float(sc.dt_arr[k]) if k > 0 else 1.0
        v = float(sc.voltage_v[k])
        i = float(sc.current_a[k])
        t = float(sc.temp_measured_c[k])

        repo_est.reset(0.5, 0.01)
        ref_est.reset(0.5, 0.01)
        out_repo = repo_est.step(Measurement(v=v, i=i, temp_c=t, dt=dt, dropout=False))
        out_ref = ref_est.step(v=v, i=i, temp_c=t, dt=dt)
        diff = abs(out_repo.soc - out_ref.soc)
        if diff > max_single_step:
            max_single_step = diff

    print(f"Max single-step |dSOC|: {max_single_step:.4e} ({max_single_step * 100:.4e} pp)")
    assert max_single_step <= 1.0e-12, f"Single-step diff {max_single_step} exceeds 1e-12!"

    # 2. Full DST 25,000-step simulation
    z0 = float(sc.truth_soc[0])
    std0 = float(sc.gap_pp / 100.0)
    repo_est.reset(z0, soc_std=std0)
    ref_est.reset(z0, soc_std=std0)

    max_dsoc = 0.0
    n = len(sc.time_s)

    for k in range(n):
        dt = float(sc.dt_arr[k]) if k > 0 else 1.0
        v = float(sc.voltage_v[k])
        i = float(sc.current_a[k])
        t = float(sc.temp_measured_c[k])

        meas = Measurement(v=v, i=i, temp_c=t, dt=dt, dropout=False)
        out_repo = repo_est.step(meas)
        out_ref = ref_est.step(v=v, i=i, temp_c=t, dt=dt)

        diff = abs(out_repo.soc - out_ref.soc)
        if diff > max_dsoc:
            max_dsoc = diff

    final_diff = abs(out_repo.soc - out_ref.soc)
    print(f"Full DST Max |dSOC|: {max_dsoc:.4e} ({max_dsoc * 100:.4e} pp)")
    print(f"Full DST Final |dSOC|: {final_diff:.4e} ({final_diff * 100:.4e} pp)")

    assert final_diff <= 1.0e-12, f"Final SOC diff {final_diff} exceeds 1e-12!"
    assert max_dsoc <= 1.0e-12, f"Accumulated trajectory diff {max_dsoc} exceeds 1e-12!"


def test_bms_soc_ref_runtime_limit():
    """Verify BmsSocEstimatorRef per-step runtime is <= 5.0 ms."""
    est = BmsSocEstimatorRef()
    est.reset(0.80, soc_std=0.005)

    n_steps = 1000
    t0 = time.perf_counter()
    for _ in range(n_steps):
        est.step(v=3.28, i=1.5, temp_c=25.0, dt=1.0)
    t_tot = time.perf_counter() - t0
    ms_per_step = (t_tot / n_steps) * 1000.0

    print(f"BmsSocEstimatorRef runtime: {ms_per_step:.4f} ms per step")
    assert ms_per_step <= 5.0, f"Runtime {ms_per_step} ms exceeds 5.0 ms limit"
