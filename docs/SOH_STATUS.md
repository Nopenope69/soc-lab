# SOH Estimator Qualification Status Matrix

> [!NOTE] Revision (V2.13 Precision & Baseline Audit)
> - **$SOH_R$ Estimation Skill Assessment**: In headline text and qualification records: The $SOH_R$ ground-truth label is $r_{\text{pulse, 10s}}(\text{RPT}_k) / r_{\text{pulse, 10s}}(\text{RPT}_0)$ from Step 20 and the 14-feature model takes $r_{10\text{s},\text{ohm}}$ and $\Delta V_{10\text{s}}$ from the same pulse; a trivial baseline ($r_{10\text{s}} / \bar{r}_0$, where $\bar{r}_0 = 0.031755\ \Omega$ is the mean RPT-0 $r_{10\text{s}}$ over the training cells) scores MAE 0.0060 on dev validation (candidate 0.0073), 0.0095 [0.0066, 0.0126] on sealed cells (candidate 0.0094 [0.0073, 0.0127]), and 0.0103 on the condition holdout (candidate 0.0117); conclusion: **no evidence of estimation skill for $SOH_R$**.

> [!NOTE] Revision (V2.12 Tautology & Feature-Label Identity Audit)  
> Documented that $SOH_R$ results do NOT represent evidence of degradation estimation skill because the ground-truth label ($SOH_R = r_{\text{pulse, 10s}}(\text{RPT}_k) / r_{\text{pulse, 10s}}(\text{RPT}_0)$) and input features ($r_{10\text{s},\text{ohm}}, \Delta V_{10\text{s}}$) are derived from the exact same Step 20 `slowpulse` measurement. A trivial baseline $\widehat{SOH}_R = r_{10\text{s},\text{ohm}} / \bar{r}_0$ achieves 0.0095 MAE on sealed cells, matching the candidate model. The 11-feature model's SOH_R MAE changed from 0.0094 to 0.0107 when $r_{10\text{s}}$ was omitted (reported as an empirical observation without asserting a cause).

> [!NOTE] Revision (V2.11)  
> Reclassified Candidate 2 (`soh_pulse_v2`) from `LAB_VALIDATED` to **`DEVELOPMENT`** on UConn REIL Dataset 5 per Governance Label Rule audit:
> - $SOH_C$: Failed criterion (d) (committed spec named only constant-mean baseline; Ridge matches or beats candidate at 0.0199 vs 0.0211 MAE; no age-only baseline was pre-registered in spec; candidate modified post-unsealing) and criterion (e) (counted in independent units: 21 sealed cells).
> - $SOH_R$: Failed criterion (d) (reference Step 20 DCIR is not independent of features $R_0, R_{10\text{s}}$ extracted from the same Step 20 pulse; Ridge matches or beats candidate at 0.0091 vs 0.0094 MAE) and criterion (e).
> Cell model cited per `README_Uconn.txt` line 16: "LithiumWerks 18650 (APR18650M1B), nominal capacity 1.2 Ah" (aged until 80% SOH, approximately 0.96 Ah). Exported C model is strictly PLACEHOLDER / UNVALIDATED.

> [!NOTE] Revision (V1.12)  
> Harmonized `LAB_VALIDATED` definition with the 5-point governance rule across status classifications and qualification roadmaps.

> **Governing Framework**: Hardening 2 / Phase 6 Validation Standard  
> **Status Classifications**:
> - `LAB_VALIDATED`: LAB_VALIDATED requires ALL of: (a) real files with verified manifest hashes; (b) every evaluation script tracked in the repo and reproduced from a clean shell; (c) a spec committed BEFORE the sealed set is evaluated; (d) a held-out result that beats a fair baseline on a reference that is independent of the estimator's own integral; (e) enough data to support the claim, stated in numbers. Everything else is DEVELOPMENT.
> - `SIM_VALIDATED`: Validated on simulation models (PyBaMM electrochemical models) or synthetic analytical degradation curves.
> - `FIELD_VALIDATED`: Validated on real in-service fleet operational data.
> - `UNVALIDATED`: Lacks standardized laboratory reference measurements or has not been tested against physical cell ground truth.
> - `EXPERIMENTAL`: Under research / prototyping evaluation; not qualified for battery management control or safety limits.

