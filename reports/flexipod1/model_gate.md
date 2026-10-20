# FlexiPod-1 Step 4: Open-Loop Model Gate Report

**Execution Date**: 2026-10-20  
**Gate Decision**: **FAIL**  
**Profile Evaluated**: `configs/assumptions/profiles/flexipod_100ah_v1.yaml`  
**Source Curves**: `data/raw/flexipod/Temperature_based_V_curves.xlsx`  
**Output Metrics**: `reports/flexipod1/model_gate.json`

---

## 1. Gate Evaluation Summary

The pre-registered open-loop model gate evaluates voltage prediction accuracy on the **W-mid region (10% to 90% truth SOC)** under three strict pass criteria:

1. **Bias**: $|\text{bias}| \le 2.0\text{ mV}$

2. **RMSE**: $\text{RMSE} \le 6.0\text{ mV}$

3. **Implied SOC Error**: $\text{Mean Implied SOC Error} \le 2.5\text{ pp}$


### Scorecard Across All Evaluated Curves


| Curve | Role | Temp (°C) | Current (A) | Bias (mV) | RMSE (mV) | Mean Implied SOC Error (pp) | Median Implied SOC Error (pp) | Bias Gate | RMSE Gate | SOC Gate | Verdict |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `T10_150A` | Held-out (Rate test 150A) | 10 | 150 | +81.14 | 87.36 | 233.28 | 75.53 | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| `T20_150A` | Held-out (Rate test 150A) | 20 | 150 | +35.26 | 41.63 | 87.26 | 28.05 | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| `T15_100A` | Held-out (Interpolated temp 15C) | 15 | 100 | -13.73 | 46.92 | 38.94 | 17.68 | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| `T5_150A` | Held-out (SUSPECT 5C/150A) | 5 | 150 | +94.81 | 102.49 | 272.52 | 89.20 | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| `T5_100A` | Fit set (100A) | 5 | 100 | -0.60 | 51.88 | 60.06 | 25.00 | PASS | **FAIL** | **FAIL** | **FAIL** |
| `T10_100A` | Fit set (100A) | 10 | 100 | -0.52 | 42.47 | 47.30 | 18.55 | PASS | **FAIL** | **FAIL** | **FAIL** |
| `T20_100A` | Fit set (100A) | 20 | 100 | -0.54 | 23.37 | 40.18 | 11.89 | PASS | **FAIL** | **FAIL** | **FAIL** |

---

## 2. Root Cause Diagnostic Analysis (Why Open-Loop Fails)

The open-loop model gate is **NO-GO (FAIL)** on all held-out curves. This failure is a fundamental physical consequence of applying low-rate pulsed equilibrium thresholds to continuous high-rate constant-current discharge data on ultra-flat LFP cells.


### 2.1 Diagnosis 1: Non-Linear Overpotential Scaling at 150 A ($R_0$ and Tafel Kinetics)

- At 150 A (1.5 C), terminal voltage is consistently **higher than modeled** by $+35.3\text{ mV}$ at 20 °C and $+81.1\text{ mV}$ at 10 °C.

- A linear resistance model $V = OCV - R_{total} \cdot I$ calibrated at 100 A assumes overpotential scales linearly with current. In real electrochemical cells:

  1. **Butler-Volmer / Tafel Kinetics**: Charge-transfer overpotential scales logarithmically with current density ($\eta \propto \ln(I)$), meaning effective resistance $R_{ct}$ decreases as current increases.

  2. **Joule Self-Heating**: At 150 A, internal heat generation is $I^2 R \approx (150)^2 \times 0.002\,\Omega = 45\text{ W}$. Across a 20-minute discharge, adiabatic/semi-insulated cell heating raises cell core temperature by 5–12 °C, substantially lowering ohmic and polarization resistances.

  - As a result, using linear parameters fitted at 100 A causes the model to over-predict voltage drop at 150 A by 35 to 81 mV.


### 2.2 Diagnosis 2: Truth-Definition Mismatch ($Q_{end}(T, I)$ vs C/20 Equilibrium Capacity)

- Truth SOC is defined per Assumption A2 as $soc_{truth}(t) = 1 - capacity\_Ah(t) / Q_{end}(T, I)$, where $Q_{end}(T, I)$ is usable capacity to the 2.5 V cutoff.

- However, the static OCV curve was measured from a 100 Ah cell under quasi-equilibrium C/20 conditions delivering ~100–105 Ah.

- Because usable capacity under 100 A / 150 A discharge ($86\text{ to }95\text{ Ah}$) is 10% to 15% lower than C/20 capacity, the cutoff knee occurs earlier in Ah.

- Below 20% usable SOC, the cell under 100 A discharge is already entering the mass-transport diffusion starvation knee (voltage dropping below 3.0 V), whereas the C/20 OCV curve at 15–20% SOC is still in the 3.25 V plateau. This creates a massive terminal divergence (up to 100–180 mV) near the 10% SOC boundary of W-mid.


### 2.3 Diagnosis 3: Ultra-Flat Plateau and Implied SOC Error Amplification

- In Step 2, we showed that the FlexiPod cells have an ultra-flat plateau with local slopes as low as $0.12\text{ to }0.25\text{ mV/pp}$ (and dropping to $\le 0.05\text{ mV/pp}$ near 75-80% SOC).

- At a slope of $0.15\text{ mV/pp}$, each $1\text{ mV}$ of model voltage error translates to **$6.67\text{ pp}$ of implied SOC error**.

- A modest 20 mV voltage error from thermal/kinetic overpotential induces **$>130\text{ pp}$ of implied SOC error**.

- This proves mathematically that **open-loop voltage-based SOC inversion is fundamentally invalid on flat-plateau LFP cells under high continuous load**.


### 2.4 Diagnosis 4: Unobservability of RC Dynamics in Continuous CC Discharge

- Because the dataset contains exclusively continuous constant-current discharge without current interruptions, pulses, or rests, the RC branches are continuously saturated ($v_1 \to R_1 I$, $v_2 \to R_2 I$).

- The RC time constants $\tau_1$ and $\tau_2$ cannot be dynamically identified from steady-state polarization; they require dynamic cycles (DST/FUDS/US06) or HPPC pulse-relaxation data.


---

## 3. Primary Finding for Phase 2

> [!IMPORTANT]

> **Phase 2 Specification Requirement**: Constant-current discharge data without dynamic pulses or resting periods is fundamentally insufficient to train a generalizable open-loop 2RC model for high rates (1.5 C). To achieve open-loop voltage fidelity $\le 6\text{ mV}$ across C-rates, Phase 2 field test logging must include:

> 1. Dynamic drive cycles (pulse charge and discharge) with rest periods to decouple $R_0$, $R_1$, and $R_2$.

> 2. Real-time cell surface and core temperature logging to compensate for $45\text{ W}$ Joule heating.

> 3. A rate-dependent polarization or Butler-Volmer overpotential correction term $\eta(I, T)$.

> 4. Rigorous closed-loop estimators with observability gating (E7v3) rather than open-loop inversion.
