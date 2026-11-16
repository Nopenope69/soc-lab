# SOH Estimator Qualification Status Matrix

> **Governing Framework**: Hardening 2 / Phase 6 Validation Standard  
> **Status Classifications**:
> - `LAB_VALIDATED`: Validated against real physically-aged cells from verified hash-manifested laboratory test files.
> - `SIM_VALIDATED`: Validated on simulation models (PyBaMM electrochemical models) or synthetic analytical degradation curves.
> - `FIELD_VALIDATED`: Validated on real in-service fleet operational data.
> - `UNVALIDATED`: Lacks standardized laboratory reference measurements or has not been tested against physical cell ground truth.
> - `EXPERIMENTAL`: Under research / prototyping evaluation; not qualified for battery management control or safety limits.

---

## 1. Executive Summary: Real-Cell Data Status

> **CRITICAL QUALIFICATION NOTE**:  
> As established by the Phase 6.1–6.3 provenance audit, **no physical laboratory degradation datasets have been loaded or evaluated for SOH**. All cohorts previously labeled "CALCE A123", "Oxford Kokam", and "MIT/Stanford" were generated synthetically in software via mathematical equations.  
> 
> Consequently:
> - **Zero estimators currently hold `LAB_VALIDATED` or `FIELD_VALIDATED` status for either $SOH_C$ or $SOH_R$.**
> - All prior `QUALIFIED` and `PROVISIONALLY_QUALIFIED` designations are reclassified to **`SIM_VALIDATED`**.
> - Resistance tracking ($SOH_R$) on physical cells remains **`UNVALIDATED`** across all estimators.

---

## 2. Granular Estimator Status Matrix

### Candidate 1: Empirical Power-Law Model (`EmpiricalEstimatorWrapper`)
*Methodology*: Power-law degradation curve fit ($\Delta C = \alpha \cdot k^\beta$) with bounded non-linear parameters.

| Output Channel | Dataset Used | Data Nature | Cells Evaluated | Split Methodology | Metric Achieved | Qualification Status | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **$SOH_C$ Point** | MIT/Stanford Cohort | Synthetic | 4 cells | Bidirectional Batch LOBO | 0.812% – 0.885% RMSE | **`SIM_VALIDATED`** | Fit to synthetic knee curve ($n_{\text{knee}}=45$). **`UNVALIDATED`** on real cells. |
| **$SOH_C$ Uncertainty** | MIT/Stanford Cohort | Synthetic | 4 cells | Bidirectional Batch LOBO | Residual variance | **`SIM_VALIDATED`** | Parametric residual spread; unvalidated on physical manufacturing batches. |
| **$SOH_R$ Point** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | No real-data result exists. Model does not estimate resistance degradation. |
| **$SOH_R$ Uncertainty** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | No real-data result exists. |

---

### Candidate 2: Pulse ECM + ElasticNet (`PulseElasticNetEstimator`)
*Methodology*: Thevenin equivalent circuit parameter identification ($R_0, R_1, C_1$) under standardized current pulses with regularized linear regression.

| Output Channel | Dataset Used | Data Nature | Cells Evaluated | Split Methodology | Metric Achieved | Qualification Status | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **$SOH_C$ Point** | HPPC Pulse Cohort | Synthetic | 60 pulses | Split by Synthetic Pulse | 1.919% RMSE | **`SIM_VALIDATED`** | Evaluated on 1-RC ECM simulated pulses. **`UNVALIDATED`** on real cell pulses. |
| **$SOH_C$ Uncertainty** | HPPC Pulse Cohort | Synthetic | 60 pulses | Split by Synthetic Pulse | Covariance trace | **`SIM_VALIDATED`** | Linear regression posterior variance under Gaussian noise assumption. |
| **$SOH_R$ Point** | HPPC Pulse Cohort | Synthetic | 60 pulses | Split by Synthetic Pulse | Direct $R_0$ extraction | **`SIM_VALIDATED`** | Direct extraction of simulated $R_0$. **`UNVALIDATED`** on physical cell DCIR. |
| **$SOH_R$ Uncertainty** | HPPC Pulse Cohort | Synthetic | 60 pulses | Split by Synthetic Pulse | Fisher Information matrix | **`SIM_VALIDATED`** | Jacobian-based identifiability covariance on simulated data. |

---

### Candidate 3: GRU Recurrent Sequence Model (`GruSohEstimator`)
*Methodology*: Gated Recurrent Unit sequence network processing cycling telemetry history ($V, I, T, \Delta t, Ah$).

