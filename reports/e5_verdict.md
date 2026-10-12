# E5 Observability-Gated EKF Verdict Report

## Executive Verdict

- **Overall Verdict**: **FAIL**
- **Best E5 Variant**: `CFG_ABC_021` ((a)+(b)+(c))
- **Rule 1 (Do No Harm on Matched)**: **PASS** (matched RMSE within 0.3 pp of E2 on t3, t4, t12)
- **Rule 2 (Help Under Mismatch)**: **PASS** (RMSE at least 50% below E2 on t3 and t4 for +5 mV and -5 mV)
- **Rule 3 (Beat Coulomb Counting on Offsets)**: **FAIL** (RMSE below E0 on initial-SOC-offset and current-bias)

> [!CAUTION]
> **No E5 configuration passed all three rules.** Per instructions, no rules are modified and no ad-hoc fixes are attempted.

## 1. Top Configurations Ranked across the Parameter Grid

| Rank | Config ID | Variant Type | $\sigma_{\text{ocv}}$ (V) | $\text{slope}_{\text{ref}}$ (V) | $\Delta soc_{\text{max}}$ | Rule 1 | Rule 2 | Avg Red. (%) | Rule 3 | Overall Verdict |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `CFG_ABC_021` | (a)+(b)+(c) | 0.005 | 0.1 | 0.0002 | PASS | PASS | 71.3% | FAIL | **FAIL** |
| 2 | `CFG_ABC_033` | (a)+(b)+(c) | 0.01 | 0.05 | 0.0002 | PASS | PASS | 72.2% | FAIL | **FAIL** |
| 3 | `CFG_ABC_037` | (a)+(b)+(c) | 0.01 | 0.1 | 0.0002 | PASS | PASS | 73.7% | FAIL | **FAIL** |
| 4 | `CFG_ABC_009` | (a)+(b)+(c) | 0.002 | 0.2 | 0.0002 | PASS | PASS | 72.2% | FAIL | **FAIL** |
| 5 | `CFG_ABC_025` | (a)+(b)+(c) | 0.005 | 0.2 | 0.0002 | PASS | PASS | 74.1% | FAIL | **FAIL** |
| 6 | `CFG_ABC_013` | (a)+(b)+(c) | 0.002 | 0.5 | 0.0002 | PASS | PASS | 76.7% | FAIL | **FAIL** |
| 7 | `CFG_ABC_038` | (a)+(b)+(c) | 0.01 | 0.1 | 0.0005 | PASS | PASS | 62.1% | FAIL | **FAIL** |
| 8 | `CFG_ABC_017` | (a)+(b)+(c) | 0.005 | 0.05 | 0.0002 | PASS | FAIL | 71.0% | FAIL | **FAIL** |
| 9 | `CFG_ABC_041` | (a)+(b)+(c) | 0.01 | 0.2 | 0.0002 | PASS | PASS | 78.2% | FAIL | **FAIL** |
| 10 | `CFG_ABC_034` | (a)+(b)+(c) | 0.01 | 0.05 | 0.0005 | PASS | FAIL | 60.2% | FAIL | **FAIL** |

## 2. Comprehensive Comparison Table: E0, E2, E6, and E5 Variants

Comparison across all 5 evaluation scenarios and 3 variants (averaged across 2 seeds).
Estimators compared:
- **E0**: Coulomb counting
- **E2**: Baseline 2RC EKF with hysteresis
- **E6**: RBC-DEKF (`CFG_021`: $Q_\theta=10^{-9}, R_\theta=10^{-4}, \sigma_0=0.002$)
- **E5 (a)**: Variance inflation only (`CFG_A_004`)
- **E5 (a+b)**: Variance inflation + slope gating (`CFG_AB_015`)
- **E5 (a+b+c)**: Full observability gating (`CFG_ABC_021`)

| Scenario | Variant | E0 (pp) | E2 Baseline (pp) | E6 RBC-DEKF (pp) | E5 (a) (pp) | E5 (a+b) (pp) | E5 (a+b+c) (pp) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **t3_bess_24h** | matched | 0.01 | 0.17 | 3.73 | 0.08 | 0.07 | 0.12 |
| **t3_bess_24h** | mismatch (-5 mV) | 0.88 | 9.40 | 13.44 | 6.45 | 4.52 | 4.20 |
| **t3_bess_24h** | mismatch (+5 mV) | 0.88 | 7.65 | 6.40 | 2.95 | 1.76 | 3.81 |
| **t4_plateau_stress** | matched | 0.00 | 0.58 | 4.45 | 0.29 | 0.18 | 0.30 |
| **t4_plateau_stress** | mismatch (-5 mV) | 0.50 | 30.68 | 30.59 | 19.59 | 16.17 | 3.08 |
| **t4_plateau_stress** | mismatch (+5 mV) | 0.50 | 30.27 | 28.79 | 17.58 | 14.82 | 3.12 |
| **t12_hysteresis_mismatch** | matched | 0.00 | 0.57 | 4.28 | 0.28 | 0.18 | 0.24 |
| **t12_hysteresis_mismatch** | mismatch (-5 mV) | 0.00 | 9.99 | 13.23 | 8.94 | 7.17 | 5.83 |
| **t12_hysteresis_mismatch** | mismatch (+5 mV) | 0.00 | 9.19 | 4.77 | 6.63 | 4.93 | 6.50 |
| **t5_initial_soc_offset** | matched | 10.00 | 0.53 | 0.47 | 0.44 | 0.71 | 6.72 |
| **t5_initial_soc_offset** | mismatch (-5 mV) | 9.82 | 7.14 | 7.90 | 7.94 | 7.92 | 8.74 |
| **t5_initial_soc_offset** | mismatch (+5 mV) | 9.82 | 3.90 | 3.66 | 3.77 | 3.88 | 6.73 |
| **t6_current_bias** | matched | 2.78 | 0.50 | 0.64 | 0.33 | 0.25 | 0.47 |
| **t6_current_bias** | mismatch (-5 mV) | 2.94 | 3.04 | 3.86 | 2.90 | 2.90 | 2.97 |
| **t6_current_bias** | mismatch (+5 mV) | 2.94 | 4.22 | 2.34 | 4.45 | 4.63 | 4.20 |

