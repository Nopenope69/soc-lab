# Gauntlet V3 State: CALCE A123 SOC Algorithm Development (Confidence-Aware)

**Status:** IN_PROGRESS  
**Current Stage:** Stage V3 (Tuning and Gates)  
**Last Completed Step:** Stage V2: D4 Adaptive Fading Ablation (`reports/gauntlet_v3/ablation.md` - DROPPED)  
**Budget Used:**
- Configurations tested: 9 / 250
- Development rounds: D4: 3/3 (DROPPED)
- Wall clock time: 0.65h / 12h limit

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
  - Keep Rule: 0/3 rounds passed. **DROPPED**. E7v3 carries forward without D4.
- [ ] **Stage V3:** Tuning and Gates (A1-007 DST tuning, Gate A & Gate B evaluation)
- [ ] **Stage V4:** Freeze (`FROZEN_SPEC.md`)
- [ ] **Stage V5:** Single Unseal (US06 and FUDS)
- [ ] **Stage V6:** Deliverable & Final Report (`ALGORITHM_SPEC.md`, `deliverable/bms_soc_ref.py`, `FINAL_V3.md`)