---

## 1. Executive Summary: Real-Cell Data Status

> **REAL-CELL SOH STATUS UPDATE (Tasks V2 & V2.11)**:  
> As established by the Task V2 laboratory evaluation and Task V2.11 governance audit on the University of Connecticut Renewable Energy & Intelligent Systems Laboratory (UConn REIL) Dataset 5 (64 physical cells, 2,855 RPT cycles, 207 manifest-verified CSV files):  
> 
> Under the 5-point governance rule:
> - **Candidate 2 (`soh_pulse_v2`) is classified as `DEVELOPMENT` for LithiumWerks 18650 (APR18650M1B) 1.2 Ah cells** (source: `README_Uconn.txt` line 16). While evaluated on real laboratory data across 21 sealed cells (956 RPT observations), it fails Criterion (d) (committed spec named only constant-mean; Ridge matches or beats candidate on both channels; reference label for $SOH_R$ shares voltage response with feature extractor; candidate modified post-unsealing) and Criterion (e) (counted in independent cell units). Furthermore, the ground-truth $SOH_R$ label is $r_{\text{pulse, 10s}}(\text{RPT}_k) / r_{\text{pulse, 10s}}(\text{RPT}_0)$ from Step 20 and the 14-feature model takes $r_{10\text{s},\text{ohm}}$ and $\Delta V_{10\text{s}}$ from the same pulse; a trivial baseline ($r_{10\text{s}} / \bar{r}_0$ over DEV train cells) scores MAE 0.0060 on dev validation (candidate 0.0073), 0.0095 [0.0066, 0.0126] on sealed cells (candidate 0.0094 [0.0073, 0.0127]), and 0.0103 on the condition holdout (candidate 0.0117); conclusion: **no evidence of estimation skill for $SOH_R$**.
> - **Candidate 2 remains strictly `UNQUALIFIED` for 100 Ah automotive/grid pack deployment.** (Failed criteria for 100 Ah pack: no 100 Ah prismatic/pouch cell data, no dynamic drive cycles, no in-service fleet operational data).
> - **All other SOH estimators (Candidates 1, 3, 4, 5, 6) remain `SIM_VALIDATED`, `EXPERIMENTAL`, or `UNVALIDATED`** on physical cells, as their prior cohorts were generated synthetically or in simulation.

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

### Candidate 2: Pulse ECM + ElasticNet (`PulseElasticNetEstimator` / `soh_pulse_v2`)
*Methodology*: Thevenin 2-RC equivalent circuit parameter identification ($R_0, R_1, C_1, R_2, C_2$) under standardized current pulses with regularized ElasticNet regression ($\alpha=0.005, \rho_C=0.10, \rho_R=0.30$) and 95% conformal uncertainty intervals. Cell description: LithiumWerks 18650 (APR18650M1B), nominal capacity 1.2 Ah (source: `README_Uconn.txt` line 16).