## 3. Detailed Audit of Pass Rules for Best E5 Variant (`CFG_ABC_021`)

### Rule 1: Do No Harm on Matched (Threshold: within 0.30 pp of E2)
- **t3_bess_24h**: E5 = `0.12` pp, E2 = `0.17` pp, Diff = `-0.05` pp -> **PASS**
- **t4_plateau_stress**: E5 = `0.30` pp, E2 = `0.58` pp, Diff = `-0.28` pp -> **PASS**
- **t12_hysteresis_mismatch**: E5 = `0.24` pp, E2 = `0.57` pp, Diff = `-0.33` pp -> **PASS**

### Rule 2: Help Under Mismatch (Threshold: at least 50% below E2 on t3 and t4)
- **t3_bess_24h (-5 mV)**: E5 = `4.20` pp, E2 = `9.40` pp, Reduction = `55.3%` (target >= 50.0%) -> **PASS**
- **t3_bess_24h (+5 mV)**: E5 = `3.81` pp, E2 = `7.65` pp, Reduction = `50.2%` (target >= 50.0%) -> **PASS**
- **t4_plateau_stress (-5 mV)**: E5 = `3.08` pp, E2 = `30.68` pp, Reduction = `90.0%` (target >= 50.0%) -> **PASS**
- **t4_plateau_stress (+5 mV)**: E5 = `3.12` pp, E2 = `30.27` pp, Reduction = `89.7%` (target >= 50.0%) -> **PASS**

### Rule 3: Beat Coulomb Counting on Offset Scenarios (Threshold: RMSE < E0)
- **t5_initial_soc_offset (matched)**: E5 = `6.72` pp vs E0 = `10.00` pp -> **PASS**
- **t5_initial_soc_offset (-5 mV)**: E5 = `8.74` pp vs E0 = `9.82` pp -> **PASS**
- **t5_initial_soc_offset (+5 mV)**: E5 = `6.73` pp vs E0 = `9.82` pp -> **PASS**
- **t6_current_bias (matched)**: E5 = `0.47` pp vs E0 = `2.78` pp -> **PASS**
- **t6_current_bias (-5 mV)**: E5 = `2.97` pp vs E0 = `2.94` pp -> **FAIL**
- **t6_current_bias (+5 mV)**: E5 = `4.20` pp vs E0 = `2.94` pp -> **FAIL**

## 4. Architectural Assumptions & Differences from Shi et al. (2026)

1. **Discrete-Time EKF Framework**: Shi et al. (2026) formulate Fisher-information weighting in a continuous-time observer framework. E5 adapts this concept into a discrete-time EKF combined with a 2RC equivalent circuit model and 1-state hysteresis.
2. **State-Selective Observability Gating**: The gating $g = \min(1, |\partial\text{OCV}/\partial\text{SOC}| / \text{slope}_{\text{ref}})$ and per-step cap $\Delta soc_{\text{max}}$ are applied strictly to the SOC state correction. Polarization current states ($i_1, i_2$) and hysteresis ($h$) retain unattenuated Kalman gain corrections to maintain accurate dynamic voltage modeling.
3. **Joseph Covariance Consistency**: To prevent overconfidence and covariance matrix singularity when updates are gated on the plateau, an effective Kalman gain $K_{\text{eff}}$ is constructed and propagated via the Joseph stabilized formulation $P^+ = (I - K_{\text{eff}} H) P (I - K_{\text{eff}} H)^T + K_{\text{eff}} R_{\text{eff}} K_{\text{eff}}^T$.
4. **Additive Model Uncertainty Inflation**: Measurement variance is inflated by an additive model uncertainty term $R_{\text{eff}} = R_v + \sigma_{\text{ocv\_model}}^2$.
5. **Dropout Handling**: In the presence of dropouts (NaN inputs), E5 executes time propagation only without measurement update.
