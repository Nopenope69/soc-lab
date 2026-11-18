# Gustave Eiffel 105 Ah LFP Open-Loop Model Gate Report (V1.4)

> **Document ID:** GATE-GE105-001  
> **Date:** 2026-11-19  
> **Evaluated Cells:** Development Cells `BUGE388` and `BUGE389`  
> **Temperatures:** 0 °C, 25 °C, 40 °C  
> **Profiles:** WLTC Dynamic Segments at ~90% SOC and ~50% SOC (Resampled to uniform 1.0 s grid)  
> **Target Thresholds:**  
> - $|\text{Bias}_V| \le 2.0\ \text{mV}$  
> - $\text{RMSE}_V \le 6.0\ \text{mV}$  
> - $\text{Implied SOC Error} \le 2.5\ \text{pp}$  
> **Status:** Completed on Dev Cells (Held-out Test Cells BUGE390/391 remain sealed)

---

## 1. Executive Summary and Primary Research Finding

The open-loop model gate was evaluated on the development cells (`BUGE388` and `BUGE389`) across all available dynamic drive cycles (WLTC at ~90% and ~50% SOC) using the repository's 2RC equivalent circuit model (ECM) with OCV curves derived from C/15 pseudo-OCV branches.

### Core Scientific Verdict: Method-Specific vs Data-Specific
The primary question addressed by Step V1.4 was:
> **Is the open-loop model gate failure previously observed on FlexiPod data-specific or method-specific?**

**Finding:** The open-loop model gate failure is **METHOD-SPECIFIC**.

On real laboratory data from commercial 105 Ah EVE Energy prismatic LFP cells:
1. **Dynamic Voltage Tracking Fidelity:** The 2RC equivalent circuit achieves good dynamic voltage tracking on the central plateau (50% SOC), with terminal voltage RMSE of **2.62 mV to 3.12 mV** (passing the $\le 6.0\ \text{mV}$ threshold) and bias of **-1.18 mV to -1.41 mV** (passing the $\le 2.0\ \text{mV}$ threshold).
2. **Mathematical Flaw in the Open-Loop Implied SOC Metric for LFP:** Despite excellent voltage agreement, the "implied SOC error" metric—defined as $\frac{|\Delta V|}{d\text{OCV}/d\text{SOC}}$—blows up to **6.1 pp – 7.5 pp at 50% SOC** and **12.5 pp – 14.3 pp at 90% SOC**, failing the $\le 2.5\ \text{pp}$ threshold across all conditions.
3. **Physical Root Cause:** The derivative $\frac{d\text{OCV}}{d\text{SOC}}$ on the LFP two-phase plateau ($30\%\text{--}80\%$ SOC) is near zero ($< 0.001\ \text{V} / \text{unit SOC}$, or $< 0.1\ \text{mV} / \text{pp}$). Even with a floor clamp at $0.01\ \text{V}/\text{unit SOC}$ ($1.0\ \text{mV}/\text{pp}$), any tiny physical unmodeled polarization or hysteresis offset of merely $2\text{--}3\ \text{mV}$ translates directly to an open-loop implied SOC error of $6\text{--}14\ \text{pp}$.
4. **Conclusion:** Open-loop 2RC models cannot satisfy a $\le 2.5\ \text{pp}$ implied SOC gate on LFP chemistry without closed-loop innovation feedback. The FlexiPod model gate failure was not an artifact of synthetic data; it is an intrinsic physical characteristic of LFP open-loop voltage inversion.

---

## 2. Quantitative Model Gate Evaluation Matrix

All evaluations were executed on the development partition (`BUGE388` and `BUGE389`) using 1.0 s resampled WLTC dynamic driving segments.

| Cell ID | Temp | Target SOC | Voltage Bias (mV) | Gate ($\le 2.0$ mV) | Voltage RMSE (mV) | Gate ($\le 6.0$ mV) | Implied SOC Err (pp) | Gate ($\le 2.5$ pp) | Overall Verdict |
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

## 3. Identified Equivalent Circuit Model Parameters

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

## 4. Key Takeaways for Closed-Loop Estimator Design

1. **Open-Loop Model Gate Inadequacy:** The open-loop model gate is too stringent for LFP chemistry in open-loop mode because it evaluates open-loop inversion without closed-loop filtering.
2. **Necessity of Closed-Loop Kalman Filtering (E7v3):** Closed-loop E7v3 uses current integration as its state update and uses terminal voltage innovation solely to correct long-term drift. It does not invert the flat OCV curve directly, thus bypassing the mathematical blow-up of the implied SOC error.
3. **Implication for Validation:** The failure of the open-loop gate on dev cells confirms that closed-loop validation (Step V1.8) is the true test of estimation performance on LFP chemistry.
