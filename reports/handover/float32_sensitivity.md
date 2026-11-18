# Float32 (Single-Precision) Numerical Sensitivity Analysis

## 1. Executive Summary

This report evaluates the numerical stability and error accumulation of the **E7v3 BMS State of Charge (SOC) reference implementation** when executed in IEEE-754 **binary32 (single-precision `float32`)** versus the baseline **binary64 (double-precision `float64`)**.

Embedded target hardware (ARM Cortex-M4F, Cortex-M7, RISC-V with Single-Precision FPU, or fixed-point DSPs) often operates with single-precision floating-point hardware to minimize instruction latency, register pressure, and power consumption.

### Key Findings

| Metric | Double Precision (float64) Baseline | Single Precision (float32) Emulation | Divergence (Worst Case) |
| :--- | :--- | :--- | :--- |
| **Full DST (25,000 steps)** Max Trajectory Error | Reference Truth | $\le 1.156 \times 10^{-6}$ fractional | **0.000116 pp** ($1.16 \times 10^{-4}\%$) |
| **Full DST (25,000 steps)** Final Error | Reference Truth | $\le 5.422 \times 10^{-9}$ fractional | **0.000001 pp** ($5.42 \times 10^{-7}\%$) |
| **Max Single-Step Drift** | Reference Truth | $< 2.4 \times 10^{-7}$ fractional | **0.000024 pp** |
| **Covariance Symmetry & Pos-Def** | Maintained | Maintained (Joseph Form) | Zero loss of positive definiteness |

**Conclusion:** The E7v3 reference estimator is **fully compatible with single-precision (float32)** implementation. The worst-case trajectory discrepancy across 25,000 driving steps is $0.000116\text{ pp}$, which is several orders of magnitude below the sensor resolution ($0.05\text{ pp}$ target).

---

## 2. Experimental Methodology

### Test Profile
- **Scenario:** Full Dynamic Stress Test (DST) at $20^\circ\text{C}$ on CALCE A123 LiFePO4 cell A1-007 (measured capacity about 1.06 Ah, format unverified).
- **Duration:** 25,000 discrete steps ($\sim 7\text{ hours}$ of dynamic EV driving cycles).
- **Initial State:** Known start ($SOC_0 = 1.0$, $\sigma_0 = 0.005$ or initial gap).

### Emulation Details
In the `Float32Estimator`, the following operations are strictly forced to IEEE-754 single precision (`numpy.float32`):
1. **Inputs:** Terminal voltage $V$, current $I$, temperature $T$, and sample interval $\Delta t$.
2. **State Vector:** $x = [SOC, i_{RC1}, i_{RC2}, h]^T$ rounded to `float32` after both measurement update and time propagation.
3. **Covariance Matrix:** $4 \times 4$ error covariance matrix $P$ rounded to `float32`.
4. **Adaptation States:** RLS impedance scale $\theta$ and variance $P_{\text{RLS}}$ rounded to `float32`.
5. **Lookup Tables:** Interpolation results for $OCV(SOC, T)$, $R_0(T)$, $R_1(T)$, $\tau_1(T)$, $R_2(T)$, $\tau_2(T)$, $Q(T)$, and $M(T)$.

---

## 3. Why E7v3 is Resilient to Float32 Quantization

1. **Joseph-Form Stabilized Covariance Update:**
   Standard Kalman filter updates compute $P_{\text{post}} = (I - KH)P$, which is prone to loss of symmetry and loss of positive definiteness under single-precision subtraction of near-equal numbers.
   E7v3 implements the Joseph form:
   $$P_{\text{post}} = (I - K_{\text{eff}} H) P (I - K_{\text{eff}} H)^T + K_{\text{eff}} R_{\text{eff}} K_{\text{eff}}^T$$
   Because both terms are quadratic forms ($A P A^T$ and $B R B^T$), the diagonal elements $P_{ii}$ are guaranteed positive by construction, preventing negative variances.

2. **Observability Slope Gating:**
   On flat LFP plateaus ($|dOCV/dSOC| \approx 0$), Kalman gains $K$ can suffer from numerical noise. By scaling the gain:
   $$g_{\text{slope}} = \min\left(1.0, \frac{|dOCV/dSOC|}{\text{slope\_ref}}\right)$$
   and applying the plateau step cap ($\Delta SOC \le \text{cap\_plateau} = 2 \times 10^{-5}$), the filter prevents floating point truncation errors from compounding.

3. **Well-Conditioned State Scaling:**
   All four states have magnitudes of order $10^{-1}$ to $10^0$:
   - $SOC \in [0.0, 1.0]$
   - $i_{RC1}, i_{RC2} \in [-10.0, 10.0]\text{ A}$
   - $h \in [-1.0, 1.0]$
   This avoids large dynamic range differences that cause exponent underflow or loss of mantissa bits in float32 additions.

---

## 4. Firmware Implementation Recommendations

For embedded BMS teams writing C/C++ or Rust firmware:
1. **Accumulator Precision for Coulomb Counting:**
   When accumulating ampere-hours over multi-day periods ($\int I \, dt$), use a 64-bit float (`double`) or a 64-bit integer fixed-point accumulator (e.g. microampere-seconds `int64_t`) to prevent catastrophic cancellation when adding small $\Delta t \cdot I$ to large accumulated totals.
2. **Matrix Symmetrization:**
   Explicitly symmetrize the covariance matrix after each update:
   $$P_{ij} = P_{ji} = \frac{1}{2}(P_{ij} + P_{ji})$$
   This ensures round-off errors do not skew off-diagonal terms.
3. **Variance Lower Bounds:**
   Enforce a non-negative floor on covariance diagonals:
   $$P_{ii} = \max(P_{ii}, 1.0 \times 10^{-10})$$
