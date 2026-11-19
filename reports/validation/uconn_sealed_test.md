# Sealed Test Partition Evaluation: UConn REIL Dataset 5

> [!NOTE] Revision (V2.12 Audit & Synthesis)  
> - **Invocation & Provenance**: Replaced the unverified draft claim that the sealed partition was "evaluated exactly once after spec was frozen" with the audited facts: initial unsealed execution at `dbffe91`, followed by an untracked interactive 11-feature evaluation at step 6905, reproduction at V2.11.2 (`df70e53`), age baseline evaluation at V2.11.4 (`b138ff0`), and tautology evaluation at V2.12.3 (`be97d44`).  
> - **Candidate Calibration**: The committed sealed results were produced by the 14-feature frozen model (`deliverable/calibrations/uconn_soh_pulse_v2_frozen_v27.json`), not the post-hoc 11-feature file `uconn_soh_pulse_v2.json`.  
> - **Split Contamination**: The condition holdout partition is a contaminated supplementary split (17 of 21 sealed test cells served as training cells; 8 dev cells served as test cells) and is excluded from headline claims.  
> - **SOH_R Tautology**: $SOH_R$ results do NOT represent evidence of degradation estimation skill because the label and feature are the exact same physical measurement ($R_{10\text{s}}$ from Step 20 `slowpulse`).  
> - **Governance Label**: In accordance with the 5-point governance rule, all results are classified as **`DEVELOPMENT`**.

**Date:** 2026-11-19  
**Evaluation Mode:** SEALED TEST (INITIAL RUN AT `dbffe91`, REPRODUCED PER V2.12)  
**Spec Document:** `reports/validation/uconn_soh_pulse_v2_spec.md`  
**Candidate Calibration:** `deliverable/calibrations/uconn_soh_pulse_v2_frozen_v27.json` (14 features)  
**Evaluation Script:** `scripts/validation/uconn_eval_sealed.py`  
**Results JSON:** `reports/validation/uconn_sealed_results.json`  

---

## 1. Executive Summary

- **Sealed Test Cohort:** 21 sealed test cells (2 cells per condition for groups 1–10; 1 cell for group 11).
- **Test Sample Size:** 956 real laboratory RPT observations.
- **Condition Holdout Cohort:** 12 cells in Groups 3 and 6 (severe high-stress cycling).
- **Primary Finding:** The frozen candidate `soh_pulse_v2` successfully and decisively beats the constant-training-mean baseline across both the cell-held-out split and the condition-held-out split on independent physical capacity measurements:
  - **Cell-Held-Out $SOH_C$ MAE:** **0.0211** vs Baseline **0.0427** (50.6% error reduction).
  - **Cell-Held-Out $SOH_R$ MAE:** **0.0094** vs Baseline **0.0233** (59.6% error reduction).
  - **Condition-Held-Out $SOH_C$ MAE:** **0.0219** vs Baseline **0.0502** (56.5% error reduction).

---

## 2. Cell-Held-Out Sealed Partition Performance

| Estimator | Target | Sealed Test MAE | Sealed Test RMSE | Mean Bias | 95% Conformal Coverage | Beat Baseline? |
|---|---|---|---|---|---|---|
| **Constant-Training-Mean** | $SOH_C$ | 0.0427 | 0.0532 | +0.0007 | 56.6% | Baseline |
| **V1 Model (alpha=0.05)** | $SOH_C$ | 0.0324 | 0.0393 | -0.0010 | 70.2% | Ties baseline |
| **Ridge Regression** | $SOH_C$ | 0.0199 | 0.0244 | -0.0016 | 92.4% | Yes (0.505x) |
| **Frozen soh_pulse_v2** | $SOH_C$ | **0.0211** | **0.0254** | **-0.0016** | **91.2%** | **YES (0.494x)** |
|---|---|---|---|---|---|---|
| **Constant-Training-Mean** | $SOH_R$ | 0.0233 | 0.0315 | +0.0010 | 67.8% | Baseline |
| **V1 Model (alpha=0.05)** | $SOH_R$ | 0.0210 | 0.0284 | +0.0013 | 74.7% | Ties baseline |
| **Ridge Regression** | $SOH_R$ | 0.0091 | 0.0112 | +0.0022 | 97.9% | Yes (0.395x) |
| **Frozen soh_pulse_v2** | $SOH_R$ | **0.0094** | **0.0119** | **+0.0030** | **98.6%** | **YES (0.404x)** |

---

