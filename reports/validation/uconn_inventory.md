# UConn REIL Dataset 5: Inventory and RPT Structure Audit

**Date:** 2026-11-19  
**Dataset:** UConn-ISU-ILCC LFP/Gr Battery Aging Dataset (Dataset 5)  
**Citation:** Nowacki et al., *Journal of Power Sources*, 628 (2025) 235813. DOI: [10.1016/j.jpowsour.2024.235813](https://doi.org/10.1016/j.jpowsour.2024.235813)  
**Licence:** Creative Commons Attribution 4.0 International (CC BY 4.0)  
**Archive:** `$SOC_DATA_DIR/uconn_reil/rpt_data.zip` (verified manifest hash in `scripts/verify_datasets.py`)  
**Working Directory:** `$SOC_DATA_DIR/uconn_reil/extracted/rpt_data/` (207 CSV files)  

---

## 1. Executive Summary

- **Total Cells:** 64 cells (numbered `02` through `65`).
- **Cell Model:** LithiumWerks 18650 power cells (APR18650M1B), nominal capacity 1.2 Ah, LFP/graphite chemistry.
- **Aging Target:** Cycled until ~80% State of Health (SOH), approximately 0.96 Ah.
- **RPT Availability:** All 64 cells have a valid, usable first Reference Performance Test (`RPT Number == 0`).
- **Initial Reference Capacity ($C_0$):** Mean 1.2134 Ah (min 1.2046 Ah, max 1.2228 Ah).
- **Final Capacity & Degradation:** Mean final $SOH_C = 0.7791$ (min 0.7234, max 0.7918). RPT count per cell ranges from 22 to 77 (mean 44.6).
- **Usable First RPT Count:** 64 of 64 cells usable (stop condition requirement: $\ge 8$ cells; satisfied).

---

## 2. Cell and Condition Group Breakdown

The dataset comprises 11 distinct cycling condition groups. Groups 1–10 contain 6 cells each; Group 11 contains 4 cells:

| Condition Group | Cell Range | Cell Count | RPT Count (Min / Mean / Max) | Mean Initial $C_0$ (Ah) | Final $SOH_C$ (Min / Mean / Max) |
|---|---|---|---|---|---|
| **Group 1** | Cell 02 – 07 | 6 | 30 / 36.2 / 42 | 1.2136 | 0.7707 / 0.7823 / 0.7909 |
| **Group 2** | Cell 08 – 13 | 6 | 36 / 42.2 / 53 | 1.2131 | 0.7786 / 0.7846 / 0.7881 |
| **Group 3** | Cell 14 – 19 | 6 | 22 / 22.5 / 23 | 1.2144 | 0.7234 / 0.7519 / 0.7746 |
| **Group 4** | Cell 20 – 25 | 6 | 53 / 61.2 / 68 | 1.2147 | 0.7765 / 0.7808 / 0.7877 |
| **Group 5** | Cell 26 – 31 | 6 | 52 / 58.8 / 71 | 1.2143 | 0.7820 / 0.7870 / 0.7904 |
| **Group 6** | Cell 32 – 37 | 6 | 23 / 26.2 / 28 | 1.2142 | 0.7648 / 0.7748 / 0.7821 |
| **Group 7** | Cell 38 – 43 | 6 | 44 / 46.7 / 51 | 1.2156 | 0.7673 / 0.7764 / 0.7839 |
| **Group 8** | Cell 44 – 49 | 6 | 28 / 31.3 / 37 | 1.2126 | 0.7541 / 0.7753 / 0.7907 |
| **Group 9** | Cell 50 – 55 | 6 | 56 / 57.3 / 58 | 1.2125 | 0.7825 / 0.7869 / 0.7916 |
| **Group 10** | Cell 56 – 61 | 6 | 66 / 71.5 / 77 | 1.2119 | 0.7815 / 0.7869 / 0.7911 |
| **Group 11** | Cell 62 – 65 | 4 | 30 / 33.0 / 35 | 1.2097 | 0.7781 / 0.7848 / 0.7918 |
| **Overall** | **Cell 02 – 65** | **64** | **22 / 44.6 / 77** | **1.2134** | **0.7234 / 0.7791 / 0.7918** |

*Note on cycling parameters: The cycling parameters (exact DOD, charge/discharge C-rates per group) were detailed in `cycling_parameters.csv` which belongs to the un-downloaded cycling archives. Group trajectories and cell mappings are verified directly from cell numbers and RPT files.*

---

## 3. RPT Structure and Pulse Protocols

Each RPT consists of up to 61 steps encompassing capacity calibration, internal resistance pulse tests at multiple states of charge, and relaxation periods.

### 3.1 Pulse Definitions (`slowpulse`)

The primary reference pulses for resistance estimation are 100-second sequences applied at three nominal states of charge: 20%, 50%, and 90% SOC.

For each SOC level, the protocol executes:
1. **Charge Pulse (100 s total):**
   - **Step A (30 s):** Constant current charge at C/5 ($+0.24\ \text{A}$).
   - **Step B (10 s):** Constant current charge at 1C ($+1.20\ \text{A}$).
   - **Step C (60 s):** Rest relaxation at zero current ($0.00\ \text{A}$).
2. **Discharge Pulse (100 s total):**
   - **Step D (30 s):** Constant current discharge at C/5 ($-0.24\ \text{A}$).
   - **Step E (10 s):** Constant current discharge at 1C ($-1.20\ \text{A}$).
   - **Step F (60 s):** Rest relaxation at zero current ($0.00\ \text{A}$).

**Step Numbers in RPT 0:**
- **20% SOC:** Steps 4–6 (Charge), Steps 7–9 (Discharge).
- **50% SOC:** Steps 12–14 (Charge), Steps 15–17 (Discharge).
- **90% SOC:** Steps 20–22 (Charge), Steps 23–25 (Discharge).

### 3.2 Reference Discharge Capacity (`ref_dchg`)

- **Step Number:** Step 28
- **Protocol:** Constant current discharge at C/3 ($-0.40\ \text{A}$) from full charge (~3.42 V) down to cutoff voltage 2.00 V.
- **Duration:** $\approx 10,919\ \text{s}$ ($\approx 3.03\ \text{hours}$).
- **Capacity Logging:** The column `Capacity (Ah)` resets to 0.0 at the beginning of Step 28 and accumulates positively up to the full discharged capacity (e.g., 1.2126 Ah on Cell 02 RPT 0).

### 3.3 Fast and Ultra-Fast Pulses

- **Fast Pulse (`fastpulse`):** Steps 32–37 (Charge) and Steps 42–47 (Discharge) at 90% SOC.
- **Ultra-Fast Pulse (`ultrafastpulse`):** Steps 51–53 (Charge) and Steps 57–59 (Discharge) at 90% SOC.

---

## 4. Sampling, Units, and Sign Conventions

| Field | Units | Description / Values |
|---|---|---|
| `Time (s)` | Seconds (s) | Sampling interval $\Delta t = 1.0\ \text{s}$ during pulses and rest; $\Delta t = 0.1\ \text{s}$ during step transitions and voltage cutoffs. |
| `Voltage (V)` | Volts (V) | Terminal voltage. Operational range: 2.00 V (discharge cutoff) to 3.60 V (charge cutoff). |
| `Current (A)` | Amperes (A) | Raw file sign convention: **Charge is positive ($I > 0$), Discharge is negative ($I < 0$)**. |
| `Capacity (Ah)` | Ampere-hours (Ah) | Cumulative capacity per step/protocol. Integrates positively during discharge. |
| `Pulse SOC` | % | Nominal target SOC: `20.0`, `50.0`, `90.0` (subject to slight drift with cycling aging, as noted in Nowacki et al.). |
| `Step Number` | Integer | Protocol step identifier (1 to 61). |
| `Segment Key` | String | Region identifier: `ref_chg`, `ref_dchg`, `slowpulse`, `fastpulse`, `ultrafastpulse`, or `-`. |
| `Pulse Type` | String | Direction: `chg`, `dchg`, or `-`. |
| `State` | String | Operating state: `CC Chg`, `CC DChg`, `CCCV Chg`, `Rest`. |

### Sign Convention Canonicalization

- **Raw File:** Charge $> 0$, Discharge $< 0$.
- **Repo Standard (`src/soc/`):** Discharge is positive ($I_{\text{repo}} > 0$), Charge is negative ($I_{\text{repo}} < 0$).
- **Conversion Rule:**
  $$I_{\text{repo}} = -I_{\text{raw}}$$
  The data loader must invert the current sign so that positive current represents discharge throughout the codebase.

---

## 5. Missing Data and Sequence Anomalies

1. **RPT Contiguity:**
   - 63 of 64 cells exhibit strictly contiguous RPT numbering ($0, 1, 2, \dots, N$).
   - **Cell 60 (Group 10):** Contains 77 RPTs spanning index 0 through 77, but RPT 76 is missing from the raw record. RPTs 0–75 and 77 are present.
2. **Missing First RPTs:**
   - Exactly **0 cells** lack an initial RPT (`RPT Number == 0`).
   - All 64 cells have a complete initial `ref_dchg` measuring $C_0$ and complete 100 s pulse sequences at 20%, 50%, and 90% SOC.
3. **Corrupted or Temporary Files:**
   - No temporary or lock files (`~$*`, `._*`) found in the extracted directory.
   - All 207 CSV files loaded without parse errors.
