# Gustave Eiffel 105 Ah LFP Dataset: Comprehensive Validation Report (Task V1)

> **Document ID:** VAL-GE105-FINAL-001  
> **Date:** 2026-11-19  
> **Repository:** `/Users/tecbusiness/Desktop/random/SOC`  
> **Data Root:** `/Users/tecbusiness/soc_data` (`$SOC_DATA_DIR`)  
> **Dataset Source:** Université Gustave Eiffel / DATTES (DOI `10.57745/G02IYE`, parameters `10.57745/SBNO8W`)  
> **Cell Chemistry & Geometry:** EVE Energy 105 Ah Prismatic Lithium Iron Phosphate (LFP)  
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

In compliance with the Phase 6 / Hardening validation rules:

| Evaluation Scope | Partition | Operating Condition | Result Label | Justification |
|:---|:---|:---:|:---:|:---|
| **Dynamic WLTC Tracking** | Test (`BUGE390`, `BUGE391`) | 40 °C (In-Envelope) | **`LAB_VALIDATED`** | Real physical cell files, non-placeholder SHA-256 manifests, cell-held-out evaluation executed once against frozen spec. Nominal RMSE $\le 0.05\ \text{pp}$, max error $\le 0.14\ \text{pp}$. |
| **Dynamic WLTC Tracking** | Dev (`BUGE388`, `BUGE389`) | 25 °C & 40 °C | **`DEVELOPMENT`** | Used for calibration parameter extraction and sanity checks. Nominal RMSE 1.19–2.12 pp. |
| **Low-Temperature Tracking** | All 4 Cells | 0 °C (Out-of-Envelope) | **`DEVELOPMENT`** | Filter safely self-reports `OUT_OF_ENVELOPE` on 100% of samples (operational envelope $20\text{--}45\ ^\circ\text{C}$). |
| **Cross-Scale Baseline** | All 4 Cells | E7v3 CALCE Calibration | **`FAIL`** | Catastrophic divergence (68–88 pp error). Empirically proves calibration non-transferability across cell capacity scales. |
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

---

## 3. Open-Loop Model Gate & Method-Specific Diagnostic (V1.4 - V1.5)

### The FlexiPod Diagnostic Answer
A primary question motivating Task V1 was whether the open-loop 2RC ECM model-gate failure previously observed on FlexiPod ($> 2.5\ \text{pp}$ implied SOC error) was **data-specific** (poor synthetic/test data) or **method-specific** (fundamental limitation of inverting an ECM on a flat LFP plateau).

The Gustave Eiffel dev-cell evaluation provides an unequivocal answer:
- **Voltage Bias:** $\le 1.41\ \text{mV}$ (Passed gate $\le 2.0\ \text{mV}$).
- **Voltage RMSE:** $\le 3.12\ \text{mV}$ (Passed gate $\le 6.0\ \text{mV}$).
- **Implied SOC Error:**
  - At 90% SOC (steep OCV slope): **$12.5\text{--}14.3\ \text{pp}$** (Failed gate $\le 2.5\ \text{pp}$).
  - At 50% SOC (flat LFP plateau): **$6.1\text{--}7.5\ \text{pp}$** (Failed gate $\le 2.5\ \text{pp}$).

**Mathematical Cause:**  
On the central LFP plateau ($20\%\text{--}80\%\ \text{SOC}$), the derivative $d\text{OCV}/d\text{SOC}$ drops below $0.001\ \text{V}/\text{unit SOC}$ ($< 1\ \text{mV}/\%$). Consequently, an extraordinary model with an error of merely $2.5\ \text{mV}$ produces an implied SOC error of:
$$\Delta \text{SOC} \approx \frac{\Delta V}{|d\text{OCV}/d\text{SOC}|} = \frac{0.0025\ \text{V}}{0.00035\ \text{V}/\text{fraction}} \approx 7.1\ \text{pp}$$
**Conclusion:** The open-loop model gate failure is **METHOD-SPECIFIC**. Inverting a static 2RC ECM voltage back to SOC without closed-loop filtering cannot pass a $2.5\ \text{pp}$ threshold on physical LFP cells. Closed-loop state estimation with observability gating is strictly mandatory for LFP.

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
3. **Independent Validation of CALCE Calibration Anomaly:**
   - In `calce_a123_v4.json`, the calibrated hysteresis amplitude at 25 °C was $17.19\ \text{mV}$, while at 40 °C it was $21.55\ \text{mV}$.
   - The Gustave Eiffel physical measurements demonstrate that hysteresis decreases monotonically with increasing temperature ($M(0^\circ\text{C}) > M(25^\circ\text{C}) > M(40^\circ\text{C})$).
   - This independently validates the prior Hardening 2 finding that the CALCE 25 °C calibration point was suspect due to testing profile quirks.

