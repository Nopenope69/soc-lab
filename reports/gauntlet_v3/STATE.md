# Gauntlet V3 State: CALCE A123 SOC Algorithm Development (Confidence-Aware)

**Status:** COMPLETED (END STATE: GO)  
**Current Stage:** Completed  
**Last Completed Step:** Stage V6: Deliverable and Final Report (`deliverable/bms_soc_ref.py`, `ALGORITHM_SPEC.md`, `FINAL_V3.md`)  
**Budget Used:**
- Configurations tested: 33 / 250
- Development rounds: D4: 3/3 (DROPPED)
- Wall clock time: 1.85h / 12h limit

---

## Active Rules & Protocol Parameters
- **R1:** DST only used for fitting, tuning, selection and gate decisions before freeze. US06 and FUDS are development data (read in earlier diagnostics, not sealed); read ONLY in Stage V5, ONCE, after freeze commit. After V5 nothing changed or rerun.
- **R2:** All thresholds, gates, keep rules, and budgets are strictly fixed.
- **R3:** Truth = Coulomb integral of UNMODIFIED current, start SOC = 1 - CV-taper gap(T) (`reports/diagnostics/d8_anchor_gap.csv`), temperature-scheduled C/20 capacity $Q(T)$ of THAT cell. E0 uses the same $Q(T)$ as the truth. Fault injection corrupts measurement stream only.
  - Script Guarantee Line: `truth_soc = start_soc - (np.cumsum(unmodified_current * dt) / (3600.0 * q_c20))`
- **R4:** 25 °C is suspect: reported everywhere, excluded from gate decisions, tuning and selection. Decision temperatures: 20, 30, 40, 50 °C. Tuning: 20, 30 °C. Held-out: 40, 50 °C.
- **R5:** Every number from a saved script run with command logged. Commits on each stage and round: `gauntlet3 <stage>: <result>`. New files get new names (suffix `_v5`, `e7v3`, etc.); never overwrite existing files or edit existing estimators.
- **R6:** AST no-hardcoded-constants test and estimator-isolation test must pass. Full test suite green at end of V3 and V5. No learned components.
- **R7:** Stop and write `FINAL_V3.md` on data inconsistency, rule conflict, test failure needing threshold change, or budget exhausted.

### Declared Protocol Changes (V3)
- **P1:** Scheduled capacity $Q(T)$ table across all estimators instead of fixed scalar capacity.
- **P2:** Fair E0 on Set X evaluated with A1-007 $Q(T)$ (oracle E0 with A1-008 $Q(T)$ reported separately).
- **P3:** Confidence-aware start via `reset(soc0, soc_std)`. S-A and S-C use `max(0.5 pp, CV-taper gap(T))`; S-B uses `10 pp`; S-G uses `0.5 pp` with wrong start.
- **P4:** New scenario S-G "wrongly confident start" (start 80, 60, 40%; offsets $\pm 3, \pm 5$ pp; `soc_std = 0.5 pp`).
- **P5:** $\gamma = 50.0$ for all runs (UNIDENTIFIED); report sensitivity in $\{1, 10, 50\}$.

---

## Stage Progress Log
- [x] **Stage V0:** Audits Before Any Change (`reports/gauntlet_v3/audit.md`)
  - (a) RLS direction confirmed: $\theta(t) > 1.0$ at all temps on Set X, tracks independent physical $R_0$ ratios.
  - (b) Variant test: Joint $R_0 + R_1$ wins on SBC (41.3% improvement on Set X). Kept.
  - (c) Deliverable audit: zero bad imports; lacks $Q(T)/M(T)$ tables and `reset(soc0, soc_std)`.
  - (d) $\tau_2$ bound audit: clamping degrades voltage RMSE & bias. Calibrated 600s model kept.
- [x] **Stage V1:** Implement P1 to P4 (`e7v3.py`, scenario builder v3, baselines)
  - E7v3 reduces S-C held-out drift by **-39.1%** on A1-007 (3.725 pp -> 2.270 pp) and **-34.1%** on Set X (4.638 pp -> 3.057 pp).
  - S-G baseline confirmed: E7v3 achieves 2.36 - 2.98 pp (better than E0 3.98 pp, but slow to breakout of false plateau lock).
- [x] **Stage V2:** Component D4 Adaptive Covariance Fading (`reports/gauntlet_v3/ablation.md`)
  - 3 rounds evaluated (default fading, fast breakout, direct max reset).
  - Findings: on flat LFP plateau, 3-5 pp SOC error produces 1.5-5 mV voltage error, which does not exceed $k \sqrt{S} \approx 71\text{ mV}$. Lowering $k$ caused false triggers on Set X (+17.7% degradation).
