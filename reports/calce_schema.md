# CALCE A123 LFP Dataset Schema & Inspection Report

## 1. Executive Summary

This report documents the exhaustive structural and physical inspection of the **CALCE A123 26650 LiFePO4 (LFP)** battery dataset located in `data/raw/calce_a123/`. 
All 36 data workbooks across 8 temperatures ($-10^\circ\text{C}$, $0^\circ\text{C}$, $10^\circ\text{C}$, $20^\circ\text{C}$, $25^\circ\text{C}$, $30^\circ\text{C}$, $40^\circ\text{C}$, $50^\circ\text{C}$) and 2 individual cells (`A1-007` and `A1-008`) were analyzed for channel schema, sheet organization, sampling intervals, sign conventions, profile step sequences, temperature tracking, and data integrity anomalies.

---

## 2. Dataset Overview & Inventory

### 2.1 Cell Specifications
- **Cell Chemistry:** Lithium Iron Phosphate ($\text{LiFePO}_4$ / LFP)
- **Cell Form Factor:** Cylindrical 26650
- **Manufacturer / Model:** A123 Systems APR18650m1 / 26650 (rated capacity $1.11\,\text{Ah}$, nominal voltage $3.3\,\text{V}$)
- **Tested Cells:** Two distinct cell specimens tested in parallel across all temperatures:
  - Cell 1: `A1-007`
  - Cell 2: `A1-008`

### 2.2 File Inventory (36 Raw Workbooks)
The dataset comprises 16 unzipped directories containing 36 spreadsheet files:
- **20 Dynamic Test Files (`A123_DST-US06-FUDS-*`):**
  - $-10^\circ\text{C}$ (Folder `A123_DST-US06-FUDS-N10`): 2 files (`A1-007`, `A1-008`), `.xlsx`
  - $0^\circ\text{C}$ (`A123_DST-US06-FUDS-0`): 2 files (`A1-007`, `A1-008`), `.xlsx`
  - $10^\circ\text{C}$ (`A123_DST-US06-FUDS-10`): 2 files (`A1-007`, `A1-008`), `.xlsx`
  - $20^\circ\text{C}$ (`A123_DST-US06-FUDS-20`): 6 files (see Section 7 for details):
    - `A1-007-DST-US06-FUDS-20-20120809.xls` (legacy BIFF8 format)
    - `A1-008-DST-US06-FUDS-20-20120809.xls` (legacy BIFF8 format)
    - `A1-007-DST-US06-FUDS-20-20120817.xlsx`
    - `A1-008-DST-US06-FUDS-20-20120817.xlsx`
    - `A1-007-DST-US06-FUDS-20-20120817-newprofile.xlsx`
    - `A1-008-DST-US06-FUDS-20-20120817-newprofile.xlsx`
  - $25^\circ\text{C}$ (`A123_DST-US06-FUDS-25`): 2 files (`A1-007`, `A1-008`), `.xlsx`
  - $30^\circ\text{C}$ (`A123_DST-US06-FUDS-30`): 2 files (`A1-007`, `A1-008`), `.xlsx`
  - $40^\circ\text{C}$ (`A123_DST-US06-FUDS-40`): 2 files (`A1-007`, `A1-008`), `.xlsx`
  - $50^\circ\text{C}$ (`A123_DST-US06-FUDS-50`): 2 files (`A1-007`, `A1-008`), `.xlsx`
- **16 Low-Current OCV Files (`A123_OCV*`):**
  - Exactly 2 files per temperature (`A1-007` and `A1-008`), all in `.xlsx` format:
    - $-10^\circ\text{C}$ (`A123_OCV-10-20120629`): 2 files
    - $0^\circ\text{C}$ (`A123_OCV0-20120618`): 2 files
    - $10^\circ\text{C}$ (`A123_OCV10-20120611`): 2 files
    - $20^\circ\text{C}$ (`A123_OCV20-20120614`): 2 files
    - $25^\circ\text{C}$ (`A123_OCV25-20120905`): 2 files
    - $30^\circ\text{C}$ (`A123_OCV30-20120625`): 2 files
    - $40^\circ\text{C}$ (`A123_OCV40-20120627`): 2 files
    - $50^\circ\text{C}$ (`A123_OCV50-20120702`): 2 files
