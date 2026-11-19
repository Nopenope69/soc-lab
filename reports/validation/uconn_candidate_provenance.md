# UConn SOH Candidate Provenance and Feature Discrepancy Audit (Task V2.11)

> [!NOTE] Revision (V2.11)  
> Formal audit of calibration candidate versions, feature dimensionalities, sealed evaluation history, and artifact provenance across Task V2 steps.

**Document ID:** AUD-UCONN-PROV-001  
**Date:** 2026-11-19  
**Repository:** `/Users/tecbusiness/Desktop/random/SOC`  
**Branch:** `validation/uconn`  

---

## 1. Candidate Versions Across Git History

The calibration file `deliverable/calibrations/uconn_soh_pulse_v2.json` evolved across commits as follows:

| Git Commit | Step | SHA-256 Checksum | Number of Features | Number of $SOH_C$ Coeffs | Number of $SOH_R$ Coeffs |
|:---|:---:|:---:|:---:|:---:|:---:|
| `f592bc7` | **V2.7** | `efd71dc3f4d34698169250df6e62331add594087a37109f499a352df2795c095` | 14 | 14 | 14 |
| `dbffe91` | **V2.8** | `efd71dc3f4d34698169250df6e62331add594087a37109f499a352df2795c095` | 14 | 14 | 14 |
| `9f01f09` | **V2.9** | `d2e7ee280ed7e1ec50dd017e3c83d54f1b56ca023fe0f6a387c81fb45d61cca7` | 11 | 11 | 11 |

### 1.1 Detailed Feature Lists

1. **V2.7 (`f592bc7`) & V2.8 (`dbffe91`) [14 Features]:**
   - Feature List: `['r0_ohm', 'r1_ohm', 'c1_f', 'r2_ohm', 'c2_f', 'r_total_ohm', 'tau1_s', 'tau2_s', 'i_amplitude_a', 'temp_c', 'v_initial_v', 'delta_v_1s', 'delta_v_10s', 'r_10s_ohm']`
   - Intercepts: $SOH_C = 0.918993784$, $SOH_R = 0.987213839$
   - Number of non-zero coefficients: $SOH_C$ has 9 non-zero weights; $SOH_R$ has 5 non-zero weights.

2. **V2.9 (`9f01f09`) [11 Features]:**
   - Feature List: `['r0_ohm', 'r1_ohm', 'c1_f', 'r2_ohm', 'c2_f', 'r_total_ohm', 'tau1_s', 'tau2_s', 'i_amplitude_a', 'temp_c', 'v_initial_v']`
   - Omitted Features: `delta_v_1s`, `delta_v_10s`, `r_10s_ohm`
   - Intercepts: $SOH_C = 0.918993784$, $SOH_R = 0.987213839$
   - Number of non-zero coefficients: $SOH_C$ has 6 non-zero weights; $SOH_R$ has 5 non-zero weights.

---

## 2. Determination of Model Generating Committed Sealed Results

- **Committed Artifacts:** `reports/validation/uconn_sealed_results.json` and `reports/validation/uconn_sealed_test.md` were committed in **V2.8 (`dbffe91`)**.
- **Model Used:** At commit `dbffe91`, `deliverable/calibrations/uconn_soh_pulse_v2.json` had SHA-256 `efd71dc3f4d34698169250df6e62331add594087a37109f499a352df2795c095` (**14 features**).
- **Finding:** The committed sealed results in `reports/validation/uconn_sealed_results.json` and `uconn_sealed_test.md` were generated exclusively by the **14-feature model**, NOT the 11-feature model.

---

## 3. Session Log & Git Audit of Sealed Cell Evaluations

From git history and the session log (`transcript.jsonl`):

1. **Step V2.8 Execution:**
   - Candidate: 14-feature frozen model (`efd71dc3f4d3...`).
   - Evaluated against the 21 sealed test cells (956 RPT samples) and 2 condition-held-out groups (12 cells, 497 samples) via `scripts/validation/uconn_eval_sealed.py`.
   - Results committed in `dbffe91`.
2. **Step V2.9 Unsealed Modification & Second Evaluation:**
   - During step index 6905 in the session log, an interactive command evaluated a newly trained **11-feature model** on `reports/validation/uconn_sealed_features.csv` (the sealed test partition).
   - In step index 6906, the session log records the evaluation output:
     `11-feature model on SEALED test cells: SOH_C MAE = 0.0209 vs Baseline 0.0427 (Ratio = 0.490); SOH_R MAE = 0.0107 vs Baseline 0.0233 (Ratio = 0.461)`.
   - In step index 6907, `deliverable/calibrations/uconn_soh_pulse_v2.json` was rewritten with the 11-feature model parameters and committed in `9f01f09`.
   - **Conclusion:** A model was indeed evaluated on the sealed cells a second time in step index 6905 of the session log, and the calibration JSON was subsequently modified after unsealing.

---

## 4. Comprehensive Table of Candidate Evaluations on Sealed / Held-Out Data

| Session / Git Step | Candidate SHA-256 | Features | Evaluated Target Partition | Target | MAE | Baseline MAE | Status / Notes |
|:---|:---|:---:|:---|:---:|:---:|:---:|:---|
| **V2.8 (`dbffe91`)** | `efd71dc3f4d3...` | 14 | 21 Sealed Test Cells (956 RPTs) | $SOH_C$ | **0.0211** | 0.0427 | Pre-registered sealed run; committed in `dbffe91` |
| **V2.8 (`dbffe91`)** | `efd71dc3f4d3...` | 14 | 21 Sealed Test Cells (956 RPTs) | $SOH_R$ | **0.0094** | 0.0233 | Pre-registered sealed run; committed in `dbffe91` |
| **V2.8 (`dbffe91`)** | `efd71dc3f4d3...` | 14 | Groups 3 & 6 Condition Holdout (497 RPTs) | $SOH_C$ | **0.0219** | 0.0502 | Pre-registered condition holdout run |
| **V2.9 (Log step 6905)** | `d2e7ee280ed7...` | 11 | 21 Sealed Test Cells (956 RPTs) | $SOH_C$ | **0.0209** | 0.0427 | Post-hoc evaluation after unsealing; uncommitted script snippet |
| **V2.9 (Log step 6905)** | `d2e7ee280ed7...` | 11 | 21 Sealed Test Cells (956 RPTs) | $SOH_R$ | **0.0107** | 0.0233 | Post-hoc evaluation after unsealing; uncommitted script snippet |

---

## 5. Artifact Preservation & Relabeling

1. **V2.7 Frozen Artifact Extraction:**
   - File: `deliverable/calibrations/uconn_soh_pulse_v2_frozen_v27.json`
   - Extracted directly via `git show f592bc7:deliverable/calibrations/uconn_soh_pulse_v2.json`.
   - Verified SHA-256: `efd71dc3f4d34698169250df6e62331add594087a37109f499a352df2795c095`.
2. **Current 11-Feature File Relabeling:**
   - File: `deliverable/calibrations/uconn_soh_pulse_v2.json`
   - Label added: `"label": "post-hoc candidate (modified after unsealing)"`.
   - `"candidate_status": "post-hoc candidate (modified after unsealing)"`.
3. **C Header Provenance Warning:**
   - File: `deliverable/edge_pkg/soh_pulse_elasticnet_v2.h`
   - Added provenance warning header specifying that it was derived from the 11-feature post-hoc candidate, and that the pre-registered sealed results from the 14-feature model do not describe it.
