# Phase B2 Session Memory & Handoff Document

**Date:** October 19, 2026  
**Repository:** `/Users/tecbusiness/Desktop/random/SOC`  
**Git HEAD Commit:** `3aa460d` (preceding code commit `a32d96a`)  
**Working Tree Status:** Clean  
**Test Suite Status:** 125 passed in 345.63s (`reports/b2/test_run_b2.log`)  
**Phase Status:** Part A Complete; Part B Pre-Registration FROZEN pending human approval. Zero Phase B2 evaluations have been run.

---

## 1. Quick Resume Guide for New Chat

If resuming in a fresh session, read this document, [`reports/b2/B2_preregistration.md`](file:///Users/tecbusiness/Desktop/random/SOC/reports/b2/B2_preregistration.md), and [`reports/b2/b2_prep_summary.md`](file:///Users/tecbusiness/Desktop/random/SOC/reports/b2/b2_prep_summary.md).

### The Immediate Next Action Required:
1. **Awaiting Human Approval:** Review the pre-registration protocol in `reports/b2/B2_preregistration.md`.
2. **Approval Action:** Once the human reviewer confirms approval, update line 3 of `reports/b2/B2_preregistration.md` to:
   ```markdown
   **Pre-registration Status:** APPROVED
   ```
3. **Execution Command for Phase B2 Evaluation:**
   ```bash
   ./.venv/bin/python scripts/evaluate_calce.py --profile calce_a123_v2 --output reports/b2/calce_a123_b2_verdict.md
   ```
4. **Scoring:** Score the benchmark against the pre-registered numerical criteria in Section 6 of `B2_preregistration.md`.

---

## 2. Fundamental Data Status & Hard Rules

- **Verbatim Data Status:**
  ```text
  US06 and FUDS were read during diagnostics D3-D7 and the M=0 ablation. They are NO LONGER SEALED.
  They are development data. All parameter identification, tuning, variant selection and design decisions
  in this task must use DST only. US06 and FUDS may be used for reporting only after the pre-registration
  is frozen. A truly sealed test requires new data (FlexiPod or another LFP dataset) and is out of scope.
  ```
- **Rules Enforced:**
  1. No tuning or parameter selection using US06 or FUDS. All parameters fit on DST.
  2. Every number comes from a saved script run.
  3. No edits to existing estimators in `src/soc/estimators/` (except the `typing.Any` import fix).
  4. New parameter files use `_v2` suffix.
  5. Test suite runs with timeouts.

---

## 3. Key Diagnostic Findings Established in Part A

### A1b. Independent $R_0$ Measurement
- Script: `scripts/diagnostics/a1b_independent_r0.py` -> `reports/b2/a1b_independent_r0.md`
- Step-based $R_0$ from discrete 1-second current steps ($|\Delta I| \ge 1.0\text{ A}$) in DST Step 8:
  - **A1-007:** 20 °C: 0.1578 Ω, 25 °C: 0.1570 Ω, 30 °C: 0.1531 Ω, 40 °C: 0.1524 Ω, 50 °C: 0.1525 Ω.
  - **A1-008:** 20 °C: 0.1739 Ω, 25 °C: 0.1958 Ω, 30 °C: 0.1746 Ω, 40 °C: 0.1766 Ω, 50 °C: 0.2222 Ω.
- Matches old baseline $R_0$ within **1.0% to 2.1%** ($\text{ratio} = 1.014\text{ to }1.021$). Proves baseline $R_0$ was not inflated.
- Voltage dip at 3.85 A peak current predicted by step $R_0$ matches observation within **0.0 to 1.5 mV**.
- 25 °C OCV test run 3 months later (2012-09-05) with 5,097 s CV hold; marked as *"unexplained, treated as suspect"*. $M$ is not averaged.

### A1 Redo. Physical Hysteresis Amplitude $M(T)$
- Script: `scripts/diagnostics/a1_hysteresis_audit.py` -> `reports/b2/a1_hysteresis_audit.md`
- Plateau-median half-gap corrected for $2 \times 55\text{ mA} \times R_{0,\text{step}}$:
  - **A1-007:** 20 °C: **27.01 mV**, 25 °C: **17.19 mV** (suspect), 30 °C: **24.36 mV**, 40 °C: **21.55 mV**, 50 °C: **19.88 mV**.
  - **A1-008:** 20 °C: **24.38 mV**, 25 °C: **15.68 mV** (suspect), 30 °C: **21.94 mV**, 40 °C: **19.17 mV**, 50 °C: **14.56 mV**.
- Shift from old $R_0$ to independent $R_0$ is $< +0.18\text{ mV}$.
- Old scalar $M = 64.6\text{ mV}$ was 2.4x to 3.8x too large.

### A2. Re-Identification on DST
- Script: `scripts/identify_calce_params_v2.py`
- $R_0$ tight-bounded around $R_{0,\text{ind}}$ ($\pm 30\%$). Fitted $R_0$ moved only **+0.95% to +3.64%**.
- Diagnostic Variant 3: Free $M \in [0, 40\text{ mV}]$ changed DST fit RMSE by $< 0.28\text{ mV}$ while hitting 40 mV bound, proving dynamic cycles cannot distinguish hysteresis from diffusion.
- Profiles generated:
  - `configs/assumptions/profiles/calce_a123_v2.yaml`
  - `configs/assumptions/profiles/calce_a123_a1008_v2.yaml`
  - `configs/assumptions/profiles/calce_a123_v2_m0.yaml`
  - `configs/assumptions/profiles/calce_a123_a1008_v2_m0.yaml`

### A3. Cutoff Diagnosis & Open-Loop Gate
- Script: `scripts/diagnostics/a3_open_loop_and_estimators.py`
- **Cutoff Diagnosis:** Model never crosses 2.0 V on DST because cycler reached 2.0 V cutoff when Coulomb-counting truth SOC was still at 2.6% to 3.4% (where equilibrium OCV $> 2.50\text{ V}$) and OCV table floor is clamped at ~2.27 V (Causes b & d).
- **W-mid Gate (SOC 10–90% on DST):**
  - RMSE $\le 15.0\text{ mV}$ passed at all temperatures (7.39 to 13.39 mV).
  - $|\text{bias}| \le 5.0\text{ mV}$ failed at 20, 25, 30, 50 °C (+5.1 to +9.8 mV) due to global least-squares fitting balancing steep lower-knee errors.
- **E5 Variant Selection:** `E5 v2` achieved 5.83 pp DST median RMSE (vs 7.91 pp for `E5 v1`). `E5 v2` is selected as the primary variant.

### A4. Housekeeping Fixes
- `src/soc/estimators/registry.py`: Added `Any` to typing import. Verified with `test_registry_annotations_evaluate_cleanly`.
- `src/soc/harness/runner.py`: `pass_all_bars = None` and `"n/a"` for scenarios without bars.
- `src/soc/eval/report.py`: Enforced `t12_hysteresis_mismatch` bar (`t12_mismatch_rmse_rise_max: 0.015`).
- Cell designation standardized to `"A123 1.11 Ah LFP (APR18650M1A-class)"`.
- `scripts/evaluate_calce.py`: Variant selection updated to DST-only baseline; Rules 2 & 3 scored two-sided.

---

## 4. Pre-Registered Rules & Bars in B2

1. **Rule 1 (Operating Plateau Tracking):**
   $$\text{RMSE}_{\text{mid}} \le 6.0\text{ pp}$$
   for primary estimator `E5 v2` across gating temperatures on US06 and FUDS.
2. **Rule 2 (Two-Sided Non-Inferiority to Baseline E2):**
   $$|\text{RMSE}_{\text{mid}}(\text{E5 v2}) - \text{RMSE}_{\text{mid}}(\text{E2})| \le 1.0\text{ pp}$$
   in $\ge 80\%$ of gating runs.
3. **Rule 3 (Plateau Recovery from Offset):**
   On Scenario B2-T2 ($z_0 \in [0.20, 0.80]$ with $\Delta z_0 = \pm 10\text{ pp}$):
   $$\text{Error at } t = 600\text{ s} \le 3.0\text{ pp}$$
   $$\text{RMSE} < \text{RMSE}(\text{E0-sched}) \times 0.70$$
4. **Rule 4 (Cell Transfer Sanity):**
   $$\text{Transfer Ratio } \le 1.50\times$$
   $$\text{RMSE}(\text{Own Fit}) \le \text{RMSE}(\text{Transferred Fit}) \times 1.00$$
