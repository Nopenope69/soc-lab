# E5 v2 Observability-Gated EKF Verdict Report

## Executive Verdict

- **Overall Verdict**: **FAIL**
- **Best E5 v2 Configuration**: `CFG_V2_085`
  - $\sigma_{\text{ocv}}$: `0.02 V`
  - $\text{slope}_{\text{ref}}$: `0.2 V`
  - $\text{cap}_{\text{plateau}}$: `1e-05`
  - $\text{cap}_{\text{knee}}$: `0.01`

### Per-Rule Verdicts:
- **Rule 1 (Parity on Matched Scenarios)**: **PASS** (matched RMSE within 0.3 pp of E2 on t3, t4, t12, t5_knee_crossing, t6)
- **Rule 2 (Help Under Mismatch on Plateau)**: **FAIL** (RMSE at least 50% below E2 on t3 and t4 for +5 mV and -5 mV)
- **Rule 3 (Knee Crossing & Current Bias Boundaries)**: **FAIL** (t5 within 2 pp of E2; t6 mismatched within 0.5 pp of E0)
- **Rule 4 (Held-Out Generalization)**: **FAIL** (<= E2 + 0.3 pp in >= 90% runs; avg reduction >= 30% across mismatched runs)

> [!CAUTION]
> **E5 v2 did not achieve a full PASS across all four rules.** Per strict instructions, rules were not modified and no ad-hoc workarounds were applied.

## 1. Comparison Table: E0, E2, E5 v1 Best, and E5 v2 Best

Performance across the evaluation scenarios (mean RMSE in pp across tuning seeds 0 and 1):
- **E0**: Coulomb counting
- **E2**: Baseline 2RC EKF with hysteresis
- **E5 v1 Best**: `CFG_ABC_021` (fixed cap = 0.0002)
- **E5 v2 Best**: `CFG_V2_085` (observability cap: plateau=1e-05, knee=0.01)

| Scenario | Variant | E0 (pp) | E2 Baseline (pp) | E5 v1 Best (pp) | E5 v2 Best (pp) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **t3_bess_24h** | matched | 0.01 | 0.17 | 0.12 | 0.07 |
| **t3_bess_24h** | mismatch (-5 mV) | 0.88 | 9.40 | 4.20 | 4.36 |
| **t3_bess_24h** | mismatch (+5 mV) | 0.88 | 7.65 | 3.81 | 1.76 |
| **t4_plateau_stress** | matched | 0.00 | 0.58 | 0.30 | 0.18 |
| **t4_plateau_stress** | mismatch (-5 mV) | 0.50 | 30.68 | 3.08 | 16.06 |
| **t4_plateau_stress** | mismatch (+5 mV) | 0.50 | 30.27 | 3.12 | 14.61 |
| **t12_hysteresis_mismatch** | matched | 0.00 | 0.57 | 0.24 | 0.18 |
| **t12_hysteresis_mismatch** | mismatch (-5 mV) | 0.00 | 9.99 | 5.83 | 7.17 |
| **t12_hysteresis_mismatch** | mismatch (+5 mV) | 0.00 | 9.19 | 6.50 | 4.93 |
| **t5_knee_crossing** | matched | 10.00 | 0.45 | 3.40 | 0.64 |
| **t5_knee_crossing** | mismatch (-5 mV) | 9.48 | 3.80 | 4.46 | 3.91 |
| **t5_knee_crossing** | mismatch (+5 mV) | 9.48 | 1.56 | 3.47 | 1.74 |
| **t6_current_bias** | matched | 2.78 | 0.50 | 0.47 | 0.25 |
| **t6_current_bias** | mismatch (-5 mV) | 2.94 | 3.04 | 2.97 | 2.90 |
| **t6_current_bias** | mismatch (+5 mV) | 2.94 | 4.22 | 4.20 | 4.63 |

## 2. Detailed Audit of Pass Rules for Best E5 v2 Config

### Rule 1: Matched Parity (Threshold: within 0.30 pp of E2)
- **t3_bess_24h**: E5 v2 = `0.07` pp, E2 = `0.17` pp, Diff = `-0.10` pp -> **PASS**
- **t4_plateau_stress**: E5 v2 = `0.18` pp, E2 = `0.58` pp, Diff = `-0.40` pp -> **PASS**
- **t12_hysteresis_mismatch**: E5 v2 = `0.18` pp, E2 = `0.57` pp, Diff = `-0.39` pp -> **PASS**
- **t5_knee_crossing**: E5 v2 = `0.64` pp, E2 = `0.45` pp, Diff = `+0.19` pp -> **PASS**
- **t6_current_bias**: E5 v2 = `0.25` pp, E2 = `0.50` pp, Diff = `-0.24` pp -> **PASS**