| Output Channel | Dataset Used | Data Nature | Cells Evaluated | Split Methodology | Metric Achieved | Qualification Status | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **$SOH_C$ Point** | UConn REIL Dataset 5 | Real Laboratory Data | 64 cells (21 sealed cells, 956 RPT observations) | Cell Holdout (Pre-registered sealed test) | 0.0211 MAE (2.54% RMSE, -0.16% bias) | **`DEVELOPMENT`** (1.2 Ah cylindrical)<br>*(**`UNQUALIFIED`** for 100 Ah pack)* | Evaluated on real LithiumWerks 18650 (APR18650M1B) cells (README_Uconn.txt line 16). Classified `DEVELOPMENT`: failed criterion (d) (Ridge achieves lower MAE 0.0199; spec named only constant-mean; no age-only baseline named; modified post-unsealing) and (e) (counted in cells). Unqualified for 100 Ah pack. |
| **$SOH_C$ Uncertainty** | UConn REIL Dataset 5 | Real Laboratory Data | 64 cells (21 sealed cells, 956 RPT observations) | Cell Holdout (Pre-registered sealed test) | 91.2% empirical coverage ($q_{95}=0.0430$) | **`DEVELOPMENT`** (1.2 Ah cylindrical)<br>*(**`UNQUALIFIED`** for 100 Ah pack)* | Non-parametric conformal quantile calibrated on 11 held-out dev validation cells. Undercovers 95% nominal level on sealed cells. Classified `DEVELOPMENT`. |
| **$SOH_R$ Point** | UConn REIL Dataset 5 | Real Laboratory Data | 64 cells (21 sealed cells, 956 RPT observations) | Cell Holdout (Pre-registered sealed test) | 0.0094 MAE (1.19% RMSE, +0.30% bias) | **`DEVELOPMENT`** (1.2 Ah cylindrical)<br>*(**`UNQUALIFIED`** for 100 Ah pack)* | Evaluated on real LithiumWerks 18650 cells. Classified `DEVELOPMENT`: failed criterion (d) (reference Step 20 DCIR is not independent of Step 20 pulse features; Ridge achieves lower MAE 0.0091) and (e). Unqualified for 100 Ah pack. |
| **$SOH_R$ Uncertainty** | UConn REIL Dataset 5 | Real Laboratory Data | 64 cells (21 sealed cells, 956 RPT observations) | Cell Holdout (Pre-registered sealed test) | 98.6% empirical coverage ($q_{95}=0.0285$) | **`DEVELOPMENT`** (1.2 Ah cylindrical)<br>*(**`UNQUALIFIED`** for 100 Ah pack)* | Non-parametric conformal quantile calibrated on 11 held-out dev validation cells. Overconservative coverage. Classified `DEVELOPMENT`. |

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

LAB_VALIDATED requires ALL of: (a) real files with verified manifest hashes; (b) every evaluation script tracked in the repo and reproduced from a clean shell; (c) a spec committed BEFORE the sealed set is evaluated; (d) a held-out result that beats a fair baseline on a reference that is independent of the estimator's own integral; (e) enough data to support the claim, stated in numbers. Everything else is DEVELOPMENT.

For physical battery SOH estimation, this specifically entails:
1. **Raw Laboratory Files Outside Repository**: Data must reside at `$SOC_DATA_DIR` (e.g. `~/soc_data`) and be verified against a non-placeholder SHA-256 manifest in `data/manifests/`.
2. **Cell-Held-Out Splits**: Evaluation must follow strict Cell Leave-One-Battery-Out (LOBO) or batch holdouts defined prior to evaluation in `configs/validation/`.
3. **Reference Capacity Protocols**: SOH_C ground truth must be derived from C/20 or standardized 1C reference capacity checkups at controlled temperature (e.g. 25°C).
4. **Standardized DCIR Protocols**: SOH_R ground truth must be derived from standardized 10s HPPC discharge pulses at defined SOC (e.g. 50% SOC) and controlled temperature.


---

## 4. Gustave Eiffel 105 Ah LFP Dataset SOH Evidence Assessment

> [!NOTE] Revision (V1.11 Relabeling Notice)  
> In accordance with Task V1.11 LABEL RULE, LAB_VALIDATED requires: (a) real files with verified manifest hashes; (b) evaluation scripts tracked in the repository and reproduced from a clean shell; (c) a spec committed before sealed evaluation; (d) a held-out result that beats a fair baseline on an independent reference; (e) sufficient data volume. All GE105 results are classified as `DEVELOPMENT` (zero SOH evidence, BOL characterisation only).

