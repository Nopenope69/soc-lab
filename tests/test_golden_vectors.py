"""Verification test for deliverable/golden reference vectors."""

import csv
import math
from pathlib import Path
import sys
import pytest

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from deliverable.bms_soc_ref import BmsSocEstimatorRef
from deliverable.calibration import default_calce_calibration


def _verify_golden_csv(filename: str, soc0: float, soc_std: float):
    csv_path = repo_root / "deliverable" / "golden" / filename
    assert csv_path.exists(), f"Golden vector file {csv_path} does not exist"

    calib = default_calce_calibration()
    est = BmsSocEstimatorRef(calib)
    est.reset(soc0, soc_std=soc_std)

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            step = int(row["step"])
            dt = float(row["dt_s"])
            v = float(row["voltage_v"]) if row["voltage_v"] != "nan" else math.nan
            i = float(row["current_a"]) if row["current_a"] != "nan" else math.nan
            t = float(row["temp_c"]) if row["temp_c"] != "nan" else math.nan

            expected_soc = float(row["soc_est"])
            expected_std = float(row["soc_std"])
            expected_theta = float(row["theta"])
            expected_flags = row["status_flags"].split("|")

            out = est.step(v=v, i=i, temp_c=t, dt=dt)

            assert abs(out.soc - expected_soc) <= 1e-12, f"SOC mismatch at step {step}: {out.soc} vs {expected_soc}"
            assert abs(out.soc_std - expected_std) <= 1e-12, f"SOC std mismatch at step {step}: {out.soc_std} vs {expected_std}"
            assert abs(out.theta - expected_theta) <= 1e-8, f"Theta mismatch at step {step}: {out.theta} vs {expected_theta}"
            assert out.status_flags == expected_flags, f"Flags mismatch at step {step}: {out.status_flags} vs {expected_flags}"


def test_golden_dynamic_vectors():
    """Verify bit-identical reproduction of golden_synthetic_dynamic.csv."""
    _verify_golden_csv("golden_synthetic_dynamic.csv", soc0=0.85, soc_std=0.005)


def test_golden_dropouts_vectors():
    """Verify bit-identical reproduction of golden_synthetic_dropouts.csv."""
    _verify_golden_csv("golden_synthetic_dropouts.csv", soc0=0.70, soc_std=0.02)
