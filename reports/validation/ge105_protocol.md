# Gustave Eiffel 105 Ah LFP Validation Protocol (V1.3)

> [!NOTE] Revision (V1.12)  
> Updated `LAB_VALIDATED` definition to the 5-point governance rule, replaced validated operating envelope statement with declared calibration envelope `[20, 45]` °C, and revised cell format terminology (format unverified for CALCE, 105 Ah cell format).

> **Document ID:** PROTOCOL-GE105-001  
> **Date:** 2026-11-19  
> **Dataset:** EVE Energy LFP 105Ah Cells (BUGE388..BUGE391)  
> **Experimental Data DOI:** [10.57745/G02IYE](https://doi.org/10.57745/G02IYE)  
> **Parameter Data DOI:** [10.57745/SBNO8W](https://doi.org/10.57745/SBNO8W)  
> **Licence:** Etalab Open Licence 2.0  
> **Author:** Antigravity / SOC-Lab Validation Team  
> **Status:** Pre-evaluation Frozen Declaration (committed prior to any model evaluation)

---

## 1. Scope and Objective

This protocol governs the real-data validation of equivalent circuit models (2RC ECM) and closed-loop State of Charge (SOC) estimators on the Gustave Eiffel 105 Ah LFP dataset.

The objectives are:
1. Validate open-loop ECM model fidelity on large-format (105 Ah) commercial LFP cells.
2. Determine whether earlier model-gate failures on FlexiPod were data-specific (synthetic pulse artifacts) or method-specific (2RC ECM limitations on LFP chemistry).
3. Evaluate closed-loop SOC tracking accuracy and convergence for frozen E7v3 (with cross-chemistry CALCE calibration and matched GE105 calibration) against baseline Coulomb counting (E0).
4. Establish transferability evidence from CALCE A123 LiFePO4 cell (measured capacity about 1.06 Ah, format unverified) to large traction cells (EVE Energy 105 Ah).

---

## 2. Cell Partitions and Isolation Rules (Rule R3)

Cell partitioning strictly separates model parameter identification and tuning from validation testing:

| Partition | Cell ID | Role | Evaluation Constraints |
|:---|:---:|:---|:---|
| **Development (Train)** | `BUGE388` | ECM parameter identification, OCV curve fitting, and calibration tuning | Freely accessible during development |
| **Development (Val)** | `BUGE389` | Hyperparameter selection, filter tuning, and threshold verification | Freely accessible during development |
| **Sealed Test** | `BUGE390` | Held-out validation cell 1 | **SEALED.** Evaluated exactly once after freezing the specification |
| **Sealed Test** | `BUGE391` | Held-out validation cell 2 | **SEALED.** Evaluated exactly once after freezing the specification |

### Sealed Test Set Access Enforcement
- Access to cells `BUGE390` and `BUGE391` is guarded by `ValidationSplitConfig.get_test_cells(final=True)` in `src/soc/data/registry.py`.
- No calibration parameters, covariance matrices, or estimator thresholds may be adjusted after unsealing `BUGE390` and `BUGE391`.

---

## 3. Ground-Truth SOC Definition and Evaluation Metrics

### 3.1 Nature of the Reference SOC Signal
- In DATTES processed MATLAB files, `profiles.soc` is derived from cycler ampere-hour integration ($I_{\text{file}} \cdot dt$), re-anchored to $100.0\%$ at full-charge cut-off events ($V \ge 3.65\ \text{V}$, $I \le C/20$).
- **Crucial Methodological Caveat:** `profiles.soc` is **NOT** an independent electrochemical truth measurement. It is an Ah-counting reference.
- **Consequence for Baseline Comparison:** Pure anchored Coulomb counting (E0) will align with `profiles.soc` to within numerical integration precision by construction. Consequently, low E0 error does not demonstrate physical superiority—it merely reflects identical integration of the same current channel.

### 3.2 Primary Evaluation Metrics
Estimators are evaluated on:
1. **Convergence Under Initialization Error:** Estimators are initialized with a deliberate $\pm 10.0\ \text{pp}$ error ($SOC_0 = SOC_{\text{true}} \pm 0.10$). Metric: time to converge within $\pm 2.0\ \text{pp}$ of reference ($t_{\text{pull-in}}$).
2. **Dynamic Tracking Error:**
   - Maximum absolute error: $\max |SOC_{\text{est}} - SOC_{\text{ref}}|$ (percentage points, pp).
   - Root Mean Square Error: $\text{RMSE}_{\text{SOC}}$ (pp).
   - Final endpoint error: $|SOC_{\text{est}}(t_{\text{end}}) - SOC_{\text{ref}}(t_{\text{end}})|$ (pp).
3. **Voltage Prediction Error (Closed-Loop Residuals):**
   - Terminal voltage bias: $\text{Bias}_V = \frac{1}{N} \sum (V_{\text{meas}} - V_{\text{pred}})$.
   - Terminal voltage RMSE: $\text{RMSE}_V = \sqrt{\frac{1}{N} \sum (V_{\text{meas}} - V_{\text{pred}})^2}$.
4. **Implementation Parity:** Absolute difference between Python E7v3 and C-reference `deliverable/bms_soc_ref.py`:
   $$\max |SOC_{\text{python}} - SOC_{\text{bms\_ref}}| \le 10^{-12}$$

---

## 4. Timebase and Resampling Protocol

1. **Primary Grid ($\Delta t = 1.0\ \text{s}$):**
   - Dynamic drive cycles (WLTC) are resampled to a uniform 1.0-second time grid.
   - Charge conservation: Step current $I_k$ is calculated via exact trapezoidal integration across the 1.0 s interval:
     $$I_k = \frac{1}{\Delta t} \int_{t_k}^{t_{k+1}} I(t) dt$$
   - Terminal voltage $V_k$ and reference $SOC_k$ are linearly interpolated onto the 1.0 s grid.
   - No interpolation is permitted across rests exceeding 10.0 seconds.
2. **Sensitivity Grid (Native Irregular $\Delta t$):**
   - The native time series ($\Delta t \in [0.002, 10.026]\ \text{s}$) is evaluated in parallel to test E7v3's continuous-discrete matrix exponential state transition under varying time steps.

---

## 5. Dynamic Segment Extraction (WLTC)

WLTC driving cycles are extracted from full-protocol files (at 0, 25, 40 °C):
- **Detection Criteria:** Exactly 44 consecutive constant-current micro-phases (mode 1) with individual durations $\le 120.0\ \text{s}$, totaling $986.0 \pm 1.0\ \text{s}$.
- **Segment 1 (~90% SOC):** Executed after discharging ~10.5 Ah from full charge followed by 1 hour rest.
- **Segment 2 (~50% SOC):** Executed after discharging an additional ~38.2 Ah followed by 30 minutes rest.
- **Test Integrity Gate:** A dedicated unit test asserts that all eligible full-protocol files yield exactly two segments. (Baseline 2023-06-27 files BUGE390/391 25C terminated at phase 166 before WLTC was added to the cycler protocol).

---

## 6. Open-Loop ECM Gate (Step V1.4)

Before closed-loop estimator testing, the underlying 2RC equivalent circuit model must pass the open-loop fidelity gate on dev cells (`BUGE388` and `BUGE389`):

| Gate Metric | Threshold | Physical Rationale |
|:---|:---:|:---|
| **Voltage Bias** | $\le 2.0\ \text{mV}$ | Verifies unbiased OCV and polarization modeling |
| **Voltage RMSE** | $\le 6.0\ \text{mV}$ | Ensures RC time-constant dynamic tracking fidelity |
| **Implied SOC Error** | $\le 2.5\ \text{pp}$ | Bounded worst-case open-loop SOC drift |

Thresholds are kept strictly identical to the repository standard; no tuning or loosening is permitted.

---

## 7. Operational Status Labels (Rule R8)

Results are tagged according to the repository validation rules:
- **`LAB_VALIDATED`**: LAB_VALIDATED requires ALL of: (a) real files with verified manifest hashes; (b) every evaluation script tracked in the repo and reproduced from a clean shell; (c) a spec committed BEFORE the sealed set is evaluated; (d) a held-out result that beats a fair baseline on a reference that is independent of the estimator's own integral; (e) enough data to support the claim, stated in numbers. Everything else is DEVELOPMENT. Applied declared calibration envelope [20, 45] C (ge105_v1.json); dynamic evidence exists at 25 and 40 C (dev) and 40 C (test) only.
- **`DEVELOPMENT`**: Assigned to dev-cell evaluations (`BUGE388`, `BUGE389`), intermediate calibrations, and tests run outside the validated envelope (e.g. 0 °C, which is explicitly tagged `OUT_OF_ENVELOPE`).

---

## 8. SOH Scope Limitation

Per Rule 1 and Rule 8:
- The Gustave Eiffel dataset consists exclusively of beginning-of-life (BOL) characterisation tests.
- Re-tests at 25 °C represent cycler/contact measurement repeatability and temporal drift, not degradation.
- **NO SOH results** will be claimed or generated from this dataset.
