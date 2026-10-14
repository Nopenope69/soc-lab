"""Diagnostic D9: Plateau quantification.

Quantifies dOCV/dSOC (mV per pp) for the identified OCV curve per gating temperature (20, 25, 30, 40, 50 C).
Outputs:
- SOC ranges where dOCV/dSOC < 0.5 mV/pp and < 1.0 mV/pp.
- Implied SOC error (pp) resulting from a 5 mV voltage error across the plateau.
- Plot: reports/diagnostics/d9_docv_dsoc.png
- Summary table CSV: reports/diagnostics/d9_plateau_summary.csv
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.models.tables import InterpolatedTable2D
from scripts.evaluate_calce import build_param_sets

GATING_TEMPS = [20, 25, 30, 40, 50]

def run_d9():
    print("=== D9. Plateau Quantification ===\n")
    reports_dir = repo_root / "reports" / "diagnostics"
    reports_dir.mkdir(parents=True, exist_ok=True)

    param_sets = build_param_sets("calce_a123")
    base_params = param_sets["E2"]

    temps = list(base_params.temperatures_c)
    socs = list(base_params.soc_grid)
    ocv_table = InterpolatedTable2D(temps, socs, base_params.ocv_table)

    # Dense SOC evaluation grid from 0.01 to 0.99 (step 0.005)
    dense_soc = np.linspace(0.01, 0.99, 491)

    summary_rows = []

    fig, ax = plt.subplots(figsize=(10, 6))

    for temp in GATING_TEMPS:
        docv_dz_arr = np.array([ocv_table.derivative_soc(z, float(temp)) for z in dense_soc])
        # Convert derivative to mV per pp:
        # docv/dz is Volts per unit SOC.
        # 1 unit SOC = 100 pp. 1 V = 1000 mV.
        # docv/d(pp) in mV/pp = (docv/dz * 1000) / 100 = 10 * docv/dz.
        docv_dpp_mv = docv_dz_arr * 10.0

        # Mask < 0.5 mV/pp and < 1.0 mV/pp
        mask_05 = docv_dpp_mv < 0.5
        mask_10 = docv_dpp_mv < 1.0

        def get_continuous_ranges(mask, x):
            if not np.any(mask):
                return "None"
            ranges = []
            in_range = False
            start_x = None
            for i, val in enumerate(mask):
                if val and not in_range:
                    in_range = True
                    start_x = x[i]
                elif not val and in_range:
                    in_range = False
                    ranges.append((start_x, x[i-1]))
            if in_range:
                ranges.append((start_x, x[-1]))
            return "; ".join([f"[{r[0]*100:.1f}%, {r[1]*100:.1f}%]" for r in ranges])

        range_05_str = get_continuous_ranges(mask_05, dense_soc)
        range_10_str = get_continuous_ranges(mask_10, dense_soc)

        # Implied SOC error for a 5 mV voltage residual:
        # err_pp = 5.0 mV / (dOCV/dpp mV/pp)
        # Compute min, median, max implied error in the < 1.0 mV/pp region
        if np.any(mask_10):
            slopes_in_plat = docv_dpp_mv[mask_10]
            implied_err_pp = 5.0 / slopes_in_plat
            min_implied = float(np.min(implied_err_pp))
            med_implied = float(np.median(implied_err_pp))
            max_implied = float(np.max(implied_err_pp))
        else:
            min_implied = med_implied = max_implied = float("nan")

        min_slope = float(np.min(docv_dpp_mv))

        summary_rows.append({
            "Temp (C)": temp,
            "Min Slope (mV/pp)": min_slope,
            "SOC Range < 0.5 mV/pp": range_05_str,
            "SOC Range < 1.0 mV/pp": range_10_str,
            "Implied 5mV Err: Median (pp)": med_implied,
            "Implied 5mV Err: Max (pp)": max_implied,
        })

        ax.plot(dense_soc * 100.0, docv_dpp_mv, label=f"{temp}°C (min: {min_slope:.2f} mV/pp)")

    df = pd.DataFrame(summary_rows)
    print("--- Plateau Slope & Implied SOC Error Summary ---")
    print(df.to_string(index=False))

    csv_out = reports_dir / "d9_plateau_summary.csv"
    df.to_csv(csv_out, index=False)
    print(f"\nSaved plateau summary to: {csv_out}")

    ax.axhline(0.5, color="red", linestyle=":", label="0.5 mV/pp threshold")
    ax.axhline(1.0, color="orange", linestyle="--", label="1.0 mV/pp threshold")
    ax.set_title("dOCV/dSOC (mV per pp) across Gating Temperatures")
    ax.set_xlabel("State of Charge (%)")
    ax.set_ylabel("Slope dOCV/dSOC (mV / pp)")
    ax.set_xlim(100, 0)  # Inverted
    ax.set_ylim(0, 15)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right")

    fig.tight_layout()
    png_out = reports_dir / "d9_docv_dsoc.png"
    fig.savefig(png_out, dpi=150)
    plt.close(fig)
    print(f"Saved plateau slope plot to: {png_out}")

if __name__ == "__main__":
    run_d9()
