# Gauntlet State: CALCE A123 SOC Algorithm Development

**Status:** RUNNING  
**Current Stage:** Stage 1.5 (Component Development)  
**Last Completed Step:** Round C4 evaluated (e6v2 DROPPED)  
**Budget Used:**
- Configurations tested: 4 / 400
- Stage 1 Ladder iterations: 2 / 3 per rung (Rung 1 evaluated, Rung 2 fitted and passed)
- Component development rounds: 1 / 3 for C1, C2, C3, C4 (all evaluated)

## Active Estimator Reference
- Best estimator so far: **E2 Baseline** (BCD: 3.287 pp, S-A: 1.700 pp, S-F: 16.527 pp)

## Active Rules & Parameters
- **R1:** DST only for fitting, tuning, selection, and gate decisions in Stages 1 to 3. US06 and FUDS read ONLY in Stage 4 once after freeze.
- **R2:** All thresholds, ladders, bars, keep rules and budgets are strictly fixed.
- **R3:** Truth SOC = Coulomb-integrated from unmodified current, with start SOC = 1 - CV-taper gap(T) from `reports/diagnostics/d8_anchor_gap.csv` and temperature-scheduled capacity Q(T). Fault injection corrupts measurement stream only.
  - Script Guarantee Line: `truth_soc = start_soc - (np.cumsum(unmodified_current * dt) / (3600.0 * q_c20))`
- **R4:** 25 °C is suspect; reported in all tables, excluded from gate decisions, tuning, and selection. Decision temperatures: 20, 30, 40, 50 °C. Tuning: 20, 30 °C. Held-out selection: 40, 50 °C. Cell A1-008 for transfer checks only.
- **R5:** All numbers from saved scripts with logged commands. Commits on each stage/round with message `gauntlet <stage/round>: <result>`. New files get new names/suffixes (`_v3`, `e5v3`, `e6v2`, etc.). Existing estimators and parameter files are never overwritten.
- **R6:** E3, E4, E5 (e5v3), E6 (e6v2), E7 developed as new files. Must pass AST no-hardcoded-constants test and estimator isolation test.
- **R7:** Stop and write `FINAL.md` on data inconsistency, rule conflict, unfixable test failure, or budget exhaustion.

## Stage 1 Summary
- **Rung 1 (Current v2 parameters):** FAIL (|bias| <= 5 mV, RMSE <= 15 mV). Failed at 20 °C (+14.16 mV bias, 16.90 mV RMSE) and 30 °C (+9.49 mV bias, 11.94 mV RMSE).
- **Rung 2 (Residuals restricted to W-mid only):** PASS. Passed at all decision temperatures:
  - 20 °C: Bias = +0.48 mV, RMSE = 6.92 mV (PASS)
  - 25 °C (suspect): Bias = +0.35 mV, RMSE = 4.32 mV (PASS)
  - 30 °C: Bias = +0.54 mV, RMSE = 5.94 mV (PASS)
  - 40 °C: Bias = +0.49 mV, RMSE = 5.28 mV (PASS)
  - 50 °C: Bias = +0.55 mV, RMSE = 5.81 mV (PASS)
- **Ladder Exit:** Stopped at Rung 2. Rungs 3–5 bypassed per protocol.
- **Output Artifacts:**
  - `configs/assumptions/profiles/calce_a123_v3.yaml`
  - `reports/gauntlet/stage1_model_gate.csv`
  - `reports/gauntlet/stage1_model_gate.md`
  - `reports/gauntlet/stage1.log`