> **Dataset:** Gustave Eiffel 105 Ah LFP Dataset (`DOI: 10.57745/G02IYE`, parameters `10.57745/SBNO8W`)  
> **Status:** NO SOH EVIDENCE (Beginning-of-Life Characterisation Only)

The Gustave Eiffel 105 Ah LFP dataset contains tests across four cells (`BUGE388`, `BUGE389`, `BUGE390`, `BUGE391`) conducted exclusively for **beginning-of-life (BOL) electro-thermal characterisation** across temperatures from 0 °C to 40 °C.

Key verification findings regarding SOH:
1. **Zero Degradation Cycling:** The cells were not subjected to long-term cycle aging or calendar aging campaigns. Total accumulated throughput is under 20 equivalent full cycles per cell.
2. **Short Characterisation Protocols:** Tests consist solely of characterisation checkups: initial 1C capacity check cycles, 30 s impedance pulses, C/15 pseudo-OCV ramps, and 986 s dynamic WLTC profiles.
3. **Repeated 25 °C Tests Are Drift, Not Aging:** Repeat 25 °C partial checkups performed on `BUGE388` ($\Delta \text{Cap} = -1.17\%$), `BUGE389` ($\Delta \text{Cap} = -1.89\%$), and `BUGE390` ($\Delta \text{Cap} = -1.27\%$) reflect cycler channel drift, contact impedance variation, and thermal equilibration differences across test days, **not irreversible electrochemical degradation**.
4. **Qualification Implication:** This dataset provides zero valid ground-truth degradation trajectories ($SOH_C$ or $SOH_R$). Therefore, **no SOH estimators can be qualified or awarded `LAB_VALIDATED` status from this dataset**. SOH status remains unchanged across all candidate models.

---

## 5. UConn REIL Dataset 5 SOH Validation Summary (Task V2 & V2.11)

> **Dataset:** UConn REIL Dataset 5 (207 manifest-verified CSV files, 2,855 RPT cycles)  
> **Target Chemistry & Geometry:** LithiumWerks 18650 (APR18650M1B), nominal capacity 1.2 Ah (source: `README_Uconn.txt` line 16, stating 1.2 Ah nominal and aging to 80% SOH, about 0.96 Ah), 64 physical cells  
> **Evaluation Reference:** `reports/validation/uconn_report.md`, `reports/validation/uconn_sealed_test.md`  
> **Calibration Artifact:** `deliverable/calibrations/uconn_soh_pulse_v2.json` (re-labeled post-hoc candidate, modified after unsealing)  
> **C Header:** `deliverable/edge_pkg/soh_pulse_elasticnet_v2.h` (placeholder / unvalidated)

### Summary of Results
Task V2 executed laboratory evaluation of pulse-based SOH estimation across all 64 cells in UConn REIL Dataset 5, spanning 2,855 RPT characterisation cycles across 11 cycling conditions.

1. **Governance Compliance & Relabeling:** Reclassified to **`DEVELOPMENT`** due to unmet criteria (d) and (e):
   - **Criterion (a) [PASS]:** Manifest-verified files (`data/manifests/uconn_reil_dataset5.sha256`, 100% hash match).
   - **Criterion (b) [PASS]:** Tracked scripts in `scripts/validation/` reproducible from clean shell.
   - **Criterion (c) [PASS]:** Specification and partitions committed before unsealing test cells (`f4a8d87`, `f592bc7`).
   - **Criterion (d) [FAIL]:**
     - $SOH_C$: Committed spec named only constant-mean baseline; Ridge regression matches or beats candidate (0.0199 vs 0.0211 MAE); no age-only baseline was named in spec; candidate calibration was modified post-unsealing.
     - $SOH_R$: Ground-truth reference (Step 20 DCIR) shares the voltage response with features ($r_{10\text{s},\text{ohm}}, \Delta V_{10\text{s}}$) extracted from the exact same Step 20 pulse; $SOH_R$ results are not evidence of estimation skill because label and feature are the same physical measurement. A trivial baseline $\widehat{SOH}_R = r_{10\text{s}} / \bar{r}_0$ achieves 0.0095 MAE on sealed cells, matching the candidate model (0.0094) and Ridge (0.0089). When evaluated without $r_{10\text{s}}$ in the 11-feature post-hoc model, SOH_R MAE changed from 0.0094 to 0.0107 (reported as an empirical observation without asserting a cause).
   - **Criterion (e) [FAIL]:** Counted in independent units (21 sealed cells, and only 2 condition groups).