- [x] **Stage V3:** Tuning and Gates (`reports/gauntlet_v3/stage_v3_gates.md`)
  - Evaluated 24 configurations; selected `cand_cplat_2.0e-05` (q_soc=2e-9, cap_plat=2e-5).
  - Runtime: 0.0959 ms/step (<< 5.0 ms limit); array shapes fixed (4,) and (4,4).
  - GATE A (A1-007 held-out): **PASS** across all 5 clauses (S-A 1.32 pp, S-B 2.40 pp / 100% win rate, S-C 0.68/0.76 pp, S-G 2.63 pp, S-F 1.75 pp).
  - GATE B (Set X / A1-008): **PASS** across all 4 clauses at all 4 decision temps (20, 30, 40, 50 °C).
  - Overfitting gap: +0.046 pp (2.609 pp tuning vs 2.655 pp held-out).
- [x] **Stage V4:** Freeze (`reports/gauntlet_v3/FROZEN_SPEC.md`)
  - Full test suite verified green (205 passed in 375.17s).
  - SHA-256 hashes generated for all model profiles, tables, and scripts.
  - Frozen candidate: `cand_cplat_2.0e-05` (q_soc=2e-9, cap_plat=2e-5, ff=0.999, sl_ref=0.20).
- [x] **Stage V5:** Single Unseal (`reports/gauntlet_v3/stage_v5_unseal.md`)
  - Evaluated on US06 (highway dynamic) and FUDS (urban dynamic) across 20, 30, 40, 50 °C (25 °C reported).
  - US06: GATE A PASS, GATE B PASS.
  - FUDS: GATE A PASS, GATE B PASS.
  - VERDICT: **GO**.
- [x] **Stage V6:** Deliverable & Final Report (`ALGORITHM_SPEC.md`, `deliverable/bms_soc_ref.py`, `tests/test_bms_soc_ref.py`, `FINAL_V3.md` - END STATE: GO)

---

## VERIFICATION PASS (Post-Stage V6 Audit & Reconciliation)

- **Step 1 (Pre-Registered Gates Audit)**: Audited verbatim pre-registered gate clauses against saved JSON. Confirmed that all clauses of GATE A and GATE B pass across DST, US06, and FUDS at all decision temperatures (20, 30, 40, 50 °C). Mechanical end-state verdict: **GO**.
- **Step 2 (Baseline Table Reconciliation)**: Rebuilt Estimator Family Comparison table from `reports/gauntlet_v3/baselines_results.json`. Corrected E0 to fair start ($0.021\text{ pp}$ S-A, $0.048\text{ pp}$ S-C, $7.290\text{ pp}$ S-B, $3.979\text{ pp}$ S-G, $1.633\text{ pp}$ mean S-F). Clarified that legacy 5.918 pp was a Gauntlet V1 configuration artifact, mapped E1 correctly to 2RC EKF without hysteresis, and confirmed E0 non-zero S-F error due to current bias and capacity mismatch.
- **Step 3 (Case Counts & Pattern Audit)**: Verified case counts across all scenarios. S-B evaluated 16 cases/temp (32 cases on DST held-out 40/50 °C with 32/32 wins; 64 cases on US06/FUDS). Corrected copy-pasted Gate B win rates to true counts: US06 = 60/64 (93.8%), FUDS = 59/64 (92.2%). Verified near-constant S-C and S-G means across temperatures as genuine physical plateau dynamics.
- **Step 4 (Protocol Windows Computation)**: Recomputed sample-weighted error metrics for W-low ($<10\%$), W-mid ($10-90\%$), W-high ($>90\%$), and Plateau ($40-80\%$) across all 30 conditions in `reports/gauntlet_v3/verification/window_splits.json`. Verified exact reconstruction $\text{RMSE}_{\text{full}} = \sqrt{\sum N_w \text{RMSE}_w^2 / N_{\text{tot}}}$ to machine precision ($\le 4.44 \times 10^{-16}$). Commit: `233eec4`.
- **Step 5 (Reference Implementation Equivalence)**: Traced step 0 discrepancy between `deliverable/bms_soc_ref.py` and `E7V3CompositeFilter`. Identified root cause: `BmsSocParameters.coulombic_efficiency` defaulted to 1.0 instead of 0.998. Fixed default in `deliverable/bms_soc_ref.py` and proved float64 bit-level mathematical equivalence bounded by $\le 1.4 \times 10^{-16}$ across 25,000 steps. Tightened test suite assertions to $\le 10^{-12}$. All 209 repo tests green. Commit: `40a1722`.
- **Step 6 (v3.1 Spec and Report Corrections)**: Created `reports/gauntlet_v3/ALGORITHM_SPEC_v3.1.md` and `reports/gauntlet_v3/FINAL_V3_v3.1.md` incorporating recomputed window tables, clarified data boundaries (US06/FUDS development data, CALCE sub-zero existence vs exclusion), true Coulombic efficiency (0.998), CV-taper gap citations, and accurate D4 ablation summary. Commit: `d5eeaa4`.
- **Step 7 (Verification Summary)**: Produced comprehensive audit document `reports/gauntlet_v3/verification/VERIFICATION.md` detailing every threshold difference, discrepancy, file provenance, and the final mechanical **GO** verdict.

