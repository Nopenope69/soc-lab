# FlexiPod-1 Assumption Register

**Status**: UNCONFIRMED (All items marked `[ASSUMPTION]` pending explicit human confirmation)  
**Date**: 2026-10-20  
**Repository**: `/Users/tecbusiness/Desktop/random/SOC`  
**Datasets**: `data/raw/flexipod/OCV_and_HPPC_data_of_cells.xlsx`, `data/raw/flexipod/Temperature_based_V_curves.xlsx`  

---

## Registered Assumptions

### [ASSUMPTION A1]: Cell Capacity Class in `Temperature_based_V_curves.xlsx`
- **Description**: The 100 A and 150 A constant-current discharge curves in `Temperature_based_V_curves.xlsx` belong to a **100 Ah-class** cell (observed delivered end capacities range from 86.35 Ah to 95.15 Ah; current accumulation rate is $0.0277\text{ Ah/s}$ at 100 A, matching $100\text{ A} / 3600\text{ s}$), and NOT the 206 Ah cell named on the workbook's `IR vs T (206Ah)` sheet.
- **OCV Baseline Selection**: Use `Ganfeng_100Ah` OCV averaged across Cells 1, 2, and 3 as the primary open-circuit voltage model.
- **Sensitivity Requirement**: Run a secondary sensitivity evaluation using `Ganfeng_206Ah` OCV and report the exact voltage and SOC difference across the SOC range.
- **Status**: `[ASSUMPTION - PENDING HUMAN CONFIRMATION]`

---

### [ASSUMPTION A2]: Start SOC and Ground Truth Trajectory Formulation
- **Description**: Each constant-current discharge curve begins from a fully charged state ($100\%\text{ SOC}$) at rest following a CC-CV charge.
- **Ground Truth Formulation**:
  $$\text{SOC}_{\text{truth}}(t) = 1.0 - \frac{\text{Capacity}_{\text{Ah}}(t)}{Q_{\text{end}}(T, I)}$$
  where $Q_{\text{end}}(T, I)$ is the total delivered capacity up to the terminal $2.5\text{ V}$ cutoff at that specific temperature $T$ and discharge current $I$ (representing total usable capacity under that rate and thermal condition, rather than a quasi-equilibrium $C/20$ capacity).
- **Caveat**: Flag that this ground truth definition carries an unknown start SOC uncertainty resulting from unrecorded relaxation duration, temperature soak, and CV-taper termination conditions.
- **Status**: `[ASSUMPTION - PENDING HUMAN CONFIRMATION]`

---

### [ASSUMPTION A3]: Current Sign Convention
- **Description**: Discharge currents in raw workbook sheets are recorded with a negative sign (e.g. $-99.85\text{ A}$, $-149.85\text{ A}$).
- **Repository Convention**: Positive current indicates discharge ($I > 0$), negative current indicates charge ($I < 0$).
- **Transformation**: Apply $I_{\text{repo}} = -I_{\text{file}}$ once at data ingestion.
- **Verification**: Verify and print the sign and magnitude of the mean current after loading to confirm positive discharge sign.
- **Status**: `[ASSUMPTION - PENDING HUMAN CONFIRMATION]`

---

### [ASSUMPTION A4]: OCV Test Temperature and Quasi-Equilibrium
- **Description**: The charge and discharge OCV branches in `OCV_and_HPPC_data_of_cells.xlsx` are quasi-equilibrium measurements, but the test C-rate is not documented in the sheets. Furthermore, the test ambient temperature is unrecorded.
- **Assumed Temperature**: Ambient temperature is assumed to be nominal room temperature ($25\text{ }^\circ\text{C}$).
- **Thermal Invariance Limit**: Because OCV data exists at only this single undocumented temperature, the identified symmetric-mean OCV curve $\text{OCV}(z)$ is applied across all temperatures ($5, 10, 15, 20\text{ }^\circ\text{C}$) without temperature-dependent shift. This physical limitation is formally recorded.
- **Status**: `[ASSUMPTION - PENDING HUMAN CONFIRMATION]`

---

### [ASSUMPTION A5]: Ganfeng 100Ah Voltage Curves Role
- **Description**: The `Ganfeng_100Ah_Voltagecurves` sheet in `OCV_and_HPPC_data_of_cells.xlsx` contains a single 150 A discharge curve without specified temperature.
- **Usage Scope**: This sheet is used strictly for an auxiliary rate-check comparison and is excluded from temperature-dependent parameter identification.
- **Status**: `[ASSUMPTION - PENDING HUMAN CONFIRMATION]`
