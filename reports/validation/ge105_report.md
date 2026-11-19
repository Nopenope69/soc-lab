# Gustave Eiffel 105 Ah LFP Dataset: Comprehensive Validation Report (Task V1)

> [!NOTE] Revision (V1.12 Documentation Honesty and Provenance Auditing)  
> - Updated cell format descriptions: replaced cylindrical/26650 assertions with "CALCE A123 LiFePO4 cell (measured capacity about 1.06 Ah, format unverified)" and noted format unverified in readmes for 105 Ah cells.  
> - Model Gate: Added full 8-condition out-of-sample cross-validation table (Section 4.3), corrected voltage-RMSE bar to pre-registered 6.0 mV (citing reports/flexipod1/model_gate.md), replaced inter-cell impedance variation speculation with untested attribution, and marked Kalman gain scaling as untested (no ablation).  
> - Appended Section 9 detailing V1.12 audit and governance findings, commands run, and real test counts.

> [!NOTE] Revision (V1.11 Relabeling Notice)  
> In accordance with Task V1.11 LABEL RULE, all GE105 test cell results are reclassified from `LAB_VALIDATED` to **`DEVELOPMENT`**.  
> **Unmet LABEL RULE Criteria:**  
> - **Criterion (c):** Specification was not committed to git prior to unsealing (committed simultaneously with results in `847843c`).  
> - **Criterion (d):** Reference `profiles.soc` is an Ah-counting current integral, not an independent electrochemical ground truth; nominal tracking is identical to E0.  
> - **Criterion (e):** Insufficient data volume: in-envelope test data covers only 12 scenarios of 986 s at 40 °C (25 °C full tests for BUGE390/391 lack WLTC segments).

> **Document ID:** VAL-GE105-FINAL-001  
> **Date:** 2026-11-19  
> **Repository:** `/Users/tecbusiness/Desktop/random/SOC`  
> **Data Root:** `/Users/tecbusiness/soc_data` (`$SOC_DATA_DIR`)  
> **Dataset Source:** Université Gustave Eiffel / DATTES (DOI `10.57745/G02IYE`, parameters `10.57745/SBNO8W`)  
> **Cell Chemistry & Geometry:** EVE Energy 105 Ah Lithium Iron Phosphate (LFP) (format unverified in dataset readmes)  
> **Branch:** `validation/ge105`  
> **Evaluation Protocol:** Strictly Cell-Held-Out (Dev: `BUGE388`, `BUGE389`; Sealed Test: `BUGE390`, `BUGE391`)  
> **Estimators Evaluated:**  
> - **E0**: Baseline Anchored Coulomb Counting (Nominal 105.04 Ah)  
> - **Frozen E7v3 (CALCE Calibration)**: Cross-chemistry/scale baseline (`calce_a123_v4.json`)  
> - **E7v3 (GE105 Calibration)**: Matched calibration container (`ge105_v1.json`)  
> - **Reference Implementation**: `deliverable/bms_soc_ref.py` (executed in parallel)

---

## 1. Executive Summary & Qualification Status

This report synthesizes the end-to-end laboratory validation of state-of-charge (SOC) estimation and Equivalent Circuit Model (ECM) identification using physical, hash-manifested laboratory test data from the Gustave Eiffel 105 Ah LFP dataset.

### Formal Qualification Labels

In compliance with the Phase 6 / Hardening validation rules and V1.11 LABEL RULE:

| Evaluation Scope | Partition | Operating Condition | Result Label | Justification |
|:---|:---|:---:|:---:|:---|
| **Dynamic WLTC Tracking** | Test (`BUGE390`, `BUGE391`) | 40 °C (In-Envelope) | **`DEVELOPMENT`** | Reclassified from LAB_VALIDATED per V1.11 LABEL RULE criteria (c), (d), and (e). Test evaluation script tracked and reproduced from clean shell. |
| **Dynamic WLTC Tracking** | Dev (`BUGE388`, `BUGE389`) | 25 °C & 40 °C | **`DEVELOPMENT`** | Used for calibration parameter extraction and sanity checks. Nominal RMSE 1.19–2.12 pp. |
| **Low-Temperature Tracking** | All 4 Cells | 0 °C (Out-of-Envelope) | **`DEVELOPMENT`** | Filter safely self-reports `OUT_OF_ENVELOPE` on 100% of samples (operational envelope $20\text{--}45\ ^\circ\text{C}$). |
| **Capacity-Mismatch Demo** | All 4 Cells | E7v3 CALCE Raw (1.06 Ah) | **`FAIL`** | Capacity-mismatch demonstration (1.06 Ah table on 105 Ah cell), not a transfer result. Fair scaled CALCE achieves 3.8–5.9 pp RMSE. |
| **SOH Tracking ($SOH_C$, $SOH_R$)** | All 4 Cells | All Temperatures | **`NO SOH EVIDENCE`** | Dataset contains beginning-of-life (BOL) characterisation only; zero cycle or calendar aging data. |

---

## 2. Dataset Inventory & Integrity Verification (V1.1 - V1.2)

1. **Physical Manifest Verification:**
   - 36 processed `.mat` files across 4 physical cells (`BUGE388`: 9, `BUGE389`: 9, `BUGE390`: 10, `BUGE391`: 8).
   - 100% of files verified against SHA-256 checksums in `data/manifests/gustave_eiffel_g02iye.sha256` (`INTEGRITY_OK`).
   - Published parameter file `batt_data.mat` verified against `data/manifests/gustave_eiffel_sbno8w.sha256`.