---

## CLOSE-OUT PASS (Table Integrity, Convergence, Drift, and Range Checks)

- **C1: Table Integrity Audit**: Verified all gate numbers against code and saved JSON. Verdict: **REPRODUCES**. Corrected report copy-paste errata (E1 achieved 8/16 wins with mean 7.157 pp, E2/E7v2 raw JSON values reconciled, E0 Oracle vs Fair analyzed, loss cases on US06/FUDS confirmed at 61/64 for A1-007, initial covariance setting audited).
- **C2: Convergence & Region Decomposition**: Analyzed 672 cases across DST, US06, and FUDS. S-B convergence time: median = 783.9 s (13.1 min), p90 = 3334.3 s (55.6 min); S-G convergence time: median = 2655.2 s (44.3 min), p90 = 4644.2 s (77.4 min); never-converged rate = 0.0%; mean end error = 0.627 pp. Plateau contributes 86.6% (S-B) and 78.5% (S-G) of variance reduction. Commit: `8dfa080`.
- **C3: Multi-Segment Drift**: Evaluated 9-hour continuous cycling workbooks across 56 conditions. E7v3 unanchored bounds final error to -0.85 pp (A1-007) and -1.18 pp (A1-008) under $\pm 20\text{ mA}$ sensor bias (vs E0 drift of -15.8 to -19.8 pp), achieving up to +18.9 pp drift reduction. Anchored variant completely clears drift each cycle. Commit: `5cd3bca`.
- **C4: Out-of-Range Temperatures**: Evaluated 10, 0, and -10 °C on A1-007. Computed D8 anchor gaps (10 °C: 3.490 pp, 0 °C: 0.391 pp, -10 °C: 0.143 pp). Documented performance degradation mechanisms (3.49 pp polarization gap at 10 °C, lower knee impedance rise at 0 °C, 4x impedance rise and voltage cutoff at -10 °C). Commit: `a5359af`.
- **C5: Document Updates**: Published `reports/gauntlet_v3/ALGORITHM_SPEC_v3.2.md` and `reports/gauntlet_v3/FINAL_V3_v3.2.md` incorporating all C1-C4 forensic results, ground truth caveats, and the 7-pillar field validation requirements. Commit: `99b53e2`.
- **Close-Out Report**: Generated master close-out document `reports/gauntlet_v3/closeout/CLOSEOUT.md`. Final end state: **GO (development-data validation on CALCE; not field-validated)**.

---

## FINAL CLOSE-OUT PASS (Ablation, Real Baseline Drift, Sub-20 C Gates, Final Docs)

- **F1: Component Ablation**: Evaluated 5 architectural variants (V-a to V-e) across 24 conditions (2 cells x 3 profiles x 4 temps). Identified simplest variant passing all Gate A clauses on A1-007 (V-c: confidence-aware reset + observability gate/cap) and proved that V-e (Frozen E7v3) is the ONLY variant passing Gate B across cells due to RLS impedance adaptation. Commit: `8eb2af6`.
- **F2: Drift with Real Baseline & No-Top-Knee Test**: Evaluated 9-hour continuous cycling with anchored/unanchored E0/E7v3 and isolated single discharge tests without top knees under 7 fault conditions. Proved that E7v3 recovers +2.5 to +6.5 pp of error in the lower knee over anchored E0, and confirmed plateau drift equivalence (-0.8 to -1.0 pp/hr) due to intentional observability gating. Commit: `c1860d2`.
- **F3: Sub-20 C Clause Table**: Evaluated all pre-registered Gate A clauses at 10, 0, and -10 C on A1-007 across DST, US06, and FUDS. Identified soft margin breaches at 10 C (3.49 pp CV-taper gap) and impedance-driven convergence delays at 0 and -10 C (2.6x to 4.5x R0 surge). Lowest temperature passing all clauses: None (certified envelope strictly 20 to 50 C). Commit: `e8a5b6f`.
- **F4: Final Documents Update**: Generated `reports/gauntlet_v3/ALGORITHM_SPEC_v3.3.md` and `reports/gauntlet_v3/FINAL_V3_v3.3.md` directly via `scripts/generate_final_documents.py` from saved JSON records. Verified S-B (0.626662 pp) and S-G (0.626626 pp) mean end errors to 6 decimal places and explained the 35.2 ppb residual. Commit: `b2e74f6`.
- **Final Master Closeout**: Produced `reports/gauntlet_v3/final/FINAL_CLOSEOUT.md`. Final End State: **GO (development-data validation on CALCE; not field-validated)**.


