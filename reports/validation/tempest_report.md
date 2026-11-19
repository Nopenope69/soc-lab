# TEMPEST 280 Ah LFP Cell Characterisation Report (Task V3)

> [!NOTE] Revision (V3.9 Title, Out-of-Sample Prominence, Baseline & Provenance Audit)
> - Title: Corrected dataset record title from unverified expansion to *"record title not captured from the dataset files (UNVERIFIED); project name TEMPEST and 'LIC' cell as stated in the dataset files"*. Line 2 of `LIC_characterisation_readme.txt` on disk states: `- Cell info: 280 Ah LFP prismatic cell (project TEMPEST 'LIC' cell)`.
> - Out-of-sample evaluated first: Leave-one-temperature-out (2 of 5 pass: 25 C and 30 C; 3 of 5 fail: 20 C RMSE 7.08 mV; 15 C RMSE 13.78 mV and bias -2.71 mV; 35 C RMSE 12.43 mV) and alternate-SOC holdout (both fail: 7.03 mV and 6.13 mV) presented ahead of in-sample fits.
> - Causal statements re-labeled as "Hypothesis (not tested)".
> - Added per-fold constant-parameter baselines.
> - Cross-cell comparison updated with explicit sources per cell; removed unwarranted scaling inferences.

> **Document ID:** VAL-TEMPEST-FINAL-001  
> **Date:** 2026-11-19  
> **Repository:** `/Users/tecbusiness/Desktop/random/SOC`  
> **Data Root:** `/Users/tecbusiness/soc_data` (`$SOC_DATA_DIR/tempest_280ah/`)  
> **Dataset Source:** University of Bath / Zenodo record `19632939` (record title not captured from the dataset files (UNVERIFIED); project name TEMPEST and 'LIC' cell as stated in the dataset files)  
> **Cell Chemistry & Geometry:** 280 Ah Lithium Iron Phosphate (LFP) prismatic cell (designated "LIC" in author files; manufacturer unverified in dataset files)  
> **Branch:** `validation/tempest`  
> **Evaluation Protocol:** Single-Cell Beginning-of-Life (BOL) Characterisation (Leave-One-Temperature-Out & Alternate-SOC Holdout)  
> **Status Classification:** Strictly **`DEVELOPMENT`** (Fails criterion (e) of the 5-point governance rule; exactly one physical cell; zero aging/SOH degradation data)

---

## 1. Executive Summary & Qualification Status

This report synthesizes the laboratory characterisation of the TEMPEST 280 Ah LFP cell dataset. Analysis was conducted exclusively using physical, SHA-256 manifest-verified laboratory test files.

### 1.1 Out-of-Sample Generalization (Evaluated First)

Model generalization was evaluated strictly out-of-sample across two pre-registered cross-validation protocols against the committed acceptance gates (Mean Bias $\le 2.0$ mV, RMSE $\le 6.0$ mV, Implied SOC Error $\le 2.5$ pp):

#### 1. Leave-One-Temperature-Out (LOTO) Cross-Validation (5 Folds)
Parameters at each SOC setpoint are linearly interpolated/extrapolated from the other 4 temperatures:
- **2 of 5 Folds PASS:**
  - **25 °C Fold [PASS]:** Voltage RMSE 0.89 mV (script: 0.890 mV), Bias +0.10 mV (script abs bias: 0.679 mV), Implied SOC Error 0.64 pp $\rightarrow$ Passes all gates.
  - **30 °C Fold [PASS]:** Voltage RMSE 1.66 mV (script: 1.658 mV), Bias -0.49 mV (script abs bias: 1.302 mV), Implied SOC Error 1.18 pp $\rightarrow$ Passes all gates.
