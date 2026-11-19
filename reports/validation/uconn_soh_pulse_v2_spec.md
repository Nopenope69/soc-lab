# Frozen Candidate Specification: `soh_pulse_v2`

**Candidate Identifier:** `soh_pulse_v2`  
**Calibration File:** `deliverable/calibrations/uconn_soh_pulse_v2.json`  
**Date Frozen:** 2026-11-19  
**Target Chemistry:** LFP/Graphite  
**Target Cell Model:** LithiumWerks APR18650M1B (18650 cylindrical, 1.2 Ah nominal)  
**Qualification Status:** strictly **UNQUALIFIED** (small cylindrical cells; not qualified for 100 Ah automotive/grid pack deployment)  
**Governance Invariant:** Hyperparameters and coefficients were selected and frozen strictly on the 43 development cells (`configs/validation/uconn_splits.yaml`). Sealed test cells (21 cells) and sealed test conditions (Groups 3 and 6) remain untouched and unaccessed.

---

## 1. Model Mathematical Architecture

The estimator implements dual regularized linear models operating on standardized features:

$$\hat{y}_{\text{norm}} = b + \sum_{j=1}^{14} w_j \left( \frac{x_j - \mu_j}{\sigma_j} \right)$$

Physical bounds clamping:
- Capacity SOH: $\hat{SOH}_C = \min(\max(\hat{y}_C, 0.20), 1.20)$
- Resistance SOH: $\hat{SOH}_R = \min(\max(\hat{y}_R, 0.20), 2.50)$

Conformal 95% uncertainty interval:
- $[\hat{SOH}_C - q_{95,C}, \hat{SOH}_C + q_{95,C}]$ with $q_{95,C} = 0.04255$
- $[\hat{SOH}_R - q_{95,R}, \hat{SOH}_R + q_{95,R}]$ with $q_{95,R} = 0.02633$

---

## 2. Feature Vectors and Standard Scaler Parameters

Features are computed from the 100-second discharge pulse at 50% nominal SOC:

| Index | Feature Name | Mean $\mu_j$ | Scale $\sigma_j$ | Physical Meaning |
|---|---|---|---|---|
| 0 | `r0_ohm` | $0.017330\ \Omega$ | $0.000656\ \Omega$ | High-frequency ohmic resistance |
| 1 | `r1_ohm` | $0.009678\ \Omega$ | $0.000557\ \Omega$ | Fast charge-transfer resistance |
| 2 | `c1_f` | $565.92\ \text{F}$ | $35.38\ \text{F}$ | Fast polarization capacitance |
| 3 | `r2_ohm` | $0.065610\ \Omega$ | $0.005498\ \Omega$ | Slow diffusion resistance |
| 4 | `c2_f` | $1429.24\ \text{F}$ | $102.16\ \text{F}$ | Slow diffusion capacitance |
| 5 | `r_total_ohm` | $0.092617\ \Omega$ | $0.005842\ \Omega$ | Total resistance ($R_0 + R_1 + R_2$) |
| 6 | `tau1_s` | $5.4818\ \text{s}$ | $0.5226\ \text{s}$ | Fast time constant |
| 7 | `tau2_s` | $93.5165\ \text{s}$ | $7.6691\ \text{s}$ | Slow time constant |
| 8 | `i_amplitude_a` | $0.45140\ \text{A}$ | $0.003468\ \text{A}$ | Pulse mean discharge current |
| 9 | `temp_c` | $25.0000\ ^\circ\text{C}$ | $1.0000\ ^\circ\text{C}$ | Environmental temperature |
| 10 | `v_initial_v` | $3.306735\ \text{V}$ | $0.000925\ \text{V}$ | Pre-pulse relaxation voltage |
| 11 | `delta_v_1s` | $0.018943\ \text{V}$ | $0.000722\ \text{V}$ | 1-second transient voltage drop |
| 12 | `delta_v_10s` | $0.030100\ \text{V}$ | $0.000983\ \text{V}$ | 10-second pulse voltage drop |
| 13 | `r_10s_ohm` | $0.031358\ \Omega$ | $0.001025\ \Omega$ | 10-second apparent pulse resistance |

---

## 3. Frozen Weights and Intercepts

### 3.1 SOH_C Model (Capacity Retention)

- **Hyperparameters:** $\alpha = 0.005$, $\text{l1\_ratio} = 0.10$
- **Intercept $b_C$:** `0.9189938`
- **Active Non-Zero Features:** 9 of 14

| Feature | Weight $w_{C,j}$ | Feature | Weight $w_{C,j}$ |
|---|---|---|---|
| `r0_ohm` | `-0.0030854` | `tau2_s` | `0.0` |
| `r1_ohm` | `-0.0072436` | `i_amplitude_a` | `+0.0044863` |
| `c1_f` | `+0.0018041` | `temp_c` | `0.0` |
| `r2_ohm` | `0.0` | `v_initial_v` | `-0.0033036` |
| `c2_f` | `+0.0218710` | `delta_v_1s` | `0.0` |
| `r_total_ohm` | `-0.0084204` | `delta_v_10s` | `-0.0111213` |
| `tau1_s` | `0.0` | `r_10s_ohm` | `-0.0132266` |

### 3.2 SOH_R Model (Resistance Growth)

- **Hyperparameters:** $\alpha = 0.005$, $\text{l1\_ratio} = 0.30$
- **Intercept $b_R$:** `0.9872138`
- **Active Non-Zero Features:** 6 of 14

| Feature | Weight $w_{R,j}$ | Feature | Weight $w_{R,j}$ |
|---|---|---|---|
| `r0_ohm` | `0.0` | `tau2_s` | `0.0` |
| `r1_ohm` | `0.0` | `i_amplitude_a` | `+0.0021047` |
| `c1_f` | `0.0` | `temp_c` | `0.0` |
| `r2_ohm` | `+0.0041880` | `v_initial_v` | `-0.0001325` |
| `c2_f` | `-0.0035103` | `delta_v_1s` | `0.0` |
| `r_total_ohm` | `0.0` | `delta_v_10s` | `+0.0138138` |
| `tau1_s` | `0.0` | `r_10s_ohm` | `+0.0090098` |

---

## 4. Acceptance Gate Audit (DEV Validation Partition)

- **GATE-1 ($SOH_C \le 0.030$):** **PASS** ($\text{MAE} = 0.0225$)
- **GATE-2 ($SOH_R \le 0.050$):** **PASS** ($\text{MAE} = 0.0073$)
- **GATE-3 (Beat Fair Baseline $\le 0.90\times$):** **PASS** (Ratio = $0.518 \le 0.90$, 48.3% error reduction)
- **GATE-4 (Active Features $\ge 2$):** **PASS** (9 active for C, 6 active for R)
- **GATE-5 (Deterministic Execution):** **PASS** (Zero jitter)
