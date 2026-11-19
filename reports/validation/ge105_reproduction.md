# Gustave Eiffel 105 Ah LFP Evaluation Reproduction Report (V1.11)

> [!NOTE] Revision (V1.13 Capacity Sensitivity Script Tracking)  
> Tracked `scripts/validation/ge105_capacity_sensitivity.py` and added Section 4 verifying clean-shell reproduction of all 12 scenarios and per-file capacities in `reports/validation/ge105_capacity_sensitivity.md` with 0.00 pp discrepancy.

> [!NOTE] Revision (V1.12 Dev Reproducibility Clarification)  
> Documented that `scripts/validation/ge105_eval_dev.py` was recovered from the session transcript (step 5559) rather than an on-disk file existing at the time of V1.8, and clarified that the evidence demonstrating equivalence is matching outputs only.

> **Document ID:** REPRO-GE105-001  
> **Date:** 2026-11-19  
> **Status:** VERIFIED & REPRODUCED  
> **Scripts Tracked:**  
> - Dev partition evaluation: `scripts/validation/ge105_eval_dev.py`  
> - Sealed test partition evaluation: `scripts/validation/ge105_eval_test.py`  
> - Dev capacity sensitivity evaluation: `scripts/validation/ge105_capacity_sensitivity.py`  
> **Original Scratch Sources:**  
> - Scratch path: `/Users/tecbusiness/.gemini/antigravity/brain/8270f035-7beb-4f11-ba37-1a3b6b61035a/scratch/eval_test_cells.py`  
> - Backup copy: `/Users/tecbusiness/soc_backup/v1_scratch/eval_test_cells.py`  
> - Original SHA-256: `1507417106f269c35d1fd5f97a0dc709b3791447c8958b9812ca0ef411dd656c`  
> - Original timestamp: `2026-11-19 03:23:48` (local time)

---

## 1. Executive Summary

In Task V1.11 Item 1, the closed-loop evaluation scripts previously residing only in temporary scratch directories or session logs were recovered, audited, parameterized, and tracked into the repository under `scripts/validation/`.

Both scripts were executed from a clean shell using `.venv/bin/python`:
1. **Development Partition (`scripts/validation/ge105_eval_dev.py`):** Recovered from the session transcript (step 5559), not from a file that existed on disk at the time of the V1.8 run. The evidence showing it is the same code consists exclusively of matching outputs (the re-executed script matches the committed table in `reports/validation/ge105_closed_loop_dev.md` with 0.00 pp discrepancy across all 36 scenarios).
2. **Sealed Test Partition (`scripts/validation/ge105_eval_test.py`):** Parameterized from the original scratch script (`eval_test_cells.py`). Evaluated across 24 scenarios on cells `BUGE390` and `BUGE391`.
3. **Original Backup Scratch Verification:** The original, unedited backup script `/Users/tecbusiness/soc_backup/v1_scratch/eval_test_cells.py` was executed independently once from a clean shell.

### Key Finding:
- **Test Cells Reproduction:** Output of the tracked script `scripts/validation/ge105_eval_test.py`, the backup scratch script, and the committed table in `reports/validation/ge105_closed_loop_test.md` are **bit-for-bit identical (0.00 pp discrepancy across all 24 scenarios)**.
- **Dev Cells Reproduction:** Output of `scripts/validation/ge105_eval_dev.py` matches the committed table in `reports/validation/ge105_closed_loop_dev.md` with **0.00 pp discrepancy across all 36 scenarios**.

---

## 2. Sealed Test Partition Side-by-Side Comparison

Evaluation of cells `BUGE390` and `BUGE391` on dynamic WLTC segments (~90% and ~50% target SOC):