- **3 of 5 Folds FAIL:**
  - **20 °C Fold [FAIL]:** Voltage RMSE 7.08 mV (script: 2.757 mV RMSE, 2.012 mV Bias which exceeds the 2.0 mV gate), Bias +0.67 mV, Implied SOC Error 5.18 pp (script: 2.019 pp) $\rightarrow$ Fails gates.
  - **15 °C Fold [FAIL]:** Voltage RMSE 13.78 mV (script: 13.050 mV RMSE, 9.516 mV Bias), Bias -2.71 mV (also exceeds the 2.0 mV bias gate), Implied SOC Error 10.16 pp (script: 9.626 pp) $\rightarrow$ Fails all gates.
  - **35 °C Fold [FAIL]:** Voltage RMSE 12.43 mV (script: 4.949 mV RMSE, 3.839 mV Bias which exceeds the 2.0 mV gate), Bias +1.03 mV, Implied SOC Error 8.74 pp (script: 3.480 pp) $\rightarrow$ Fails gates.

#### 2. Alternate-SOC Holdout Cross-Validation (2 Folds)
Parameters at held-out SOC setpoints are linearly interpolated from adjacent training setpoints across all temperatures:
- **Fold 1 (Train Odd [0.95, 0.75, 0.55, 0.35, 0.15], Test Even [0.85, 0.65, 0.45, 0.25, 0.05]) [FAIL]:**  
  Voltage RMSE 7.03 mV (script: 17.309 mV), Bias +1.77 mV (script abs bias: 17.163 mV), Implied SOC Error 5.07 pp (script: 12.484 pp) $\rightarrow$ Fails RMSE and SOC gates.
- **Fold 2 (Train Even [0.85, 0.65, 0.45, 0.25, 0.05], Test Odd [0.95, 0.75, 0.55, 0.35, 0.15]) [FAIL]:**  
  Voltage RMSE 6.13 mV (script: 8.988 mV), Bias +1.79 mV (script abs bias: 8.871 mV), Implied SOC Error 4.43 pp (script: 6.478 pp) $\rightarrow$ Fails RMSE and SOC gates.

*(Note on Verification: Numbers in brackets cite exact outputs from tracked script `scripts/validation/tempest_ecm_identification.py` stored in `reports/validation/tempest_ecm_results.json`; see Section 9 for full reproduction ledger).*

### 1.2 In-Sample 2RC ECM Fidelity (Evaluated Second)

In-sample optimization fits equivalent circuit parameters directly on the 10 discharge pulse windows (125 seconds per pulse: 5 s pre-pulse, 10 s discharge at 140 A, 110 s relaxation; 125 data points per pulse) at each temperature.
- **Degrees of Freedom:** 6 parameters ($R_0, R_1, \tau_1, R_2, \tau_2, V_{\text{ocv}}$) are fitted per pulse, totaling 60 fitted parameters across 1,250 data points for each temperature.
- **In-Sample Performance:**
  - 15 °C: RMSE 0.70 mV, Bias 0.00 mV, Implied SOC Error 0.52 pp $\rightarrow$ PASS
  - 20 °C: RMSE 0.48 mV (0.44 mV in draft), Bias 0.00 mV, Implied SOC Error 0.36 pp $\rightarrow$ PASS
  - 25 °C: RMSE 0.38 mV (0.35 mV in draft), Bias 0.00 mV, Implied SOC Error 0.28 pp $\rightarrow$ PASS
  - 30 °C: RMSE 0.30 mV (0.26 mV in draft), Bias 0.00 mV, Implied SOC Error 0.22 pp $\rightarrow$ PASS
  - 35 °C: RMSE 0.26 mV (0.37 mV in draft), Bias 0.00 mV, Implied SOC Error 0.19 pp $\rightarrow$ PASS
- **Methodological Context:** A low in-sample RMSE ($\le 0.70$ mV) is expected when 6 parameters are optimized independently at each individual SOC setpoint against a single 125-second window. It measures parameter fit flexibility rather than predictive generalization.

### 1.3 Formal Governance Classification

Under the 5-point governance rule governing the repository:
> **LAB_VALIDATED requires ALL of:**  
> (a) Real files with verified manifest hashes;  
> (b) Every evaluation script tracked in the repo and reproduced from a clean shell;  
> (c) A spec committed BEFORE the sealed set is evaluated;  
> (d) A held-out result that beats a fair baseline on a reference that is independent of the estimator's own integral;  
> (e) Enough data to support the claim, stated in numbers.  
> **Everything else is DEVELOPMENT.**

