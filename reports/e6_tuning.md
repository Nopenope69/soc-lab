# E6 Tuning & Pass/Fail Verdict Report

## Executive Verdict

- **Overall Verdict**: **FAIL**
- **Rule 1 (Do No Harm)**: **FAIL** (matched RMSE within 0.3 pp of E2)
- **Rule 2 (Help Under Mismatch)**: **FAIL** (RMSE below E2 on all scenarios, avg reduction >= 20%)
- **Rule 3 (Sanity)**: **FAIL** (theta settles with correct sign to counteract injected offset)

> [!CAUTION]
> **No configuration passed all three rules.** Per instructions, no further fixes or rule modifications are attempted.

## 1. Top 5 Configurations Ranked by Worst-Case Deviation

| Rank | Config ID | $Q_\theta$ | $R_\theta$ | $\sigma_0(\theta)$ | Rule 1 | Rule 2 | Avg Red. (%) | Rule 3 | Overall | Penalty |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `CFG_021` | 1.0e-09 | 1.0e-04 | 0.002 | FAIL | FAIL | -1.0% | FAIL | **FAIL** | 95.06 |
| 2 | `CFG_013` | 1.0e-10 | 1.0e-04 | 0.002 | FAIL | FAIL | -4.5% | FAIL | **FAIL** | 99.84 |
| 3 | `CFG_005` | 1.0e-12 | 1.0e-04 | 0.002 | FAIL | FAIL | -8.5% | FAIL | **FAIL** | 104.37 |
| 4 | `CFG_017` | 1.0e-09 | 2.5e-05 | 0.002 | FAIL | FAIL | -8.4% | FAIL | **FAIL** | 106.19 |
| 5 | `CFG_009` | 1.0e-10 | 2.5e-05 | 0.002 | FAIL | FAIL | -5.0% | FAIL | **FAIL** | 108.71 |

## 2. Side-by-Side Comparison for Best Configuration

**Best Configuration (`CFG_021`) Tunings**:
- `filter.rbc_q_theta`: `1.0e-09`
- `filter.rbc_r_theta`: `1.0e-04`
- `filter.rbc_initial_theta_std`: `0.002`

| Scenario | Variant | Metric | E2 (Baseline) | E6 (`flag=true`) | E6 (`flag=false`) | E1 (Reference) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **t3_bess_24h** | matched | RMSE (pp) | 0.17 | 3.73 | 4.67 | 5.91 |
| **t3_bess_24h** | mismatch (-5 mV) | RMSE (pp) | 9.40 | 13.44 | 9.51 | 6.08 |
| **t3_bess_24h** | mismatch (+5 mV) | RMSE (pp) | 7.65 | 6.40 | 4.44 | 4.88 |
| **t4_plateau_stress** | matched | RMSE (pp) | 0.58 | 4.45 | 6.28 | 8.55 |
| **t4_plateau_stress** | mismatch (-5 mV) | RMSE (pp) | 30.68 | 30.59 | 27.87 | 25.12 |
| **t4_plateau_stress** | mismatch (+5 mV) | RMSE (pp) | 30.27 | 28.79 | 24.97 | 24.81 |
| **t12_hysteresis_mismatch** | matched | RMSE (pp) | 0.57 | 4.28 | 6.19 | 8.53 |
| **t12_hysteresis_mismatch** | mismatch (-5 mV) | RMSE (pp) | 9.99 | 13.23 | 11.33 | 9.36 |
| **t12_hysteresis_mismatch** | mismatch (+5 mV) | RMSE (pp) | 9.19 | 4.77 | 8.71 | 8.84 |

## 3. Theta vs Time Convergence Plot

Convergence of residual bias $\hat{\theta}(t)$ on `t3_bess_24h` under +5 mV OCV mismatch:

![Residual Bias Convergence](e6_theta_t3_bess_24h.png)

## 4. Detailed Audit of Pass Rules for Best Configuration

### Rule 1: Do No Harm (Matched RMSE <= E2 + 0.30 pp)
- **t3_bess_24h**: E6 RMSE minus E2 RMSE = `+3.56` pp (threshold: +0.30 pp) -> **FAIL**
- **t4_plateau_stress**: E6 RMSE minus E2 RMSE = `+3.87` pp (threshold: +0.30 pp) -> **FAIL**
- **t12_hysteresis_mismatch**: E6 RMSE minus E2 RMSE = `+3.71` pp (threshold: +0.30 pp) -> **FAIL**

### Rule 2: Help Under Mismatch (RMSE < E2 on all scenarios, Avg Reduction >= 20%)
- **Average Error Reduction**: `-1.0%` (threshold: >= 20.0%) -> **FAIL**
- **t3_bess_24h (mismatched_neg5)**: E6 `13.44` pp vs E2 `9.40` pp -> **FAIL**
- **t3_bess_24h (mismatched_pos5)**: E6 `6.40` pp vs E2 `7.65` pp -> **PASS**
- **t4_plateau_stress (mismatched_neg5)**: E6 `30.59` pp vs E2 `30.68` pp -> **PASS**
- **t4_plateau_stress (mismatched_pos5)**: E6 `28.79` pp vs E2 `30.27` pp -> **PASS**
- **t12_hysteresis_mismatch (mismatched_neg5)**: E6 `13.23` pp vs E2 `9.99` pp -> **FAIL**
- **t12_hysteresis_mismatch (mismatched_pos5)**: E6 `4.77` pp vs E2 `9.19` pp -> **PASS**

### Rule 3: Sanity (Theta Settling Sign)
- **t3_bess_24h (+5 mV)**: final $\theta$ = `-8.85` mV (expected negative) -> **PASS**
- **t3_bess_24h (-5 mV)**: final $\theta$ = `-7.62` mV (expected positive) -> **FAIL**
- **t4_plateau_stress (+5 mV)**: final $\theta$ = `-41.84` mV (expected negative) -> **PASS**
- **t4_plateau_stress (-5 mV)**: final $\theta$ = `-36.05` mV (expected positive) -> **FAIL**
- **t12_hysteresis_mismatch (+5 mV)**: final $\theta$ = `-2.34` mV (expected negative) -> **PASS**
- **t12_hysteresis_mismatch (-5 mV)**: final $\theta$ = `-2.43` mV (expected positive) -> **FAIL**

