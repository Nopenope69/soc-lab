"""Stage V2: Component D4 (Adaptive Covariance Fading) Ablation.

Evaluates D4 configurations across up to 3 rounds against the Gauntlet V3 Keep Rule:
- Tuning temperatures: 20 C, 30 C on A1-007 DST
- Held-out temperatures: 40 C, 50 C on A1-007 and Set X (A1-008) DST
- Keep Rule: SBC improves by >= 3.0% on tuning temps (20, 30 C) on A1-007
  AND does not degrade on held-out temps (<= 1.0% degradation allowed on held-out SBC, 0% on S-A).
"""

from dataclasses import replace
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Tuple
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e7v3_d4 import E7V3D4Filter
from scripts.gauntlet_v3_scenarios import prepare_scenario_data_v3, evaluate_estimator_v3, ScenarioDataSet

TEMPS = [20, 25, 30, 40, 50]
CELLS = ["A1-007", "A1-008"]
TUNING_TEMPS = [20, 30]
HELDOUT_TEMPS = [40, 50]


def main():
    print("=" * 70)
    print("GAUNTLET V3 - STAGE V2 COMPONENT D4 ABLATION")
    print("=" * 70)

    t0 = time.time()
    out_dir = repo_root / "reports" / "gauntlet_v3"

    # 1. Load baseline results
    with open(out_dir / "baselines_results.json", "r") as f:
        baselines = json.load(f)

    e7v3_base = baselines["E7v3"]
    base_tuning_sbc = float(np.mean([e7v3_base["A1-007"][str(t)]["sbc_mean_rmse_pp"] for t in TUNING_TEMPS]))
    base_held_007_sbc = float(np.mean([e7v3_base["A1-007"][str(t)]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS]))
    base_held_008_sbc = float(np.mean([e7v3_base["A1-008"][str(t)]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS]))
    base_held_007_sa = float(np.mean([e7v3_base["A1-007"][str(t)]["sa_rmse_pp"] for t in HELDOUT_TEMPS]))
    base_held_008_sa = float(np.mean([e7v3_base["A1-008"][str(t)]["sa_rmse_pp"] for t in HELDOUT_TEMPS]))

    print(f"E7v3 Baseline Metrics:")
    print(f"  A1-007 Tuning SBC (20, 30 C): {base_tuning_sbc:.4f} pp")
    print(f"  A1-007 Held-out SBC (40, 50 C): {base_held_007_sbc:.4f} pp")
    print(f"  Set X Held-out SBC (40, 50 C): {base_held_008_sbc:.4f} pp")
    print(f"  A1-007 Held-out S-A: {base_held_007_sa:.4f} pp")
    print(f"  Set X Held-out S-A: {base_held_008_sa:.4f} pp")

    # 2. Pre-load datasets
    print("\nPreloading ScenarioDataSets...")
    datasets: Dict[Tuple[str, int], ScenarioDataSet] = {}
    for cell in CELLS:
        for temp in TEMPS:
            datasets[(cell, temp)] = prepare_scenario_data_v3(temp, "DST", cell)

    # 3. Define D4 Rounds (<= 3 rounds)
    rounds: List[Dict[str, Any]] = [
        {
            "round": 1,
            "name": "D4_R1_default",
            "desc": "k=3.0, N=60s, lambda_f=1.05/step, P_max=(10pp)^2, mode=step_factor",
            "tunings": {"d4_k": 3.0, "d4_duration_s": 60.0, "d4_lambda_f": 1.05, "d4_p_max": 0.01, "d4_mode": "step_factor"},
        },
        {
            "round": 2,
            "name": "D4_R2_fast",
            "desc": "k=2.0, N=30s, lambda_f=1.10/step, P_max=(10pp)^2, mode=step_factor",
            "tunings": {"d4_k": 2.0, "d4_duration_s": 30.0, "d4_lambda_f": 1.10, "d4_p_max": 0.01, "d4_mode": "step_factor"},
        },
        {
            "round": 3,
            "name": "D4_R3_direct_max",
            "desc": "k=3.0, N=60s, direct inflation P->min(P_max, (5pp)^2), mode=direct_max",
            "tunings": {"d4_k": 3.0, "d4_duration_s": 60.0, "d4_lambda_f": 1.0, "d4_p_max": 0.0025, "d4_mode": "direct_max"},
        },
    ]

    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)

    round_evals = []

    # 4. Run each round
    for r in rounds:
        print(f"\n--- Running Round {r['round']}: {r['name']} ---")
        p_cand = replace(base_params, **r["tunings"])

        cand_results = {"A1-007": {}, "A1-008": {}}
        for cell in CELLS:
            for temp in TEMPS:
                sc = datasets[(cell, temp)]
                res = evaluate_estimator_v3(lambda p: E7V3D4Filter(p_cand), p_cand, sc)
                cand_results[cell][str(temp)] = res
                print(f"  {cell} @ {temp:2d} C | SA: {res['sa_rmse_pp']:.3f} pp | SC: {res['sc_mean_rmse_pp']:.3f} pp | SG: {res['sg_mean_rmse_pp']:.3f} pp | SBC: {res['sbc_mean_rmse_pp']:.3f} pp")

        # Compute metrics
        tuning_sbc = float(np.mean([cand_results["A1-007"][str(t)]["sbc_mean_rmse_pp"] for t in TUNING_TEMPS]))
        held_007_sbc = float(np.mean([cand_results["A1-007"][str(t)]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS]))
        held_008_sbc = float(np.mean([cand_results["A1-008"][str(t)]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS]))
        held_007_sa = float(np.mean([cand_results["A1-007"][str(t)]["sa_rmse_pp"] for t in HELDOUT_TEMPS]))
        held_008_sa = float(np.mean([cand_results["A1-008"][str(t)]["sa_rmse_pp"] for t in HELDOUT_TEMPS]))

        tuning_gain_pct = ((base_tuning_sbc - tuning_sbc) / base_tuning_sbc) * 100.0
        held_007_deg_pct = ((held_007_sbc - base_held_007_sbc) / base_held_007_sbc) * 100.0
        held_008_deg_pct = ((held_008_sbc - base_held_008_sbc) / base_held_008_sbc) * 100.0
        sa_007_diff_pp = held_007_sa - base_held_007_sa
        sa_008_diff_pp = held_008_sa - base_held_008_sa

        pass_tuning = (tuning_gain_pct >= 3.0)
        pass_held_007 = (held_007_deg_pct <= 1.0)
        pass_held_008 = (held_008_deg_pct <= 1.0)
        pass_sa = (sa_007_diff_pp <= 0.0 and sa_008_diff_pp <= 0.0)

        keep = pass_tuning and pass_held_007 and pass_held_008 and pass_sa

        print(f"\nRound {r['round']} Verdict:")
        print(f"  Tuning Gain: {tuning_gain_pct:+.2f}% (req >= +3.0%) -> {'PASS' if pass_tuning else 'FAIL'}")
        print(f"  A1-007 Held-out SBC Delta: {held_007_deg_pct:+.2f}% (req <= +1.0%) -> {'PASS' if pass_held_007 else 'FAIL'}")
        print(f"  Set X Held-out SBC Delta: {held_008_deg_pct:+.2f}% (req <= +1.0%) -> {'PASS' if pass_held_008 else 'FAIL'}")
        print(f"  Held-out SA Delta: 007={sa_007_diff_pp:+.4f} pp, 008={sa_008_diff_pp:+.4f} pp (req <= 0.0) -> {'PASS' if pass_sa else 'FAIL'}")
        print(f"  DECISION: {'KEEP' if keep else 'DROP'}")

        round_evals.append({
            "round": r["round"],
            "name": r["name"],
            "desc": r["desc"],
            "tunings": r["tunings"],
            "tuning_sbc": tuning_sbc,
            "held_007_sbc": held_007_sbc,
            "held_008_sbc": held_008_sbc,
            "held_007_sa": held_007_sa,
            "held_008_sa": held_008_sa,
            "tuning_gain_pct": tuning_gain_pct,
            "held_007_deg_pct": held_007_deg_pct,
            "held_008_deg_pct": held_008_deg_pct,
            "sa_007_diff_pp": sa_007_diff_pp,
            "sa_008_diff_pp": sa_008_diff_pp,
            "pass_tuning": pass_tuning,
            "pass_held_007": pass_held_007,
            "pass_held_008": pass_held_008,
            "pass_sa": pass_sa,
            "decision": "KEEP" if keep else "DROP",
            "results": cand_results,
        })

    # 5. Overall Stage V2 Decision
    any_kept = any(r["decision"] == "KEEP" for r in round_evals)
    best_candidate = None
    if any_kept:
        kept_rounds = [r for r in round_evals if r["decision"] == "KEEP"]
        best_candidate = max(kept_rounds, key=lambda x: x["tuning_gain_pct"])
        stage_decision = "KEEP"
    else:
        stage_decision = "DROP"

    print("\n" + "=" * 70)
    print(f"STAGE V2 FINAL DECISION: {stage_decision}")
    print("=" * 70)

    # 6. Save JSON and Markdown report
    with open(out_dir / "d4_ablation_results.json", "w") as f:
        json.dump({
            "stage_decision": stage_decision,
            "best_candidate": best_candidate["name"] if best_candidate else None,
            "base_metrics": {
                "base_tuning_sbc": base_tuning_sbc,
                "base_held_007_sbc": base_held_007_sbc,
                "base_held_008_sbc": base_held_008_sbc,
                "base_held_007_sa": base_held_007_sa,
                "base_held_008_sa": base_held_008_sa,
            },
            "rounds": round_evals,
        }, f, indent=2)

    write_ablation_markdown(out_dir / "ablation.md", round_evals, stage_decision, base_tuning_sbc, base_held_007_sbc, base_held_008_sbc, base_held_007_sa, base_held_008_sa)
    print(f"Ablation report written to {out_dir / 'ablation.md'}")


