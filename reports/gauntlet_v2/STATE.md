# Gauntlet V2 State: CALCE A123 SOC Algorithm Development

**Status:** RUNNING  
**Current Stage:** Stage V2 (Component Development)  
**Last Completed Step:** Stage V2 Component D2: E4v2 (KEPT: Set X SBC -41.32%, A1-007 SBC -4.12%)  
**Budget Used:**
- Configurations tested: 2 / 300
- Development rounds: 1 / 3 for D1; 1 / 3 for D2; 0 / 3 for D3
- Wall clock time: 1.2h / 14h limit

---

## Active Rules & Parameters
- **R1:** DST only used for fitting, tuning, selection and gate decisions before the freeze. US06 and FUDS are development data (read in earlier diagnostics, not sealed); read ONLY in Stage V5, ONCE, after the freeze commit. After V5 nothing changed, retuned or rerun.
- **R2:** All thresholds, gates, keep rules, and budgets are strictly fixed.
- **R3:** Truth = Coulomb integral of UNMODIFIED current, start SOC = 1 - CV-taper gap(T) (`reports/diagnostics/d8_anchor_gap.csv`), temperature-scheduled C/20 capacity $Q(T)$ of THAT cell. E0 uses the same $Q(T)$ as the truth. Fault injection corrupts measurement stream only.
  - Script Guarantee Line: `truth_soc = start_soc - (np.cumsum(unmodified_current * dt) / (3600.0 * q_c20))`
- **R4:** 25 °C is suspect: reported everywhere, excluded from gate decisions, tuning and selection. Decision temperatures: 20, 30, 40, 50 °C. Tuning: 20, 30 °C. Held-out: 40, 50 °C.
- **R5:** Every number from a saved script run with command logged. Use timeouts and log files. Commits on each stage and round: `gauntlet2 <stage>: <result>`. New files get new names (suffix `_v4`, `e5v4`, etc.); never overwrite existing files or edit existing estimators.
- **R6:** Only components listed in Stage V2 may be developed, as new files (no external code, no earlier chat copy). AST no-hardcoded-constants test and estimator-isolation test must pass. Keep full test suite green. No learned or neural components in this run.
- **R7:** Stop and write `FINAL_V2.md` on data inconsistency, rule conflict, test failure needing threshold change, or budget exhausted.

---

## Stage Progress Log
- [x] **Stage V0:** Reconcile and Errata (`reports/gauntlet_v2/errata.md`)
- [x] **Stage V1:** Model Identifiability and Cross-Cell Calibration (`calce_a123_v4.yaml` chosen)
- [ ] **Stage V2:** Component Development (D1: e5v4, D2: E4v2, D3: Innovation Gating)
- [ ] **Stage V3:** Composite and Tuning (E7v2, GATE A & GATE B evaluation)
- [ ] **Stage V4:** Freeze (`reports/gauntlet_v2/FROZEN_SPEC.md`)
- [ ] **Stage V5:** Single Unseal (US06 and FUDS evaluation)
- [ ] **Stage V6:** Deliverable & Final Report (`reports/gauntlet_v2/ALGORITHM_SPEC.md`, `deliverable/bms_soc_ref.py`, `reports/gauntlet_v2/FINAL_V2.md`)