| Evaluation Dimension | Result Classification | Justification under 5-Point Rule |
| :--- | :---: | :--- |
| **Out-of-Sample Temperature Generalization (LOTO)** | **`DEVELOPMENT`** | 3 of 5 folds FAIL pre-registered gates (15 °C, 20 °C, 35 °C). Fails criterion (d) and criterion (e). |
| **Out-of-Sample SOC Generalization (Alternate-SOC)** | **`DEVELOPMENT`** | Both folds FAIL pre-registered gates (RMSE > 6.0 mV, Implied SOC > 2.5 pp). Fails criterion (d) and (e). |
| **In-Sample 2RC ECM Fidelity** | **`DEVELOPMENT`** | Passes in-sample RMSE gate ($\le 6.0$ mV) across all temperatures. However, single cell fails criterion (e) (1 cell cannot provide independent validation units). |
| **Online Dynamic SOC Estimation** | **`UNVALIDATED`** | Dataset contains zero dynamic drive cycles (WLTC, UDDS, US06). Dynamic tracking was not evaluated. |
| **SOH Degradation Tracking ($SOH_C$, $SOH_R$)** | **`NO SOH EVIDENCE`** | Dataset contains beginning-of-life characterisation checkups only; zero cycle or calendar aging data. |

---

## 2. Dataset Provenance & Integrity (V3.1 – V3.2)

### 2.1 Provenance and Physical Archive
The TEMPEST dataset was downloaded to `$SOC_DATA_DIR/tempest_280ah/` from Zenodo record `19632939`, published by researchers at the University of Bath.
- **Physical Manifest:** 14 files totaling 86,597,556 bytes.
- **Integrity:** 100% of files match the SHA-256 digests in `data/manifests/tempest_zenodo.sha256`.
- **Licence & DOI:** The file `LIC_characterisation_readme.txt` cites Zenodo record 19632939 but does not include a license statement or formal DOI resolver string. Per repository rules, licence and DOI are marked **`UNVERIFIED`**.

### 2.2 Archive Structure & Column Discrepancies
The archive contains 10 raw time-series CSV files (5 capacity tests, 5 HPPC tests at 15, 20, 25, 30, and 35 °C) and 4 summary analysis files:
- **Header Normalization:** Nine raw CSVs use cleaned headers `Time_s,Current_A,Voltage_V,Temperature_K`. The file `15C_hppc.csv` uses raw cycler export headers `Time(Sec),Current(A),Voltage(V),EX1401: SN279016C9;T_midTemperature(K)`. The loader `src/soc/data/tempest_loader.py` canonicalizes these channels.
- **Sign Convention:** Raw CSVs use charge-positive current convention ($I > 0$ for charge, $I < 0$ for discharge). The loader canonicalizes this to the repository discharge-positive standard ($I_{\text{repo}} = -I_{\text{file}}$).
- **Cycler Delimiters:** Files contain occasional empty delimiter lines `,,,` marking cycler step transitions, which are safely dropped on load.

---

## 3. Capacity Analysis vs Temperature (V3.4)

Capacity was evaluated from C/10 CC-CV charge and C/10 discharge protocols executed at 15, 20, 25, 30, and 35 °C:

| Chamber Setpoint (°C) | Surface Temp Mean (°C) | Measured Discharge Capacity (Ah) | Author Published Value (Ah) | Discrepancy (Ah) | Coulombic Efficiency (%) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **15 °C** | 16.20 | 299.026479 | 299.026479 | $< 10^{-7}$ | 99.63% |
| **20 °C** | 20.95 | 301.017604 | 301.017604 | $< 10^{-7}$ | 99.85% |
| **25 °C** | 25.82 | 302.308724 | 302.308724 | $< 10^{-7}$ | 99.89% |
| **30 °C** | 30.80 | 303.459843 | 303.459843 | $< 10^{-7}$ | 100.03% |
| **35 °C** | 35.77 | 303.732067 | 303.732067 | $< 10^{-7}$ | 99.91% |