2. **Sampling & Timebase Properties:**
   - Irregular sampling: strictly positive monotonic $\Delta t$ (0 non-positive samples), median $0.1\ \text{s}$, minimum $0.0019\ \text{s}$, maximum $10.026\ \text{s}$.
   - Primary evaluation resampled onto a uniform $1.0\ \text{s}$ grid using sub-interval trapezoidal charge conservation. Timebase sensitivity testing showed that native irregular $\Delta t$ introduces $< 0.17\ \text{pp}$ difference in tracking RMSE.
3. **Current Sign Convention:**
   - Raw MAT files use charge-positive current (Coulomb counting slope $d(DoD)/d(\int I dt) = -1.0$).
   - The loader `src/soc/data/ge105_loader.py` canonicalizes this in a single place to repo discharge-positive convention ($I_{\text{repo}} = -I_{\text{file}}$).
4. **Thermal Channel Quirks:**
   - The time-series struct field `profiles.T` is empty across all files.
   - Temperature input is strictly mapped to the thermal chamber setpoint extracted from the canonical filename regex `^(\d{8})_(\d{4})_(.+?)_(\d+)C(?:_([a-zA-Z0-9]+))?_([a-zA-Z0-9]+)_dattes\.mat$`.
5. **WLTC Structure Across Files:**
   - All full-protocol files contain exactly two 44-phase dynamic WLTC segments (986 seconds each) at ~90% SOC and ~50% SOC, except the earliest test files for `BUGE390` 25C and `BUGE391` 25C (both 2023-06-27), which terminated at phase 166 before WLTC was incorporated into the test script.
6. **Per-Cell Metadata Capacity Variation (`result.metadata.cell.nom_capacity`):**
   Inspection of the MAT structure field `result.metadata.cell.nom_capacity` across all 36 files reveals that in DATTES, this field does not represent a static nameplate specification, but rather a run-specific measured capacity that varies across tests:

| Cell ID | File Name | `result.metadata.cell.nom_capacity` (Ah) | Matches `105.042655`? |
|:---|:---|:---:|:---:|
| **BUGE388** | `20230804_1122_full_0C_buge388_dattes.mat` | 103.664478 | No |
| **BUGE388** | `20230808_1118_partial_10C_buge388_dattes.mat` | 105.387856 | No |
| **BUGE388** | `20230810_1112_partial_15C_buge388_dattes.mat` | 105.303818 | No |
| **BUGE388** | `20230825_1333_full_25C_buge388_dattes.mat` | **105.042655** | **YES (Exact match)** |
| **BUGE388** | `20230829_1115_partial_20C_buge388_dattes.mat` | 104.729185 | No |
| **BUGE388** | `20231110_1642_partial_25C_buge388_dattes.mat` | 103.799427 | No |
| **BUGE388** | `20231116_1716_partial_30C_buge388_dattes.mat` | 103.809594 | No |
| **BUGE388** | `20231120_1103_partial_35C_buge388_dattes.mat` | 103.798772 | No |
| **BUGE388** | `20231123_1349_full_40C_buge388_dattes.mat` | 103.847153 | No |
| **BUGE389** | `20230808_1242_full_25C_buge389_dattes.mat` | 105.750278 | No |
| **BUGE389** | `20230812_2136_full_0C_buge389_dattes.mat` | 103.031451 | No |
| **BUGE389** | `20230816_1246_partial_35C_buge389_dattes.mat` | 104.233152 | No |
| **BUGE389** | `20230822_1420_partial_20C_buge389_dattes.mat` | 103.739411 | No |
| **BUGE389** | `20230825_1339_full_40C_buge389_dattes.mat` | 104.276614 | No |
| **BUGE389** | `20230830_1602_partial_30C_buge389_dattes.mat` | 103.498032 | No |
| **BUGE389** | `20230901_1054_partiel_15C_buge389_dattes.mat` | 103.446786 | No |
| **BUGE389** | `20230904_1341_partial_10C_buge389_dattes.mat` | 102.888420 | No |
| **BUGE389** | `20230905_1721_partial_25C_buge389_dattes.mat` | 103.196057 | No |
| **BUGE390** | `20230627_1131_full_25C_buge390_dattes.mat` | 106.635223 | No |
| **BUGE390** | `20230703_1138_pseudoOCV_25C_buge390_dattes.mat` | 105.991817 | No |
| **BUGE390** | `20230710_1503_partial_15C_buge390_dattes.mat` | 105.402544 | No |
| **BUGE390** | `20230712_1137_full_0C_buge390_dattes.mat` | 103.905782 | No |
| **BUGE390** | `20230717_1001_partial_20C_buge390_dattes.mat` | 105.323820 | No |
| **BUGE390** | `20230718_1510_partial_30C_buge390_dattes.mat` | 105.508861 | No |
| **BUGE390** | `20230720_1112_partial_35C_buge390_dattes.mat` | 105.491448 | No |
| **BUGE390** | `20230721_2113_full_40C_buge390_dattes.mat` | 105.867902 | No |
| **BUGE390** | `20230724_1505_partial_10C_buge390_dattes.mat` | 104.737433 | No |
| **BUGE390** | `20230726_0918_partial_25C_final_buge390_dattes.mat` | 104.886871 | No |
| **BUGE391** | `20230627_1135_full_25C_buge391_dattes.mat` | 106.537465 | No |
| **BUGE391** | `20230712_1137_full_0C_buge391_dattes.mat` | 104.200387 | No |
| **BUGE391** | `20231205_1137_partial_20C_buge391_dattes.mat` | 104.157114 | No |
| **BUGE391** | `20231207_1254_partial_15C_buge391_dattes.mat` | 104.202208 | No |
| **BUGE391** | `20231211_1606_partial_10C_buge391_dattes.mat` | 103.675439 | No |
| **BUGE391** | `20231214_1526_partial_30C_buge391_dattes.mat` | 103.943779 | No |
| **BUGE391** | `20240130_1403_partial_35C_buge391_dattes.mat` | 103.532242 | No |
| **BUGE391** | `20240201_1650_full_40C_buge391_dattes.mat` | 104.435322 | No |

