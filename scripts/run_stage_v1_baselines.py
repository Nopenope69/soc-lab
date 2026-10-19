"""Stage V1 Baseline Evaluation Script.

Evaluates E0 (fair), E0 (oracle, Set X only), E1, E2, E7v2, and E7v3 across
all temperatures (20, 25, 30, 40, 50 C) on A1-007 and Set X (A1-008) DST.
"""

from dataclasses import replace
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import Estimator, ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.e7v2 import E7V2CompositeFilter
from soc.estimators.e7v3 import E7V3CompositeFilter
from scripts.gauntlet_v3_scenarios import prepare_scenario_data_v3, evaluate_estimator_v3, ScenarioDataSet

TEMPS = [20, 25, 30, 40, 50]
CELLS = ["A1-007", "A1-008"]


def main():
    print("=" * 70)
    print("GAUNTLET V3 - STAGE V1 BASELINE EVALUATION")
    print("=" * 70)

    t0_all = time.time()

    # 1. Load base configuration
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)

    # 2. Pre-generate datasets for all temperatures and cells
    print("\n[1/3] Preloading DST ScenarioDataSets...")
    datasets: Dict[Tuple[str, int], ScenarioDataSet] = {}
    for cell in CELLS:
        for temp in TEMPS:
            print(f"  Loading {cell} @ {temp} C DST...")
            datasets[(cell, temp)] = prepare_scenario_data_v3(temp, "DST", cell)

    # 3. Estimator definitions
    estimators: List[Tuple[str, Callable[[ParamSet], Estimator], bool]] = [
        ("E0_fair", lambda p: E0CoulombCounting(p), False),
        ("E0_oracle", lambda p: E0CoulombCounting(p), True),
        ("E1", lambda p: E1ExtendedKalmanFilter(p), False),
        ("E2", lambda p: E2EKFHysteresis(p), False),
        ("E7v2", lambda p: E7V2CompositeFilter(p), False),
        ("E7v3", lambda p: E7V3CompositeFilter(p), False),
    ]

    # 4. Run evaluations
    print("\n[2/3] Running Scenario Evaluations (S-A, S-B, S-C, S-G, S-F)...")
    results: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for est_name, factory, is_oracle in estimators:
        results[est_name] = {}
        for cell in CELLS:
            if est_name == "E0_oracle" and cell != "A1-008":
                continue  # Oracle E0 only distinct on Set X
            results[est_name][cell] = {}
            for temp in TEMPS:
                t_start = time.time()
                data = datasets[(cell, temp)]
                res = evaluate_estimator_v3(factory, base_params, data, is_oracle_e0=is_oracle)
                elapsed = time.time() - t_start
                results[est_name][cell][str(temp)] = res
                print(f"  {est_name:10s} | {cell} @ {temp:2d} C | SA: {res['sa_rmse_pp']:.3f} pp | SC: {res['sc_mean_rmse_pp']:.3f} pp | SG: {res['sg_mean_rmse_pp']:.3f} pp | SBC: {res['sbc_mean_rmse_pp']:.3f} pp | ({elapsed:.1f}s)")

    # 5. Save raw JSON results
    out_dir = repo_root / "reports" / "gauntlet_v3"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "baselines_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[3/3] Saved raw baseline results to {json_path}")

    # 6. Generate summary tables
    print("\nGenerating baselines.md summary...")
    generate_baselines_report(results, out_dir / "baselines.md", time.time() - t0_all)
    print(f"Baseline evaluation completed in {time.time() - t0_all:.1f} s.")


