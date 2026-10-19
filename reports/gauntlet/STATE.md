# Gauntlet State: CALCE A123 SOC Algorithm Development

**Status:** NO-GO(estimator) (Finished & Verified Post-E0 Audit)  
**Current Stage:** Stage 2.5 Resolution - FINAL END OF RUN  
**Final Outcome:** NO-GO(estimator). Following E0 Fairness Audit, E0 was fixed in the scenario runner to use temperature-scheduled capacity Q(T). Re-evaluation of GATE 2 for frozen winner E7 confirmed identical failure on Clause (ii) individual case win rate: 30 / 38 cases = 78.95% vs mandatory >= 80.0% (short by 1 case). Stages 3 and 4 strictly bypassed. US06 and FUDS were not read in this run (they were development data read in earlier diagnostics).  
**Budget Used:**
- Configurations tested: 50 / 400 (6 in Stage 1.5, 44 in Stage 2)
- Stage 1 Ladder iterations: 2 / 3 per rung (Rung 1 evaluated, Rung 2 fitted and passed)
- Component development rounds: 1 / 3 for C1, C2, C3, C4, C5, C6 (all 6 completed and dropped)
- Wall clock time: < 3.5 hours (well within 16-hour limit)

## Active Estimator Reference
- Selected Standalone Estimator: **E2 (tune_2)** (Tune BCD: 2.351 pp, Held-out BCD: 2.578 pp, Held-out S-A: 1.209 pp, Held-out S-F Worst: 4.648 pp)

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

## Stage 2 Summary: Estimator Ladder & Tuning
- **Standalone Candidates Tested:** E0, E0_recal, E1, E2, E3, E4, e5v3, e6v2 (44 total configs).
- **Candidate Standings (Held-out BCD 40 & 50 °C):**
  - E0 baseline: 6.236 pp
  - E0_recal baseline: 6.236 pp
  - E1 baseline: 5.335 pp (Tune: 6.400 pp, S-A: 4.021 pp)
  - E2 (tune_2): 2.578 pp (Tune: 2.351 pp, S-A: 1.209 pp)
  - E3 (tune_6): 2.656 pp (Tune: 2.626 pp, S-A: 1.464 pp)
  - E4 (tune_6): 2.482 pp (Tune: 2.589 pp, S-A: 1.447 pp)
  - e5v3 (tune_1): 2.362 pp (Tune: 2.432 pp, S-A: 1.394 pp)
  - e6v2 (tune_2): 2.974 pp (Tune: 2.624 pp, S-A: 3.281 pp)
- **Selection Decision:** Under SELECTION RULE ("lowest held-out mean RMSE over S-B, S-C, S-D; ties within 0.5 pp go to the simpler estimator in the order E1 < E2 < E3 < E4 < e5v3 < e6v2"), `e5v3` was lowest at 2.362 pp; `E2 (tune_2)` at 2.578 pp was within 0.5 pp ($2.578 - 2.362 = 0.216\text{ pp} \le 0.5\text{ pp}$) and won on simplicity tie-break.
- **GATE 2 Evaluation on Selected Winner (E2 tune_2):**
  - Clause (i) S-A Non-Inferiority: win = 1.209 pp <= 5.918 pp (E0+5) and <= 5.021 pp (E1+1) -> **PASS**
  - Clause (ii) BCD Recovery: win = 2.578 pp <= 0.70*E0 (4.365 pp) -> PASS on mean; Individual case wins: 30 / 38 (78.9% vs >= 80.0% requirement) -> **FAIL**
  - Clause (iii) S-F Fault Robustness: win SF mean = 1.570 pp <= 7.013 pp (E0 SF mean + 5) -> **PASS**
  - Overall GATE 2: **FAIL** (triggers Stage 2.5 evaluation / Optional E7b residual consideration).
- **Hysteresis Ablation:** With M(T) BCD = 2.578 pp vs With M=0 BCD = 5.417 pp ($\Delta = -2.839\text{ pp}$, hysteresis strongly helps on DST).
- **Output Artifacts:**
  - `reports/gauntlet/stage2_ladder.csv`
  - `reports/gauntlet/stage2_ladder.md`
  - `reports/gauntlet/stage2_tuning_log.csv`
  - `reports/gauntlet/stage2.log`

## Stage 2.5 Summary: E7 Composite & Optional E7b
- **Candidate Filter:** E7 (core filter of winning standalone E2 tune_2; no Stage 1.5 components added because C1–C6 all failed the Keep Rule).
- **Runtime Benchmark:** 0.0740 ms/step (execution is 67x faster than the 5.0 ms/step limit). Static memory allocations: 4-state vector, 4x4 covariance matrix.
- **GATE 2 Verification on E7:**
  - Clause (i) Matched S-A: 1.209 pp <= E0 (5.918 pp) and <= E1 (5.021 pp) -> **PASS**
  - Clause (ii) S-B, S-C, S-D Recovery: Group mean RMSE = 2.578 pp <= 0.70 * E0 (4.365 pp) -> PASS. Individual case win rate: 30 / 38 cases = 78.9% (Threshold: >= 80.0%, 31/38 needed) -> **FAIL** (short by exactly 1 case).
  - Clause (iii) S-F Faults: Mean RMSE = 1.570 pp <= E0 + 5 pp (7.013 pp) -> **PASS**.
  - Overall Gate 2: **FAIL**.
- **Optional E7b (Learned Residual):**
  - Model: Ridge regression / shallow nonlinear residual trained on DST 20 & 30 °C.
  - Held-out Evaluation (40 & 50 °C): Relative improvement over E7 was +8.35% (peak +15.53% with extreme regularisation), failing the mandatory Keep Rule requirement of >= 20.0% relative improvement.
  - Result: E7b **DROPPED**.
- **Protocol Mandate Action:**
  - Per protocol: *"If E7 (or E7b) fails GATE 2: END as NO-GO(estimator). Report the gate breakdown, the failure mode, and whether the cause is unobservability, parameter error, or sensor error. Do not proceed."*
  - Stages 3 (Uncertainty Bar) and 4 (The Unseal) are strictly bypassed. US06 and FUDS were not read in this run (they were development data read in earlier diagnostics).
  - `deliverable/bms_soc_ref.py` is NOT written; instead, `reports/gauntlet/failure_analysis_design_note.md` documents the architectural and physical causes.
- **Output Artifacts:**
  - `scripts/stage2_5_e7.py`
  - `scripts/test_e7b_learned_residual.py`
  - `reports/gauntlet/stage2_5.log`
  - `reports/gauntlet/stage2_5_e7.csv`
  - `reports/gauntlet/stage2_5_e7.md`
  - `reports/gauntlet/failure_analysis_design_note.md`