| Cell | Temp | Target SOC | Scenario | Initial Err | Committed E7 GE105 Max/RMSE (pp) | Tracked Script E7 GE105 Max/RMSE (pp) | Backup Scratch E7 GE105 Max/RMSE (pp) | Discrepancy | Committed Flags | Tracked Flags |
|:---|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **BUGE390** | 40 °C | ~90% | Nominal | +0.0 pp | 0.05 / 0.02 | 0.05 / 0.02 | 0.05 / 0.02 | **0.00 pp** | `['OK']` | `['OK']` |
| BUGE390 | 40 °C | ~90% | +10 pp | +10.0 pp | 8.92 / 4.95 | 8.92 / 4.95 | 8.92 / 4.95 | **0.00 pp** | `['OK']` | `['OK']` |
| BUGE390 | 40 °C | ~90% | -10 pp | -10.0 pp | 10.47 / 9.46 | 10.47 / 9.46 | 10.47 / 9.46 | **0.00 pp** | `['OK']` | `['OK']` |
| **BUGE390** | 40 °C | ~50% | Nominal | +0.0 pp | 0.06 / 0.02 | 0.06 / 0.02 | 0.06 / 0.02 | **0.00 pp** | `['OK']` | `['OK']` |
| BUGE390 | 40 °C | ~50% | +10 pp | +10.0 pp | 12.15 / 8.08 | 12.15 / 8.08 | 12.15 / 8.08 | **0.00 pp** | `['OK']` | `['OK']` |
| BUGE390 | 40 °C | ~50% | -10 pp | -10.0 pp | 10.01 / 8.17 | 10.01 / 8.17 | 10.01 / 8.17 | **0.00 pp** | `['OK']` | `['OK']` |
| **BUGE390** | 0 °C | ~90% | Nominal | +0.0 pp | 0.65 / 0.38 | 0.65 / 0.38 | 0.65 / 0.38 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| BUGE390 | 0 °C | ~90% | +10 pp | +10.0 pp | 9.00 / 1.70 | 9.00 / 1.70 | 9.00 / 1.70 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| BUGE390 | 0 °C | ~90% | -10 pp | -10.0 pp | 17.25 / 11.61 | 17.25 / 11.61 | 17.25 / 11.61 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| **BUGE390** | 0 °C | ~50% | Nominal | +0.0 pp | 1.00 / 0.41 | 1.00 / 0.41 | 1.00 / 0.41 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| BUGE390 | 0 °C | ~50% | +10 pp | +10.0 pp | 23.76 / 10.64 | 23.76 / 10.64 | 23.76 / 10.64 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| BUGE390 | 0 °C | ~50% | -10 pp | -10.0 pp | 20.00 / 9.41 | 20.00 / 9.41 | 20.00 / 9.41 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| **BUGE391** | 40 °C | ~90% | Nominal | +0.0 pp | 0.12 / 0.05 | 0.12 / 0.05 | 0.12 / 0.05 | **0.00 pp** | `['OK']` | `['OK']` |
| BUGE391 | 40 °C | ~90% | +10 pp | +10.0 pp | 9.00 / 5.06 | 9.00 / 5.06 | 9.00 / 5.06 | **0.00 pp** | `['OK']` | `['OK']` |
| BUGE391 | 40 °C | ~90% | -10 pp | -10.0 pp | 10.38 / 9.10 | 10.38 / 9.10 | 10.38 / 9.10 | **0.00 pp** | `['OK']` | `['OK']` |
| **BUGE391** | 40 °C | ~50% | Nominal | +0.0 pp | 0.14 / 0.06 | 0.14 / 0.06 | 0.14 / 0.06 | **0.00 pp** | `['OK']` | `['OK']` |
| BUGE391 | 40 °C | ~50% | +10 pp | +10.0 pp | 16.86 / 9.51 | 16.86 / 9.51 | 16.86 / 9.51 | **0.00 pp** | `['OK']` | `['OK']` |
| BUGE391 | 40 °C | ~50% | -10 pp | -10.0 pp | 10.09 / 8.22 | 10.09 / 8.22 | 10.09 / 8.22 | **0.00 pp** | `['OK']` | `['OK']` |
| **BUGE391** | 0 °C | ~90% | Nominal | +0.0 pp | 0.53 / 0.39 | 0.53 / 0.39 | 0.53 / 0.39 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| BUGE391 | 0 °C | ~90% | +10 pp | +10.0 pp | 9.00 / 1.45 | 9.00 / 1.45 | 9.00 / 1.45 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| BUGE391 | 0 °C | ~90% | -10 pp | -10.0 pp | 18.74 / 12.83 | 18.74 / 12.83 | 18.74 / 12.83 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| **BUGE391** | 0 °C | ~50% | Nominal | +0.0 pp | 0.87 / 0.35 | 0.87 / 0.35 | 0.87 / 0.35 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| BUGE391 | 0 °C | ~50% | +10 pp | +10.0 pp | 21.81 / 9.22 | 21.81 / 9.22 | 21.81 / 9.22 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |
| BUGE391 | 0 °C | ~50% | -10 pp | -10.0 pp | 15.20 / 8.33 | 15.20 / 8.33 | 15.20 / 8.33 | **0.00 pp** | `['OUT_OF_ENVELOPE']` | `['OUT_OF_ENVELOPE']` |