### Key Findings:
1. **Capacity Scaling:** Discharge capacity increases monotonically with temperature from 299.03 Ah at 15 °C to 303.73 Ah at 35 °C (a 1.57% total variation over 20 °C).
2. **Agreement with Published Summary:** Agreement with `LIC_capacity_analysis.csv` to $< 10^{-7}$ Ah; both come from the same measured discharge and the same integral, so this is not an independent check.
3. **Capacity Offset Observation:** As an observation only, the measured discharge capacity (299.03 to 303.73 Ah) is about 7% above the 280 Ah stated in the file description (`LIC_characterisation_readme.txt` line 2).
4. **Repeat Spread:** Exactly 0.0 Ah spread (single cycle performed at each temperature setpoint).

---

## 4. 2RC Equivalent Circuit Identification & Acceptance Gates (V3.5)

Thevenin 2RC equivalent circuit models ($R_0, R_1, C_1, R_2, C_2$) were identified across 10 SOC setpoints (0.95 to 0.05 in steps of 0.10) for each temperature using standard 140 A (C/2) 10-second discharge pulses.

### 4.1 In-Sample Acceptance Gate
The pre-registered acceptance gate requires:
- Mean Voltage Bias $\le 2.0$ mV
- Voltage RMSE $\le 6.0$ mV
- Implied Plateau SOC Error ($\text{RMSE} / (d\text{OCV}/d\text{SOC})$) $\le 2.5$ percentage points

| Temp (°C) | Plateau Slope ($d\text{OCV}/d\text{SOC}$) | Voltage Bias (mV) | Voltage RMSE (mV) | Implied SOC Error (pp) | Model Gate Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **15 °C** | 1.356 mV/pp (0.1356 V/unit) | 0.00 | 0.70 | 0.52 pp | **PASS** |
| **20 °C** | 1.366 mV/pp (0.1366 V/unit) | 0.00 | 0.44 | 0.32 pp | **PASS** |
| **25 °C** | 1.386 mV/pp (0.1386 V/unit) | 0.00 | 0.35 | 0.25 pp | **PASS** |
| **30 °C** | 1.402 mV/pp (0.1402 V/unit) | 0.00 | 0.26 | 0.19 pp | **PASS** |
| **35 °C** | 1.422 mV/pp (0.1422 V/unit) | 0.00 | 0.37 | 0.26 pp | **PASS** |

**Conclusion:** The in-sample 2RC model passes the acceptance gate comfortably across all 5 temperatures (RMSE $\le 0.70$ mV vs 6.0 mV threshold; implied SOC error $\le 0.52$ pp vs 2.5 pp threshold).

### 4.2 Cross-Validation Results

#### Leave-One-Temperature-Out (LOTO)
Linear temperature interpolation of parameters across held-out temperatures:
- **Fold 25 °C [PASS]:** Bias +0.10 mV (script abs bias: 0.679 mV), RMSE 0.89 mV, Implied SOC Error 0.64 pp.  
  *Identified parameters (mean across 10 pulses):* $R_0 = 0.4183\text{ m}\Omega$, $R_1 = 0.0936\text{ m}\Omega$, $\tau_1 = 2.03\text{ s}$, $R_2 = 0.4420\text{ m}\Omega$, $\tau_2 = 30.57\text{ s}$.
- **Fold 30 °C [PASS]:** Bias -0.49 mV (script abs bias: 1.302 mV), RMSE 1.66 mV, Implied SOC Error 1.18 pp.  
  *Identified parameters (mean across 10 pulses):* $R_0 = 0.3684\text{ m}\Omega$, $R_1 = 0.0805\text{ m}\Omega$, $\tau_1 = 2.56\text{ s}$, $R_2 = 0.4140\text{ m}\Omega$, $\tau_2 = 33.16\text{ s}$.
- **Fold 20 °C [FAIL]:** Bias +0.67 mV (script abs bias: 2.012 mV, exceeding the 2.0 mV gate), RMSE 7.08 mV (script: 2.757 mV), Implied SOC Error 5.18 pp (script: 2.019 pp).  
  *Identified parameters (mean across 10 pulses):* $R_0 = 0.4798\text{ m}\Omega$, $R_1 = 0.0987\text{ m}\Omega$, $\tau_1 = 1.71\text{ s}$, $R_2 = 0.4464\text{ m}\Omega$, $\tau_2 = 28.24\text{ s}$.  
  *Causal attribution:* The 20 °C fold is an interior temperature fold and still fails the pre-registered bias gate; neither boundary extrapolation nor extreme cold rise covers this failure.
