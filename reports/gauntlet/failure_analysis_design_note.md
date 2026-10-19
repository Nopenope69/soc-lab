# Technical Failure Analysis & Future Test Campaign Design Note
**Document:** Gauntlet Stage 2.5 Failure Analysis  
**Project:** CALCE A123 18650 LFP SOC Estimation Algorithm Development  
**Target Audience:** Battery Systems Engineering, Algorithms, and Test Commissioning Teams  
**Disposition:** NO-GO(estimator) — Algorithm Development Gate Failure at Stage 2.5  

---

## 1. Executive Failure Summary
The Gauntlet autonomous run terminated at **Stage 2.5** with a formal verdict of **NO-GO(estimator)**. The candidate algorithm (`E7`, composed of the tuned `E2` Extended Kalman Filter with temperature-scheduled hysteresis) satisfied the matched scenario requirement (Clause i) and fault injection robustness (Clause iii), but failed **GATE 2 Clause (ii)**:
- **Requirement:** Group-mean RMSE over S-B, S-C, S-D $\le 0.70 \times \text{E0 RMSE}$ **AND** individual case win rate against E0 $\ge 80.0\%$.
- **Observed:** Group-mean RMSE was $2.578\text{ pp}$ ($\le 4.365\text{ pp}$, passing the mean threshold at $41.3\%$ of E0), but the estimator beat pure Coulomb counting in only **$30 \text{ of } 38$ cases ($78.9\%$)**, falling short of the $80.0\%$ bar by exactly 1 case ($31/38 = 81.6\%$).
- **Optional E7b (Learned Residual):** Evaluated per protocol rules on DST at 20 & 30 °C and validated on held-out 40 & 50 °C. Although E7b raised individual wins to $32/38$ ($84.2\%$), it achieved only **$+8.35\%$ relative RMSE improvement** (peak $+15.53\%$ with extreme regularisation), failing the mandatory $\ge +20.0\%$ Keep Rule threshold. E7b was dropped, sealing the NO-GO finish.

---

## 2. Root Physical Diagnosis: Unobservability on the LFP Plateau

The failure is rooted in fundamental electrochemistry and observability, not software bug or implementation defect:

### A. The Null Space of Flat Two-Phase OCV
Between $10\%$ and $90\%$ SOC, the phase transition $\text{LiFePO}_4 \leftrightarrow \text{FePO}_4$ produces a virtually flat open-circuit voltage profile:
$$\frac{d\text{OCV}}{d\text{SOC}} \approx 174\text{ to } 178\text{ mV / unit SOC} \quad (1.74\text{ to } 1.78\text{ mV per percentage point of SOC})$$
For an initial SOC offset of $\Delta z = 5\text{ pp}$, the expected voltage innovation signal is:
$$\Delta V = \frac{d\text{OCV}}{d\text{SOC}} \cdot \Delta z \approx 8.7\text{ mV}$$
This $8.7\text{ mV}$ signal is of the same order of magnitude as:
1. Dynamic hysteresis amplitude $M(T) \approx 10\text{–}15\text{ mV}$.
2. Diffusion overpotentials across the RC networks ($V_{RC1} + V_{RC2} \sim 15\text{–}30\text{ mV}$).
3. Voltage measurement quantization and sensor thermal drift ($R_v \sim 0.5\text{–}1.0\text{ mV}$).

### B. Why Pure Coulomb Counting (E0) Prevailed in 8 of 38 Cases
In scenarios S-B (small initial offset, e.g. $\pm 5\text{ pp}$ starting at $40\%$ SOC) and S-D (unknown start after rest), the evaluation profile contains zero injected current bias. Pure Coulomb counting (E0) integrates current perfectly, maintaining a flat horizontal error profile equal to the initial offset throughout the mid-plateau window.
In contrast, an Extended Kalman Filter operating on the flat plateau receives tiny voltage innovations with high uncertainty. When thermal variations or unmodelled diffusion transients create minor voltage deviations, the filter gain applies small corrective nudges in the state space. Because the local gradient is near zero, these nudges cause random-walk drift in $\hat{z}$. Consequently, the filter's transient RMSE over short mid-plateau windows can exceed the static offset of pure Coulomb integration ($1.2\text{–}1.8\text{ pp}$ vs $1.0\text{–}1.5\text{ pp}$).

### C. Thermal Generalization Breakdown at Elevated Temperatures
On held-out selection temperatures ($40^\circ\text{C}$ and $50^\circ\text{C}$), internal cell resistance decreases, further compressing the voltage excitation envelope. Furthermore, cell-to-cell transfer evaluation on cell `A1-008` revealed catastrophic divergence at $50^\circ\text{C}$:
- A1-007 (50 °C DST): S-A RMSE = $1.075\text{ pp}$, BCD Mean = $2.901\text{ pp}$.
- A1-008 (50 °C DST): S-A RMSE = $6.488\text{ pp}$, BCD Mean = $13.447\text{ pp}$ (Worst fault error = $24.785\text{ pp}$).
This divergence indicates that at elevated temperatures, subtle manufacturing differences in capacity degradation and SEI resistance create severe model mismatch that static parameter scheduling cannot accommodate.

---

## 3. Specifications for the Next Test Campaign

To overcome the plateau unobservability barrier and develop a deployable LFP SOC estimator, the next testing campaign must provide data that current CALCE tests lack:

### 1. Multi-Branch Dynamic Hysteresis Characterisation
- **Current Limitation:** CALCE data only provides C/20 quasi-static curves and single-rate DST/FUDS/US06 pulses. Dynamic hysteresis relaxation rates ($\gamma$) were mathematically unidentifiable.
- **Required Test:** Symmetric charge/discharge partial cycles with variable rest periods ($15\text{ min}$, $1\text{ h}$, $4\text{ h}$, $24\text{ h}$) across the $20\%\text{–}80\%$ plateau to decouple true equilibrium thermodynamic potential from kinetic relaxation.

### 2. Multi-Frequency Electrochemical Impedance Spectroscopy (EIS)
- **Current Limitation:** ECM parameters $R_0, R_1, C_1, R_2, C_2$ were fitted to time-domain pulses, confounding bulk electrolyte resistance with double-layer capacitance and solid-state diffusion.
- **Required Test:** In-operando EIS sweeps ($10\text{ kHz}$ to $1\text{ mHz}$) across SOC grid points ($5\%$ intervals) and temperatures ($10, 20, 30, 40, 50^\circ\text{C}$) under both charge and discharge currents.

### 3. Deliberate Knee-Observability Cycle Profiles
- **Current Limitation:** Operational BESS cycling often remains trapped within the $20\%\text{–}80\%$ plateau for days, where voltage feedback is unobservable.
- **Required Protocol:** Design BMS operational profiles that periodically visit the lower knee ($<15\%$ SOC) or upper knee ($>85\%$ SOC) where $|d\text{OCV}/d\text{SOC}| > 15\text{ mV / pp}$. In these steep zones, Kalman gain increases by $10\times$, rapidly collapsing accumulated Coulomb counting drift.

### 4. Fleet-Level Multi-Cell Aging Matrix
- **Current Limitation:** CALCE data contains only fresh cells A1-007 and A1-008.
- **Required Test:** A multi-cell fleet matrix ($n \ge 12$ cells) aged under differential thermal and C-rate stress to parameterize co-estimation of state of health ($\text{SOH}$) and effective capacity $Q(T, \text{aging})$. Without continuous online capacity adaptation, LFP SOC algorithms cannot maintain $<3\text{ pp}$ accuracy across cell lifetime.

---
*Authored autonomously during CALCE A123 Gauntlet Stage 2.5.*