---

## 3. Development Partition Side-by-Side Comparison

Evaluation of cells `BUGE388` and `BUGE389` across 25 °C, 40 °C, and 0 °C:

| Cell | Temp | Target SOC | Scenario | Initial Err | Committed E7 GE105 Max/RMSE (pp) | Tracked Script E7 GE105 Max/RMSE (pp) | Discrepancy |
|:---|:---:|:---:|:---|:---:|:---:|:---:|:---:|
| **BUGE388** | 25 °C | 90% | Nominal | 0.0 pp | 2.82 / 1.90 | 2.82 / 1.90 | **0.00 pp** |
| BUGE388 | 25 °C | 90% | +10 pp | +10.0 pp | 9.00 / 4.94 | 9.00 / 4.94 | **0.00 pp** |
| BUGE388 | 25 °C | 90% | -10 pp | -10.0 pp | 11.51 / 9.67 | 11.51 / 9.67 | **0.00 pp** |
| **BUGE388** | 25 °C | 50% | Nominal | 0.0 pp | 15.36 / 5.48 | 15.36 / 5.48 | **0.00 pp** |
| BUGE388 | 25 °C | 50% | +10 pp | +10.0 pp | 10.75 / 6.22 | 10.75 / 6.22 | **0.00 pp** |
| BUGE388 | 25 °C | 50% | -10 pp | -10.0 pp | 10.05 / 7.57 | 10.05 / 7.57 | **0.00 pp** |
| **BUGE388** | 40 °C | 90% | Nominal | 0.0 pp | 3.05 / 1.19 | 3.05 / 1.19 | **0.00 pp** |
| BUGE388 | 40 °C | 90% | +10 pp | +10.0 pp | 9.00 / 5.04 | 9.00 / 5.04 | **0.00 pp** |
| BUGE388 | 40 °C | 90% | -10 pp | -10.0 pp | 10.50 / 9.28 | 10.50 / 9.28 | **0.00 pp** |
| **BUGE388** | 40 °C | 50% | Nominal | 0.0 pp | 9.56 / 3.02 | 9.56 / 3.02 | **0.00 pp** |
| BUGE388 | 40 °C | 50% | +10 pp | +10.0 pp | 12.44 / 7.98 | 12.44 / 7.98 | **0.00 pp** |
| BUGE388 | 40 °C | 50% | -10 pp | -10.0 pp | 9.98 / 8.00 | 9.98 / 8.00 | **0.00 pp** |
| **BUGE388** | 0 °C | 90% | Nominal | 0.0 pp | 11.10 / 7.75 | 11.10 / 7.75 | **0.00 pp** |
| BUGE388 | 0 °C | 90% | +10 pp | +10.0 pp | 9.00 / 4.32 | 9.00 / 4.32 | **0.00 pp** |
| BUGE388 | 0 °C | 90% | -10 pp | -10.0 pp | 16.81 / 11.32 | 16.81 / 11.32 | **0.00 pp** |
| **BUGE388** | 0 °C | 50% | Nominal | 0.0 pp | 25.43 / 11.60 | 25.43 / 11.60 | **0.00 pp** |
| BUGE388 | 0 °C | 50% | +10 pp | +10.0 pp | 25.40 / 12.73 | 25.40 / 12.73 | **0.00 pp** |
| BUGE388 | 0 °C | 50% | -10 pp | -10.0 pp | 20.60 / 9.89 | 20.60 / 9.89 | **0.00 pp** |
| **BUGE389** | 25 °C | 90% | Nominal | 0.0 pp | 2.97 / 2.12 | 2.97 / 2.12 | **0.00 pp** |
| BUGE389 | 25 °C | 90% | +10 pp | +10.0 pp | 8.93 / 4.83 | 8.93 / 4.83 | **0.00 pp** |
| BUGE389 | 25 °C | 90% | -10 pp | -10.0 pp | 11.79 / 10.27 | 11.79 / 10.27 | **0.00 pp** |
| **BUGE389** | 25 °C | 50% | Nominal | 0.0 pp | 10.64 / 3.31 | 10.64 / 3.31 | **0.00 pp** |
| BUGE389 | 25 °C | 50% | +10 pp | +10.0 pp | 9.61 / 5.50 | 9.61 / 5.50 | **0.00 pp** |
| BUGE389 | 25 °C | 50% | -10 pp | -10.0 pp | 10.07 / 7.76 | 10.07 / 7.76 | **0.00 pp** |
| **BUGE389** | 40 °C | 90% | Nominal | 0.0 pp | 3.09 / 1.22 | 3.09 / 1.22 | **0.00 pp** |
| BUGE389 | 40 °C | 90% | +10 pp | +10.0 pp | 9.00 / 5.00 | 9.00 / 5.00 | **0.00 pp** |
| BUGE389 | 40 °C | 90% | -10 pp | -10.0 pp | 10.52 / 9.27 | 10.52 / 9.27 | **0.00 pp** |
| **BUGE389** | 40 °C | 50% | Nominal | 0.0 pp | 9.70 / 3.17 | 9.70 / 3.17 | **0.00 pp** |
| BUGE389 | 40 °C | 50% | +10 pp | +10.0 pp | 12.17 / 7.79 | 12.17 / 7.79 | **0.00 pp** |
| BUGE389 | 40 °C | 50% | -10 pp | -10.0 pp | 10.10 / 8.20 | 10.10 / 8.20 | **0.00 pp** |
| **BUGE389** | 0 °C | 90% | Nominal | 0.0 pp | 13.24 / 8.03 | 13.24 / 8.03 | **0.00 pp** |
| BUGE389 | 0 °C | 90% | +10 pp | +10.0 pp | 9.00 / 3.91 | 9.00 / 3.91 | **0.00 pp** |
| BUGE389 | 0 °C | 90% | -10 pp | -10.0 pp | 18.81 / 12.31 | 18.81 / 12.31 | **0.00 pp** |
| **BUGE389** | 0 °C | 50% | Nominal | 0.0 pp | 23.40 / 10.11 | 23.40 / 10.11 | **0.00 pp** |
| BUGE389 | 0 °C | 50% | +10 pp | +10.0 pp | 25.43 / 12.23 | 25.43 / 12.23 | **0.00 pp** |
| BUGE389 | 0 °C | 50% | -10 pp | -10.0 pp | 15.85 / 9.01 | 15.85 / 9.01 | **0.00 pp** |

