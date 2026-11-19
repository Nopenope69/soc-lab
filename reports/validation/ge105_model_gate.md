# Gustave Eiffel 105 Ah LFP Open-Loop Model Gate Report (V1.4)

> [!NOTE] Revision (V1.12)  
> Corrected voltage RMSE threshold citation to pre-registered 6.0 mV (per `reports/flexipod1/model_gate.md`), expanded out-of-sample results across all 8 conditions, noted test regime divergence for FlexiPod comparison, and marked untested hypotheses.

> **Document ID:** GATE-GE105-001  
> **Date:** 2026-11-19  
> **Evaluated Cells:** Development Cells `BUGE388` and `BUGE389`  
> **Temperatures:** 0 °C, 25 °C, 40 °C  
> **Profiles:** WLTC Dynamic Segments at ~90% SOC and ~50% SOC (Resampled to uniform 1.0 s grid)  
> **Target Thresholds:**  
> - $|\text{Bias}_V| \le 2.0\ \text{mV}$  
> - $\text{RMSE}_V \le 6.0\ \text{mV}$ (cite `reports/flexipod1/model_gate.md`)  
> - $\text{Implied SOC Error} \le 2.5\ \text{pp}$  
> **Status:** Completed on Dev Cells (Held-out Test Cells BUGE390/391 remain sealed)

---

## 1. Executive Summary and Primary Research Finding

The open-loop model gate evaluates whether an equivalent circuit model (ECM) can track cell terminal voltage dynamically and invert terminal voltage residuals into bounded SOC errors prior to closed-loop estimation.

### Separation of Acceptance Criteria & Comparison with FlexiPod
To evaluate open-loop model validity honestly, the two acceptance criteria must be separated:
1. **Dynamic Voltage Tracking Criterion:** Evaluates terminal voltage tracking error ($|\text{Bias}_V| \le 2.0\ \text{mV}$, $\text{RMSE}_V \le 6.0\ \text{mV}$; cite `reports/flexipod1/model_gate.md`).
   - **FlexiPod Outcome:** The model **failed on voltage tracking**, exhibiting large terminal voltage RMSE of **23 to 87 mV** (well exceeding the pre-registered $\le 6.0\ \text{mV}$ threshold; cite `reports/flexipod1/model_gate.md`). Note that the FlexiPod comparison is between different tests (continuous constant-current discharge curves versus dynamic WLTC segments), so a gap exists but its cause is not established.
   - **Gustave Eiffel Outcome:** On commercial 105 Ah LFP dev cells (`BUGE388`, `BUGE389`), 2RC voltage tracking **passes** on the plateau at 50% SOC with terminal voltage RMSE of **2.62 mV to 3.12 mV** (passing $\le 6.0\ \text{mV}$) and bias of **-1.18 mV to -1.41 mV** (passing $\le 2.0\ \text{mV}$). Across all 25 °C and 40 °C conditions, voltage RMSE is $\le 6.83\ \text{mV}$.
2. **Implied-SOC Error Criterion:** Evaluates open-loop voltage error inversion into state space ($\text{Implied SOC Error} = \frac{|\Delta V|}{d\text{OCV}/d\text{SOC}} \le 2.5\ \text{pp}$ or $\le 5.0\ \text{pp}$).
   - **Gustave Eiffel Outcome:** Implied-SOC error **fails across all conditions**, yielding **6.1 pp to 7.5 pp at 50% SOC** and **12.5 pp to 14.3 pp at 90% SOC** (failing both $\le 2.5\ \text{pp}$ and $\le 5.0\ \text{pp}$).
   - **Physical Root Cause:** The derivative $\frac{d\text{OCV}}{d\text{SOC}}$ on the LFP two-phase plateau ($30\%\text{--}80\%$ SOC) is near zero ($< 0.001\ \text{V} / \text{unit SOC}$, or $< 0.1\ \text{mV} / \text{pp}$). Even with a floor clamp at $0.01\ \text{V}/\text{unit SOC}$ ($1.0\ \text{mV}/\text{pp}$), any tiny unmodeled polarization or hysteresis residual of merely $2\text{--}3\ \text{mV}$ directly causes an open-loop implied SOC error of $6\text{--}14\ \text{pp}$. The implied-SOC criterion is plateau-limited on any LFP cell, and this was known in advance.
3. **Behavior in Closed-Loop Operation:**
   - It is incorrect to claim that closed-loop filtering "corrects for this discrepancy" automatically. As demonstrated in closed-loop held-out testing (Item 4), when initialized with a +10 pp perturbation at 50% SOC, the filter **diverges** on the flat plateau, ending at **12.15 pp** on `BUGE390` and **16.23 pp** on `BUGE391` (worse than the initial 10.0 pp disturbance and worse than open-loop Coulomb counter E0). Small voltage residuals on the plateau lack the gradient required for reliable state correction.

