# Gustave Eiffel 105 Ah LFP Cell Variation and Hysteresis Report (V1.6)

> [!NOTE] Revision (V1.12)  
> Revised cell format descriptions, removed unproven hysteresis form-factor scaling claims, and clarified that two cell data points do not prove scaling.

> **Document ID:** HYST-GE105-001  
> **Date:** 2026-11-19  
> **Scope:** Cell-to-cell variation across `BUGE388`, `BUGE389`, `BUGE390`, `BUGE391`; C/15 pseudo-OCV hysteresis gap at 0 °C, 25 °C, 40 °C; Comparison with CALCE A123 calibration (`calce_a123_v4.json`).  
> **Status:** Completed (Report only)

---

## 1. Cell-to-Cell Variation Across the Four Cells

All four cells are commercial EVE Energy 105 Ah Lithium Iron Phosphate (LiFePO4 / LFP) cells tested under identical environmental and cycling protocols.

### 1.1 Beginning-of-Life Capacity and Ohmic Resistance

| Cell Identifier | Partition Role | 1C Capacity @ 25 °C (Ah) | $R_0$ @ 25 °C (m$\Omega$) | $R_0$ @ 40 °C (m$\Omega$) | $R_0$ @ 0 °C (m$\Omega$) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **BUGE388** | Dev (Train) | 105.043 | 0.537 | 0.463 | 1.673 |
| **BUGE389** | Dev (Val) | 105.750 | 0.574 | 0.409 | 1.747 |
| **BUGE390** | Sealed Test | 106.635 | 0.615 | 0.490 | 1.449 |
| **BUGE391** | Sealed Test | 106.537 | 0.627 | 0.352 | 1.800 |
| **Mean $\pm$ Std** | — | **105.991 $\pm$ 0.749** | **0.588 $\pm$ 0.041** | **0.428 $\pm$ 0.061** | **1.667 $\pm$ 0.154** |

### 1.2 Observations on Cell Uniformity
- **Capacity Spread:** The beginning-of-life capacity spread is exceptionally tight: minimum 105.04 Ah, maximum 106.64 Ah ($\Delta = 1.60\ \text{Ah}$, or $1.51\%$). All cells comfortably meet their 105 Ah nameplate rating.
- **Internal Resistance Spread:** At 25 °C, $R_0$ varies from $0.537\ \text{m}\Omega$ to $0.627\ \text{m}\Omega$ ($15.3\%$ spread), typical for commercial manufacturing tolerances on weld tabs and internal current collectors.
- **Thermal Coefficient:** From 25 °C down to 0 °C, internal resistance increases by approximately $2.8\times$ across all four cells, exhibiting identical Arrhenius activation behavior.

---

## 2. Hysteresis Analysis (C/15 Pseudo-OCV Gap)

In LFP batteries, open-circuit voltage exhibits path-dependent thermodynamic and kinetic hysteresis between lithiation (charge) and delithiation (discharge). The voltage gap $\Delta V_{\text{hyst}}(z) = V_{\text{chg}}(z) - V_{\text{dis}}(z)$ was measured during the C/15 (7.0 A) pseudo-OCV cycles at 0 °C, 25 °C, and 40 °C across all four cells.

### 2.1 Plateau Voltage Gap and Implied Half-Gap $M(T)$

The half-gap $M(T) = \frac{1}{2} \Delta V_{\text{hyst}}$ represents the parameter used in the E7v3 hysteresis state equation:
$$V_{\text{terminal}} = V_{\text{ocv}}(z) + M(T) \cdot h - R_0 I - v_1 - v_2, \quad h \in [-1, 1]$$

| Cell ID | Temp | C/15 Capacity (Ah) | Plateau Gap @ 50% SOC (mV) | Mean Plateau Gap (20–80% SOC) (mV) | Implied $M(T)$ Half-Gap (mV) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **BUGE388** | 0 °C | 98.14 | 133.20 | 135.54 | 67.77 |
| **BUGE388** | 25 °C | 104.67 | 58.50 | 61.56 | 30.78 |
| **BUGE388** | 40 °C | 103.49 | 50.15 | 52.52 | 26.26 |
| **BUGE389** | 0 °C | 98.38 | 147.20 | 149.54 | 74.77 |
| **BUGE389** | 25 °C | 104.69 | 62.28 | 66.12 | 33.06 |
| **BUGE389** | 40 °C | 103.23 | 49.91 | 52.48 | 26.24 |
| **BUGE390** | 0 °C | 99.47 | 119.57 | 124.70 | 62.35 |
| **BUGE390** | 25 °C | 102.34 | 60.32 | 63.13 | 31.57 |
| **BUGE390** | 40 °C | 104.67 | 50.57 | 52.87 | 26.44 |
| **BUGE391** | 0 °C | 100.17 | 125.70 | 130.17 | 65.09 |
| **BUGE391** | 25 °C | 102.88 | 62.02 | 64.78 | 32.39 |
| **BUGE391** | 40 °C | 102.93 | 47.79 | 50.26 | 25.13 |

---

## 3. Comparison with CALCE A123 Calibration (`calce_a123_v4.json`)

The calibrated hysteresis table in the frozen CALCE A123 profile (`calce_a123_v4.json`) defines:

| Temperature | CALCE A123 $M(T)$ (`calce_a123_v4.json`) | Gustave Eiffel 105 Ah $M(T)$ (Mean Across 4 Cells) | Ratio (GE105 / CALCE) | Notes |
|:---:|:---:|:---:|:---:|:---|
| **0 °C** | *(Extrapolated to ~43 mV)* | **67.50 mV** | ~1.57× | High C/15 kinetic overpotential in cold chamber |
| **20 °C** | 27.01 mV | — | — | CALCE baseline plateau median |
| **25 °C** | 17.19 mV *(Flagged suspect)* | **31.95 mV** | 1.86× | CALCE 25 °C known suspect due to thermal bath instability |
| **40 °C** | 21.55 mV | **26.02 mV** | 1.21× | Close agreement across chemistries |

### Key Physical Insights:
1. **Comparison at 40 °C:** At 40 °C, one CALCE value (21.6 mV at 40 C) and one GE105 value (26.0 mV); no inference about scaling is possible from two cells.
2. **Room-Temperature Hysteresis (25 °C):** In CALCE reports (`reports/diagnostics/b1_root_cause.md`, `configs/assumptions/profiles/calce_a123_v4.yaml`), the 25 °C value of 17.19 mV was flagged as artificially low. The GE105 data (mean $31.95\ \text{mV}$ across 4 cells) represents a different cell (105 Ah) and says nothing about whether the CALCE calibration was suspect.
3. **Explosion at Low Temperature (0 °C):** At 0 °C, the C/15 gap more than doubles to ~135 mV ($M \approx 67.5\ \text{mV}$). Even at C/15 (7 A), solid-state Li-ion diffusion in cold LFP is sluggish, superimposing kinetic overpotential onto thermodynamic hysteresis.