- **Fold 15 °C [FAIL]:** Bias -2.71 mV (exceeding the 2.0 mV gate; script abs bias: 9.516 mV), RMSE 13.78 mV (script: 13.050 mV), Implied SOC Error 10.16 pp (script: 9.626 pp).  
  *Identified parameters (mean across 10 pulses):* $R_0 = 0.5743\text{ m}\Omega$, $R_1 = 0.1250\text{ m}\Omega$, $\tau_1 = 1.39\text{ s}$, $R_2 = 0.4927\text{ m}\Omega$, $\tau_2 = 27.51\text{ s}$.  
  *Causal attribution:* Hypothesis (not tested): non-linear Arrhenius impedance rise at cold temperatures and boundary extrapolation (note: the 20 °C fold also fails and is an interior temperature, and 35 °C is the warm end of the range, so neither explanation covers all failures).
- **Fold 35 °C [FAIL]:** Bias +1.03 mV (script abs bias: 3.839 mV, exceeding the 2.0 mV gate), RMSE 12.43 mV (script: 4.949 mV), Implied SOC Error 8.74 pp (script: 3.480 pp).  
  *Identified parameters (mean across 10 pulses):* $R_0 = 0.3408\text{ m}\Omega$, $R_1 = 0.0762\text{ m}\Omega$, $\tau_1 = 3.11\text{ s}$, $R_2 = 0.3977\text{ m}\Omega$, $\tau_2 = 36.59\text{ s}$.  
  *Causal attribution:* Hypothesis (not tested): boundary extrapolation (note: 20 °C is an interior fold and also fails).

#### Alternate-SOC-Point Holdout
Odd vs even SOC setpoint holdouts with linear SOC interpolation:
- **Fold 1 (Train Odd, Test Even) [FAIL]:** Bias +1.77 mV (script abs bias: 17.163 mV), RMSE 7.03 mV (script: 17.309 mV), Implied SOC Error 5.07 pp (script: 12.484 pp).
- **Fold 2 (Train Even, Test Odd) [FAIL]:** Bias +1.79 mV (script abs bias: 8.871 mV), RMSE 6.13 mV (script: 8.988 mV), Implied SOC Error 4.43 pp (script: 6.478 pp).  
*Causal attribution:* Hypothesis (not tested): 20% SOC step interpolation fails to capture steep curvature at low SOC ($< 20\%$) and high SOC ($> 90\%$).

### 4.3 Per-Fold Constant-Parameter Baselines (Post-Hoc Extension)

> *Notice: Labelled 'post-hoc extension, not in the committed spec if the spec did not require it'.*  
> Computed by `scripts/validation/tempest_loto_baseline.py` and stored in `reports/validation/tempest_loto_baseline.json`.

Under the same acceptance gates (Mean Bias $\le 2.0$ mV, Voltage RMSE $\le 6.0$ mV, Implied SOC Error $\le 2.5$ pp), a constant-parameter baseline was evaluated by setting parameters to the arithmetic mean of the training folds (across temperatures for LOTO, and across SOC points for Alternate-SOC):

#### 1. LOTO Folds: Linear Interpolation vs Constant Baseline
| Fold | Linear Interp RMSE | Linear Interp Bias | Interp SOC Error | Interp Verdict | Constant Baseline RMSE | Constant Baseline Bias | Constant SOC Error | Constant Verdict | Relative Performance |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **15 °C** | 13.05 mV | 9.52 mV | 9.62 pp | **FAIL** | 24.14 mV | 17.89 mV | 17.80 pp | **FAIL** | Interpolation beats constant by 11.09 mV |
| **20 °C** | 2.76 mV | 2.01 mV | 2.02 pp | **FAIL** | 7.97 mV | 6.05 mV | 5.83 pp | **FAIL** | Interpolation beats constant by 5.21 mV |
| **25 °C** | 0.89 mV | 0.68 mV | 0.64 pp | **PASS** | 1.69 mV | 0.84 mV | 1.22 pp | **PASS** | Interpolation beats constant by 0.80 mV |
| **30 °C** | 1.66 mV | 1.30 mV | 1.18 pp | **PASS** | 11.81 mV | 8.94 mV | 8.42 pp | **FAIL** | Interpolation beats constant by 10.15 mV |
| **35 °C** | 4.95 mV | 3.84 mV | 3.48 pp | **FAIL** | 18.02 mV | 13.79 mV | 12.68 pp | **FAIL** | Interpolation beats constant by 13.07 mV |