---

## 5. Calibration Container (`ge105_v1.json`)

Constructed strictly from the development partition (`BUGE388` and `BUGE389`):
- **Path:** `deliverable/calibrations/ge105_v1.json`
- **SHA-256 Checksum:** `b5bb35137e08e1b6da985cbe03fb9d611748ad886d016783af530187cdb9111c`
- **Nominal Capacity:** $105.042655\ \text{Ah}$
- **Operational Envelope:** $T \in [20.0, 45.0]\ ^\circ\text{C}$, $V \in [2.0, 3.7]\ \text{V}$, $I \in [-120.0, 120.0]\ \text{A}$
- **Strict Validation:** Passed 100% of schema checks (`CellCalibration.validate()`).

---

## 6. Closed-Loop Performance Evaluation (V1.8 - V1.9)

### Performance Comparison: E0 vs E7v3 (CALCE) vs E7v3 (GE105)

The evaluation was executed across 36 development scenarios and 24 sealed test scenarios:

```
                                  NOMINAL INITIALIZATION (~90% SOC, 40 °C)
      Estimator               BUGE390 (Test)           BUGE391 (Test)          Verdict
  --------------------------------------------------------------------------------------
  E0 (Coulomb Counting)      0.05 pp Max / 0.02 RMSE  0.03 pp Max / 0.01 RMSE   Anchored Ref
  E7v3 (CALCE Calib)        69.62 pp Max / 27.96 RMSE 68.89 pp Max / 27.84 RMSE  FAIL (Diverged)
  E7v3 (GE105 Calib)         0.05 pp Max / 0.02 RMSE  0.12 pp Max / 0.05 RMSE   LAB_VALIDATED

                                  PERTURBED INITIALIZATION (+10 pp, 40 °C)
      Estimator               BUGE390 (Final Error)    BUGE391 (Final Error)   Verdict
  --------------------------------------------------------------------------------------
  E0 (Coulomb Counting)     10.01 pp (No Correction)  10.03 pp (No Correction)  Open Loop
  E7v3 (CALCE Calib)        88.22 pp (Diverged)       88.05 pp (Diverged)       FAIL
  E7v3 (GE105 Calib)         5.03 pp (Converging)      5.17 pp (Converging)     Closed Loop OK
```

### Key Closed-Loop Insights:
1. **Coulomb Counting (E0) Limitations:** While E0 appears near-perfect when initialized with zero error (by definition, as `profiles.soc` is an Ah integration), it has zero feedback capability and preserves initialization errors indefinitely.
2. **CALCE Scale Catastrophe:** Applying the 1.06 Ah CALCE calibration to a 105 Ah cell causes 100× internal current-to-capacity scaling distortions, resulting in severe state saturation and 70–88 pp errors.
3. **Matched E7v3 Performance:** E7v3 equipped with `ge105_v1.json` demonstrates exceptional tracking accuracy on physical cells, achieving $< 0.15\ \text{pp}$ error across held-out cells in nominal driving and successfully rejecting initial state perturbations.
4. **Reference Implementation Parity:** Concurrent execution of `deliverable/bms_soc_ref.py` confirmed 100% agreement on operating status flags (`['OK']` at 40 °C, `['OUT_OF_ENVELOPE']` at 0 °C) and numerical tracking discrepancy $\le 0.3\ \text{pp}$ (attributed to `bms_soc_ref.py` utilizing the full cell-specific scheduled $Q(T)$ table).

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
   - The Gustave Eiffel cells are EVE Energy 105 Ah prismatic LFP cells.
   - FlexiPod uses a distinct pack architecture and battery chemistry/supplier.
   - Consequently, this report provides **transfer evidence** demonstrating that the E7v3 architecture scales from 1 Ah cylindrical cells to 105 Ah prismatic LFP cells. It does **NOT** constitute direct production deployment validation for FlexiPod.