def write_ablation_markdown(out_path, round_evals, stage_decision, base_tuning_sbc, base_held_007_sbc, base_held_008_sbc, base_held_007_sa, base_held_008_sa):
    lines = [
        "# Stage V2: Component D4 (Adaptive Covariance Fading) Ablation",
        "",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Dataset**: CALCE A123 DST (A1-007, Set X / A1-008)  ",
        f"**Stage Decision**: **{stage_decision}**  ",
        "",
        "---",
        "",
        "## 1. Keep Rule Criteria",
        "",
        "Per Gauntlet V3 Protocol (applied to composite SBC across S-B, S-C, S-G):",
        "- **Tuning SBC Improvement**: $\\ge 3.0\\%$ improvement on A1-007 tuning temperatures (20, 30 °C).",
        "- **Held-Out SBC Degradation**: $\\le 1.0\\%$ degradation allowed on held-out temperatures (40, 50 °C) on A1-007 and Set X.",
        "- **S-A Degradation**: $0.0\\%$ degradation allowed on S-A held-out RMSE.",
        "- **Action on Failure**: If no candidate satisfies the Keep Rule across $\\le 3$ rounds, DROP D4. Estimator continues as clean E7v3.",
        "",
        "---",
        "",
        "## 2. Baseline vs D4 Candidates Evaluation Table",
        "",
        "| Candidate / Round | Tuning SBC (pp) | Tuning Gain (%) | A1-007 Held SBC (pp) | Set X Held SBC (pp) | A1-007 Held SA (pp) | Set X Held SA (pp) | Verdict |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
        f"| **E7v3 Baseline** | {base_tuning_sbc:.4f} | -- | {base_held_007_sbc:.4f} | {base_held_008_sbc:.4f} | {base_held_007_sa:.4f} | {base_held_008_sa:.4f} | **BASELINE** |",
    ]

    for r in round_evals:
        lines.append(
            f"| **Round {r['round']} ({r['name']})** | {r['tuning_sbc']:.4f} | {r['tuning_gain_pct']:+.2f}% | {r['held_007_sbc']:.4f} ({r['held_007_deg_pct']:+.2f}%) | {r['held_008_sbc']:.4f} ({r['held_008_deg_pct']:+.2f}%) | {r['held_007_sa']:.4f} ({r['sa_007_diff_pp']:+.4f}) | {r['held_008_sa']:.4f} ({r['sa_008_diff_pp']:+.4f}) | **{r['decision']}** |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Detailed Round Analysis")
    lines.append("")

    for r in round_evals:
        lines.append(f"### Round {r['round']}: {r['name']}")
        lines.append(f"- **Configuration**: `{r['desc']}`")
        lines.append(f"- **Tuning SBC Gain**: `{r['tuning_gain_pct']:+.2f}%` (Gate requirement: $\\ge +3.0\\%$) -> **{'PASS' if r['pass_tuning'] else 'FAIL'}**")
        lines.append(f"- **A1-007 Held-Out SBC Delta**: `{r['held_007_deg_pct']:+.2f}%` (Gate limit: $\\le +1.0\\%$) -> **{'PASS' if r['pass_held_007'] else 'FAIL'}**")
        lines.append(f"- **Set X Held-Out SBC Delta**: `{r['held_008_deg_pct']:+.2f}%` (Gate limit: $\\le +1.0\\%$) -> **{'PASS' if r['pass_held_008'] else 'FAIL'}**")
        lines.append(f"- **Held-Out S-A Delta**: 007 = `{r['sa_007_diff_pp']:+.4f} pp`, Set X = `{r['sa_008_diff_pp']:+.4f} pp` (Gate limit: $\\le 0.0\\text{{ pp}}$) -> **{'PASS' if r['pass_sa'] else 'FAIL'}**")
        lines.append(f"- **Decision**: **{r['decision']}**")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 4. Stage V2 Conclusion")
    lines.append("")
    if stage_decision == "KEEP":
        lines.append(f"Component D4 is **KEPT**. Round candidate carries forward into Stage V3 composite tuning.")
    else:
        lines.append("Component D4 is **DROPPED**. Neither candidate achieved the required $\\ge 3.0\\%$ gain without violating held-out degradation constraints. Estimator E7v3 carries forward into Stage V3 in its pure form (confidence-aware reset + scheduled $Q(T)/M(T)$ + RLS adaptation + observability gating).")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