---

## 2. In-Sample Quantitative Model Gate Evaluation Matrix

> [!IMPORTANT] In-Sample Identification Notice  
> All evaluations in this section are **in-sample**: the 2RC equivalent circuit parameters were identified by nonlinear regression directly on the exact same WLTC dynamic segments on which they were evaluated.

All in-sample evaluations were executed on the development partition (`BUGE388` and `BUGE389`) using 1.0 s resampled WLTC dynamic driving segments.

| Cell ID | Temp | Target SOC | Voltage Bias (mV) | Gate ($\le 2.0$ mV) | Voltage RMSE (mV) | Gate ($\le 6.0$ mV) | Implied SOC Err (pp) | Gate ($\le 2.5$ pp) | In-Sample Verdict |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **BUGE388** | 25 °C | 90% | -3.29 | FAIL | 6.43 | FAIL | 13.15 | FAIL | **FAIL** |
| **BUGE388** | 25 °C | 50% | -1.41 | **PASS** | 3.12 | **PASS** | 7.47 | FAIL | **FAIL** |
| **BUGE388** | 40 °C | 90% | -2.52 | FAIL | 5.00 | **PASS** | 12.49 | FAIL | **FAIL** |
| **BUGE388** | 40 °C | 50% | -1.21 | **PASS** | 2.73 | **PASS** | 7.41 | FAIL | **FAIL** |
| **BUGE388** | 0 °C | 90% | -9.38 | FAIL | 19.00 | FAIL | 13.22 | FAIL | **FAIL (OOF)** |
| **BUGE388** | 0 °C | 50% | -4.69 | FAIL | 10.21 | FAIL | 8.06 | FAIL | **FAIL (OOF)** |
| **BUGE389** | 25 °C | 90% | -3.47 | FAIL | 6.83 | FAIL | 13.29 | FAIL | **FAIL** |
| **BUGE389** | 25 °C | 50% | -1.33 | **PASS** | 3.08 | **PASS** | 6.11 | FAIL | **FAIL** |
| **BUGE389** | 40 °C | 90% | -2.50 | FAIL | 4.95 | **PASS** | 14.32 | FAIL | **FAIL** |
| **BUGE389** | 40 °C | 50% | -1.18 | **PASS** | 2.62 | **PASS** | 6.71 | FAIL | **FAIL** |
| **BUGE389** | 0 °C | 90% | -10.16 | FAIL | 21.36 | FAIL | 13.69 | FAIL | **FAIL (OOF)** |
| **BUGE389** | 0 °C | 50% | -5.20 | FAIL | 11.68 | FAIL | 8.98 | FAIL | **FAIL (OOF)** |

*(Note: 0 °C is explicitly flagged `OUT_OF_ENVELOPE` per E7v3 operational envelope specifications).*

---

## 3. Identified Equivalent Circuit Model Parameters (In-Sample Fits)

Parameters were identified by non-linear least squares on each WLTC driving profile using the 2RC discrete state equations:

$$V_{\text{model}}(t) = V_{\text{ocv}}(z(t)) - R_0 \cdot I(t) - v_1(t) - v_2(t)$$

$$\begin{aligned}
v_1(t_{k+1}) &= e^{-\Delta t / \tau_1} v_1(t_k) + R_1 (1 - e^{-\Delta t / \tau_1}) I(t_k) \\
v_2(t_{k+1}) &= e^{-\Delta t / \tau_2} v_2(t_k) + R_2 (1 - e^{-\Delta t / \tau_2}) I(t_k)
\end{aligned}$$

| Cell | Temp | Target SOC | $R_0$ (m$\Omega$) | $R_1$ (m$\Omega$) | $\tau_1$ (s) | $R_2$ (m$\Omega$) | $\tau_2$ (s) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **BUGE388** | 25 °C | 90% | 0.608 | 0.384 | 12.2 | 1.243 | 185.0 |
| **BUGE388** | 25 °C | 50% | 0.565 | 0.342 | 9.5 | 1.015 | 178.2 |
| **BUGE388** | 40 °C | 90% | 0.534 | 0.285 | 10.4 | 0.964 | 178.5 |
| **BUGE388** | 40 °C | 50% | 0.513 | 0.280 | 9.1 | 0.816 | 166.5 |
| **BUGE389** | 25 °C | 90% | 0.640 | 0.395 | 12.8 | 1.295 | 187.3 |
| **BUGE389** | 25 °C | 50% | 0.598 | 0.355 | 9.8 | 1.050 | 180.1 |
| **BUGE389** | 40 °C | 90% | 0.551 | 0.292 | 10.7 | 0.990 | 179.8 |
| **BUGE389** | 40 °C | 50% | 0.530 | 0.288 | 9.3 | 0.840 | 168.2 |