- **Temporary Lock Files:**
  - 3 Microsoft Excel lock files (`~$*`, 165 bytes) present in raw folders (`DST-0`, `DST-40`, `OCV30`); must be explicitly filtered out by loaders.

---

## 3. Workbook Structure & Sheet Architecture

Every workbook exported from Arbin MITS Pro cycler contains multiple sheets:

| Sheet Name | Content & Purpose | Handling Rule |
| :--- | :--- | :--- |
| **`Info`** | Test metadata: Channel number, test start date/time, Arbin schedule filename (`.sdu`), operator, original `.res` binary path. | Parse for validation and provenance tracking. |
| **`Channel_1-005`** / **`Channel_1-006`** | Primary time-series test log with full measurement precision. | **Canonical data source** for all processing. |
| **`Channel_Chart`** | Embedded Arbin graphical charts (`openpyxl.chartsheet`). | Ignore; not a tabular worksheet. |
| **`Sheet1`** / **`Sheet2`** | Simplified sub-sampled views (e.g., 6 columns in `Sheet1`, 3 columns in `Sheet2`). | Ignore; subsets only. |

### Cell to Sheet Mapping
The Arbin cycler assigns hardware channels `1-005` and `1-006` to the test fixtures:
- **Dynamic Tests (`A123_DST-US06-FUDS-*`):**
  - Cell `A1-007` $\longrightarrow$ sheet **`Channel_1-006`** across all 8 temperatures.
  - Cell `A1-008` $\longrightarrow$ sheet **`Channel_1-005`** across all 8 temperatures.
- **Low-Current OCV Tests (`A123_OCV*`):**
  - Temperatures $-10^\circ\text{C}, 0^\circ\text{C}, 10^\circ\text{C}, 20^\circ\text{C}, 30^\circ\text{C}, 40^\circ\text{C}, 50^\circ\text{C}$:
    - Cell `A1-007` $\longrightarrow$ sheet **`Channel_1-005`**
    - Cell `A1-008` $\longrightarrow$ sheet **`Channel_1-006`**
  - Temperature $25^\circ\text{C}$ (`A123_OCV25-20120905`):
    - Cell `A1-007` $\longrightarrow$ sheet **`Channel_1-006`**
    - Cell `A1-008` $\longrightarrow$ sheet **`Channel_1-005`** (inverted relative to other OCV tests!)
- **Robust Parsing Rule:** Loaders must select the sheet whose name starts with `Channel_1-` rather than hard-coding a specific channel number.

---

## 4. Column Schema & Units

There are two consistent column sets across all `Channel_1-*` sheets:

| Column Header | Unit | Type | Description |
| :--- | :--- | :--- | :--- |
| `Data_Point` | - | `int64` | Sequential point counter (1-indexed). |
| `Test_Time(s)` | $\text{s}$ | `float64` | Cumulative test time since experiment start. |
| `Date_Time` | - | `datetime64[ns]` | Wall-clock timestamp (`YYYY-MM-DD HH:MM:SS`). |
| `Step_Time(s)` | $\text{s}$ | `float64` | Elapsed time within the current `Step_Index`. |
| `Step_Index` | - | `int64` | Cycler state machine step number (1–27 for dynamic, 1–8 for OCV). |
| `Cycle_Index` | - | `int64` | Cycle loop counter (constant 1 in dynamic steps). |
| `Current(A)` | $\text{A}$ | `float64` | Terminal current. **Raw sign: Charge $> 0$, Discharge $< 0$**. |
| `Voltage(V)` | $\text{V}$ | `float64` | Terminal cell voltage. |
| `Charge_Capacity(Ah)` | $\text{Ah}$ | `float64` | Accumulated charge capacity. |
| `Discharge_Capacity(Ah)`| $\text{Ah}$ | `float64` | Accumulated discharge capacity. |
| `Charge_Energy(Wh)` | $\text{Wh}$ | `float64` | Accumulated charge energy. |
| `Discharge_Energy(Wh)` | $\text{Wh}$ | `float64` | Accumulated discharge energy. |
| `dV/dt(V/s)` | $\text{V/s}$ | `float64` | Numerical derivative of voltage. |
| `Internal_Resistance(Ohm)`| $\Omega$ | `float64` | High-frequency DC resistance diagnostic. |
| `Is_FC_Data` | - | `bool` / `int` | Arbin flag (all 0 in these tests). |
| `AC_Impedance(Ohm)` | $\Omega$ | `float64` | AC impedance log (all 0). |
| `ACI_Phase_Angle(Deg)` | $\text{deg}$ | `float64` | AC phase angle (all 0). |
| `Temperature (C)_1` | $^\circ\text{C}$ | `float64` | Primary thermocouple (surface or chamber). Present in all 36 files. |
| `Temperature (C)_2` | $^\circ\text{C}$ | `float64` | Secondary thermocouple. Present in 14 OCV files (Set 2). |

---

## 5. Sign Convention & Unit Mapping

### 5.1 Sign Inversion Requirement
- **Raw CALCE (Arbin MITS Pro) Convention:**
  - $\text{Current} > 0$ denotes **Charge**
  - $\text{Current} < 0$ denotes **Discharge**
- **Repository & Plant Simulator Convention (`src/soc/models/plant.py`):**
  - $\text{Current} > 0$ denotes **Discharge**
  - $\text{Current} < 0$ denotes **Charge**
- **Mandatory Loader Transformation:**
  $$\mathbf{I}_{\text{repo}} = -\mathbf{I}_{\text{raw}}$$
  When this transformation is applied, positive current depletes cell SOC ($d\text{SOC}/dt < 0$), matching Coulomb counting in `E0` through `E6`.

---

## 6. Profile Demarcation & Step Sequences

### 6.1 Dynamic Files (`A123_DST-US06-FUDS-*`)
Every dynamic file contains exactly **27 steps** organized into three consecutive test regimes. Each profile is preceded by a complete CC-CV full charge followed by a rest, guaranteeing that **each dynamic profile starts from a known $100\%$ SOC state**:

| Step Range | Step Index | Operational Phase | Current Range | End Condition / Duration | SOC State |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **Pre-DST** | 1 | Rest / Initial State | $0\,\text{A}$ | Instantaneous | - |
| | 2 | CC Discharge (Pre-conditioning) | $-1.1\,\text{A}$ | Voltage cutoff $V \le 2.0\,\text{V}$ | $0\%$ |
| | 3 | Rest | $0\,\text{A}$ | $115\,\text{s}$ | $0\%$ |
| | 4 | CC Charge (1C) | $+1.1\,\text{A}$ | Voltage cutoff $V \ge 3.60\,\text{V}$ | $\approx 90\%$ |
| | 5 | CV Charge (Float) | $+1.1 \to +0.055\,\text{A}$ | Current taper to C/20 ($0.055\,\text{A}$) | $100\%$ |
| | 6 | Transition | $0\,\text{A}$ | 1 point | $100\%$ |
| | 7 | Pre-Profile Rest | $0\,\text{A}$ | $115\,\text{s}$ ($V \approx 3.56\,\text{V}$) | **$100\%$** |
| **Profile 1 (DST)** | **8** | **DST Dynamic Drive Cycle** | $[-3.85\,\text{A}, +1.93\,\text{A}]$ | **Voltage cutoff $V \le 2.0\,\text{V}$ ($\sim 7400\,\text{s}$)** | **$100\% \to 0\%$** |
| | 9 | Post-DST Rest | $0\,\text{A}$ | $\sim 6800\,\text{s}$ ($\sim 1.9\,\text{hr}$) | Relaxed |
| | 10–11 | Transitions | $0\,\text{A}$ | 2 points | - |
| **Pre-US06** | 12 | CC Charge (1C) | $+1.1\,\text{A}$ | Voltage cutoff $V \ge 3.60\,\text{V}$ | $\approx 90\%$ |
| | 13 | CV Charge (Float) | $+1.1 \to +0.055\,\text{A}$ | Current taper to C/20 ($0.055\,\text{A}$) | $100\%$ |
| | 14 | Transition | $0\,\text{A}$ | 1 point | $100\%$ |
| | 15 | Pre-Profile Rest | $0\,\text{A}$ | $115\,\text{s}$ ($V \approx 3.56\,\text{V}$) | **$100\%$** |
| **Profile 2 (US06)** | **16** | **US06 Dynamic Drive Cycle** | $[-3.85\,\text{A}, +0.83\,\text{A}]$ | **Voltage cutoff $V \le 2.0\,\text{V}$ ($\sim 6980\,\text{s}$)** | **$100\% \to 0\%$** |
| | 17 | Post-US06 Rest | $0\,\text{A}$ | $\sim 6000\,\text{s}$ ($\sim 1.7\,\text{hr}$) | Relaxed |
| | 18–19 | Transitions | $0\,\text{A}$ | 2 points | - |
| **Pre-FUDS** | 20 | CC Charge (1C) | $+1.1\,\text{A}$ | Voltage cutoff $V \ge 3.60\,\text{V}$ | $\approx 90\%$ |
| | 21 | CV Charge (Float) | $+1.1 \to +0.055\,\text{A}$ | Current taper to C/20 ($0.055\,\text{A}$) | $100\%$ |
| | 22 | Transition | $0\,\text{A}$ | 1 point | $100\%$ |
| | 23 | Pre-Profile Rest | $0\,\text{A}$ | $115\,\text{s}$ ($V \approx 3.56\,\text{V}$) | **$100\%$** |
| **Profile 3 (FUDS)**| **24** | **FUDS Dynamic Drive Cycle** | $[-3.85\,\text{A}, +2.06\,\text{A}]$ | **Voltage cutoff $V \le 2.0\,\text{V}$ ($\sim 7400\,\text{s}$)** | **$100\% \to 0\%$** |
| | 25 | Post-FUDS Rest | $0\,\text{A}$ | $\sim 5500\,\text{s}$ ($\sim 1.5\,\text{hr}$) | Relaxed |
| | 26–27 | Transitions | $0\,\text{A}$ | 2 points | - |

**Profile Boundaries in Time:**
- **DST:** Start = Step 8 row 0; End = Step 8 last row.
- **US06:** Start = Step 16 row 0; End = Step 16 last row.
- **FUDS:** Start = Step 24 row 0; End = Step 24 last row.

### 6.2 Low-Current OCV Files (`A123_OCV*`)
Every low-current OCV file contains exactly **8 steps**:

| Step Index | Operational Phase | Applied Current | Duration / Termination | Voltage Range | Notes |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **1** | Initial Rest | $0\,\text{A}$ | Instantaneous | $\sim 2.90\,\text{V}$ | Initial cell status |
| **2** | CC Charge (Prep) | $+1.18\,\text{A}$ | Cutoff $V \ge 3.60\,\text{V}$ | $2.90 \to 3.60\,\text{V}$ | 1C constant current |
| **3** | CV Charge (Prep) | $+1.18 \to 0.01\,\text{A}$| Cutoff $I \le 0.01\,\text{A}$ | $3.60\,\text{V}$ | Voltage hold to full saturation |
| **4** | Rest at Full Charge | $0\,\text{A}$ | $3540\,\text{s}$ ($\approx 1\,\text{hr}$) | $3.60 \to \sim 3.51\,\text{V}$ | Relaxation to equilibrium OCV |
| **5** | **C/20 Discharge Branch** | **$-0.050\,\text{A}$** | **Cutoff $V \le 2.000\,\text{V}$** | **$3.51 \to 2.000\,\text{V}$** | **Duration $\approx 21.3\,\text{hr}$ ($15,300\,\text{pts}$)** |
| **6** | Rest at Depletion | $0\,\text{A}$ | $3540\,\text{s}$ ($\approx 1\,\text{hr}$) | $2.00 \to \sim 2.48\,\text{V}$ | Relaxation at $0\%$ SOC |
| **7** | **C/20 Charge Branch** | **$+0.050\,\text{A}$** | **Cutoff $V \ge 3.600\,\text{V}$** | **$2.48 \to 3.600\,\text{V}$** | **Duration $\approx 21.2\,\text{hr}$ ($15,260\,\text{pts}$)** |
| **8** | Final Rest | $0\,\text{A}$ | $3540\,\text{s}$ ($\approx 1\,\text{hr}$) | $3.60 \to \sim 3.50\,\text{V}$ | Final relaxation |

---

## 7. Sampling Interval Distributions

Sampling rates across all files were measured empirically:

| Phase | Steps | Median $\Delta t$ | $\text{P}_{10}$ | $\text{P}_{90}$ | Min / Max $\Delta t$ | Behavior |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Dynamic Drive Cycles** | 8, 16, 24 | **$1.00\,\text{s}$** | $1.00\,\text{s}$ | $1.01\,\text{s}$ | $0.01\,\text{s} - 1.03\,\text{s}$ | Regular 1 Hz sampling with millisecond jitter |
| **C/20 OCV Branches** | 5, 7 | **$5.00\,\text{s}$** | $5.00\,\text{s}$ | $5.01\,\text{s}$ | $1.21\,\text{s} - 6.66\,\text{s}$ | Uniform 5 s interval with occasional voltage event logging |
| **CC / CV Charges** | 4, 5, 12, 13, 20, 21 | **$5.00\,\text{s}$** | $5.00\,\text{s}$ | $5.01\,\text{s}$ | $0.60\,\text{s} - 5.01\,\text{s}$ | Uniform 5 s interval |
| **Short Pre-Rest** | 7, 15, 23 | **$5.00\,\text{s}$** | $5.00\,\text{s}$ | $5.01\,\text{s}$ | $4.88\,\text{s} - 5.01\,\text{s}$ | 24 points ($115\,\text{s}$) |
| **Long Post-Rest** | 9, 17, 25 | $\sim 361\,\text{s}$ | $361.0\,\text{s}$ | $361.0\,\text{s}$ | $361.0\,\text{s} - 1373.0\,\text{s}$ | Coarse logging during relaxation ($\sim 20$ points over $2\,\text{hr}$) |
| **OCV 1-Hour Rest** | 4, 6, 8 | **$60.00\,\text{s}$** | $60.00\,\text{s}$ | $60.01\,\text{s}$ | $59.7\,\text{s} - 60.0\,\text{s}$ | Exactly 60 points per hour |

---

## 8. Temperature Variations & Capacity Measurements

### 8.1 Empirical Capacity Table Across Temperatures
Measured C/20 discharge capacity from OCV tests vs. delivered dynamic capacity in drive cycles:

| Temperature | Cell | $Q_{\text{OCV, C/20}}$ (Ah) | $Q_{\text{DST}}$ (Ah) | $Q_{\text{US06}}$ (Ah) | $Q_{\text{FUDS}}$ (Ah) | Ratio $\frac{Q_{\text{DST}}}{Q_{\text{OCV}}}$ | Mean Measured $T$ ($^\circ\text{C}$) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$-10^\circ\text{C}$** | `A1-007` | **1.0600** | 0.7351 | 0.7570 | 0.7712 | $69.3\%$ | $-10.6^\circ\text{C}$ |
| | `A1-008` | **1.0791** | 0.4366 | 0.5282 | 0.4075 | $40.5\%$ | $-10.4^\circ\text{C}$ |
| **$0^\circ\text{C}$** | `A1-007` | **1.0580** | 0.9420 | 0.9316 | 0.9531 | $89.0\%$ | $+0.2^\circ\text{C}$ |
| | `A1-008` | **1.0815** | 0.8968 | 0.9319 | 0.9528 | $82.9\%$ | $+0.5^\circ\text{C}$ |
| **$10^\circ\text{C}$** | `A1-007` | **1.0421** | 0.9928 | 0.9976 | 0.9814 | $95.3\%$ | $+10.5^\circ\text{C}$ |
| | `A1-008` | **1.0574** | 0.9954 | 1.0145 | 0.9819 | $94.1\%$ | $+10.9^\circ\text{C}$ |
| **$20^\circ\text{C}$** | `A1-007` | **1.0652** | 1.0289 | 1.0187 | 1.0222 | $96.6\%$ | $+21.5^\circ\text{C}$ |
| | `A1-008` | **1.0868** | 1.0441 | 1.0460 | 1.0491 | $96.1\%$ | $+21.7^\circ\text{C}$ |
| **$25^\circ\text{C}$** | `A1-007` | **1.0636** | 1.0356 | 1.0330 | 1.0361 | $97.4\%$ | $+26.6^\circ\text{C}$ |
| | `A1-008` | **1.0879** | 1.0441 | 1.0579 | 1.0576 | $96.0\%$ | $+26.5^\circ\text{C}$ |
| **$30^\circ\text{C}$** | `A1-007` | **1.0730** | 1.0418 | 1.0422 | 1.0403 | $97.1\%$ | $+30.6^\circ\text{C}$ |
| | `A1-008` | **1.0983** | 1.0610 | 1.0599 | 1.0649 | $96.6\%$ | $+30.8^\circ\text{C}$ |
| **$40^\circ\text{C}$** | `A1-007` | **1.0802** | 1.0542 | 1.0500 | 1.0576 | $97.6\%$ | $+40.5^\circ\text{C}$ |
| | `A1-008` | **1.1050** | 1.0842 | 1.0766 | 1.0770 | $98.1\%$ | $+40.7^\circ\text{C}$ |
| **$50^\circ\text{C}$** | `A1-007` | **1.0810** | 1.0554 | 1.0583 | 1.0586 | $97.6\%$ | $+50.8^\circ\text{C}$ |
| | `A1-008` | **1.1049** | 1.0827 | 1.0611 | 1.0866 | $98.0\%$ | $+51.0^\circ\text{C}$ |

### 8.2 Key Physical Insights
1. **Nominal vs. Measured Capacity:** Rated capacity is $1.11\,\text{Ah}$. Actual measured C/20 capacity ranges from $1.042\,\text{Ah}$ to $1.105\,\text{Ah}$ across temperatures.
2. **Cell Discrepancy:** Cell `A1-008` has consistently higher capacity ($\sim 20\,\text{mAh}$ higher) than `A1-007` at all temperatures. However, at $-10^\circ\text{C}$, `A1-008` suffered from acute polarization under dynamic currents, delivering only $40\%$ of C/20 capacity before hitting $2.0\,\text{V}$, compared to $69\%$ for `A1-007`.
3. **Dynamic Usable Capacity:** From $10^\circ\text{C}$ to $50^\circ\text{C}$, high dynamic currents extract $94\%$ to $98\%$ of C/20 capacity before hitting the lower voltage cutoff ($2.0\,\text{V}$).

---

## 9. Inconsistencies, Anomalies & Edge Cases

The comprehensive audit identified the following specific discrepancies between temperatures and files:

1. **The $20^\circ\text{C}$ Dynamic Rerun Anomaly:**
   - On 2012-08-09, the experimenters tested $20^\circ\text{C}$ using schedule `A1-FUDS-DST-US06-20120809.sdu`, running FUDS first. Files: `A1-007-DST-US06-FUDS-20-20120809.xls` and `A1-008-DST-US06-FUDS-20-20120809.xls` in legacy `.xls` format.
   - On 2012-08-17, they reran $20^\circ\text{C}$ using the standardized schedule `A1-DST-US06-FUDS-20120809.sdu` (running DST first, US06 second, FUDS third), saving as `...20120817.xlsx` and `...20120817-newprofile.xlsx`.
   - **Verification:** Inspection confirms `20120817.xlsx` and `20120817-newprofile.xlsx` contain 100% identical data rows ($24,304$ rows for `A1-007`, $24,992$ rows for `A1-008`). The canonical, consistent file to use for $20^\circ\text{C}$ is `20120817.xlsx`.
2. **$-10^\circ\text{C}$ Directory Naming:**
   - Dynamic directory is named `A123_DST-US06-FUDS-N10` (using `N10` rather than `-10`). OCV directory is named `A123_OCV-10-20120629`.
3. **$25^\circ\text{C}$ OCV Sheet Channel Inversion:**
   - In 7 of the 8 OCV folders, `A1-007` is on `Channel_1-005` and `A1-008` is on `Channel_1-006`.
   - In `A123_OCV25-20120905`, this is inverted: `A1-007` is on `Channel_1-006` and `A1-008` is on `Channel_1-005`.
4. **$10^\circ\text{C}$ OCV Test Interruption & Non-Monotonic Jump:**
   - In both `A1-007-OCV10-20120611.xlsx` and `A1-008-OCV10-20120611.xlsx`, a 6-hour test interruption occurred between 03:17:21 and 09:25:57 on 2012-06-12 at row 5449 during Step 5 (discharge branch).
   - `Test_Time(s)` jumped backwards by $94.4\,\text{s}$ ($30,576.6\,\text{s} \to 30,482.1\,\text{s}$), and open-circuit relaxation raised voltage by $+24.3\,\text{mV}$.
   - **Handling:** Loader must enforce strict timestamp monotonicity by adjusting or reconstructing cumulative test time using sampling intervals $\Delta t$.
5. **Temperature Channel Discrepancy:**
   - All 20 dynamic files and the $25^\circ\text{C}$ OCV file contain 1 temperature channel (`Temperature (C)_1`).
   - The other 14 OCV files contain 2 temperature channels (`Temperature (C)_1` and `Temperature (C)_2`).
6. **Auxiliary Sheets and Lock Files:**
   - `Channel_Chart` (chartsheet) and `Sheet1` / `Sheet2` (subsets) are present in some workbooks.
   - 3 Excel lock files (`~$*`) exist on disk.

---

## 10. Summary Verification Checklist

| Item | Status | Verification Detail |
| :--- | :---: | :--- |
| File formats | Verified | 34 `.xlsx` files, 2 `.xls` files (both at $20^\circ\text{C}$ 20120809). |
| Canonical sheet | Verified | Prefix `Channel_1-` identifies the sole complete data sheet in all 36 workbooks. |
| Columns & units | Verified | 18 columns (Set 1) or 19 columns (Set 2). Voltage in V, Current in A, Time in s. |
| Sampling interval | Verified | Median $1.0\,\text{s}$ for dynamic; $5.0\,\text{s}$ for OCV branches; $60.0\,\text{s}$ for OCV rests. |
| Sign convention | Verified | Raw is Arbin ($I > 0$ charge, $I < 0$ discharge). Must invert: $I_{\text{repo}} = -I_{\text{raw}}$. |
| Profile boundaries | Verified | Step 8 = DST, Step 16 = US06, Step 24 = FUDS across all temperatures. |
| Start SOC | Verified | Exactly $100\%$ SOC at start of Step 8, 16, and 24 following CC-CV saturation and rest. |
| Inconsistencies | Documented | $20^\circ\text{C}$ rerun, `N10` naming, $25^\circ\text{C}$ sheet swap, $10^\circ\text{C}$ 6-hr pause, lock files. |