### Rule 2: Mismatch Reduction on Plateau (Threshold: >= 50% below E2 on t3 and t4)
- **t3_bess_24h (-5 mV)**: E5 v2 = `4.36` pp, E2 = `9.40` pp, Reduction = `53.6%` -> **PASS**
- **t3_bess_24h (+5 mV)**: E5 v2 = `1.76` pp, E2 = `7.65` pp, Reduction = `77.0%` -> **PASS**
- **t4_plateau_stress (-5 mV)**: E5 v2 = `16.06` pp, E2 = `30.68` pp, Reduction = `47.7%` -> **FAIL**
- **t4_plateau_stress (+5 mV)**: E5 v2 = `14.61` pp, E2 = `30.27` pp, Reduction = `51.7%` -> **PASS**

### Rule 3: Knee Crossing & Current Bias Boundaries
- **t5_knee_crossing (matched)**: E5 v2 = `0.64` pp, E2 = `0.45` pp, |Diff| = `0.19` pp (target <= 2.0 pp) -> **PASS**
- **t5_knee_crossing (-5 mV)**: E5 v2 = `3.91` pp, E2 = `3.80` pp, |Diff| = `0.12` pp (target <= 2.0 pp) -> **PASS**
- **t5_knee_crossing (+5 mV)**: E5 v2 = `1.74` pp, E2 = `1.56` pp, |Diff| = `0.18` pp (target <= 2.0 pp) -> **PASS**
- **t6_current_bias (-5 mV)**: E5 v2 = `2.90` pp vs E0 = `2.94` pp, Diff = `-0.04` pp (target <= +0.50 pp) -> **PASS**
- **t6_current_bias (+5 mV)**: E5 v2 = `4.63` pp vs E0 = `2.94` pp, Diff = `+1.69` pp (target <= +0.50 pp) -> **FAIL**

### Rule 4: Held-Out Generalization Audit
- **Total Held-Out Evaluated Runs**: `357`
- **Runs with RMSE(E5) <= RMSE(E2) + 0.30 pp**: `331` / `357` (`92.7%`, target >= 90.0%) -> **PASS**
- **Average Error Reduction Across Held-Out Mismatches**: `10.1%` (target >= 30.0%) -> **FAIL**
- **Rule 4 Verdict**: ****FAIL****

## 3. Top 10 Configurations from Tuning Grid

| Rank | Config ID | $\sigma_{\text{ocv}}$ (V) | $\text{slope}_{\text{ref}}$ (V) | $\text{cap}_{\text{plat}}$ | $\text{cap}_{\text{knee}}$ | Rule 1 | Rule 2 | Avg Red (%) | Rule 3 | Penalty |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `CFG_V2_085` | 0.02 | 0.2 | 1e-05 | 0.01 | PASS | FAIL | 57.5% | FAIL | 14.22 |
| 2 | `CFG_V2_088` | 0.02 | 0.2 | 3e-05 | 0.01 | PASS | FAIL | 57.5% | FAIL | 14.23 |
| 3 | `CFG_V2_091` | 0.02 | 0.2 | 5e-05 | 0.01 | PASS | FAIL | 57.5% | FAIL | 14.24 |
| 4 | `CFG_V2_094` | 0.02 | 0.2 | 0.0001 | 0.01 | PASS | FAIL | 57.4% | FAIL | 14.27 |
| 5 | `CFG_V2_062` | 0.01 | 0.5 | 1e-05 | 0.02 | PASS | FAIL | 57.7% | FAIL | 14.31 |
| 6 | `CFG_V2_065` | 0.01 | 0.5 | 3e-05 | 0.02 | PASS | FAIL | 57.7% | FAIL | 14.31 |
| 7 | `CFG_V2_068` | 0.01 | 0.5 | 5e-05 | 0.02 | PASS | FAIL | 57.7% | FAIL | 14.32 |
| 8 | `CFG_V2_071` | 0.01 | 0.5 | 0.0001 | 0.02 | PASS | FAIL | 57.6% | FAIL | 14.35 |
| 9 | `CFG_V2_087` | 0.02 | 0.2 | 1e-05 | 0.05 | PASS | FAIL | 56.8% | FAIL | 14.58 |
| 10 | `CFG_V2_090` | 0.02 | 0.2 | 3e-05 | 0.05 | PASS | FAIL | 56.8% | FAIL | 14.58 |