**Conclusion:** The constant `105.042655` hardcoded in `src/soc/data/ge105_loader.py` and allowlisted in `tests/allowlisted_constants.json` matches **only one single file** (`BUGE388` 25 °C full test). It does not match the other three cells (`BUGE389`, `BUGE390`, `BUGE391`) or even other tests on the same cell (`BUGE388`), which range between 102.88 Ah and 106.64 Ah. No code changes are made to frozen loaders or allowlists per task instructions.

---

## 3. Open-Loop Model Gate & Diagnostic Analysis (V1.4 - V1.5)

### Separation of Criteria: Voltage Tracking vs. Implied-SOC Inversion
The open-loop model gate evaluates two distinct criteria that must not be conflated:
1. **Dynamic Voltage Tracking:** Evaluates terminal voltage tracking error ($|\text{Bias}_V| \le 2.0\ \text{mV}$, $\text{RMSE}_V \le 6.0\ \text{mV}$; cite `reports/flexipod1/model_gate.md`).
   - **FlexiPod:** The model **failed on voltage tracking**, exhibiting terminal voltage RMSE of **23 to 87 mV** (well exceeding the pre-registered $\le 6.0\ \text{mV}$ threshold; cite `reports/flexipod1/model_gate.md`). Note that the FlexiPod comparison is between different tests (continuous constant-current discharge curves versus dynamic WLTC segments), so a gap exists but its cause is not established.
   - **Gustave Eiffel (In-Sample):** 2RC voltage tracking **passes** on the plateau at 50% SOC with terminal voltage RMSE of **2.62 mV to 3.12 mV** (passing $\le 6.0\ \text{mV}$) and bias of **-1.18 mV to -1.41 mV** (passing $\le 2.0\ \text{mV}$).
2. **Implied-SOC Error Inversion:** Evaluates open-loop voltage error mapped into SOC space ($\frac{|\Delta V|}{d\text{OCV}/d\text{SOC}} \le 2.5\ \text{pp}$ or $\le 5.0\ \text{pp}$).
   - **Gustave Eiffel:** Implied-SOC error **fails across all conditions**, yielding **6.1 pp to 7.5 pp at 50% SOC** and **12.5 pp to 14.3 pp at 90% SOC** (failing both $\le 2.5\ \text{pp}$ and $\le 5.0\ \text{pp}$).
   - **Physical Cause:** The derivative $d\text{OCV}/d\text{SOC}$ on the LFP two-phase plateau is near zero ($< 1\ \text{mV}/\%$). Any minute unmodeled polarization or hysteresis residual of merely $2\text{--}3\ \text{mV}$ directly causes an open-loop implied SOC error of $6\text{--}14\ \text{pp}$. The implied-SOC criterion is plateau-limited on any LFP cell and this was known in advance.
3. **Closed-Loop Divergence Risk:** The filter does **not** automatically correct for plateau divergence. As demonstrated in closed-loop testing on held-out test cells (Item 4), when disturbed by +10 pp at 50% SOC, E7v3 diverges on the flat plateau, ending at **12.15 pp** on `BUGE390` and **16.23 pp** on `BUGE391` (worse than open-loop Coulomb counting E0).

### In-Sample Identification & Out-of-Sample Cross-Validation
- **In-Sample Notice:** The 2RC parameters identified in step V1.4 were identified directly from the same WLTC dynamic segments on which they were evaluated in step V1.5.
- **Out-of-Sample Cross-Validation:** Evaluating parameters fit on `BUGE388` against `BUGE389` data and vice-versa (dev partition only):

| Fit Cell | Eval Cell | Temp | Target SOC | Voltage Bias (mV) | Voltage RMSE (mV) | Implied SOC Err (pp) | Voltage Gate | Implied SOC Gate |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **BUGE388** | **BUGE389** | 25 °C | 90% | -6.23 | 7.92 | 15.60 | FAIL | FAIL |
| **BUGE388** | **BUGE389** | 25 °C | 50% | -2.64 | 3.77 | 7.60 | FAIL | FAIL |
| **BUGE388** | **BUGE389** | 40 °C | 90% | -2.02 | 5.13 | 14.39 | FAIL | FAIL |
| **BUGE388** | **BUGE389** | 40 °C | 50% | -0.77 | 2.97 | 7.07 | **PASS** | FAIL |
| **BUGE389** | **BUGE388** | 25 °C | 90% | -2.18 | 6.59 | 13.49 | FAIL | FAIL |
| **BUGE389** | **BUGE388** | 25 °C | 50% | -0.39 | 3.44 | 7.76 | **PASS** | FAIL |
| **BUGE389** | **BUGE388** | 40 °C | 90% | -1.92 | 5.06 | 12.53 | **PASS** | FAIL |
| **BUGE389** | **BUGE388** | 40 °C | 50% | -0.62 | 2.85 | 7.42 | **PASS** | FAIL |

