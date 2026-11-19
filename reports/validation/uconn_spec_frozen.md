# Frozen Evaluation Specification: UConn REIL Dataset 5 Pulse-Based SOH

> [!NOTE] Revision (V2.12 Provenance & Invocation Audit)  
> As documented in `reports/validation/uconn_spec_provenance.md` and `reports/validation/uconn_reproduction.md`, Section 7 Item 4 originally drafted that test cells would be "evaluated exactly ONCE". In reality, the sealed test cells were executed initially at `dbffe91`, followed by an interactive 11-feature evaluation at step 6905, reproduction at V2.11.2 (`df70e53`), age baseline evaluation at V2.11.4 (`b138ff0`), and tautology baseline evaluation at V2.12.3 (`be97d44`). The initial 14-feature candidate frozen at V2.7 reproduced bit-for-bit per V2.12 Item 1.

**Document Status:** FROZEN PRIOR TO EVALUATION  
**Date:** 2026-11-19  
**Specification Version:** 1.0  
**Target Dataset:** UConn-ISU-ILCC LFP/Gr Battery Aging Dataset (Dataset 5, DOI: [10.1016/j.jpowsour.2024.235813](https://doi.org/10.1016/j.jpowsour.2024.235813))  
**Data Manifest:** `data/manifests/uconn_reil_dataset5.sha256`  
**Configuration File:** `configs/validation/uconn_config.yaml`  
**Splits Declaration:** `configs/validation/uconn_splits.yaml`  

---

## 1. Governance and Invariants

This specification is committed in isolation prior to conducting any model training or evaluation on the development or test partitions, strictly enforcing the following rules:

1. **Rule R1 (Data Location):** Raw data remains outside the repository under `$SOC_DATA_DIR/uconn_reil/extracted/rpt_data`.
2. **Rule R2 (Data Integrity):** Every raw file has its SHA-256 hash verified against the manifest. No synthetic, simulated, or default labels are permitted; samples with missing steps or non-physical data are strictly excluded.
3. **Rule R3 (Cell and Condition Isolation):**
   - Development partition: 43 dev cells (32 train, 11 validation) across all 11 conditions.
   - Sealed test partition: 21 sealed test cells (2 cells per condition for groups 1–10; 1 cell for group 11).
   - Condition holdout partition: 9 dev conditions (52 cells); 2 sealed test conditions (Groups 3 and 6, 12 cells).
   - The sealed test partitions must NEVER be accessed during hyperparameter exploration. They are evaluated ONCE only after candidate model `soh_pulse_v2` is frozen.
4. **Rule R4 (Frozen Algorithms):** Estimators `src/soc/estimators/e7v3.py`, `src/soc/estimators/base.py`, and `deliverable/bms_soc_ref.py` remain untouched.
5. **Rule R5 (Fair Baseline):** Any candidate model must beat a fair, non-trivial baseline (the constant-training-mean baseline) on independent held-out data to qualify for validation claims.

---

## 2. Estimators Under Evaluation

Three distinct estimator classes will be evaluated on the development partition and subsequently on the sealed test partition:

### 2.1 Constant-Training-Mean Baseline (Fair Reference)

The empirical mean of the target label computed over the training set:
$$\hat{y}_i = \bar{y}_{\text{train}} = \frac{1}{N_{\text{train}}} \sum_{j \in \mathcal{D}_{\text{train}}} y_j$$
- Evaluated separately for $SOH_C$ and $SOH_R$.
- Serves as the minimal sanity threshold: any predictive model that fails to achieve a lower MAE than this constant baseline provides negative predictive value.

### 2.2 Ridge Regression Baseline ($L_2$ Regularization)

Linear regression with pure $L_2$ weight penalty:
$$\min_{\mathbf{w}, b} \frac{1}{2N} \|\mathbf{y} - (\mathbf{X}\mathbf{w} + b)\|_2^2 + \frac{\alpha}{2} \|\mathbf{w}\|_2^2$$
- Standardizes feature inputs $\mathbf{X}$ to zero mean and unit variance.
- Retains all feature dimensions without inducing sparsity.

### 2.3 Pulse ECM + ElasticNet Estimator (Physics-Constrained $L_1 + L_2$)

Linear model regularized by a convex combination of $L_1$ and $L_2$ penalties:
$$\min_{\mathbf{w}, b} \frac{1}{2N} \|\mathbf{y} - (\mathbf{X}\mathbf{w} + b)\|_2^2 + \alpha \cdot \rho \|\mathbf{w}\|_1 + \frac{\alpha (1 - \rho)}{2} \|\mathbf{w}\|_2^2$$
where $\alpha \ge 0$ is the overall penalty scale and $\rho \in [0, 1]$ is the `l1_ratio`.
- Model targets dual predictions: $\hat{SOH}_C$ and $\hat{SOH}_R$.
- Generates sparse, interpretable coefficient vectors suitable for embedded BMS C export.

---

## 3. Feature Definitions

Features are derived from the 100-second `slowpulse` sequence at nominal 50.0% SOC discharge (with auxiliary evaluations at 90.0% and 20.0% SOC):

### 3.1 2-RC Equivalent Circuit Model (ECM) Features

Fitted using nonlinear least-squares (`least_squares`) with physical box constraints:
$$\Delta V_{\text{polarization}}(t) = I R_0 + I R_1 \left(1 - e^{-t/\tau_1}\right) + I R_2 \left(1 - e^{-t/\tau_2}\right)$$
The extracted 11-dimensional feature vector comprises:
1. $R_0$: High-frequency ohmic resistance ($\Omega$)
2. $R_1$: Fast charge-transfer polarization resistance ($\Omega$)
3. $C_1$: Fast capacitance ($C_1 = \tau_1 / R_1$, F)
4. $R_2$: Slow diffusion polarization resistance ($\Omega$)
5. $C_2$: Slow capacitance ($C_2 = \tau_2 / R_2$, F)
6. $R_{\text{total}} = R_0 + R_1 + R_2$: Total internal resistance ($\Omega$)
7. $\tau_1$: Fast time constant (s)
8. $\tau_2$: Slow time constant (s)
9. $I_{\text{amplitude}}$: Current step magnitude (A)
10. $T$: Ambient / chamber temperature setpoint (°C)
11. $V_{\text{initial}}$: Pre-pulse open-circuit relaxation voltage (V)

### 3.2 Direct Pulse Response Features

To ensure robust performance even when non-linear 2-RC fitting experiences parameter degeneracy, direct discrete voltage differences are included:
12. $\Delta V_{1s} = |V(t_0 + 1\text{s}) - V(t_0)|$: 1-second transient response (V)
13. $\Delta V_{10s} = |V(t_0 + 10\text{s}) - V(t_0)|$: 10-second pulse step response (V)
14. $R_{10s} = \Delta V_{10s} / |\Delta I|$: 10-second apparent pulse resistance ($\Omega$)
15. $R_{1s} = \Delta V_{1s} / |\Delta I|$: 1-second apparent pulse resistance ($\Omega$)

---

## 4. Hyperparameter Search Grid (DEV Partition Only)

Hyperparameters are selected via cross-validation strictly on the 43 development cells:

| Parameter | Grid Search Values | Default |
|---|---|---|
| Regularization Strength $\alpha$ | $[0.001, 0.005, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0]$ | 0.05 |
| ElasticNet Mixing Ratio $\rho$ (`l1_ratio`) | $[0.1, 0.3, 0.5, 0.7, 0.9, 0.95]$ | 0.50 |
| ECM Max Condition Number | $[10^4, 10^5, 10^6]$ | $10^5$ |
| ECM Max Fit RMSE | $[5.0, 10.0, 15.0, 25.0]\ \text{mV}$ | $15.0\ \text{mV}$ |

---

## 5. Evaluation Metrics

All models will be scored using the following four statistical metrics:

1. **Mean Absolute Error (MAE):**
   $$\text{MAE} = \frac{1}{N} \sum_{i=1}^N |\hat{y}_i - y_i|$$
2. **Root Mean Squared Error (RMSE):**
   $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^N (\hat{y}_i - y_i)^2}$$
3. **Mean Signed Bias:**
   $$\text{Bias} = \frac{1}{N} \sum_{i=1}^N (\hat{y}_i - y_i)$$
4. **95% Interval Coverage:**
   $$\text{Coverage}_{95\%} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}\left( y_i \in [\hat{y}_i - 1.96 \hat{\sigma}_i, \hat{y}_i + 1.96 \hat{\sigma}_i] \right)$$