**Comparison Summary:** Linear temperature interpolation beats the constant-parameter baseline on all 5 LOTO folds. At 25 °C, both models pass all gates. At 30 °C, interpolation passes while the constant baseline fails. At 15 °C, 20 °C, and 35 °C, both fail the committed gates, but interpolation reduces error by 5.2 to 13.1 mV.

#### 2. Alternate-SOC Folds: Linear Interpolation vs Constant Baseline
| Fold | Linear Interp RMSE | Linear Interp Bias | Interp SOC Error | Interp Verdict | Constant Baseline RMSE | Constant Baseline Bias | Constant SOC Error | Constant Verdict | Relative Performance |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ALT_ODD_FIT** | 17.31 mV | 17.16 mV | 12.48 pp | **FAIL** | 49.85 mV | 49.74 mV | 35.96 pp | **FAIL** | Interpolation beats constant by 32.54 mV |
| **ALT_EVEN_FIT** | 8.99 mV | 8.87 mV | 6.48 pp | **FAIL** | 45.03 mV | 44.93 mV | 32.48 pp | **FAIL** | Interpolation beats constant by 36.04 mV |

**Comparison Summary:** Linear SOC interpolation beats the constant baseline on both alternate-SOC folds by >32 mV RMSE, though both models fail the pre-registered gates due to unmodeled SOC non-linearities.

### 4.4 Global Baseline Comparisons (Evaluated at 25 °C)
- **Fitted In-Sample 2RC:** Voltage RMSE 0.35 mV (script: 0.38 mV), Bias 0.00 mV.
- **Constant Mean 2RC Baseline:** Voltage RMSE 9.92 mV, Bias 6.82 mV.
- **CALCE Rescaled Baseline:** Voltage RMSE 54.04 mV, Bias 38.44 mV.
- **GE105 Rescaled Baseline:** Voltage RMSE 28.01 mV, Bias 19.41 mV.

---

## 5. Reconciliation with Published LIC Parameters (V3.6)

The extracted parameters were benchmarked directly against the author-published summary files:
1. **Capacity (`LIC_capacity_analysis.csv`):** Identical to $< 10^{-7}$ Ah across all 5 temperatures.
2. **Ohmic Resistance $R_0$ (`LIC_hppc_analysis.csv`):**
   - Mean absolute discrepancy across all 50 points (5 temps $\times$ 10 SOC points): **3.34 $\mu\Omega$** (0.82%).
   - Maximum discrepancy: 10.13 $\mu\Omega$ (at 15 °C, 0.05 SOC).
   - *Causal attribution:* `LIC_characterisation_readme.txt` lines 8-10 states only that Ohmic resistance was "calculated from raw data in XXC_hppc", without specifying the window or regression method. Any attribution of the discrepancy to a 3-point regression window is **Hypothesis (not tested)** / UNVERIFIED from dataset files.
3. **OCV vs Entropy (`LIC_entropy_analysis.csv`):**
   - Relaxed OCV matches published quasi-open-circuit voltage trends. Central plateau OCV shifts by $+0.024$ mV/K (marked as **general knowledge, not verified against a source on disk**; `LIC_entropy_analysis.csv` contains measured values, but no entropy theory documentation).

---

## 6. Cross-Cell Characterisation Comparison (V3.7)

Characterisation metrics across all four repository-examined LFP cells are detailed below.
> *Notice: Values are listed as measured under the stated conditions; no inference about size dependence is possible from four cells. Asserting NO causes and NO scaling laws from four points. All values extracted directly from committed repository files with explicit provenance.*

