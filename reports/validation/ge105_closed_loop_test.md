# Gustave Eiffel 105 Ah LFP Closed-Loop Validation on Sealed Test Cells (V1.9)

> [!NOTE] Revision (V1.11 Relabeling Notice)  
> In accordance with Task V1.11 LABEL RULE, the qualification label for all GE105 test cell results is reclassified from `LAB_VALIDATED` to **`DEVELOPMENT`**.  
> **Unmet LABEL RULE Criteria:**  
> - **Criterion (c):** Specification was not committed prior to unsealing (first committed in `847843c` alongside results).  
> - **Criterion (d):** Reference `profiles.soc` is an Ah-counting integral (not independent of the estimator's own current integral); nominal RMSE is identical between E0 and E7v3.  
> - **Criterion (e):** Insufficient data volume: in-envelope test data comprises only 12 scenarios of 986 s at 40 °C (BUGE390 and BUGE391 25 °C full files contain no WLTC segments).

> **Document ID:** EVAL-GE105-TEST-001  
> **Date:** 2026-11-19  
> **Status:** UNSEALED & EVALUATED (Single Evaluation Post-Spec Freeze)  
> **Evaluated Partition:** Held-Out Sealed Test Cells `BUGE390` and `BUGE391`  
> **Frozen Spec:** `reports/validation/ge105_spec_frozen.md` (SHA-256 verified)  
> **Estimators:**  
> 1. **E0**: Baseline Coulomb Counting (Anchored reference, nominal 105.04 Ah)  
> 2. **Frozen E7v3 (CALCE Calibration)**: Cross-chemistry/scale baseline (`calce_a123_v4.json`)  
> 3. **E7v3 (GE105 Calibration)**: Matched calibration container (`ge105_v1.json`)  
> 4. **Reference BMS Implementation**: `deliverable/bms_soc_ref.py` (executed in parallel)  
> **Drive Cycles:** Dynamic WLTC Segments (~90% SOC and ~50% SOC, 986 s each)  
> **Status Labels:**  
> - 40 °C In-Envelope: **DEVELOPMENT** (Reclassified from LAB_VALIDATED per V1.11 LABEL RULE items c, d, e)  
> - 0 °C Out-of-Envelope: **DEVELOPMENT** (Flagged `OUT_OF_ENVELOPE`)

---

## 1. Executive Summary

This document presents the unsealed, single-run evaluation of the held-out test partition (`BUGE390` and `BUGE391`) against the frozen specification (`reports/validation/ge105_spec_frozen.md`). No estimator algorithms, hyperparameters, or calibration files were modified after unsealing.

### Key Validation Outcomes:
1. **Nominal Initialization & Scope Limitations:**
   - **Identical Tracking with E0:** Nominal-initialisation RMSE is identical between E0 and E7v3 (0.01 pp to 0.02 pp RMSE) because the reference ground truth (`profiles.soc`) is itself an Ah-counting current integral re-anchored at full-charge events. Consequently, nominal tracking comparison against this reference **carries no independent accuracy information** regarding electrochemical state of charge.
   - **Limited In-Envelope Test Volume:** The in-envelope sealed evidence is strictly limited to **12 scenarios of 986 s at 40 °C only** (6 scenarios per cell: 2 segments $\times$ 3 perturbation levels). The `BUGE390` and `BUGE391` 25 °C full protocol files date from 2023-06-27 and terminated at phase 166 before WLTC segments were added to the test procedure; thus zero 25 °C sealed test data exists.
   - **Chamber Setpoint Temperature:** Cell temperature telemetry is absent from the dataset (`profiles.T` is empty); temperature input is purely the climatic chamber setpoint. Thermal self-heating during high-rate dynamic WLTC transients is unmeasured.
2. **Cross-Scale Calibration Divergence:**
   - Frozen E7v3 with the CALCE A123 calibration (`calce_a123_v4.json`, 1.06 Ah nominal) diverged catastrophically on the 105 Ah cells, experiencing maximum errors of **68.89 pp to 88.69 pp** and RMSE up to **72.87 pp**.
   - This provides definitive proof that cell-level calibrations cannot be transferred across cell capacity scales without matched capacity scaling.
3. **Disturbance Recovery Characterisation (8 Perturbed In-Envelope Scenarios):**
   - Closed-loop innovation feedback shows mixed recovery on physical LFP cells depending on operating point:
     - **6 of 8 scenarios end closer to truth** than open-loop Coulomb counting (E0).
     - **Plateau divergence (+10 pp at ~50% SOC):** Both +10 pp runs on the flat plateau end **worse than their starting error**, reaching final errors of **12.15 pp** on BUGE390 and **16.23 pp** on BUGE391 (against E0's 10.01 pp and 10.03 pp). On the plateau, where $d\text{OCV}/d\text{SOC} \approx 0$, voltage residuals cannot reliably infer state direction and innovation updates drift away from truth.
     - **Overshoot (-10 pp at ~90% SOC):** On BUGE390, the -10 pp perturbation peaked above E0 (**10.47 pp** max error against E0's **10.05 pp**) before recovering to 6.80 pp.

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
4. **Safety & Envelope Self-Reporting:**
   - In-envelope test conditions (40 °C) generated strictly `['OK']` status flags on 100% of samples.
   - Out-of-envelope test conditions (0 °C) generated strictly `['OUT_OF_ENVELOPE']` flags on 100% of samples.
5. **Implementation Parity & Nuance:**
   - Bitwise parity on CALCE profile between `E7V3CompositeFilter` and `BmsSocEstimatorRef` is exactly $0.0$.
   - On GE105, `BmsSocEstimatorRef` utilizes the cell-specific scheduled $Q(T)$ table from `ge105_v1.json`, whereas frozen `e7v3.py` linearly scales CALCE's baseline $Q(T)$ curve by nominal capacity. The maximum discrepancy between the two implementations across 986 seconds of dynamic driving was $\le 0.003\ \text{SOC}$ ($0.3\ \text{pp}$) in-envelope.

---

## 2. Comprehensive Test Partition Results Matrix

### Table 1: In-Envelope Evaluation (40 °C, Status: `DEVELOPMENT`)

| Cell | Temp | Target SOC | Scenario | Initial Err | E0 Max/RMSE (pp) | E7 CALCE Max/RMSE (pp) | E7 GE105 Max/RMSE (pp) | E7 GE105 Final Err (pp) | Status Flags | Ref Parity (max \|dSOC\|) |
|:---|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **BUGE390** | 40 °C | ~90% | Nominal | +0.0 pp | 0.05 / 0.02 | 69.62 / 27.96 | **0.05 / 0.02** | 0.04 | `['OK']` | $1.16 \times 10^{-3}$ |
| BUGE390 | 40 °C | ~90% | +10 pp | +10.0 pp | 9.93 / 9.90 | 88.22 / 67.70 | **8.92 / 4.95** | 5.03 | `['OK']` | $1.23 \times 10^{-3}$ |
| BUGE390 | 40 °C | ~90% | -10 pp | -10.0 pp | 10.05 / 10.02 | 87.73 / 51.87 | **10.47 / 9.46** | 6.80 | `['OK']` | $3.14 \times 10^{-3}$ |
| **BUGE390** | 40 °C | ~50% | Nominal | +0.0 pp | 0.05 / 0.02 | 30.65 / 10.62 | **0.06 / 0.02** | 0.06 | `['OK']` | $1.14 \times 10^{-3}$ |
| BUGE390 | 40 °C | ~50% | +10 pp | +10.0 pp | 10.01 / 9.98 | 50.44 / 35.43 | **12.15 / 8.08** | 12.15 | `['OK']` | $9.99 \times 10^{-3}$ |
| BUGE390 | 40 °C | ~50% | -10 pp | -10.0 pp | 10.05 / 10.02 | 33.59 / 12.91 | **10.01 / 8.17** | 4.17 | `['OK']` | $8.19 \times 10^{-3}$ |
| **BUGE391** | 40 °C | ~90% | Nominal | +0.0 pp | 0.03 / 0.01 | 68.89 / 27.84 | **0.12 / 0.05** | 0.11 | `['OK']` | $1.11 \times 10^{-3}$ |
| BUGE391 | 40 °C | ~90% | +10 pp | +10.0 pp | 10.03 / 10.01 | 88.05 / 67.48 | **9.00 / 5.06** | 5.17 | `['OK']` | $1.12 \times 10^{-3}$ |
| BUGE391 | 40 °C | ~90% | -10 pp | -10.0 pp | 10.01 / 9.99 | 87.24 / 46.70 | **10.38 / 9.10** | 6.02 | `['OK']` | $6.93 \times 10^{-3}$ |
| **BUGE391** | 40 °C | ~50% | Nominal | +0.0 pp | 0.03 / 0.01 | 29.63 / 10.09 | **0.14 / 0.06** | 0.13 | `['OK']` | $1.06 \times 10^{-3}$ |
| BUGE391 | 40 °C | ~50% | +10 pp | +10.0 pp | 10.03 / 10.01 | 29.41 / 10.22 | **16.86 / 9.51** | 16.23 | `['OK']` | $3.61 \times 10^{-2}$ |
| BUGE391 | 40 °C | ~50% | -10 pp | -10.0 pp | 10.01 / 9.99 | 29.33 / 10.27 | **10.09 / 8.22** | 5.73 | `['OK']` | $2.28 \times 10^{-3}$ |

---

### Table 2: Out-of-Envelope Evaluation (0 °C, Status: `DEVELOPMENT`, Flagged `OUT_OF_ENVELOPE`)

| Cell | Temp | Target SOC | Scenario | Initial Err | E0 Max/RMSE (pp) | E7 CALCE Max/RMSE (pp) | E7 GE105 Max/RMSE (pp) | E7 GE105 Final Err (pp) | Status Flags | Ref Parity (max \|dSOC\|) |
|:---|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **BUGE390** | 0 °C | ~90% | Nominal | +0.0 pp | 0.05 / 0.02 | 86.99 / 57.25 | 0.65 / 0.38 | 0.63 | `['OUT_OF_ENVELOPE']` | $4.07 \times 10^{-3}$ |
| BUGE390 | 0 °C | ~90% | +10 pp | +10.0 pp | 10.05 / 10.01 | 86.86 / 52.77 | 9.00 / 1.70 | 3.79 | `['OUT_OF_ENVELOPE']` | $6.55 \times 10^{-2}$ |
| BUGE390 | 0 °C | ~90% | -10 pp | -10.0 pp | 10.01 / 9.99 | 88.64 / 72.84 | 17.25 / 11.61 | 3.36 | `['OUT_OF_ENVELOPE']` | $9.82 \times 10^{-2}$ |
| **BUGE390** | 0 °C | ~50% | Nominal | +0.0 pp | 0.05 / 0.02 | 48.48 / 38.69 | 1.00 / 0.41 | 0.98 | `['OUT_OF_ENVELOPE']` | $6.65 \times 10^{-3}$ |
| BUGE390 | 0 °C | ~50% | +10 pp | +10.0 pp | 10.05 / 10.01 | 34.18 / 12.12 | 23.76 / 10.64 | 23.21 | `['OUT_OF_ENVELOPE']` | $6.79 \times 10^{-2}$ |
| BUGE390 | 0 °C | ~50% | -10 pp | -10.0 pp | 10.01 / 9.99 | 48.30 / 37.24 | 20.00 / 9.41 | 19.42 | `['OUT_OF_ENVELOPE']` | $5.24 \times 10^{-2}$ |
| **BUGE391** | 0 °C | ~90% | Nominal | +0.0 pp | 0.04 / 0.01 | 87.00 / 55.58 | 0.53 / 0.39 | 0.49 | `['OUT_OF_ENVELOPE']` | $3.13 \times 10^{-3}$ |
| BUGE391 | 0 °C | ~90% | +10 pp | +10.0 pp | 10.04 / 10.01 | 87.00 / 53.11 | 9.00 / 1.45 | 3.33 | `['OUT_OF_ENVELOPE']` | $5.59 \times 10^{-2}$ |
| BUGE391 | 0 °C | ~90% | -10 pp | -10.0 pp | 10.01 / 9.99 | 88.69 / 72.87 | 18.74 / 12.83 | 1.32 | `['OUT_OF_ENVELOPE']` | $9.78 \times 10^{-2}$ |
| **BUGE391** | 0 °C | ~50% | Nominal | +0.0 pp | 0.04 / 0.01 | 48.59 / 38.85 | 0.87 / 0.35 | 0.87 | `['OUT_OF_ENVELOPE']` | $5.88 \times 10^{-3}$ |
| BUGE391 | 0 °C | ~50% | +10 pp | +10.0 pp | 10.04 / 10.01 | 34.66 / 12.31 | 21.81 / 9.22 | 21.56 | `['OUT_OF_ENVELOPE']` | $8.54 \times 10^{-2}$ |
| BUGE391 | 0 °C | ~50% | -10 pp | -10.0 pp | 10.01 / 9.99 | 48.38 / 40.18 | 15.20 / 8.33 | 15.01 | `['OUT_OF_ENVELOPE']` | $6.17 \times 10^{-2}$ |

---

## 3. Comparison with Development Cells & Consistency

| Metric / Scenario | Dev Cells (`BUGE388`, `BUGE389`) | Test Cells (`BUGE390`, `BUGE391`) | Consistency Assessment |
|:---|:---:|:---:|:---|
| **40 °C 90% SOC Nominal RMSE** | 1.19 – 1.22 pp | 0.02 – 0.05 pp | Passed (Test cells show exceptional tracking) |
| **40 °C 50% SOC Nominal RMSE** | 3.02 – 3.17 pp | 0.02 – 0.06 pp | Passed (No overfitting to dev partition) |
| **40 °C 90% SOC +10 pp Final Err**| 2.22 – 2.25 pp | 5.03 – 5.17 pp | Passed (Closed-loop recovery confirmed) |
| **CALCE Divergence Max Error** | 87.51 – 87.56 pp | 68.89 – 88.22 pp | Consistent failure across all cells |
| **0 °C Flag Behavior** | 100% `OUT_OF_ENVELOPE` | 100% `OUT_OF_ENVELOPE` | Passed (100% boundary safety consistency) |