---

## 4. Development Capacity Sensitivity Reproduction

In Task V1.13, `scripts/validation/ge105_capacity_sensitivity.py` was tracked into the repository to reproduce every number in `reports/validation/ge105_capacity_sensitivity.md` directly from the repository code and data roots (`$SOC_DATA_DIR`).

The script was executed from a clean shell using:
```bash
.venv/bin/python scripts/validation/ge105_capacity_sensitivity.py
```

### 4.1 Per-File Capacity Reproduction (Section 2.1)
All 6 evaluated MAT files in the development partition (`BUGE388` and `BUGE389`) match bit-for-bit:

| Cell | Ambient Temp (°C) | Evaluated MAT File | Committed $Q_{\text{file}}$ (Ah) | Tracked Script $Q_{\text{file}}$ (Ah) | Discrepancy |
|:---|:---:|:---|:---:|:---:|:---:|
| `BUGE388` | 25 | `20230825_1333_full_25C_buge388_dattes.mat` | 105.042655 | 105.042655 | **0.000000 Ah** |
| `BUGE388` | 40 | `20231123_1349_full_40C_buge388_dattes.mat` | 103.847153 | 103.847153 | **0.000000 Ah** |
| `BUGE388` | 0 | `20230804_1122_full_0C_buge388_dattes.mat` | 103.664478 | 103.664478 | **0.000000 Ah** |
| `BUGE389` | 25 | `20230808_1242_full_25C_buge389_dattes.mat` | 105.750278 | 105.750278 | **0.000000 Ah** |
| `BUGE389` | 40 | `20230825_1339_full_40C_buge389_dattes.mat` | 104.276614 | 104.276614 | **0.000000 Ah** |
| `BUGE389` | 0 | `20230812_2136_full_0C_buge389_dattes.mat` | 103.031451 | 103.031451 | **0.000000 Ah** |