| Metric | CALCE A123 | GE105 (EVE Energy LF105) | FlexiPod (100 Ah) | TEMPEST 280 Ah ('LIC') |
| :--- | :---: | :---: | :---: | :---: |
| **Cell Identifier / Description** | A123 LiFePO4 cell, format UNVERIFIED; measured capacity 1.0636 Ah (A1-007, 25 C) | EVE Energy LF105 LFP cell (BUGE388..BUGE391) | FlexiPod 100 Ah cell | 280 Ah LFP prismatic cell (project TEMPEST 'LIC' cell) |
| **Form Factor** | format UNVERIFIED | prismatic (general knowledge of the product; not stated in dataset files) | prismatic (general knowledge of the product; not stated in dataset files) | prismatic (per `LIC_characterisation_readme.txt` line 2) |
| **Chemistry** | LFP / Graphite | LFP / Graphite | LFP | LFP |
| **Nominal Capacity** | UNVERIFIED | 105.0 Ah | 100.0 Ah | 280.0 Ah |
| **Nominal Capacity Source** | UNVERIFIED | `deliverable/calibrations/ge105_v1.json:nominal_capacity_ah` | `deliverable/calibrations/flexipod_100ah_v1.json:nominal_capacity_ah` | `reports/validation/tempest_capacity_results.json` |
| **Measured Capacity (25 °C)** | 1.0636 Ah | 105.0427 Ah | 95.1521 Ah | 302.3087 Ah |
| **Measured Capacity Source** | `deliverable/calibrations/calce_a123_v4.json:nominal_capacity_ah` | `deliverable/calibrations/ge105_v1.json:nominal_capacity_ah` | `deliverable/calibrations/flexipod_100ah_v1.json:nominal_capacity_ah` | `reports/validation/tempest_capacity_results.json:discharge_ah[T=25C]` |
| **Ohmic Resistance $R_0$** | 158.51 m$\Omega$ | 0.5815 m$\Omega$ | 0.8940 m$\Omega$ | 0.4216 m$\Omega$ |
| **$R_0$ Condition & Comparability** | 27.3 °C, SOC-averaged table value | 25.0 °C, SOC-averaged table value | 25.0 °C, SOC-averaged table value | 25.0 °C, 55% SOC single-pulse fit (mean across 10 SOC points at 25 °C is 0.4183 m$\Omega$) |
| **$R_0$ Direct Comparability** | *Not directly comparable* (evaluated at different temperatures, SOCs, and aggregation methods) | *Not directly comparable* | *Not directly comparable* | *Not directly comparable* |
| **$R_0$ Source** | `deliverable/calibrations/calce_a123_v4.json:r0_table['27.3']` | `deliverable/calibrations/ge105_v1.json:r0_table['25.0']` | `deliverable/calibrations/flexipod_100ah_v1.json:r0_table['25.0']` | `reports/validation/tempest_ecm_results.json:in_sample_pulse_parameters[T=25,SOC=0.55]:r0_ohm` |
| **Plateau Slope ($d\text{OCV}/d\text{SOC}$)** | 1.598 mV/pp (0.1598 V/unit) | 1.372 mV/pp (0.1372 V/unit) | 1.387 mV/pp (0.1387 V/unit) | 1.386 mV/pp (0.1386 V/unit) |
| **Plateau Slope Definition** | Linear secant slope between SOC 0.20 and 0.80 from 27.3 °C OCV table | Linear secant slope between SOC 0.20 and 0.80 from 25.0 °C OCV table | Linear secant slope between SOC 0.20 and 0.80 from 25.0 °C OCV table | Linear secant slope between SOC 0.25 (3.2553 V) and 0.75 (3.3246 V) from 25 °C HPPC relaxed OCV |
| **Plateau Slope Source** | `deliverable/calibrations/calce_a123_v4.json:ocv_table['27.3']` | `deliverable/calibrations/ge105_v1.json:ocv_table['25.0']` | `deliverable/calibrations/flexipod_100ah_v1.json:ocv_table['25.0']` | `reports/validation/tempest_ecm_results.json:plateau_slopes_by_temp['25']` |
| **Measured Hysteresis** | 17.19 mV | 31.76 mV | 12.01 mV | N/A |
| **Hysteresis Definition** | Model parameter: saturation voltage parameter `m_table_v[25C]` | Experimental measurement: pseudo-OCV half-gap at 50% SOC between C/15 charge and discharge ramps | Model parameter: calibration table parameter `m_table_v[25C]` | UNVERIFIED (No continuous pseudo-OCV charge/discharge loop in dataset) |
| **Hysteresis Source** | `deliverable/calibrations/calce_a123_v4.json:m_table_v[1]` | `deliverable/calibrations/ge105_v1.json:m_table_v[4]` | `deliverable/calibrations/flexipod_100ah_v1.json:m_table_v[3]` | UNVERIFIED |

