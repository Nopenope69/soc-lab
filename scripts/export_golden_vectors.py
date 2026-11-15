#!/usr/bin/env python3
"""Export deterministic golden reference vectors for embedded C/C++/Rust BMS validation."""

import csv
import math
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from deliverable.bms_soc_ref import BmsSocEstimatorRef
from deliverable.calibration import default_calce_calibration


def generate_dynamic_profile():
    rows = []
    # 500 steps of dynamic current pulses and resting intervals
    t = 0.0
    for k in range(500):
        dt = 1.0
        t += dt
        temp_c = 25.0 + 5.0 * math.sin(k * 0.02)

        # Current duty cycle: discharge pulses, charge recovery, rests
        if k < 50:
            i = 0.0
            v = 3.32
        elif k < 150:
            i = 1.5 if (k % 10 < 6) else 0.0
            v = 3.28 - 0.05 * (i / 1.5)
        elif k < 250:
            i = -0.5 if (k % 20 < 10) else 0.5
            v = 3.30 - 0.03 * i
        elif k < 350:
            # Dynamic steps
            i = 2.0 * math.sin(k * 0.1)
            v = 3.25 - 0.02 * i
        else:
            i = 0.0
            v = 3.29

        rows.append({"k": k, "time_s": t, "dt_s": dt, "voltage_v": v, "current_a": i, "temp_c": temp_c})
    return rows


def generate_dropout_profile():
    rows = []
    t = 0.0
    for k in range(200):
        dt = 0.5
        t += dt
        temp_c = 22.0
        i = 1.0

        # Inject voltage dropouts between 40..50
        if 40 <= k < 50:
            v = math.nan
        # Inject current dropouts between 100..105
        elif 100 <= k < 105:
            i = math.nan
            v = 3.27
        # Inject temperature dropout between 150..155
        elif 150 <= k < 155:
            temp_c = math.nan
            v = 3.26
        else:
            v = 3.28 - 0.0002 * k

        rows.append({"k": k, "time_s": t, "dt_s": dt, "voltage_v": v, "current_a": i, "temp_c": temp_c})
    return rows


def export_vectors(profile_data, filename, soc0=0.80, soc_std=0.01):
    calib = default_calce_calibration()
    est = BmsSocEstimatorRef(calib)
    est.reset(soc0, soc_std=soc_std)

    out_path = REPO_ROOT / "deliverable" / "golden" / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "step",
            "time_s",
            "dt_s",
            "voltage_v",
            "current_a",
            "temp_c",
            "soc_est",
            "soc_std",
            "theta",
            "delta_soc_applied",
            "status_flags",
        ])

        for entry in profile_data:
            out = est.step(
                v=entry["voltage_v"],
                i=entry["current_a"],
                temp_c=entry["temp_c"],
                dt=entry["dt_s"],
            )
            writer.writerow([
                entry["k"],
                f"{entry['time_s']:.6f}",
                f"{entry['dt_s']:.6f}",
                f"{entry['voltage_v']:.16e}" if math.isfinite(entry["voltage_v"]) else "nan",
                f"{entry['current_a']:.16e}" if math.isfinite(entry["current_a"]) else "nan",
                f"{entry['temp_c']:.16e}" if math.isfinite(entry["temp_c"]) else "nan",
                f"{out.soc:.16e}",
                f"{out.soc_std:.16e}",
                f"{out.theta:.16e}",
                f"{out.delta_soc_applied:.16e}",
                "|".join(out.status_flags),
            ])

    print(f"Exported {len(profile_data)} golden vectors to {out_path}")


def main():
    print("Generating golden reference vectors...")
    dynamic_data = generate_dynamic_profile()
    export_vectors(dynamic_data, "golden_synthetic_dynamic.csv", soc0=0.85, soc_std=0.005)

    dropout_data = generate_dropout_profile()
    export_vectors(dropout_data, "golden_synthetic_dropouts.csv", soc0=0.70, soc_std=0.02)


if __name__ == "__main__":
    main()