| Output Channel | Dataset Used | Data Nature | Cells Evaluated | Split Methodology | Metric Achieved | Qualification Status | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **$SOH_C$ Point** | LG M50T & MIT Cohorts | Simulation & Synthetic | 50 + 4 cells | Cell LOBO | 0.95% – 1.45% RMSE | **`SIM_VALIDATED`** | Evaluated on PyBaMM simulations & synthetic cohorts. **`UNVALIDATED`** on real cells. |
| **$SOH_C$ Uncertainty** | MIT Synthetic Cohort | Synthetic | 4 cells | Cell LOBO | 86.0% Coverage (Full-life) | **`SIM_VALIDATED`** | Severe underconfidence at EOL (0.0% coverage post-knee). EOL status **`UNVALIDATED`**. |
| **$SOH_R$ Point** | MIT Synthetic Cohort | Synthetic | 4 cells | Cell LOBO | 3.12% RMSE | **`SIM_VALIDATED`** | Evaluated on synthetic algebraic resistance curves. **`UNVALIDATED`** on real cells. |
| **$SOH_R$ Uncertainty** | MIT Synthetic Cohort | Synthetic | 4 cells | Cell LOBO | 78.4% Coverage | **`SIM_VALIDATED`** | Calibration degrades significantly during rapid degradation phases. |

---

### Candidate 4: Incremental Capacity Analysis + GPR-EKF (`IcaGprEkfEstimator`)
*Methodology*: $dQ/dV$ differential capacity peak feature tracking with Gaussian Process Regression prior and Extended Kalman Filter state tracking.

| Output Channel | Dataset Used | Data Nature | Cells Evaluated | Split Methodology | Metric Achieved | Qualification Status | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **$SOH_C$ Point** | CALCE Synthetic Cohort | Synthetic | 4 cells | Cell LOBO | 1.12% RMSE | **`SIM_VALIDATED`** | Requires full C/20 constant current charging curve. **`UNVALIDATED`** on real cells. |
| **$SOH_C$ Uncertainty** | CALCE Synthetic Cohort | Synthetic | 4 cells | Cell LOBO | EKF State Covariance $P_k$ | **`SIM_VALIDATED`** | Relies on synthetic measurement noise covariance tuning. |
| **$SOH_R$ Point** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | ICA does not track high-frequency ohmic resistance degradation directly. |
| **$SOH_R$ Uncertainty** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | No real-data result exists. |

---

### Candidate 5: Physics-Informed Neural Network (`PinnSohEstimator`)
*Methodology*: Multi-layer perceptron constrained by solid-state diffusion PDE residual loss and monotonicity penalty.

| Output Channel | Dataset Used | Data Nature | Cells Evaluated | Split Methodology | Metric Achieved | Qualification Status | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **$SOH_C$ Point** | PyBaMM Chen2020 | Simulation | 20 trajectories | Operating Condition LOCO | 0.631% – 0.633% RMSE | **`EXPERIMENTAL`** | Retained as experimental baseline. Modest benefit under diffusion limits only. |
| **$SOH_C$ Uncertainty** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | Deterministic network; no epistemic uncertainty quantification. |
| **$SOH_R$ Point** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | No real-data result exists. |
| **$SOH_R$ Uncertainty** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | No real-data result exists. |

---

### Candidate 6: Pure MLP Baseline (`BaselineRidgeEstimator` / MLP)
*Methodology*: Unconstrained feed-forward neural network / Ridge regression on summary statistics.

| Output Channel | Dataset Used | Data Nature | Cells Evaluated | Split Methodology | Metric Achieved | Qualification Status | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **$SOH_C$ Point** | PyBaMM Chen2020 | Simulation | 20 trajectories | Condition LOCO | 0.631% RMSE | **`SIM_VALIDATED`** | Pure black-box baseline on simulation data. **`UNVALIDATED`** on real cells. |
| **$SOH_C$ Uncertainty** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | No uncertainty output. |
| **$SOH_R$ Point** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | No real-data result exists. |
| **$SOH_R$ Uncertainty** | N/A | None | 0 | N/A | None | **`UNVALIDATED`** | No real-data result exists. |

---

## 3. Road to Physical Lab Qualification (`LAB_VALIDATED`)

To achieve `LAB_VALIDATED` status for any SOH estimator, the following strict criteria must be met:
1. **Raw Laboratory Files Outside Repository**: Data must reside at `$SOC_DATA_DIR` (e.g. `~/soc_data`) and be verified against a non-placeholder SHA-256 manifest in `data/manifests/`.
2. **Cell-Held-Out Splits**: Evaluation must follow strict Cell Leave-One-Battery-Out (LOBO) or batch holdouts defined prior to evaluation in `configs/validation/`.
3. **Reference Capacity Protocols**: SOH_C ground truth must be derived from C/20 or standardized 1C reference capacity checkups at controlled temperature (e.g. 25°C).
4. **Standardized DCIR Protocols**: SOH_R ground truth must be derived from standardized 10s HPPC discharge pulses at defined SOC (e.g. 50% SOC) and controlled temperature.