def generate_baselines_report(results: Dict[str, Any], out_path: Path, total_time_s: float):
    """Generate comprehensive markdown report comparing all baseline estimators."""
    lines = [
        "# Gauntlet V3 Baselines Report (Stage V1)",
        "",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Runtime**: {total_time_s:.1f} s  ",
        f"**Dataset**: CALCE A123 DST (A1-007 baseline, Set X / A1-008 cross-cell)  ",
        f"**Model**: `calce_a123_v4.yaml`  ",
        "",
        "---",
        "",
        "## 1. Overview and Core Verification Questions",
        "",
        "Stage V1 implements protocol changes P1 through P4:",
        "- **P1**: Temperature-scheduled capacity $Q(T)$ from D8 anchor gap across all estimators.",
        "- **P2**: Fair E0 on Set X evaluates with A1-007's $Q(T)$, while Oracle E0 uses A1-008's own $Q(T)$.",
        "- **P3**: Confidence-aware starts (`reset(soc0, soc_std)`): S-A and S-C use $\\max(0.5\\text{ pp}, \\text{CV-taper gap}(T))$, S-B uses $10\\text{ pp}$.",
        "- **P4**: Scenario S-G ('wrongly confident start') initializes at 80, 60, 40% with $\\pm 3, \\pm 5\\text{ pp}$ offsets and $P_{0,soc} = (0.5\\text{ pp})^2$.",
        "",
        "### Key Questions Answered:",
        "1. **Does E7v3 S-C drift drop compared to E7v2? By how much?**",
        "2. **Does S-G show whether D4 (adaptive covariance fading) is needed?**",
        "",
        "---",
        "",
        "## 2. Baseline Comparison Tables",
        "",
    ]

    # Decision temperatures: 20, 30, 40, 50 C. Held-out: 40, 50 C. Suspect: 25 C.
    decision_temps = ["20", "30", "40", "50"]
    heldout_temps = ["40", "50"]

    for cell in CELLS:
        lines.append(f"### Cell {cell} ({'Baseline' if cell == 'A1-007' else 'Set X / Cross-Cell'})")
        lines.append("")
        lines.append("| Estimator | S-A Held-out (pp) | S-B Mean (pp) | S-C Mean (pp) | S-G Mean (pp) | SBC Held-out (pp) | S-F Worst (pp) | 25 C SBC (pp) |")
        lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

        for est in results.keys():
            if est == "E0_oracle" and cell != "A1-008":
                continue
            r_cell = results[est][cell]

            sa_held = np.mean([r_cell[t]["sa_rmse_pp"] for t in heldout_temps])
            sb_held = np.mean([r_cell[t]["sb_mean_rmse_pp"] for t in heldout_temps])
            sc_held = np.mean([r_cell[t]["sc_mean_rmse_pp"] for t in heldout_temps])
            sg_held = np.mean([r_cell[t]["sg_mean_rmse_pp"] for t in heldout_temps])
            sbc_held = np.mean([r_cell[t]["sbc_mean_rmse_pp"] for t in heldout_temps])
            sf_worst = np.max([r_cell[t]["sf_worst_err_pp"] for t in decision_temps])
            sbc_25 = r_cell["25"]["sbc_mean_rmse_pp"]

            lines.append(
                f"| **{est}** | {sa_held:.3f} | {sb_held:.3f} | {sc_held:.3f} | {sg_held:.3f} | {sbc_held:.3f} | {sf_worst:.3f} | {sbc_25:.3f} |"
            )
        lines.append("")

    # Detailed per-temperature S-C comparison between E7v2 and E7v3
    lines.append("## 3. S-C Drift Analysis (E7v2 vs E7v3)")
    lines.append("")
    lines.append("| Cell | Temp (°C) | E7v2 S-C RMSE (pp) | E7v3 S-C RMSE (pp) | Absolute Reduction (pp) | % Drift Reduction |")
    lines.append("|:---:|:---:|:---:|:---:|:---:|:---:|")

    for cell in CELLS:
        for t in ["20", "25", "30", "40", "50"]:
            sc_v2 = results["E7v2"][cell][t]["sc_mean_rmse_pp"]
            sc_v3 = results["E7v3"][cell][t]["sc_mean_rmse_pp"]
            diff = sc_v2 - sc_v3
            pct = (diff / sc_v2) * 100.0 if sc_v2 > 0 else 0.0
            flag = " *(suspect)*" if t == "25" else ""
            lines.append(f"| {cell} | {t}{flag} | {sc_v2:.3f} | {sc_v3:.3f} | {diff:+.3f} | {pct:+.1f}% |")
    lines.append("")

    # Detailed S-G Analysis
    lines.append("## 4. S-G Analysis ('Wrongly Confident Start')")
    lines.append("")
    lines.append("Scenario S-G initializes with offsets $\\pm 3, \\pm 5\\text{ pp}$ at 80, 60, 40% SOC, but falsely sets $P_{0,soc} = (0.5\\text{ pp})^2$.")
    lines.append("")
    lines.append("| Cell | Temp (°C) | E0 S-G (pp) | E2 S-G (pp) | E7v2 S-G (pp) | E7v3 S-G (pp) | S-G Recovery Status |")
    lines.append("|:---:|:---:|:---:|:---:|:---:|:---:|:---|")

    for cell in CELLS:
        for t in ["20", "25", "30", "40", "50"]:
            sg_e0 = results["E0_fair"][cell][t]["sg_mean_rmse_pp"]
            sg_e2 = results["E2"][cell][t]["sg_mean_rmse_pp"]
            sg_v2 = results["E7v2"][cell][t]["sg_mean_rmse_pp"]
            sg_v3 = results["E7v3"][cell][t]["sg_mean_rmse_pp"]
            flag = " *(suspect)*" if t == "25" else ""
            status = "Recovers slowly / Plateau gated" if sg_v3 > 2.0 else "Fast recovery"
            lines.append(f"| {cell} | {t}{flag} | {sg_e0:.3f} | {sg_e2:.3f} | {sg_v2:.3f} | {sg_v3:.3f} | {status} |")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
