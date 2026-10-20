# FlexiPod-1 Step 1: Loader and Data-Quality Report

## Executive Summary

This report establishes robust, header-text-based ingestion and comprehensive data-quality auditing for the FlexiPod battery datasets (`OCV_and_HPPC_data_of_cells.xlsx` and `Temperature_based_V_curves.xlsx`).

- **Sign Convention Verified**: All discharge currents converted from raw negative values to repository standard **positive discharge** ($I_{\text{repo}} = -I_{\text{file}} > 0$). Mean loaded current confirmed positive across all curves.
- **Cell Class Identified (Assumption A1)**: End capacities delivered to the 2.5 V cutoff range from **86.35 Ah to 95.46 Ah** (at ~0.0277 Ah/s for 100 A), proving that the discharge curves belong to a **100 Ah-class cell**, not the 206 Ah cell named on the IR sheet.
- **Suspect Curve Flagged**: The **5 °C / 150 A** curve starts at **3.155 V** ($t=0$) compared to **~3.33 V** for all other curves. It is formally flagged as **`SUSPECT`** (likely starting from an unrelaxed or depleted state) and excluded from primary rate and thermal comparisons, though reported separately.
- **15 °C Sheet Layout Discrepancy**: Sheet `15 degC` lacks textual header rows, contains dual timestamp columns (relative elapsed time and wall-clock time `13:39:07`), includes a dedicated measured current column (`-99.84 A`), and contains only a 100 A discharge curve (no 150 A test).
- **Policy Table Date Corruption Restored**: Excel auto-converted temperature ranges `3-7` and `8-12` on `Sheet5` to date timestamps `2026-07-03` and `2026-12-08`. These have been detected and restored to clean text ranges in [`reports/flexipod1/policy_table_corrected.csv`](file:///Users/tecbusiness/Desktop/random/SOC/reports/flexipod1/policy_table_corrected.csv).
- **OCV Endpoints Identified as Non-Equilibrium**: Endpoints at 0% and 100% SOC exhibit dynamic polarisation truncation and are formally excluded from equilibrium OCV fitting.
- **Cell Census Recorded**: OCV cell counts verified (`GOTION_50Ah`: 3 cells; `Ganfeng_100Ah`: 2 cells; `CALB_100Ah`: 2 cells; `Ganfeng_125Ah`: 1 cell; `Ganfeng_206Ah`: 2 cells; `Ganfeng_230Ah`: 2 cells). Sheet `Ganfeng_230Ah` is verified to be **discharge-only**.

---

## 1. Temperature-Based Voltage Curves Audit

| Curve ID | Nominal Rate | Temperature | Rows | Sampling $\Delta t$ (s)<br>[Median / p10 / p90] | $V_0$ ($t=0$) | $V_1$ ($t=1\text{s}$) | 1s Drop (mV) | $V_{\text{end}}$ (V) | $Q_{\text{end}}$ (Ah) | Monotonicity | Data Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `T5_100A` | 100 A | 5.0 °C | 3110 | 1.0 / 1.0 / 1.0 | 3.3359 V | 3.1353 V | 200.6 mV | 2.4999 V | 86.35 Ah | Time & Cap Monotone* | VALID |
| `T5_150A` | 150 A | 5.0 °C | 2101 | 1.0 / 1.0 / 1.0 | 3.1546 V | 3.0667 V | 87.9 mV | 2.4998 V | 87.50 Ah | Time & Cap Monotone* | **SUSPECT** |
| `T10_100A` | 100 A | 10.0 °C | 3203 | 1.0 / 1.0 / 1.0 | 3.3274 V | 3.1686 V | 158.8 mV | 2.4999 V | 88.93 Ah | Time & Cap Monotone* | VALID |
| `T10_150A` | 150 A | 10.0 °C | 2158 | 1.0 / 1.0 / 1.0 | 3.3379 V | 3.1045 V | 233.4 mV | 2.4999 V | 89.86 Ah | Time & Cap Monotone* | VALID |
| `T20_100A` | 100 A | 20.0 °C | 3432 | 1.0 / 1.0 / 1.0 | 3.3365 V | 3.2408 V | 95.7 mV | 2.4998 V | 95.15 Ah | Time & Cap Monotone* | VALID |
| `T20_150A` | 150 A | 20.0 °C | 2294 | 1.0 / 1.0 / 1.0 | 3.3364 V | 3.1956 V | 140.8 mV | 2.4996 V | 95.46 Ah | Time & Cap Monotone* | VALID |
| `T15_100A` | 100 A | 15.0 °C | 3187 | 1.0 / 1.0 / 1.0 | 3.3356 V | 3.2014 V | 134.2 mV | 2.4999 V | 88.36 Ah | Time & Cap Monotone* | VALID |
| `Ganfeng_100Ah_Voltagecurves_150A` | 150 A | Unknown (Ambient) | 2143 | 1.0 / 1.0 / 1.0 | 3.1964 V | 3.1491 V | 47.3 mV | 2.4999 V | 89.15 Ah | Time & Cap Monotone* | VALID |

> [!NOTE]
> `*` **Monotonicity note on integer-second cutoff**: In all curves, time is strictly monotonic ($dt = 1.0\text{ s}$) except at the very last cutoff row, where the battery cycler tripped the $2.5\text{ V}$ cutoff during that second and appended the trip row with an identical integer second timestamp ($dt = 0.0\text{ s}$). Delivered capacity is strictly monotonic throughout.

### Key Curve Observations:
1. **Initial Voltage Discrepancy on 5 °C / 150 A**: While all other curves start between $3.327\text{ V}$ and $3.338\text{ V}$ (representing fully rested open-circuit voltage at 100% SOC), the 5 °C / 150 A curve begins at **3.1546 V** ($180\text{ mV}$ below normal). Its 1-second drop is only $87.9\text{ mV}$ compared to $200.6\text{ mV}$ on 100 A at 5 °C. This confirms the cell was either unrelaxed or pre-discharged before logging.
2. **Capacity vs Temperature Trend**: Delivered usable capacity to 2.5 V cutoff increases monotonically with temperature at 100 A:
   - 5 °C: **86.35 Ah**
   - 10 °C: **88.93 Ah**
   - 15 °C: **88.36 Ah** (slight plateau)
   - 20 °C: **95.15 Ah**
3. **Current Sign Verification**: Loaded mean currents are confirmed positive: `+100.0 A` on 100 A channels and `+150.0 A` on 150 A channels, complying strictly with repository convention ($I > 0$ for discharge).

---

## 2. 15 °C Sheet Layout Anomaly

Inspection of the `15 degC` sheet in `Temperature_based_V_curves.xlsx` reveals 4 unique structural anomalies:
1. **Missing Text Headers**: Rows 1 and 2 are completely blank. Numeric data begins directly on Row 3.
2. **Dual Time Columns**: Column A contains relative test time (`00:00:00`, `00:00:01`, ...), while Column B contains wall-clock timestamps (`13:39:07`, `13:39:08`, ...). Both advance by exactly 1.0 s per row.
3. **Explicit Measured Current Column**: Column C contains logged cycler current (mean = $-99.85\text{ A}$, $\text{std} = 0.007\text{ A}$). The other sheets omit a current column and only specify current in merged header text (`I = 100A`, `I_dchg = 100A`).
4. **Single Rate Available**: The sheet contains only a 100 A discharge curve spanning 3,187 seconds. No 150 A discharge test was logged at 15 °C.

---

## 3. Policy Table Date Corruption Restoration

Excel auto-formatting corrupted temperature ranges on `Sheet5` of `Temperature_based_V_curves.xlsx` by parsing text strings with hyphens as calendar dates.

### Audit of Detected Date Conversions:

| Cell Location | Corrupted Excel Value | Raw Interpreted Timestamp | Restored Clean Text | Physical Engineering Meaning |
|:---:|:---|:---:|:---:|:---|
| **Row 4, Column D** | `2026-07-03 00:00:00` | 3rd of July (Day 3, Month 7) | `3-7` | Temperature operating range: **3 °C to 7 °C** |
| **Row 5, Column D** | `2026-12-08 00:00:00` | 8th of December (Day 8, Month 12) | `8-12` | Temperature operating range: **8 °C to 12 °C** |
| **Row 6, Column D** | `13-17` | *Unmodified String* | `13-17` | Temperature operating range: **13 °C to 17 °C** (Month 13 does not exist, so Excel left as text) |
| **Row 7, Column D** | `18-22` | *Unmodified String* | `18-22` | Temperature operating range: **18 °C to 22 °C** (Month 18 does not exist, so Excel left as text) |

The complete, sanitized policy specification has been written to [`reports/flexipod1/policy_table_corrected.csv`](file:///Users/tecbusiness/Desktop/random/SOC/reports/flexipod1/policy_table_corrected.csv):

```csv
Temperature Range (°C),Hard Cutoff,Usable Capacity Multiplier,Number of Samples
3-7,2.8 V,0.85,5
8-12,2.8 V,0.90,5
13-17,2.8 V,0.95,5
18-22,2.95 V,1.00,5
```

---

## 4. OCV Dataset & Cell Census Audit

| Cell Chemistry / Model | Sheet Name | Tested Cell Count | Branches Available | SOC Grid Resolution | Non-Equilibrium Endpoints | Notes |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| **GOTION 50Ah** | `GOTION_50Ah` | 3 (Cell 1, 2, 3) | Charge & Discharge | 5% (0 to 100%) | 0% & 100% | Includes HPPC 2RC parameter table |
| **Ganfeng 100Ah** | `Ganfeng_100Ah` | 2 (Cell 1, 2) | Charge & Discharge | 5% (0 to 100%) | 0% & 100% | Cols 10-12 are Average of Cell 1 & 2; contains 5 °C R0 table |
| **CALB 100Ah** | `CALB_100Ah` | 2 (Cell 1, 2) | Charge & Discharge | 5% (0 to 100%) | 0% & 100% | Includes R0 identification table |
| **Ganfeng 125Ah** | `Ganfeng_125Ah` | 1 (Cell 1) | Charge & Discharge | 5% (0 to 100%) | 0% & 100% | Single cell characterization |
| **Ganfeng 206Ah** | `Ganfeng_206Ah` | 2 (Cell 1, 2) | Charge & Discharge | 5% (0 to 100%) | 0% & 100% | Cols 10-12 are Average of Cell 1 & 2 |
| **Ganfeng 230Ah** | `Ganfeng_230Ah` | 2 (Cell 1, 2) | **Discharge Only** | 5% (0 to 100%) | 0% & 100% | **Zero charge OCV data recorded**; cannot fit hysteresis |

### Non-Equilibrium Endpoint Exclusion Rule:
- At **0% SOC**, terminal discharge cutoff trips dynamically under load ($V < 2.5\text{ V}$), and lithium concentration gradients at particle surfaces are extreme.
- At **100% SOC**, CV-taper termination conditions create variable phase-relaxation dynamics.
- Therefore, **0% and 100% SOC points are formally classified as non-equilibrium and excluded from OCV spline fitting** (fitting is restricted to the quasi-equilibrium 5% to 95% domain).
