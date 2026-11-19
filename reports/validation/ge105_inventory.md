# Gustave Eiffel 105 Ah LFP Dataset Inventory (V1.1)

> [!NOTE] Revision (V1.12)  
> Clarified cell format provenance: noted that prismatic format is derived from general knowledge of the EVE LF105 product and is not stated in the dataset readmes.

> **Dataset Title:** Characterisation tests of EVE Energy LFP 105Ah cells  
> **Experimental Data DOI:** [10.57745/G02IYE](https://doi.org/10.57745/G02IYE)  
> **Identified Parameters DOI:** [10.57745/SBNO8W](https://doi.org/10.57745/SBNO8W)  
> **Licence:** Etalab Open Licence 2.0  
> **Location:** `$SOC_DATA_DIR/gustave_eiffel_105ah/`  
> **Authors:** Pedro Von Hohendorff Seger, Eduardo Redondo-Iglesias, Serge Pelissier (Univ Gustave Eiffel, ELECTRIMACS 2024)  
> **Status:** Real on-disk files verified against SHA-256 manifests (`INTEGRITY_OK`).

---

## 1. Executive Summary

The Gustave Eiffel dataset provides extensive characterisation data for four commercial EVE Energy 105 Ah Lithium Iron Phosphate (LiFePO4 / LFP) cells (prismatic format from general knowledge of the EVE LF105 product; not stated in the dataset readmes) designated `BUGE388`, `BUGE389`, `BUGE390`, and `BUGE391`. Tests were conducted across eight ambient temperatures: 0, 10, 15, 20, 25, 30, 35, and 40 °C using a Biologic BCS 815 battery cycler inside a thermal chamber.

A total of **36 processed DATTES MATLAB (`.mat`) files** are present on disk under `$SOC_DATA_DIR/gustave_eiffel_105ah/main_extracted/processed_data/2_processed_data/<CELL>/`. Additionally, the repository includes the author-provided equivalent circuit model (2RC ECM) parameter file `batt_data.mat` under `params_extracted/`.

---

## 2. Inventory of Processed Data Files (36/36)

All 36 files on disk were surveyed and verified bit-exact against `data/manifests/gustave_eiffel_g02iye.sha256`.

| Cell | Temp | Type | Date | Samples | Duration (h) | Phases | Size (MB) | Filename |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **BUGE388** | 0 °C | full | 2023-08-04 | 529,933 | 69.1 | 265 | 12.9 | `20230804_1122_full_0C_buge388_dattes.mat` |
| BUGE388 | 10 °C | partial | 2023-08-08 | 462,924 | 28.4 | 164 | 11.0 | `20230808_1118_partial_10C_buge388_dattes.mat` |
| BUGE388 | 15 °C | partial | 2023-08-10 | 455,843 | 27.7 | 164 | 10.7 | `20230810_1112_partial_15C_buge388_dattes.mat` |
| BUGE388 | 25 °C | full | 2023-08-25 | 498,131 | 64.1 | 265 | 11.5 | `20230825_1333_full_25C_buge388_dattes.mat` |
| BUGE388 | 20 °C | partial | 2023-08-29 | 488,550 | 28.0 | 164 | 11.6 | `20230829_1115_partial_20C_buge388_dattes.mat` |
| BUGE388 | 25 °C | partial (repeat) | 2023-11-10 | 520,311 | 27.4 | 165 | 12.5 | `20231110_1642_partial_25C_buge388_dattes.mat` |
| BUGE388 | 30 °C | partial | 2023-11-16 | 471,570 | 27.4 | 165 | 10.9 | `20231116_1716_partial_30C_buge388_dattes.mat` |
| BUGE388 | 35 °C | partial | 2023-11-20 | 439,647 | 27.3 | 165 | 9.8 | `20231120_1103_partial_35C_buge388_dattes.mat` |
| BUGE388 | 40 °C | full | 2023-11-23 | 492,029 | 62.5 | 265 | 11.3 | `20231123_1349_full_40C_buge388_dattes.mat` |
| **BUGE389** | 25 °C | full | 2023-08-08 | 495,947 | 63.2 | 265 | 11.6 | `20230808_1242_full_25C_buge389_dattes.mat` |
| BUGE389 | 0 °C | full | 2023-08-12 | 541,869 | 70.3 | 265 | 13.4 | `20230812_2136_full_0C_buge389_dattes.mat` |
| BUGE389 | 35 °C | partial | 2023-08-16 | 413,158 | 27.9 | 165 | 9.1 | `20230816_1246_partial_35C_buge389_dattes.mat` |
| BUGE389 | 20 °C | partial | 2023-08-22 | 483,751 | 28.1 | 165 | 11.5 | `20230822_1420_partial_20C_buge389_dattes.mat` |
| BUGE389 | 40 °C | full | 2023-08-25 | 491,873 | 62.5 | 265 | 11.4 | `20230825_1339_full_40C_buge389_dattes.mat` |
| BUGE389 | 30 °C | partial | 2023-08-30 | 428,825 | 27.5 | 165 | 9.6 | `20230830_1602_partial_30C_buge389_dattes.mat` |
| BUGE389 | 15 °C | partiel (quirk) | 2023-09-01 | 482,023 | 27.4 | 164 | 11.6 | `20230901_1054_partiel_15C_buge389_dattes.mat` |
| BUGE389 | 10 °C | partial | 2023-09-04 | 479,266 | 27.4 | 164 | 11.6 | `20230904_1341_partial_10C_buge389_dattes.mat` |
| BUGE389 | 25 °C | partial (repeat) | 2023-09-05 | 490,597 | 39.4 | 165 | 10.5 | `20230905_1721_partial_25C_buge389_dattes.mat` |
| **BUGE390** | 25 °C | full (baseline) | 2023-06-27 | 491,824 | 58.9 | 167 | 11.5 | `20230627_1131_full_25C_buge390_dattes.mat` |
| BUGE390 | 25 °C | pseudoOCV | 2023-07-03 | 112,763 | 34.0 | 9 | 3.5 | `20230703_1138_pseudoOCV_25C_buge390_dattes.mat` |
| BUGE390 | 15 °C | partial | 2023-07-10 | 567,977 | 28.1 | 164 | 14.3 | `20230710_1503_partial_15C_buge390_dattes.mat` |
| BUGE390 | 0 °C | full | 2023-07-12 | 539,340 | 69.5 | 265 | 13.4 | `20230712_1137_full_0C_buge390_dattes.mat` |
| BUGE390 | 20 °C | partial | 2023-07-17 | 501,809 | 28.1 | 164 | 12.1 | `20230717_1001_partial_20C_buge390_dattes.mat` |
| BUGE390 | 30 °C | partial | 2023-07-18 | 423,419 | 27.5 | 165 | 9.5 | `20230718_1510_partial_30C_buge390_dattes.mat` |
| BUGE390 | 35 °C | partial | 2023-07-20 | 406,524 | 27.4 | 165 | 8.9 | `20230720_1112_partial_35C_buge390_dattes.mat` |
| BUGE390 | 40 °C | full | 2023-07-21 | 493,391 | 63.1 | 265 | 11.4 | `20230721_2113_full_40C_buge390_dattes.mat` |
| BUGE390 | 10 °C | partial | 2023-07-24 | 503,260 | 28.1 | 164 | 12.3 | `20230724_1505_partial_10C_buge390_dattes.mat` |
| BUGE390 | 25 °C | partial (final) | 2023-07-26 | 447,334 | 27.6 | 165 | 10.3 | `20230726_0918_partial_25C_final_buge390_dattes.mat` |
| **BUGE391** | 25 °C | full (baseline) | 2023-06-27 | 491,763 | 58.9 | 167 | 11.3 | `20230627_1135_full_25C_buge391_dattes.mat` |
| BUGE391 | 0 °C | full | 2023-07-12 | 529,512 | 69.6 | 265 | 12.9 | `20230712_1137_full_0C_buge391_dattes.mat` |
| BUGE391 | 20 °C | partial | 2023-12-05 | 519,997 | 27.5 | 165 | 12.6 | `20231205_1137_partial_20C_buge391_dattes.mat` |
| BUGE391 | 15 °C | partial | 2023-12-07 | 523,284 | 27.4 | 164 | 12.8 | `20231207_1254_partial_15C_buge391_dattes.mat` |
| BUGE391 | 10 °C | partial | 2023-12-11 | 525,529 | 27.5 | 164 | 13.0 | `20231211_1606_partial_10C_buge391_dattes.mat` |
| BUGE391 | 30 °C | partial | 2023-12-14 | 447,046 | 27.5 | 165 | 10.1 | `20231214_1526_partial_30C_buge391_dattes.mat` |
| BUGE391 | 35 °C | partial | 2024-01-30 | 407,388 | 27.3 | 165 | 8.9 | `20240130_1403_partial_35C_buge391_dattes.mat` |
| BUGE391 | 40 °C | full | 2024-02-01 | 491,030 | 62.5 | 265 | 11.4 | `20240201_1650_full_40C_buge391_dattes.mat` |

**Total:** 36 files across 4 cells, ~17.1 million recorded measurements, ~412 MB uncompressed data.

---

## 3. Sampling Characteristics and Timebase

An exhaustive statistical audit across all 36 files confirms:
- **Interval Monotonicity:** Exactly 0 non-positive time intervals ($\Delta t \le 0$) were found across all 17,144,385 time intervals.
- **Irregular Sampling Grid:**
  - $\Delta t_{\min} \approx 0.0019\ \text{s}$ (during steep transitions and current step events).
  - $\Delta t_{\text{median}} = 0.1000\ \text{s}$ (standard high-frequency logging rate).
  - $\Delta t_{p95} = 1.000\ \text{s}$.
  - $\Delta t_{p99} = 10.000\ \text{s}$ (during long CC/CV periods and steady rests).
  - $\Delta t_{\max} = 10.026\ \text{s}$.
- **Implication for Estimator Evaluation:**
  1. The primary evaluation pipeline resamples dynamic segments to a fixed $\Delta t = 1.0\ \text{s}$ grid using exact trapezoidal charge integration and voltage interpolation.
  2. The native irregular $\Delta t$ timebase is evaluated in parallel as a sensitivity check to ensure the continuous-discrete E7v3 estimator remains robust under irregular time steps.

---

## 4. Signal Conventions, Units, and Calibration Limits

Inspection of the MATLAB structure `result.profiles` and `result.metadata` reveals:

1. **Current Polarity (Charge Positive in Raw File):**
   - In DATTES processed files, current $I > 0$ represents charging, and $I < 0$ represents discharging.
   - Empirical slope test: $\frac{\Delta(\text{dod\_ah})}{I_{\text{file}} \cdot \Delta t / 3600} = -1.0000000000$ (charge decreases DoD).
   - **Repository Requirement:** The repository standard convention is **Discharge Positive** ($I > 0$ discharge, $I < 0$ charge).
   - **Loader Rule:** The loader inverts current in exactly one place:
     $$I_{\text{repo}} = -I_{\text{file}}$$
2. **Terminal Voltage ($U$):**
   - Measured in Volts ($V$).
   - Metadata limits: $V_{\min} = 2.4986\ \text{V}$, $V_{\max} = 3.6503\ \text{V}$.
3. **State of Charge ($soc$) and Depth of Discharge ($dod\_ah$):**
   - `dod_ah`: In Ampere-hours ($\text{Ah}$).
   - `soc`: In percent ($\%$), ranging from $0.2\%$ to $100.1\%$.
   - **Crucial Ground-Truth Note:** `profiles.soc` is an internal Ah-counting reference re-anchored by DATTES at full-charge events. It is NOT an independent physical measurement. Coulomb counters (E0) will appear artificially close to it by construction.
4. **Disallowed Accumulator Channels (`ah`, `ah_cha`, `ah_dis`):**
   - Given in $\text{mAh}$, reset at intermediate phase and cycle boundaries. Must never be differenced across entire files.
5. **Absence of Cell Temperature Channel (`profiles.T`):**
   - `profiles.T` is an empty vector in every file.
   - Temperature input is strictly taken from the **chamber setpoint** indicated by the filename ($0, 10, 15, 20, 25, 30, 35, 40\ ^\circ\text{C}$).
   - High C-rate cell self-heating cannot be observed from this dataset.

---

## 5. Filename Quirks and Robust Regex Matching

All filenames follow a variant of the DATTES naming convention:
```
<dateYYMMDD>_<timeHHMM>_<type>_<T>C_<cell>_dattes.mat
```
The following variations are present:
1. **French spelling:** `BUGE389/20230901_1054_partiel_15C_buge389_dattes.mat` (`partiel` instead of `partial`).
2. **Pseudo-OCV standalone file:** `BUGE390/20230703_1138_pseudoOCV_25C_buge390_dattes.mat`.
3. **Appended modifier:** `BUGE390/20230726_0918_partial_25C_final_buge390_dattes.mat` (contains `_final_`).
4. **Shared timestamp:** `BUGE390` and `BUGE391` both have files named `20230712_1137_full_0C_<cell>_dattes.mat`. Manifest hashes confirm these are distinct binary files.

**Canonical Parser Regex:**
```python
re.compile(r"^(\d{8})_(\d{4})_(.+?)_(\d+)C(?:_([a-zA-Z0-9]+))?_([a-zA-Z0-9]+)_dattes\.mat$")
```
Tested against the entire directory tree: **36 matched, 0 unmatched**.

---

## 6. WLTC Dynamic Drive-Cycle Identification

Full-protocol files contain four distinct experimental phases:
1. **Capacity cycles:** 3 CC-CV charge/discharge cycles at 1C (105 A).
2. **Pulse impedance:** 30 s pulses with 180 s rests at 0.25C, 0.5C, and 1C at every 10% SOC increment.
3. **Pseudo-OCV:** C/15 charge and discharge (7 A, ~53,500 s each).
4. **WLTC Validation Segments:** Two dynamic driving cycles performed at ~90% SOC and ~50% SOC.

### Dynamic Segment Detection Rule
Each WLTC drive cycle consists of **44 consecutive constant-current micro-phases** with phase durations $\le 120\ \text{s}$, totaling exactly **986.0 seconds** (~16.4 minutes) of dynamic charge and discharge current:
- **Segment 1 (~90% SOC):** Executed after discharging ~10.5 Ah from 100% SOC followed by 1 hour rest.
- **Segment 2 (~50% SOC):** Executed after an additional ~38.2 Ah discharge followed by 30 minutes rest.

### Audit of WLTC Segments Across Full Files
- **10 of 12 full files** contain both 986-second WLTC segments (BUGE388 at 0, 25, 40 °C; BUGE389 at 0, 25, 40 °C; BUGE390 at 0, 40 °C; BUGE391 at 0, 40 °C).
- **The earliest two files** (`BUGE390` 25C full and `BUGE391` 25C full, tested on 2023-06-27) terminated at phase 166 (at 52.5 Ah discharge) before the WLTC cycling script was incorporated into the testing regime. These two files contain capacity, pulse impedance, and pseudo-OCV, but no WLTC segments.

---

## 7. Measurement Repeatability and Temporal Drift (Not SOH)

For cells BUGE388, BUGE389, and BUGE390, a repeat 25 °C test was executed weeks to months later. Comparing the measured 1C discharge capacity and 1C 30s discharge pulse resistance gives:

| Cell | Test 1 Date | Test 2 Date | Elapsed | Cap 1 (Ah) | Cap 2 (Ah) | $\Delta$ Cap | R 1 (m$\Omega$) | R 2 (m$\Omega$) | $\Delta$ R |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **BUGE388** | 2023-08-25 | 2023-11-10 | 77 days | 104.537 | 103.311 | -1.226 Ah (-1.17%) | 0.510 | 0.518 | +0.008 m$\Omega$ (+1.48%) |
| **BUGE389** | 2023-08-08 | 2023-09-05 | 28 days | 104.902 | 102.918 | -1.984 Ah (-1.89%) | 0.559 | 0.535 | -0.025 m$\Omega$ (-4.44%) |
| **BUGE390** | 2023-06-27 | 2023-07-26 | 29 days | 105.953 | 104.605 | -1.348 Ah (-1.27%) | 0.520 | 0.495 | -0.025 m$\Omega$ (-4.78%) |

> [!IMPORTANT]
> Per Rule 1 and Rule 8, these differences reflect cycler measurement repeatability, contact resistance variations, and temporal rest drift at beginning-of-life. They do **NOT** constitute SOH aging evidence. No SOH degradation claims will be drawn from this dataset.