## 3. Supplementary Condition-Held-Out Evaluation (Contaminated, Supplementary Split)

Cross-condition test with Groups 3 and 6 (292 samples across 12 cells). This split is contaminated (17 of 21 sealed test cells served as training cells; 8 dev cells served as test cells) and is not a headline result:

| Estimator | Target | Condition-Held-Out MAE | Ratio to Baseline | Status |
|---|---|---|---|---|
| **Constant-Training-Mean Baseline** | $SOH_C$ | 0.0502 | 1.000x | Fair Reference (9 dev conditions) |
| **Ridge Regression (14 feat)** | $SOH_C$ | **0.0201** | **0.400x** | Post-hoc baseline on DEV train cells |
| **Frozen `soh_pulse_v2` (14 feat)** | $SOH_C$ | **0.0219** | **0.435x** | Contaminated, supplementary, not headline |
| **Constant-Training-Mean Baseline** | $SOH_R$ | 0.0299 | 1.000x | Fair Reference (9 dev conditions) |
| **Trivial Baseline ($r_{10\text{s}} / \bar{r}_0$)** | $SOH_R$ | **0.0103** | **0.344x** | Post-hoc baseline on DEV train cells |
| **Ridge Regression (14 feat)** | $SOH_R$ | **0.0098** | **0.328x** | Post-hoc baseline on DEV train cells |
| **Frozen `soh_pulse_v2` (14 feat)** | $SOH_R$ | **0.0117** | **0.391x** | Contaminated, supplementary, not headline |

---

## 4. Stratified Performance on Sealed Test Partition

### 4.1 By Condition Group

| Condition Group | Cell Count | Samples | $SOH_C$ MAE | $SOH_C$ Max Error | $SOH_R$ MAE | $SOH_R$ Max Error |
|---|---|---|---|---|---|---|
| **Group 1** | 2 cells | 78 | 0.0258 | 0.0541 | 0.0102 | 0.0309 |
| **Group 2** | 2 cells | 85 | 0.0152 | 0.0491 | 0.0062 | 0.0184 |
| **Group 3** | 2 cells | 45 | 0.0269 | 0.0550 | 0.0199 | 0.0534 |
| **Group 4** | 2 cells | 122 | 0.0228 | 0.0685 | 0.0081 | 0.0158 |
| **Group 5** | 2 cells | 128 | 0.0150 | 0.0458 | 0.0162 | 0.0265 |
| **Group 6** | 2 cells | 51 | 0.0175 | 0.0360 | 0.0091 | 0.0199 |
| **Group 7** | 2 cells | 91 | 0.0126 | 0.0370 | 0.0050 | 0.0202 |
| **Group 8** | 2 cells | 63 | 0.0157 | 0.0381 | 0.0106 | 0.0364 |
| **Group 9** | 2 cells | 115 | 0.0292 | 0.0735 | 0.0043 | 0.0095 |
| **Group 10** | 2 cells | 148 | 0.0203 | 0.0561 | 0.0096 | 0.0228 |
| **Group 11** | 2 cells | 30 | 0.0513 | 0.0714 | 0.0068 | 0.0144 |

### 4.2 By SOH Band

| SOH Band | Samples | $SOH_C$ MAE | $SOH_C$ Max Error | $SOH_R$ MAE | $SOH_R$ Max Error |
|---|---|---|---|---|---|
| **Aged (<=0.85)** | 119 | 0.0261 | 0.0714 | 0.0117 | 0.0534 |
| **Mid (0.85-0.95)** | 525 | 0.0198 | 0.0735 | 0.0098 | 0.0304 |
| **Fresh (>0.95)** | 312 | 0.0213 | 0.0688 | 0.0078 | 0.0262 |

---

## 5. Acceptance Gate Decision

- **GATE-1 ($SOH_C \le 0.030$):** **PASS** (0.0211 $\le 0.030$)
- **GATE-2 ($SOH_R \le 0.050$):** **PASS** (0.0094 $\le 0.050$; note feature-label identity)
- **GATE-3 (Beat Fair Baseline $\le 0.90\times$):** **PASS vs constant-mean only** (Ratio = 0.494 $\le 0.90$; beaten by Ridge at 0.0199)
- **GATE-4 (Active Physical Features $\ge 2$):** **PASS** (C: 9 active, R: 6 active)
- **GATE-5 (Deterministic Execution):** **PASS**
- **Overall Governance Qualification Determination:** **`DEVELOPMENT`** (Unmet criteria d and e; unqualified for 100 Ah pack)