### Reporting Stratification

Metrics will be reported overall and broken down along two dimensions:
- **By Condition Group:** Across each of the 11 aging conditions.
- **By SOH Band:**
  - High SOH (Fresh): $SOH_C > 0.95$
  - Mid SOH: $0.85 < SOH_C \le 0.95$
  - Low SOH (Aged / Near EOL): $SOH_C \le 0.85$

---

## 6. Acceptance Gates

Before any candidate model can be designated `soh_pulse_v2` and evaluated on the sealed test sets, it must satisfy all of the following gates:

| Gate ID | Target | Requirement | Rationale |
|---|---|---|---|
| **GATE-1** | $SOH_C$ Accuracy | $\text{MAE} \le 0.030$ (3.0% capacity error) on held-out dev validation cells | Ensures acceptable accuracy for BMS state-of-health tracking |
| **GATE-2** | $SOH_R$ Accuracy | $\text{MAE} \le 0.050$ (5.0% resistance error) on held-out dev validation cells | Ensures meaningful tracking of internal resistance rise |
| **GATE-3** | Beat Fair Baseline | $\text{MAE}(\text{Candidate}) \le 0.90 \times \text{MAE}(\text{Constant-Mean})$ on held-out dev validation cells | Proves model learns true predictive signal beyond the training distribution mean |
| **GATE-4** | Non-Zero Weights | $\|\mathbf{w}\|_1 > 0$ and $\ge 2$ active features with non-zero coefficients | Resolves previous issue where default regularization shrank all weights to zero |
| **GATE-5** | Deterministic Reproducibility | Zero variation across repeated execution from clean shell | Guarantees testability and auditability |

---

## 7. Sealed Test Protocol

1. Hyperparameters $\alpha^*$ and $\rho^*$ will be selected strictly on DEV cells.
2. The candidate model will be frozen and saved as `deliverable/calibrations/uconn_soh_pulse_v2.json`.
3. The sealed evaluation script will be dry-run on DEV cells to verify error-free execution.
4. Sealed test cells (21 cells) and sealed test conditions (Groups 3 and 6) will be evaluated exactly ONCE.
5. If the model fails GATE-3 on the sealed test set, execution STOPS and reports the result honestly without tuning or retrying.