2. **Predictive Performance on Sealed Partition (21 sealed cells, 956 RPT observations):**
   - $SOH_C$ Sealed MAE: 0.0211 (vs Ridge 0.0199; vs Age-Quadratic 0.0221; vs Baseline 0.0427). Overlapping bootstrap intervals with age-quadratic indicate no statistically significant advantage over a cycle counter.
   - $SOH_R$ Sealed MAE: 0.0094 (vs Ridge 0.0091; vs Trivial Baseline 0.0095; vs 11-Feature Candidate 0.0107; vs Age-Quadratic 0.0195; vs Baseline 0.0233). Lower error than age-only is an artifact of measuring resistance directly in the feature, not evidence of degradation estimation skill.
   - Supplementary Condition Holdout: Labeled contaminated, supplementary, not a headline result (17 of 21 sealed cells served as training cells; 8 dev cells served as test cells). On this split, Ridge achieves 0.0201 SOH_C MAE, beating soh_pulse_v2 (0.0219).
3. **Qualification Boundary:**
   - Classified as **`DEVELOPMENT`** for 1.2 Ah cylindrical APR18650M1B LFP cells under laboratory RPT conditions.
   - Strictly **`UNQUALIFIED`** for 100 Ah automotive/grid pack deployment due to cell format mismatch, lack of dynamic drive cycle evaluation, and lack of fleet operational data.
   - Exported C model is strictly PLACEHOLDER / UNVALIDATED (`qual_c = UNQUALIFIED`, `qual_r = UNQUALIFIED`).

---

## 6. What the UConn Results Support

Based on the laboratory evaluation, split independence audit, baseline comparisons, and feature-label identity findings on UConn REIL Dataset 5:

1. **$SOH_C$ on the 21 Sealed Cells:**
   - Ridge achieved 0.0199 MAE, `soh_pulse_v2` achieved 0.0211 MAE, and Age-Quadratic achieved 0.0221 MAE with overlapping cell-bootstrap confidence intervals ([0.0181, 0.0260] vs [0.0199, 0.0281]).
   - **No advantage over Ridge regression or simple cycle counting is demonstrated.**
2. **Interval Coverage for $SOH_C$:**
   - Conformal interval coverage was **91.2%**, falling short of the 95.0% nominal level (undercoverage).
3. **$SOH_R$ Estimation:**
   - The label is $r_{\text{pulse, 10s}}(\text{RPT}_k) / r_{\text{pulse, 10s}}(\text{RPT}_0)$ from Step 20 and the 14-feature model takes $r_{10\text{s},\text{ohm}}$ and $\Delta V_{10\text{s}}$ from the same pulse; a trivial baseline ($r_{10\text{s}} / \bar{r}_0$ over the training cells, $\bar{r}_0 = 0.031755\ \Omega$) scores MAE 0.0060 on dev validation (candidate 0.0073), 0.0095 [0.0066, 0.0126] on sealed cells (candidate 0.0094 [0.0073, 0.0127]), and 0.0103 on the condition holdout (candidate 0.0117); conclusion: **no evidence of estimation skill for $SOH_R$**.
4. **Scale Limitations:**
   - **Zero evidence for 100 Ah cells** (evaluation was strictly on 1.2 Ah cylindrical cells under laboratory characterisation protocols).
5. **C Implementation Status:**
   - The exported C header is **unvalidated and derived from the post-hoc 11-feature model** modified after unsealing.