### 4.2 Scenario Metrics Side-by-Side Comparison (Section 3)
Evaluation of 12 nominal-initialisation development scenarios:

| Cell | Temp | Target SOC | Committed E0 Base Max/RMSE (pp) | Script E0 Base Max/RMSE (pp) | Committed E0 Sens Max/RMSE (pp) | Script E0 Sens Max/RMSE (pp) | Committed E7v3 Base Max/RMSE (pp) | Script E7v3 Base Max/RMSE (pp) | Committed E7v3 Sens Max/RMSE (pp) | Script E7v3 Sens Max/RMSE (pp) | Discrepancy |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `BUGE388` | 25 °C | ~90% | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 2.82 / 1.90 | 2.82 / 1.90 | 2.82 / 1.90 | 2.82 / 1.90 | **0.00 pp** |
| `BUGE388` | 25 °C | ~50% | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 15.36 / 5.48 | 15.36 / 5.48 | 15.36 / 5.48 | 15.36 / 5.48 | **0.00 pp** |
| `BUGE388` | 40 °C | ~90% | 0.04 / 0.02 | 0.04 / 0.02 | 0.00 / 0.00 | 0.00 / 0.00 | 3.05 / 1.19 | 3.05 / 1.19 | 3.08 / 1.20 | 3.08 / 1.20 | **0.00 pp** |
| `BUGE388` | 40 °C | ~50% | 0.04 / 0.02 | 0.04 / 0.02 | 0.00 / 0.00 | 0.00 / 0.00 | 9.56 / 3.02 | 9.56 / 3.02 | 9.75 / 3.10 | 9.75 / 3.10 | **0.00 pp** |
| `BUGE388` | 0 °C | ~90% | 0.05 / 0.03 | 0.05 / 0.03 | 0.00 / 0.00 | 0.00 / 0.00 | 11.10 / 7.75 | 11.10 / 7.75 | 11.10 / 7.73 | 11.10 / 7.73 | **0.00 pp** |
| `BUGE388` | 0 °C | ~50% | 0.05 / 0.03 | 0.05 / 0.03 | 0.00 / 0.00 | 0.00 / 0.00 | 25.43 / 11.60 | 25.43 / 11.60 | 25.49 / 11.66 | 25.49 / 11.66 | **0.00 pp** |
| `BUGE389` | 25 °C | ~90% | 0.03 / 0.01 | 0.03 / 0.01 | 0.00 / 0.00 | 0.00 / 0.00 | 2.97 / 2.12 | 2.97 / 2.12 | 2.97 / 2.12 | 2.97 / 2.12 | **0.00 pp** |
| `BUGE389` | 25 °C | ~50% | 0.03 / 0.01 | 0.03 / 0.01 | 0.00 / 0.00 | 0.00 / 0.00 | 10.64 / 3.31 | 10.64 / 3.31 | 10.53 / 3.26 | 10.53 / 3.26 | **0.00 pp** |
| `BUGE389` | 40 °C | ~90% | 0.03 / 0.01 | 0.03 / 0.01 | 0.00 / 0.00 | 0.00 / 0.00 | 3.09 / 1.22 | 3.09 / 1.22 | 3.11 / 1.23 | 3.11 / 1.23 | **0.00 pp** |
| `BUGE389` | 40 °C | ~50% | 0.03 / 0.01 | 0.03 / 0.01 | 0.00 / 0.00 | 0.00 / 0.00 | 9.70 / 3.17 | 9.70 / 3.17 | 10.05 / 3.31 | 10.05 / 3.31 | **0.00 pp** |
| `BUGE389` | 0 °C | ~90% | 0.07 / 0.04 | 0.07 / 0.04 | 0.00 / 0.00 | 0.00 / 0.00 | 13.24 / 8.03 | 13.24 / 8.03 | 13.23 / 8.52 | 13.23 / 8.52 | **0.00 pp** |
| `BUGE389` | 0 °C | ~50% | 0.07 / 0.04 | 0.07 / 0.04 | 0.00 / 0.00 | 0.00 / 0.00 | 23.40 / 10.11 | 23.40 / 10.11 | 24.15 / 10.46 | 24.15 / 10.46 | **0.00 pp** |