**Out-of-Sample Results:** Across 8 conditions evaluated out-of-sample:
- **Pass Rates:** 4 of 8 conditions pass the bias gate ($|\text{Bias}_V| \le 2.0\ \text{mV}$); 6 of 8 conditions pass the voltage RMSE gate ($\text{RMSE}_V \le 6.0\ \text{mV}$).
- **RMSE Extremes:** Worst voltage RMSE is **7.92 mV** (at 25 °C / 90% SOC BUGE388 $\to$ BUGE389; 6.59 mV in reverse direction), showing degradation at 25 °C / 90% SOC (RMSE 6.59 and 7.92 mV, above the 6.0 mV bar); cause not tested. Best voltage RMSE is **2.85 mV** (at 40 °C / 50% SOC; 2.97 mV in reverse direction).
- **Implied SOC:** Fails across all 8 conditions (7.07 pp to 15.60 pp vs $\le 2.5\ \text{pp}$) due to plateau flatness.
- **Closed-Loop Gating:** The assertion that observability-based Kalman gain scaling is essential to prevent plateau runaway is marked as **not tested (no ablation)**.

### ECM Parameter Agreement with Published Dataset (SBNO8W)
- **Ohmic Resistance ($R_0$):** Our WLTC regression yielded $0.565\ \text{m}\Omega$ at 25 °C and $0.461\ \text{m}\Omega$ at 40 °C. The author's published pulse extraction in `batt_data.mat` reported $0.537\ \text{m}\Omega$ at 25 °C (5.2% difference) and $0.435\ \text{m}\Omega$ at 40 °C (5.9% difference).
- **Time Constants ($\tau_1, \tau_2$):** Dynamic driving cycles (WLTC) excite much longer solid-state diffusion relaxation modes ($\tau_1 \approx 9.5\ \text{s}, \tau_2 \approx 178\ \text{s}$) than the 30-second pulses in `batt_data.mat` ($\tau_1 \approx 0.9\ \text{s}, \tau_2 \approx 24\ \text{s}$).

---

## 4. Cell-to-Cell Variation & Hysteresis Findings (V1.6)

1. **Cell Manufacturing Consistency (BOL):**
   - 1C Discharge Capacity across 4 cells: mean $105.99\ \text{Ah}$, range $[105.15, 106.75]\ \text{Ah}$ (spread: **1.51%**).
   - Ohmic Resistance ($R_0$) across 4 cells: mean $0.588\ \text{m}\Omega$, range $[0.539, 0.629]\ \text{m}\Omega$ (spread: **15.3%**).
2. **C/15 Pseudo-OCV Hysteresis Characterisation:**
   - At 25 °C: Total gap is $61.5\text{--}66.2\ \text{mV}$, corresponding to a half-gap $M \approx 30.7\text{--}33.1\ \text{mV}$.
   - At 40 °C: Total gap is $50.1\text{--}52.8\ \text{mV}$, corresponding to a half-gap $M \approx 25.1\text{--}26.4\ \text{mV}$.
   - At 0 °C: Total gap is $125\text{--}150\ \text{mV}$, corresponding to a half-gap $M \approx 62.5\text{--}75.0\ \text{mV}$.
3. **Pseudo-OCV Hysteresis Comparison (GE105 vs. CALCE):**
   - In `calce_a123_v4.json`, the calibrated hysteresis amplitude at 25 °C was $17.19\ \text{mV}$, while at 40 °C it was $21.55\ \text{mV}$.
   - The Gustave Eiffel physical measurements demonstrate that pseudo-OCV hysteresis decreases monotonically with increasing temperature ($M(0^\circ\text{C}) \approx 62.5\text{--}75.0\ \text{mV} > M(25^\circ\text{C}) \approx 30.7\text{--}33.1\ \text{mV} > M(40^\circ\text{C}) \approx 25.1\text{--}26.4\ \text{mV}$).
   - A different cell (105 Ah cell) shows a larger pseudo-OCV hysteresis gap than the CALCE A123 LiFePO4 cell (measured capacity about 1.06 Ah, format unverified); this says nothing about whether the CALCE calibration was suspect.

---

## 5. Calibration Container (`ge105_v1.json`) & Operational Envelope Analysis

Constructed strictly from the development partition (`BUGE388` and `BUGE389`):
- **Path:** `deliverable/calibrations/ge105_v1.json`
- **SHA-256 Checksum:** `b5bb35137e08e1b6da985cbe03fb9d611748ad886d016783af530187cdb9111c`
- **Nominal Capacity:** $105.042655\ \text{Ah}$
- **Operational Envelope Fields:** $T \in [20.0, 45.0]\ ^\circ\text{C}$, $V \in [2.0, 3.7]\ \text{V}$, $I \in [-120.0, 120.0]\ \text{A}$
- **Strict Validation:** Passed 100% of schema checks (`CellCalibration.validate()`).

### Operational Envelope Limits & Evidence Basis (Item 9)

Lines 245–264 of `deliverable/calibrations/ge105_v1.json`:
```json
    "15.0": 179.15,
    "20.0": 179.15,
    "25.0": 179.15,
    "30.0": 179.15,
    "35.0": 179.15,
    "40.0": 167.35
  },
  "temp_max_c": 45.0,
  "temp_min_c": 20.0,
  "temperatures_c": [
    0.0,
    10.0,
    15.0,
    20.0,
    25.0,
    30.0,
    35.0,
    40.0
  ],
  "validation_status": "DEVELOPMENT",
```

