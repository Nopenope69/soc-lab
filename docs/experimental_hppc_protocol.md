# Experimental Test Protocol: Standardized HPPC Characterization for Physical Cells

**Document ID:** SOP-BMS-HPPC-2026-V1  
**Applies to:** Physical Lithium-Ion Cells (LFP, NMC, NCA)  
**Standard Compliance:** USABC Electric Vehicle Battery Test Procedures, IEC 62660-1, FreedomCAR Battery Test Manual

---

## 1. Objective and Scope

This standard operating protocol defines the reference measurement procedures required to generate physical ground-truth Resistance Health ($SOH_R$) and 2-RC Equivalent Circuit Model (ECM) validation data for physical battery cells.

Until data collected under this exact physical protocol is acquired, all resistance health estimations must be classified as **`PROVISIONALLY_QUALIFIED`** or **`UNVALIDATED`** in production BMS registries.

---

## 2. Hardware and Test Bench Requirements

1. **Battery Cycler:**
   - Multi-channel precision cycler (e.g. Arbin LBT, Maccor 4000, or BioLogic BCS-815).
   - Voltage measurement accuracy: $\le \pm 0.02\%$ F.S.
   - Current measurement accuracy: $\le \pm 0.05\%$ F.S.
   - 4-wire Kelvin sensing connected directly to cell terminal lugs.
   - Sampling rate: Synchronous $\ge 10\text{ Hz}$ ($dt \le 100\text{ ms}$) during pulses; $\ge 1\text{ Hz}$ during relaxation.

2. **Environmental Control:**
   - Thermal test chamber with forced-air convection.
   - Temperature stability: $\pm 0.5^\circ\text{C}$ across test duration.
   - Thermocouple attached directly to cell geometric center surface under thermal insulation patch.

---

## 3. Test Matrix and Environmental Conditioning

Every physical test specimen must undergo characterization at three standardized temperatures:
- **Cold Regime:** $15^\circ\text{C} \pm 0.5^\circ\text{C}$
- **Nominal Reference Regime:** $25^\circ\text{C} \pm 0.5^\circ\text{C}$
- **Elevated Regime:** $45^\circ\text{C} \pm 0.5^\circ\text{C}$

**Thermal Soak Rule:** A mandatory 2.0-hour open-circuit rest period must occur after chamber temperature transition before applying any electrical excitation.

---

## 4. Reference Pulse Profile Execution

At each designated SOC operating point ($80\%$, $50\%$, $20\%$ SOC):

```
       0 A |----- Rest (10s) -----|                               |----- Rest (40s) -----|
           |                      |                               |
-1.0C / -2.0C                     |__ 10s Discharge __|           |
                                                      |-- Rest ---|
+0.75C                                                (40s)       |-- 10s Regen --|
```

1. **Pre-Pulse Rest:** 10.0 seconds at $0\text{ A}$ to measure true $V_{\text{ocv}}(t_0)$.
2. **Discharge Pulse Step:**
   - Constant current discharge at $1.0\text{C}$ (and optional $2.0\text{C}$ rating test).
   - Pulse duration: Exactly $10.0\text{ s} \pm 0.01\text{ s}$.
   - Voltage must remain strictly above cell minimum cutoff voltage ($V_{\text{min}}$).
3. **Post-Pulse Relaxation:**
   - Zero current ($I = 0.000\text{ A}$) for $40.0\text{ s} \pm 0.05\text{ s}$.
   - Records exponential depolarization decay ($V_{p1}, V_{p2}$).
4. **Regeneration Charge Pulse:**
   - Constant current charge at $0.75\text{C}$ for $10.0\text{ s} \pm 0.01\text{ s}$.
5. **Post-Charge Relaxation:**
   - Zero current for $40.0\text{ s}$.

---

## 5. Mathematical Reference Formulas

### 5.1 10-Second Reference DCIR
$$\text{DCIR}_{10s}(\text{SOC}, T) = \frac{V_{\text{rest}}(t_0) - V(t_0 + 10\text{ s})}{|I_{\text{discharge}}|}$$

### 5.2 Ohmic (Instantaneous) Resistance
$$R_0(\text{SOC}, T) = \frac{V_{\text{rest}}(t_0) - V(t_0 + 100\text{ ms})}{|I_{\text{discharge}}|}$$

### 5.3 Physical SOH_R Ground Truth Definition
$$SOH_{R,\text{BOL}} = \frac{\text{DCIR}_{10s,\text{BOL}}(50\% \text{ SOC}, 25^\circ\text{C})}{\text{DCIR}_{10s,\text{current}}(50\% \text{ SOC}, 25^\circ\text{C})}$$

---

## 6. Aging Interval Schedule

- **BOL Reference (Cycle 0):** Full 3-temperature, 3-SOC characterization matrix.
- **Service Cycling:** Periodic RMP characterization conducted every **50 Equivalent Full Cycles (EFC)**.
- **EOL Qualification:** Continues until cell capacity degrades below $80.0\% \ SOH_C$ or DCIR doubles ($SOH_R \le 50.0\%$).

---

## 7. Synchronized Output Format

All data must be emitted in the `SynchronizedTelemetryRecord` format defined in `src/soh/data/synchronized_telemetry.py`.