---

## 4. Out-of-Sample Cross-Validation Gate Check (Dev Cells)

To evaluate parameter generalizability without data leakage, parameters identified on `BUGE388` were cross-validated on `BUGE389` dynamic data, and parameters identified on `BUGE389` were cross-validated on `BUGE388` dynamic data (development partition only; held-out test cells `BUGE390` and `BUGE391` were not touched):

| Fit Cell | Eval Cell | Temp | Target SOC | Voltage Bias (mV) | Gate ($\le 2.0$ mV) | Voltage RMSE (mV) | Gate ($\le 6.0$ mV) | Implied SOC Err (pp) | Gate ($\le 2.5$ pp) | Gate Verdict |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **BUGE388** | **BUGE389** | 25 °C | 90% | -6.23 | FAIL | 7.92 | FAIL | 15.60 | FAIL | **FAIL** |
| **BUGE388** | **BUGE389** | 25 °C | 50% | -2.64 | FAIL | 3.77 | **PASS** | 7.60 | FAIL | **FAIL** |
| **BUGE388** | **BUGE389** | 40 °C | 90% | -2.02 | FAIL | 5.13 | **PASS** | 14.39 | FAIL | **FAIL** |
| **BUGE388** | **BUGE389** | 40 °C | 50% | -0.77 | **PASS** | 2.97 | **PASS** | 7.07 | FAIL | **V-PASS / IMP-FAIL** |
| **BUGE389** | **BUGE388** | 25 °C | 90% | -2.18 | FAIL | 6.59 | FAIL | 13.49 | FAIL | **FAIL** |
| **BUGE389** | **BUGE388** | 25 °C | 50% | -0.39 | **PASS** | 3.44 | **PASS** | 7.76 | FAIL | **V-PASS / IMP-FAIL** |
| **BUGE389** | **BUGE388** | 40 °C | 90% | -1.92 | **PASS** | 5.06 | **PASS** | 12.53 | FAIL | **V-PASS / IMP-FAIL** |
| **BUGE389** | **BUGE388** | 40 °C | 50% | -0.62 | **PASS** | 2.85 | **PASS** | 7.42 | FAIL | **V-PASS / IMP-FAIL** |

---

## 5. Key Takeaways for Estimator Design

1. **Full Out-of-Sample Result:** Across 8 conditions evaluated out-of-sample:
   - **Conditions Evaluated:** 8 total cross-validation scenarios across 25 °C and 40 °C at 90% and 50% SOC.
   - **Bias Gate ($|\text{Bias}_V| \le 2.0\ \text{mV}$):** 4 of 8 conditions pass.
   - **Voltage RMSE Gate ($\text{RMSE}_V \le 6.0\ \text{mV}$):** 6 of 8 conditions pass.
   - **RMSE Range:** Worst voltage RMSE is **7.92 mV** (at 25 °C / 90% SOC BUGE388 $\to$ BUGE389; 6.59 mV in reverse direction); best voltage RMSE is **2.85 mV** (at 40 °C / 50% SOC; 2.97 mV in reverse direction).
   - **Implied SOC Gate ($\le 2.5\ \text{pp}$):** Fails everywhere (7.07 pp to 15.60 pp) due to the ultra-flat LFP plateau derivative.
   - **Degradation at 25 °C / 90% SOC:** Degradation at 25 °C / 90% SOC (RMSE 6.59 and 7.92 mV, above the 6.0 mV bar); cause not tested.
2. **Context on FlexiPod Comparison:** On FlexiPod, voltage RMSE was 23 to 87 mV (failing the pre-registered 6.0 mV bar; cite `reports/flexipod1/model_gate.md`). However, this comparison is between different tests (continuous constant-current discharge curves versus dynamic WLTC segments), so a gap exists but its cause is not established.
3. **No Automatic Closed-Loop Correction:** Closed-loop E7v3 does **not** magically eliminate plateau ambiguity. On the contrary, when disturbed by +10 pp at 50% SOC on held-out test cells, the closed-loop filter drifts and ends at 12.15 pp to 16.23 pp error (worse than open-loop Coulomb counter E0). The assertion that observability-based Kalman gain scaling is essential to prevent plateau runaway is **not tested (no ablation)**.
4. **In-Sample vs. Out-of-Sample Distinction:** Step V1.4 parameter identification was in-sample; out-of-sample cross-validation shows parameter transferability on the 40 °C plateau, while 25 °C 90% SOC exceeds the 6.0 mV threshold.
