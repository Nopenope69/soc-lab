# TEMPEST 280 Ah Prismatic Cell Dataset: Inventory & Characterisation Structure Audit

**Date:** 2026-11-19  
**Dataset Identifier:** `tempest_zenodo`  
**Source Repository:** Zenodo Record [19632939](https://zenodo.org/records/19632939)  
**Publishing Date:** 2026-04-17  
**Creators:** University of Bath, EU TEMPEST Project  
**Cell Description:** 280 Ah Lithium Iron Phosphate (LFP) prismatic cell (project TEMPEST "LIC" cell)  
**Data Directory:** `$SOC_DATA_DIR/tempest_280ah/` (verified via `data/manifests/tempest_zenodo.sha256`)  
**Status:** `INTEGRITY_OK` (14 files, 86,597,556 bytes, 100% SHA-256 match)

---

## 1. Executive Summary

- **Subject Cell:** Single 280 Ah commercial prismatic LFP cell designated "LIC" (Lithium-Ion Cell) in the project TEMPEST testing program.
- **Scope of Data:** Fresh cell laboratory characterisation across 5 thermal chamber temperatures: **15 °C, 20 °C, 25 °C, 30 °C, and 35 °C**.
- **Data Modalities:**
  1. **Capacity Tests (`XXC_capacity.csv`):** C/10 (28 A) CC-CV charge and CC discharge protocols to determine nominal capacity versus temperature.
  2. **HPPC Tests (`XXC_hppc.csv`):** Hybrid Pulse Power Characterisation at 10 state-of-charge (SOC) setpoints (0.95 down to 0.05 in steps of 0.10) using 10-second C/2 (140 A) discharge and charge pulses.
  3. **Provided Analysis Outputs (`LIC_*`):** Pre-computed capacity, 1RC equivalent circuit model (ECM) pulse fit parameters ($R_0, R_1, C_1$), and entropy coefficients ($\mathrm{d}V/\mathrm{d}T$).
- **Aging Data:** NOT downloaded. The available dataset contains characterisation data only; there is zero cycling aging or calendar degradation data in this directory.
- **Licence & Reuse Terms:** **UNVERIFIED**. Neither the Zenodo record text on disk nor the dataset files contain an explicit open-source licence declaration (e.g., CC-BY or MIT).
- **DOI:** **UNVERIFIED**. No DOI string is embedded in the archive or readme files.

---

## 2. Directory Inventory & Hash Manifest

All 14 files reside directly in `$SOC_DATA_DIR/tempest_280ah/` and match the manifest `data/manifests/tempest_zenodo.sha256`:

| Filename | Size (Bytes) | SHA-256 Hash | File Description |
|---|---:|---|---|
| `15C_capacity.csv` | 3,396,022 | `bae5fa2223ddf0b999cde54f125e0004c31b3add86d8aeb6b28d74f5466a04c6` | Capacity characterisation test at 15 °C |
| `15C_hppc.csv` | 13,640,054 | `7f967eacfcff6622b19e1fa73d1a48c1a3dd91fcc0bd0b6f13ee0dbcd4d7719d` | 10-point HPPC pulse test at 15 °C |
| `20C_capacity.csv` | 3,414,584 | `1cfc26d91eef89ec4a5c18dbfb9273e6eb827c6c91fd34359ad1b66fccea341d` | Capacity characterisation test at 20 °C |
| `20C_hppc.csv` | 14,275,465 | `3b9af6bef8a18b653383b8a859df6f62d836d9da28cd48e25b85cad4fe0ac65b` | 10-point HPPC pulse test at 20 °C |
| `25C_capacity.csv` | 3,463,058 | `97288b5e6e012618a13e34225fde6e68a4ea2be5d5ecaedf4682db8167685920` | Capacity characterisation test at 25 °C |
| `25C_hppc.csv` | 13,804,725 | `c7e1f5d6d773fb35ba1d0ae8983ef77b62396fbbf87aa06f7fead16d8b114b32` | 10-point HPPC pulse test at 25 °C |
| `30C_capacity.csv` | 3,436,603 | `1090fe0e4ba61479195f7aff9ec79422e5f34887b9c7cc565b3ed6e59a345df7` | Capacity characterisation test at 30 °C |
| `30C_hppc.csv` | 13,483,628 | `cbe748658ec50bcf7a32965262b7c97c40dbb5e8e2e5d10e0d001c5e63348a71` | 10-point HPPC pulse test at 30 °C |
| `35C_capacity.csv` | 3,441,659 | `44c5611bf83dce12e08c4e9b3e8e70d11a92d5929e79374e6c7eb4423188d435` | Capacity characterisation test at 35 °C |
| `35C_hppc.csv` | 14,237,628 | `89a85e08a7d927f9eb336816e9c0f2e8997b57a9f6ffe85273b1c200d690792b` | 10-point HPPC pulse test at 35 °C |
| `LIC_capacity_analysis.csv` | 107 | `cf510a7771c5ddcc088b71fd0846d11246e82fecf8f60cdbff9635d9d56b2062` | Summary discharge capacity table (5 temperatures) |
| `LIC_characterisation_readme.txt` | 1,297 | `357ecab70571b76a7540b3bb714c1b8c1e0a037af5061c8e967ea436f735273b` | Dataset documentation and thermocouple location map |
| `LIC_entropy_analysis.csv` | 484 | `d5c82b460fd71591d56656cb6d77cbcbc5922f3d15c4c0f79ae2fd224febe168` | Entropy coefficient and OCV at 5 temperatures |
| `LIC_hppc_analysis.csv` | 2,242 | `58c02d68b32b4bcd79ada357436fc56fedb4d808a351e4aca952e91005cf8fef` | Pre-computed 1RC ECM parameters ($R_0, R_1, C_1$) |

---

## 3. Columns, Headers, Units & Sign Conventions

### 3.1 Column Naming Discrepancy
An audit of raw CSV file headers identified a specific column naming discrepancy:
- **9 files** (`15C_capacity.csv`, `20C_capacity.csv`, `20C_hppc.csv`, `25C_capacity.csv`, `25C_hppc.csv`, `30C_capacity.csv`, `30C_hppc.csv`, `35C_capacity.csv`, `35C_hppc.csv`) follow standard cleaned headers:
  ```csv
  Time_s,Current_A,Voltage_V,Temperature_K
  ```
- **1 file** (`15C_hppc.csv`) retains raw cycler export channel naming:
  ```csv
  Time(Sec),Current(A),Voltage(V),EX1401: SN279016C9;T_midTemperature(K)
  ```
The loader must normalize these four fields into canonical names: `time_s`, `current_a`, `voltage_v`, and `temperature_k` (converted to `temperature_c = temperature_k - 273.15`).

### 3.2 Physical Units
- **Time:** Seconds ($s$).
- **Current:** Amperes ($A$).
- **Voltage:** Terminal voltage in Volts ($V$).
- **Temperature:** Surface temperature in Kelvin ($K$). Thermocouple positioned at the geometric center of the largest prismatic face (per `LIC_characterisation_readme.txt`, lines 25–32).

### 3.3 Sign Convention
- **Raw File Convention:**
  - $I_{\text{file}} > 0$: **Charge** (current enters cell, voltage increases toward 3.650 V).
  - $I_{\text{file}} < 0$: **Discharge** (current leaves cell, voltage decreases toward 2.500 V).
- **Repository Convention:**
  - In `soc-lab` (`calce_loader.py`, `ge105_loader.py`, `uconn_loader.py`), the canonical convention is **discharge positive**.
  - Canonical conversion: $I_{\text{repo}} = -I_{\text{file}}$.

### 3.4 Delimiter Rows (Empty / All-NaN Rows)
In cycler exports (`15C_capacity.csv`, `20C_capacity.csv`, `30C_capacity.csv`, `35C_capacity.csv`, and all `XXC_hppc.csv` files), step transitions are delimited by blank comma rows (e.g. `,,,`). These parse as `NaN` across all columns and must be dropped cleanly without corrupting sample continuity.

---

## 4. Capacity Test Protocol Structure

Each `XXC_capacity.csv` file records a full charge-discharge cycle conducted at constant thermal chamber setpoint:
1. **Initial Rest:** Rest at open circuit (duration varies from ~900 s to 14,000 s).
2. **Constant-Current Charge:** CC charge at $+28.0\ \text{A}$ ($0.1\ \text{C}$) until the cell upper cutoff voltage $V_{\text{max}} = 3.650\ \text{V}$ is reached.
3. **Constant-Voltage Hold:** CV hold at $3.650\ \text{V}$ until current tapers to approximately $14.0\ \text{A}$ ($0.05\ \text{C}$).
4. **Post-Charge Relaxation:** Rest at zero current for approximately $900\ \text{s}$ (15 minutes); voltage relaxes to ~3.37 V.
5. **Constant-Current Discharge:** CC discharge at $-28.0\ \text{A}$ ($0.1\ \text{C}$) until lower cutoff voltage $V_{\text{min}} = 2.500\ \text{V}$ is triggered.
6. **Post-Discharge Rest:** Rest at zero current for approximately $900\ \text{s}$.

### 4.1 Measured Capacity vs. Temperature
Discharge capacity was evaluated by trapezoidal and point-sum integration of discharge current ($\Delta t = 1.0\ \text{s}$):

| Nominal Temp (°C) | Raw Rows | Mean Surface Temp (°C) | Integrated Discharge Capacity (Ah) | `LIC_capacity_analysis.csv` (Ah) | Absolute Discrepancy (Ah) |
|---|---:|---:|---:|---:|---:|
| **15 °C** | 78,963 | 17.06 | 299.026479 | 299.0264792 | $< 10^{-7}$ |
| **20 °C** | 79,389 | 21.67 | 301.017604 | 301.0176039 | $< 10^{-7}$ |
| **25 °C** | 80,509 | 26.54 | 302.308724 | 302.3087238 | $< 10^{-7}$ |
| **30 °C** | 79,902 | 31.43 | 303.459843 | 303.4598428 | $< 10^{-7}$ |
| **35 °C** | 80,016 | 36.37 | 303.732067 | 303.7320668 | $< 10^{-7}$ |

*Note on Repeats:* Exactly **one** capacity test cycle was conducted at each temperature. No repeat cycles exist in these characterisation files.

---

## 5. HPPC Pulse Test Protocol Structure

Each `XXC_hppc.csv` file executes a standardized Hybrid Pulse Power Characterisation protocol across 10 SOC points:

### 5.1 Test Sequence
1. **Full Conditioning Charge:** The cell is fully charged via CC-CV ($28\ \text{A}$ to $3.65\ \text{V}$, taper to $14\ \text{A}$) followed by a $900\ \text{s}$ relaxation hold.
2. **Initial SOC Adjustment:** The cell is discharged by $5\%$ of nominal capacity ($15.11\ \text{Ah}$) at $28\ \text{A}$, followed by $900\ \text{s}$ rest to establish the **0.95 SOC** test condition.
3. **HPPC Pulse Pair at each SOC Setpoint:**
   - **Discharge Pulse:** 10.0 seconds at $-140.0\ \text{A}$ ($0.5\ \text{C}$ rate).
   - **Post-Discharge Rest:** 1,200.0 seconds (20 minutes) at zero current.
   - **Charge Pulse:** 10.0 seconds at $+140.0\ \text{A}$ ($0.5\ \text{C}$ rate).
   - **Post-Charge Rest:** 1,200.0 seconds (20 minutes) at zero current.
4. **Intermediate SOC Stepping:** Between consecutive HPPC test points, the cell is discharged by $10\%$ of nominal capacity ($30.2\ \text{Ah}$) at $28\ \text{A}$ ($0.1\ \text{C}$), followed by a $900\ \text{s}$ rest period.
5. **Tested SOC Grid:** Exactly 10 points evaluated in descending order: **0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.25, 0.15, and 0.05**.

### 5.2 Sampling Profile
The HPPC logger executes adaptive temporal sampling:
- **0.01 s (100 Hz):** Recorded during high-rate pulse application (the first second of pulse transients).
- **0.1 s (10 Hz):** Recorded during remainder of current pulses.
- **1.0 s (1 Hz):** Recorded during relaxation holds and CC stepping.

---

## 6. Analysis Files Content (`LIC_*`)

### 6.1 `LIC_characterisation_readme.txt`
Full text quoted from lines 1–32:
```text
1: LIC_characterisation_readme
2: - Cell info: 280 Ah LFP prismatic cell (project TEMPEST 'LIC' cell)
3: 
4: LIC_capacity_analysis
5: - Contains:
6: 	- Capacity of LIC cell at different temperatures, calculated from raw data in XXC_capacity, where 'XX' is the temperature in degC
7: 
8: LIC_hppc_analysis
9: - Contains:
10: 	- Ohmic resistance of LIC cell at different SoCs and temperatures, calculated from raw data in XXC_hppc, where 'XX' is the temperature in degC
11: 
12: LIC_entropy_analysis
13: - Contains:
14: 	- Entropy coefficient of LIC cell at different SoCs, where five temperature points were used at each SoC and each temperature point was held for at least 2.5 h
15: - Column headings:
16: 	- Voltage_at_XXC_V: the measured OCV at the end of a temperature hold at temperature 'XX'
17: 
18: XXC_capacity/XXC_hppc
19: - Contains:
20: 	- Raw data from capacity and HPPC tests
21: - Column headings:
22: 	- Time_s, Current_A, Voltage_V
23: 	- Temperature_K, temperature on the cell surface, on the largest face of the cell, in the middle (see image below)
24: 
25:         | |     | |
26:      ┌───────────┐
27:      │       x       │
28:      │               │
29:      │       x       │ <- Temperature measurement location
30:      │               │
31:      │               │
32:      └───────────┘
```

### 6.2 `LIC_capacity_analysis.csv`
Contains 5 rows summarizing discharge capacity in Ah as a function of temperature:
- 15 °C: 299.026 Ah
- 20 °C: 301.018 Ah
- 25 °C: 302.309 Ah
- 30 °C: 303.460 Ah
- 35 °C: 303.732 Ah

### 6.3 `LIC_hppc_analysis.csv`
Contains 50 parameter rows (5 temperatures $\times$ 10 SOC points) identifying a 1RC equivalent circuit model:
- Columns: `Temperature_C`, `SoC`, `R0_Ohm`, `R1_Ohm`, `C1_F`
- At 25 °C, $R_0$ spans from $0.403\ \text{m}\Omega$ (at 0.95 SOC) to $0.432\ \text{m}\Omega$ (at 0.05 SOC).
- $R_1$ spans from $0.096\ \text{m}\Omega$ to $0.188\ \text{m}\Omega$; $C_1$ spans from $233\ \text{kF}$ to $971\ \text{kF}$.

### 6.4 `LIC_entropy_analysis.csv`
Contains 5 rows (SOC 0.1, 0.3, 0.5, 0.7, 0.9) reporting the entropic thermal coefficient $\frac{\partial U}{\partial T}$ in $\text{V}/\text{K}$, together with relaxed open-circuit voltages recorded across thermal holds at 45 °C, 35 °C, 25 °C, 15 °C, and 5 °C.

---

## 7. Licence, Copyright & Reuse Verification

A search across all files in `$SOC_DATA_DIR/tempest_280ah/` for terms `license`, `licence`, `copyright`, `cc-by`, `creative commons`, or `doi` established:
- **No licence statement is present in any file.**
- **No DOI is specified in any file.**
- The licence is therefore formally recorded as **`UNVERIFIED`** in repository manifests.