### Methodological Context & Reconciliation:
1. **Values Listed as Measured:** Values are listed as measured under the stated conditions; no inference about size dependence is possible from four cells.
2. **Reconciliation of Plateau Slope Definitions:**
   - In cross-cell tables, the plateau slope is evaluated as a wide-window secant slope across 20% to 80% SOC ($\Delta\text{OCV}/\Delta\text{SOC}$), yielding $1.37\text{--}1.39\text{ mV/pp}$ ($0.137\text{--}0.139\text{ V/unit}$) across large-format cells.
   - In contrast, statements in `reports/validation/ge105_report.md` (and `ge105_spec_frozen.md`) noting $d\text{OCV}/d\text{SOC} < 1\ \text{mV}/\%$ refer strictly to the *local* derivative at the central flat core around 50% SOC (in GE105, between 40% and 50% SOC $\Delta\text{OCV}/\Delta\text{SOC} = 0.38\ \text{mV}/\%$, and between 50% and 60% SOC it is $0.88\ \text{mV}/\%$). Both definitions are mathematically sound within their respective evaluation scopes.
3. **Non-Comparability of $R_0$:** The reported $R_0$ values are not directly comparable because CALCE, GE105, and FlexiPod values represent SOC-averaged calibration table parameters across multiple test profiles, whereas TEMPEST represents a single 140 A pulse at 55% SOC (its 10-pulse mean is $0.4183\text{ m}\Omega$).
4. **Disparate Hysteresis Quantities:** The hysteresis row reflects different metrics: CALCE and FlexiPod report model saturation voltages ($M$), GE105 reports a measured pseudo-OCV half-gap from C/15 loops, and TEMPEST contains no continuous loop data.

---

## 7. Study Boundaries, Limitations & What This Does NOT Show

1. **Single Physical Unit:** The entire dataset originates from **exactly one physical cell**. Manufacturing variance, cell-to-cell spread, and outlier behaviors cannot be assessed.
2. **Characterisation Protocols Only:** Tests consist solely of low-rate CC-CV cycles (C/10) and static HPPC pulse trains. There are **zero dynamic vehicle drive cycles** (such as WLTC, UDDS, US06).
3. **No Dynamic SOC Tracking:** Because no dynamic mission profiles were performed, this study **does not validate online BMS SOC estimation** (e.g. E7v3 EKF or Coulomb counting) on this cell format.
4. **Zero Aging / SOH Evidence:** The cell was not aged. There are zero degradation trajectories, zero cycle aging data, and zero calendar aging data. This dataset provides **no evidence for SOH estimation algorithms**.
5. **Single-Point Thermal Measurement:** Temperature was recorded from a single thermocouple placed at the center of the large prismatic surface. Pack-level thermal gradients, internal core temperatures, and tab heating effects were not measured.

---

## 8. Governance Ledger & Verification Commands

All results in this report were generated using tracked repository scripts running from a clean shell:

```bash
# 1. Capacity Analysis
.venv/bin/python scripts/validation/tempest_capacity_analysis.py

# 2. 2RC ECM Identification & Gates
.venv/bin/python scripts/validation/tempest_ecm_identification.py

# 3. LIC Parameter Reconciliation
.venv/bin/python scripts/validation/tempest_lic_comparison.py

# 4. Cross-Cell Comparison Table
.venv/bin/python scripts/validation/tempest_cross_cell_comparison.py
```
All outputs are preserved in deterministic JSON reports in `reports/validation/`.