The code that generated this calibration envelope (step 5540):
```python
calib = CellCalibration(
    calibration_id='ge105_v1',
    schema_version='1.0',
    validation_status='DEVELOPMENT',
    temperatures_c=temps,
    soc_grid=soc_grid,
    ...
    temp_min_c=20.0,
    temp_max_c=45.0,
    voltage_min_v=2.0,
    voltage_max_v=3.7,
    current_min_a=-120.0,
    current_max_a=120.0,
)
```

> [!WARNING] Operational Envelope Limitation  
> Dynamic drive cycle data in the Gustave Eiffel dataset exists **only at 25 °C and 40 °C** (dev partition) and **40 °C** (test partition). Therefore, an operational envelope claiming validity down to 20 °C and up to 45 °C is an analytical extrapolation assumption not supported by dynamic experimental data. The frozen calibration file remains untouched per freezing rules.

---

## 6. Closed-Loop Performance Evaluation (V1.8 - V1.9)

### Performance Comparison: E0 vs E7v3 (CALCE) vs E7v3 (GE105)

The evaluation was executed across 36 development scenarios and 24 sealed test scenarios:

```
                                  NOMINAL INITIALIZATION (~90% SOC, 40 °C)
      Estimator               BUGE390 (Test)           BUGE391 (Test)          Verdict
  ---------------------------------------------------------------------------------------------------------
  E0 (Coulomb Counting)      0.05 pp Max / 0.02 RMSE  0.03 pp Max / 0.01 RMSE   Anchored Ref (Ah Integral)
  E7v3 CALCE Raw (1.06 Ah)  69.62 pp Max / 27.96 RMSE 68.89 pp Max / 27.84 RMSE  FAIL (Capacity Mismatch)
  E7v3 CALCE Fair (105 Ah)  12.79 pp Max /  5.88 RMSE 11.10 pp Max /  3.82 RMSE  Post-Hoc Fair Baseline
  E7v3 (GE105 Calib)         0.05 pp Max / 0.02 RMSE  0.12 pp Max / 0.05 RMSE   DEVELOPMENT (Item 3)
```

> **Critical Note on Nominal Results:**  
> Nominal-initialisation RMSE is identical between E0 and E7v3 (0.01 pp to 0.02 pp) because the reference `profiles.soc` is simply an Ah-counting current integral re-anchored at full-charge events. It is not an independent electrochemical ground truth. Consequently, near-zero tracking error under nominal initialization **carries no accuracy information** regarding the true physical SOC. Furthermore, the in-envelope sealed evidence is strictly limited to **12 scenarios of 986 s at 40 °C only**, as `BUGE390` and `BUGE391` 25 °C full files contain no WLTC segments. Cell temperature is an external climatic chamber setpoint, not measured cell core or surface temperature.

### Disturbance Recovery Characterisation (8 Perturbed In-Envelope Scenarios)

The closed-loop recovery response of E7v3 (GE105 calibration) across the 8 perturbed held-out test scenarios at 40 °C:

| Cell | Target SOC | Scenario | Initial Err | E0 Max (pp) | E0 RMSE (pp) | E0 Final (pp) | E7 GE105 Max (pp) | E7 GE105 RMSE (pp) | E7 GE105 Final (pp) | Final $\Delta$ vs E0 (pp) | Recovery Verdict |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **BUGE390** | ~90% | +10 pp | +10.0 pp | 9.93 | 9.90 | 9.93 | 8.92 | 4.95 | 5.03 | -4.90 pp | Closer to truth |
| **BUGE390** | ~90% | -10 pp | -10.0 pp | 10.05 | 10.02 | 10.05 | 10.47 | 9.46 | 6.80 | -3.25 pp | Closer (peaked above E0) |
| **BUGE390** | ~50% | +10 pp | +10.0 pp | 10.01 | 9.98 | 10.01 | 12.15 | 8.08 | 12.15 | +2.14 pp | **Worse than start & E0** |
| **BUGE390** | ~50% | -10 pp | -10.0 pp | 10.05 | 10.02 | 10.05 | 10.01 | 8.17 | 4.17 | -5.88 pp | Closer to truth |
| **BUGE391** | ~90% | +10 pp | +10.0 pp | 10.03 | 10.01 | 10.03 | 9.00 | 5.06 | 5.17 | -4.86 pp | Closer to truth |
| **BUGE391** | ~90% | -10 pp | -10.0 pp | 10.01 | 9.99 | 10.01 | 10.38 | 9.10 | 6.02 | -3.99 pp | Closer to truth |
| **BUGE391** | ~50% | +10 pp | +10.0 pp | 10.03 | 10.01 | 10.03 | 16.86 | 9.51 | 16.23 | +6.20 pp | **Worse than start & E0** |
| **BUGE391** | ~50% | -10 pp | -10.0 pp | 10.01 | 9.99 | 10.01 | 10.09 | 8.22 | 5.73 | -4.28 pp | Closer to truth |

**Observations on Disturbance Dynamics:**
1. **Convergence in 6 of 8 Scenarios:** 6 out of 8 perturbed scenarios end closer to truth than the baseline Coulomb counter E0.
2. **Plateau Divergence (+10 pp at ~50% SOC):** In both +10 pp runs at 50% SOC, final error ends **worse than the initial +10 pp error** (12.15 pp on BUGE390 and 16.23 pp on BUGE391, compared to E0's 10.01 pp and 10.03 pp). On the flat plateau ($d\text{OCV}/d\text{SOC} \approx 0$), small voltage residuals do not provide a reliable gradient to correct a positive offset, allowing updates to drift away from truth.
3. **Transient Overshoot (-10 pp at ~90% SOC):** On BUGE390, the -10 pp disturbance peaked above E0 (**10.47 pp** max error against E0's **10.05 pp**) before recovering to 6.80 pp.

### Key Closed-Loop Insights:
1. **Coulomb Counting (E0) Limitations:** While E0 appears near-perfect when initialized with zero error (by definition, as `profiles.soc` is an Ah integration), it has zero feedback capability and preserves initialization errors indefinitely.
2. **CALCE Capacity-Mismatch Demo vs. Fair Baseline:** Applying the unscaled 1.06 Ah CALCE calibration to a 105 Ah cell causes ~100x internal current-to-capacity scaling distortions, resulting in severe state saturation and 70–88 pp errors; this was purely a demonstration of capacity mismatch. When CALCE's nominal capacity is properly scaled to 105.04 Ah via `ParamSet` (evaluated post-hoc after unsealing), frozen E7v3 achieves 3.82–5.88 pp RMSE on test cells at 40 °C (~90% SOC).
3. **Matched E7v3 Performance:** E7v3 equipped with `ge105_v1.json` demonstrates good nominal tracking on physical cells, but disturbance recovery is non-uniform across SOC operating regions.
4. **Reference Implementation Parity Discrepancy:** Concurrent execution of `deliverable/bms_soc_ref.py` confirmed 100% agreement on operating status flags (`['OK']` at 40 °C, `['OUT_OF_ENVELOPE']` at 0 °C) and near-zero error under nominal conditions ($1.1\times 10^{-3}$ to $3.1\times 10^{-3}$ max $|d\text{SOC}|$). However, under perturbed conditions in-envelope, discrepancy reaches **up to 3.61 pp** ($3.61\times 10^{-2}$), and out of envelope up to **9.82 pp** ($9.82\times 10^{-2}$). This occurs because `deliverable/bms_soc_ref.py` uses the calibration file's capacity and temperature-dependent $Q(T)$ table directly, whereas research `e7v3.py` linearly scales CALCE's $Q(T)$ curve by nominal capacity.

---

## 7. Critical Limitations & Scope of Validity

To prevent misleading claims, the following boundaries must be observed:
1. **Beginning-of-Life (BOL) Only:**
   - The Gustave Eiffel dataset consists entirely of unaged, pristine cells (fewer than 20 equivalent full cycles per cell).
   - **Zero SOH evidence exists in this dataset.** No capacity fade or resistance growth tracking can be validated.
2. **Absence of Cell Surface Temperature Telemetry:**
   - All tests were conducted in thermal chambers where only the ambient setpoint is recorded.
   - Core cell self-heating under 1C WLTC dynamic peaks cannot be observed or modeled from this telemetry.
3. **Reference Truth Definition:**
   - Ground truth `profiles.soc` is an Ah-counting reference derived from cycler current integration re-anchored at full charge events, not an independent electrochemical or chemical measurement.
4. **Transfer Evidence vs. Deployment Validation:**
   - The Gustave Eiffel cells are EVE Energy 105 Ah LFP cells.
   - FlexiPod uses a distinct pack architecture and battery chemistry/supplier.
   - Consequently, this report provides **transfer evidence** demonstrating that the E7v3 architecture scales from CALCE A123 LiFePO4 cell (measured capacity about 1.06 Ah, format unverified) to 105 Ah cells. It does **NOT** constitute direct production deployment validation for FlexiPod.

---

## 8. V1.11: Reproducibility, Transparency and Baseline Corrections

This section summarises the reproducibility and honesty corrections completed during Task V1.11:

1. **Recovery and Tracking of Evaluation Scripts (Item 1 & 12):**
   - Step V1.9 evaluated sealed test cells using a script residing only in the temporary scratch directory (`eval_test_cells.py`), backed up to `/Users/tecbusiness/soc_backup/v1_scratch/eval_test_cells.py`.
   - Clean, reproducible, repository-tracked scripts were established: `scripts/validation/ge105_eval_dev.py` and `scripts/validation/ge105_eval_test.py`, using portable path resolution via `resolve_dataset_dir('gustave_eiffel_g02iye')` and YAML configurations (`configs/validation/ge105_splits.yaml`).
   - Clean-shell execution produced `reports/validation/ge105_reproduction.md`, proving 0.00 pp discrepancy against all committed tables.
   - Exact git timestamps and commit provenance were documented in `reports/validation/ge105_spec_provenance.md`.

2. **Relabeling to DEVELOPMENT (Item 3):**
   - In accordance with the revised LABEL RULE, GE105 test results were reclassified from `LAB_VALIDATED` to `DEVELOPMENT` in `reports/validation/ge105_report.md`, `reports/validation/ge105_closed_loop_test.md`, and `docs/SOH_STATUS.md` due to unmet criteria (c) (spec committed before test evaluation), (d) (beating fair baseline on independent reference), and (e) (sufficient data to support claim).

3. **Plateau Disturbance Divergence Characterisation (Item 4):**
   - Replaced optimistic summary phrasing with exact metrics across all 8 perturbed scenarios.
   - Highlighted that for +10 pp perturbations at ~50% SOC, the filter drifts away from truth on the flat plateau, ending at **12.15 pp** on `BUGE390` and **16.23 pp** on `BUGE391` (worse than the initial 10.0 pp disturbance and worse than Coulomb counting E0).

4. **Nominal Baseline Clarification (Item 5):**
   - Clarified that nominal-initialisation RMSE is identical between E0 and E7v3 (0.01 pp to 0.02 pp) because `profiles.soc` is an Ah current integral carrying no independent electrochemical ground truth.
   - Documented that dynamic in-envelope sealed evidence is strictly limited to 12 scenarios of 986 s at 40 °C only, and cell temperature is a chamber setpoint.

5. **Post-Hoc Fair Scaled CALCE Baseline (Item 6):**
   - Relabeled the raw CALCE column as a capacity-mismatch demonstration (1.06 Ah vs 105 Ah).
   - Added a fair baseline using CALCE parameters scaled to 105.04 Ah via the existing `ParamSet` mechanism, which achieves 3.82–5.88 pp RMSE on test cells at 40 °C (~90% SOC), evaluated post-hoc.

6. **Model Gate Corrections & Out-of-Sample Cross-Validation (Item 7):**
   - Separated acceptance criteria: FlexiPod failed voltage tracking (RMSE 23–87 mV vs pre-registered $\le 6.0\ \text{mV}$; cite `reports/flexipod1/model_gate.md`); GE105 passes voltage tracking ($\le 3.12\ \text{mV}$) but fails implied-SOC ($6.1\text{--}14.3\ \text{pp}$) due to plateau flatness. Note that FlexiPod used constant-current discharge curves versus WLTC dynamic segments.
   - Documented that Step V1.4 parameter identification was in-sample; executed out-of-sample cross-validation between `BUGE388` and `BUGE389`, showing out-of-sample voltage RMSE passes at $\le 2.97\ \text{mV}$ at 40 °C (50% SOC).

7. **Reference Implementation Parity & Open Decision (Item 8):**
   - Documented numerical discrepancy between `deliverable/bms_soc_ref.py` and research `src/soc/estimators/e7v3.py` (up to 3.61 pp perturbed in-envelope, up to 9.82 pp out-of-envelope) due to $Q(T)$ handling.
   - Recorded open architectural decision DEC-06 in `HANDOVER.md`.

8. **Operational Envelope Limits & Hysteresis Precision (Item 9):**
   - Printed lines 245–264 of `deliverable/calibrations/ge105_v1.json` and step 5540 code; documented that envelope bounds $[20.0, 45.0]\ ^\circ\text{C}$ represent an analytical assumption not covered by dynamic driving data.
   - Removed phrasing claiming CALCE 25 °C calibration was suspect; stated that a different cell (105 Ah cell) shows a larger pseudo-OCV hysteresis gap than the CALCE A123 LiFePO4 cell (measured capacity about 1.06 Ah, format unverified).

9. **Metadata Capacity Variation Across Files (Item 10):**
   - Printed per-cell `result.metadata.cell.nom_capacity` across all 36 files; documented that the constant `105.042655` matches only `BUGE388` 25 °C full test.

### Verification Commands & Test Results
- **Reproduction Scripts:**
  ```bash
  .venv/bin/python scripts/validation/ge105_eval_dev.py
  .venv/bin/python scripts/validation/ge105_eval_test.py
  ```
- **Frozen File SHA-256 Hashes:**
  ```bash
  shasum -a 256 src/soc/estimators/e7v3.py src/soc/estimators/base.py deliverable/bms_soc_ref.py deliverable/calibrations/ge105_v1.json
  ```
- **Full Test Suite Execution:**
  ```bash
  .venv/bin/python -m pytest -q -p no:cacheprovider -rs
  ```
  **Output:**
  `385 passed, 1 skipped, 1 warning in 418.42s (0:06:58)`  
  *(1 skipped: `tests/test_real_data_validation.py:267: Expected skip: Dataset 'wheeler_2025' status is NOT_DOWNLOADED. External files have not been acquired.`)*

---

## 9. V1.12: Documentation Honesty and Provenance Auditing

This section documents the documentation honesty, audit reconciliation, and sensitivity analyses completed during Task V1.12:

1. **Label Rule Definition Harmonisation (Item 1):**
   - Harmonised the definition of `LAB_VALIDATED` across `reports/validation/PROTOCOL.md`, `reports/validation/ge105_protocol.md`, and `docs/SOH_STATUS.md` to the 5-point governance requirement:
     `"LAB_VALIDATED requires ALL of: (a) real files with verified manifest hashes; (b) every evaluation script tracked in the repo and reproduced from a clean shell; (c) a spec committed BEFORE the sealed set is evaluated; (d) a held-out result that beats a fair baseline on a reference that is independent of the estimator's own integral; (e) enough data to support the claim, stated in numbers. Everything else is DEVELOPMENT."`
   - In `reports/validation/ge105_protocol.md`, updated the operational envelope statement to: `"declared calibration envelope [20, 45] C (ge105_v1.json); dynamic evidence exists at 25 and 40 C (dev) and 40 C (test) only"`.

2. **Cell-Format Terminology Harmonisation (Item 2):**
   - Removed unverified assumptions that CALCE cells are "26650", "cylindrical", or "1.1 Ah cylindrical", replacing with `"CALCE A123 LiFePO4 cell (measured capacity about 1.06 Ah, format unverified)"` across `ge105_report.md`, `ge105_cell_variation_and_hysteresis.md`, `ge105_protocol.md`, and `ge105_closed_loop_dev.md`.
   - Documented the EVE 105 Ah format in `ge105_inventory.md` as `"(prismatic format from general knowledge of the EVE LF105 product; not stated in the dataset readmes)"`, and used `"105 Ah cell"` elsewhere.
   - Reframed diffusion explanation in `ge105_parameter_comparison.md` as `"Hypothesis (not tested): The 986 s WLTC cycle excites longer-term concentration gradients across the 105 Ah cell, manifesting as a slow diffusion branch with $\tau_2 \approx 170\ \text{s}$."`
   - Clarified hysteresis scaling in `ge105_cell_variation_and_hysteresis.md`: `"one CALCE value (21.6 mV at 40 C) and one GE105 value (26.0 mV); no inference about scaling is possible from two cells"`.

3. **Out-of-Sample Model Gate Evaluation & Voltage Threshold Correction (Item 3):**
   - Evaluated the complete 8-condition cross-validation matrix between development cells `BUGE388` and `BUGE389` (2 temperatures $\times$ 2 SOCs $\times$ 2 transfer directions).
   - Documented the full results in `reports/validation/ge105_model_gate.md` and `ge105_report.md`: 8 conditions evaluated, 4 pass bias gate ($\le 2.0\ \text{mV}$), 6 pass voltage RMSE gate ($\le 6.0\ \text{mV}$), worst RMSE 7.92 mV (at 25 °C/90% SOC BUGE388 $\to$ BUGE389; 6.59 mV reverse), best RMSE 2.85 mV (at 40 °C/50% SOC; 2.97 mV reverse), implied SOC fails everywhere.
   - Replaced speculative attribution with: `"degradation at 25 C/90% SOC (RMSE 6.59 and 7.92 mV, above the 6.0 mV bar); cause not tested"`.
   - Marked Kalman gain scaling statement as `"not tested (no ablation)"`.
   - Documented that the FlexiPod comparison (RMSE 23 to 87 mV) is between different test regimes (constant-current discharge curves vs dynamic WLTC segments), so a gap exists but its cause is not established.
   - Corrected all report instances of a "20 mV" voltage-RMSE bar to the pre-registered 6.0 mV (citing `reports/flexipod1/model_gate.md`).

4. **Sealed-Test Run Count Reconciliation (Item 4):**
   - Conducted an exhaustive audit of session logs in `reports/validation/ge105_spec_provenance.md`, documenting every invocation of a sealed-test evaluation (all 12 invocations from step 5591 to 5681: step ID, command, exit code, error text, and edit made).
   - Reconciled Definition A (6 scratch script execution attempts, steps 5607–5661) and Definition B (10 total invocations prior to clean exit).

5. **Dev Reproducibility Clarification (Item 5):**
   - Documented in `reports/validation/ge105_reproduction.md` that `scripts/validation/ge105_eval_dev.py` was recovered from session transcript step 5559 (not an on-disk file existing at the time of V1.8), and that the evidence demonstrating equivalence is matching outputs only (0.00 pp discrepancy across all 36 scenarios).

6. **Nominal Capacity Sensitivity Evaluation (Item 6):**
   - Evaluated all 12 nominal-initialisation development scenarios using each cell's per-file measured `nom_capacity` ($103.03\ \text{Ah}$ to $105.75\ \text{Ah}$) versus the global baseline ($105.042655\ \text{Ah}$), documented in `reports/validation/ge105_capacity_sensitivity.md`.
   - Demonstrated that E0 tracking error drops to $\le 0.002\ \text{pp}$ Max / $\le 0.001\ \text{pp}$ RMSE when matched to per-file capacity, proving that baseline E0 non-zero error was purely an artifact of using a constant $105.04\ \text{Ah}$ parameter.
   - Confirmed closed-loop E7v3 in-envelope robustness ($\Delta \text{RMSE} \le 0.14\ \text{pp}$ across 25 °C and 40 °C).

### Verification Commands & Test Results
- **Development Capacity Sensitivity:**
  ```bash
  .venv/bin/python -c "from scripts.validation.ge105_eval_dev import ..." # evaluated in reports/validation/ge105_capacity_sensitivity.md
  ```
- **Frozen File SHA-256 Hashes:**
  ```bash
  shasum -a 256 src/soc/estimators/e7v3.py src/soc/estimators/base.py deliverable/bms_soc_ref.py deliverable/calibrations/ge105_v1.json
  ```
  Verified:
  - `src/soc/estimators/e7v3.py`: `057f4d8547b00c80306d1ddd55fbac42dc304448f306d4bbd2fdbbb77ab9154e`
  - `src/soc/estimators/base.py`: `33817e762e359c214cd9824c7684202b0ff129c9ef86b6994cdaf5fd8d8e04da`
  - `deliverable/bms_soc_ref.py`: `1e49223a5aed13554d2787d29e5a289b6541c7cabd7207480e195254001fb431`
  - `deliverable/calibrations/ge105_v1.json`: `b5bb35137e08e1b6da985cbe03fb9d611748ad886d016783af530187cdb9111c`
- **Full Test Suite Execution:**
  ```bash
  .venv/bin/python -m pytest -q -p no:cacheprovider -rs
  ```
  **Real Output:**
  ```text
  SKIPPED [1] tests/test_real_data_validation.py:267: Expected skip: Dataset 'wheeler_2025' status is NOT_DOWNLOADED. External files have not been acquired.
  385 passed, 1 skipped, 1 warning in 419.50s (0:06:59)
  ```

