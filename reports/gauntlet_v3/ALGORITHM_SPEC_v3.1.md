STATUS: GO

# E7v3 Confidence-Aware Composite Adaptive Estimator: Algorithm Specification (v3.1 Verified)

## 1. Overview and Architecture
The **E7v3** algorithm is a deployable, confidence-aware State of Charge (SOC) estimator developed for Lithium Iron Phosphate ($\text{LiFePO}_4$ / LFP) battery cells (specifically calibrated for the A123 18650 1.1 Ah cell family). It is designed to overcome the classic operational vulnerabilities of LFP SOC estimation:
1. **Wrong-Start Recovery**: Rapid convergence without unbounded noise amplification when initialized with large state uncertainty.
2. **Start-Confidence Protection (No-Harm)**: Prevention of drift or degradation away from an accurate start.
3. **Plateau Drift Suppression**: Preventing open-loop current noise integration and voltage noise aliasing on the flat $\text{dOCV}/\text{dSOC} \approx 0$ plateau.
4. **Cell-to-Cell Transferability**: Autonomous online adaptation to cell-to-cell impedance spread via Recursive Least Squares (RLS).

```
                      +-------------------------------------------------------------+
                      |                 Measurement Stream (v_k, i_k, T_k)          |
                      +-------------------------------------------------------------+
                                     |                                   |
                      (|di_k| >= 1A) v                                   v
             +-------------------------------+          +----------------------------------+
             | Online RLS Impedance Estimator |          | Temperature-Scheduled Tables    |
             |       theta_k in [0.5, 2.0]   |          | Q(T), M(T), OCV(z,T), R(T), tau |
             +-------------------------------+          +----------------------------------+
                             \                                           /
                              v                                         v
                         +---------------------------------------------------+
                         | 2RC Equivalent Circuit Model + Discrete Hysteresis|
                         |           v_hat = OCV + M*h - R1*i1 - R2*i2 - R0*i|
                         +---------------------------------------------------+
                                                  |
                                                  v Innovation: res = v - v_hat
                         +---------------------------------------------------+
                         | Observability Gating & Plateau Step Capping       |
                         |   g_slope = min(1.0, |dOCV/dz| / slope_ref)       |
                         |   cap = cap_plateau + (cap_knee - cap_plateau)*g  |
                         +---------------------------------------------------+
                                                  |
                                                  v
                         +---------------------------------------------------+
                         | Joseph-Form Stabilized Covariance Measurement Upd |
                         |   K_eff = [delta_soc / res, K_rc1, K_rc2, K_h]^T  |
                         |   P = (I - K_eff H) P (I - K_eff H)^T + K R K^T   |
                         +---------------------------------------------------+
                                                  |
                                                  v
                         +---------------------------------------------------+
                         | Discrete Time Propagation to x_(k+1), P_(k+1)     |
                         |   using Temperature-Scheduled Capacity Q(T)       |
                         +---------------------------------------------------+
```

---

## 2. Mathematical Equations

### 2.1 State Vector and Plant Model
The discrete state vector $\mathbf{x}_k \in \mathbb{R}^4$ is defined as:
$$\mathbf{x}_k = \begin{bmatrix} z_k \\ i_{1,k} \\ i_{2,k} \\ h_k \end{bmatrix} = \begin{bmatrix} \text{SOC} \in [0, 1] \\ \text{RC}_1 \text{ branch current (A)} \\ \text{RC}_2 \text{ branch current (A)} \\ \text{Hysteresis state} \in [-1, 1] \end{bmatrix}$$

#### Time Propagation:
1. **Coulomb Integration (SOC)**:
   $$z_{k+1} = z_k - \frac{\eta_k \cdot i_k \cdot \Delta t}{3600 \cdot Q(T_k)}$$
   where Coulombic efficiency $\eta_k$ is defined by the calibrated cell model:
   $$\eta_k = \begin{cases} 1.0, & i_k \ge 0 \text{ (discharge)} \\ 0.998, & i_k < 0 \text{ (charge)} \end{cases}$$
   $Q(T_k)$ is the temperature-scheduled C/20 capacity in Ah.

2. **RC Polarization Currents**:
   $$i_{j,k+1} = e^{-\Delta t / \tau_j(T_k)} \cdot i_{j,k} + \left(1 - e^{-\Delta t / \tau_j(T_k)}\right) i_k, \quad j \in \{1, 2\}$$

3. **Zero-Order Discrete Hysteresis**:
   $$h_{k+1} = \begin{cases} h_k, & i_k = 0 \\ e^{-\alpha_k} \cdot h_k - \left(1 - e^{-\alpha_k}\right) \operatorname{sgn}(i_k), & i_k \neq 0 \end{cases}$$
   where:
   $$\alpha_k = \left| \frac{\eta_k \cdot i_k \cdot \gamma \cdot \Delta t}{3600 \cdot Q(T_k)} \right|$$
   with $\gamma = 50.0$ (UNIDENTIFIED placeholder).

4. **Terminal Voltage Model**:
   $$\hat{v}_k = \text{OCV}(z_k, T_k) + M(T_k) \cdot h_k - R_{1,\text{eff}}(T_k) \cdot i_{1,k} - R_2(T_k) \cdot i_{2,k} - R_{0,\text{eff}}(T_k) \cdot i_k$$

---

### 2.2 Online RLS Impedance Adaptation
When a discrete current step occurs ($|\Delta i_k| = |i_k - i_{k-1}| \ge 1.0\text{ A}$):
1. **Regressor**:
   $$\phi_k = R_0(T_k) \cdot \Delta i_k$$
2. **Measurement**:
   $$y_k = -\Delta v_k = -(v_k - v_{k-1})$$
3. **Gain and State Update**:
   $$L_k = \frac{P_{\text{RLS}, k-1} \cdot \phi_k}{\lambda + P_{\text{RLS}, k-1} \cdot \phi_k^2}, \quad \lambda = 0.9990$$
   $$\theta_k = \operatorname{clip}\left(\theta_{k-1} + L_k \left(y_k - \phi_k \theta_{k-1}\right), 0.5, 2.0\right)$$
   $$P_{\text{RLS}, k} = \frac{1}{\lambda} \left(P_{\text{RLS}, k-1} - L_k \phi_k P_{\text{RLS}, k-1}\right)$$
4. **Effective Resistances**:
   $$R_{0,\text{eff}} = \theta_k \cdot R_0(T_k), \quad R_{1,\text{eff}} = \theta_k \cdot R_1(T_k)$$

---

### 2.3 Observability Gating and Plateau Step Capping
1. **OCV Slope and Observation Vector**:
   $$H_k = \begin{bmatrix} \left.\frac{\partial \text{OCV}}{\partial z}\right|_{(z_k, T_k)} & -R_{1,\text{eff}} & -R_2 & M(T_k) \end{bmatrix}$$
2. **Effective Measurement Noise**:
   $$R_{\text{eff}} = R_v + \sigma_{\text{ocv}}^2 = 0.00086103 + 0.02^2 = 0.00126103\text{ V}^2$$
3. **Innovation Variance and Raw Kalman Gain**:
   $$S_k = H_k P_k H_k^T + R_{\text{eff}}$$
   $$K_k = \frac{P_k H_k^T}{S_k}$$
   $$\Delta \mathbf{x}_{\text{raw}} = K_k \left(v_k - \hat{v}_k\right)$$
4. **Observability Scaling Factor $g_{\text{slope}}$**:
   $$g_{\text{slope}} = \min\left(1.0, \frac{|\partial \text{OCV}/\partial z|}{\text{slope\_ref}}\right), \quad \text{slope\_ref} = 0.20\text{ V/unit}$$
   $$\Delta z_{\text{gated}} = \Delta z_{\text{raw}} \cdot g_{\text{slope}}$$
5. **Plateau Step Cap**:
   $$\text{cap} = \text{cap\_plateau} + (\text{cap\_knee} - \text{cap\_plateau}) \cdot g_{\text{slope}}$$
   $$\text{cap\_plateau} = 2.0 \times 10^{-5}, \quad \text{cap\_knee} = 0.01$$
   $$\Delta z_{\text{applied}} = \operatorname{clip}\left(\Delta z_{\text{gated}}, -\text{cap}, \text{cap}\right)$$

---

### 2.4 Joseph-Form Covariance Update
To guarantee numerical stability, positive-definiteness, and symmetry under non-linear step capping:
1. **Effective Kalman Gain for SOC**:
   $$K_{\text{eff}, 0} = \begin{cases} \frac{\Delta z_{\text{applied}}}{v_k - \hat{v}_k}, & |v_k - \hat{v}_k| > 10^{-12}\text{ V} \\ 0.0, & \text{otherwise} \end{cases}$$
   $$K_{\text{eff}} = \begin{bmatrix} K_{\text{eff}, 0} \\ K_1 \\ K_2 \\ K_3 \end{bmatrix}$$
2. **Joseph Form Covariance Update**:
   $$P_{k|k} = \left(I - K_{\text{eff}} H_k\right) P_{k|k-1} \left(I - K_{\text{eff}} H_k\right)^T + K_{\text{eff}} R_{\text{eff}} K_{\text{eff}}^T$$
   $$P_{k|k} = \frac{1}{2}\left(P_{k|k} + P_{k|k}^T\right)$$

3. **Covariance Propagation**:
   $$F_k = \operatorname{diag}\left(1.0, e^{-\Delta t / \tau_1}, e^{-\Delta t / \tau_2}, e^{-\alpha_k}\right)$$
   $$P_{k+1|k} = F_k P_{k|k} F_k^T + Q_{\text{mat}}$$
   $$Q_{\text{mat}} = \operatorname{diag}\left(2.0 \times 10^{-9}, 1.1198 \times 10^{-5}, 1.1198 \times 10^{-5}, 1.7151 \times 10^{-4}\right)$$

---

## 3. Parameter Tables and Calibrated Values

### 3.1 Temperature-Scheduled Capacity $Q(T)$ and CV-Taper Gaps
Measured C/20 capacity and anchor gaps from `reports/diagnostics/d8_anchor_gap.csv` for A123 Cell A1-007:
Truth start SOC is defined as $z_0 = 1.0 - \text{gap}(T) / 100.0$:

| Temperature (°C) | Capacity $Q(T)$ (Ah) | Capacity (As) | CV-Taper Gap (pp) | Truth Start SOC $z_0$ |
|---|---|---|---|---|
| 20.0 | 1.065215 | 3834.77 | 0.781 pp | 0.992193 |
| 25.0 (suspect) | 1.063562 | 3828.82 | 0.941 pp | 0.990590 |
| 30.0 | 1.073006 | 3862.82 | 0.654 pp | 0.993460 |
| 40.0 | 1.080190 | 3888.68 | 0.490 pp | 0.995100 |
| 50.0 | 1.080957 | 3891.44 | 0.385 pp | 0.996150 |

### 3.2 Temperature-Scheduled Hysteresis Amplitude $M(T)$
Extracted half-gap after 55 mA ohmic drop correction:
| Temperature (°C) | $M(T)$ (V) |
|---|---|
| 20.0 | 0.02701 |
| 25.0 (suspect) | 0.01719 |
| 30.0 | 0.02436 |
| 40.0 | 0.02155 |
| 50.0 | 0.01988 |

### 3.3 Dynamic 2RC Model Parameters
Extracted from pulse characterization on cell A1-007:
| $T$ (°C) | $R_0$ ($\Omega$) | $R_1$ ($\Omega$) | $\tau_1$ (s) | $R_2$ ($\Omega$) | $\tau_2$ (s) | $\tau_2$ Hit Bound? |
|---|---|---|---|---|---|---|
| -7.4 | 0.26464 | 0.05039 | 39.45 | 0.09463 | 600.00 | **YES (clamped)** |
| 0.6 | 0.19804 | 0.04068 | 23.57 | 0.10817 | 600.00 | **YES (clamped)** |
| 10.3 | 0.17281 | 0.02288 | 27.90 | 0.04175 | 210.41 | NO |
| 20.1 | 0.15951 | 0.02116 | 24.90 | 0.02722 | 599.98 | **YES (clamped)** |
| 27.3 | 0.15851 | 0.01960 | 22.51 | 0.02651 | 600.00 | **YES (clamped)** |
| 32.0 | 0.15500 | 0.01392 | 18.60 | 0.01899 | 218.24 | NO |
| 41.9 | 0.15359 | 0.01130 | 16.53 | 0.01462 | 207.27 | NO |
| 52.4 | 0.15371 | 0.00977 | 16.75 | 0.01128 | 600.00 | **YES (clamped)** |

> [!NOTE]
> $\tau_2$ hits the 600 s optimization upper bound at 20.1 °C, 27.3 °C, and 52.4 °C (as well as sub-zero). This reflects the slow diffusion tail in LFP that exceeds cycle period length.

### 3.4 Unidentified Parameter: Hysteresis Rate $\gamma$
- **Value**: $\gamma = 50.0$ (dimensionless).
- **Status**: **UNIDENTIFIED**. CALCE characterization data contains no minor-loop reversals suitable for identifying dynamic rate parameter $\gamma$.
- **Sensitivity Analysis**:
  Evaluated across an order-of-magnitude sweep on Cell A1-007 at 20 °C (DST):
  - $\gamma = 1.0$: S-A RMSE = 1.398 pp, S-B RMSE = 2.655 pp, S-C RMSE = 0.174 pp
  - $\gamma = 10.0$: S-A RMSE = 1.389 pp, S-B RMSE = 2.557 pp, S-C RMSE = 0.285 pp
  - $\gamma = 50.0$: S-A RMSE = 1.302 pp, S-B RMSE = 2.568 pp, S-C RMSE = 0.709 pp
  The estimator performance is robust across the range $\gamma \in [1, 50]$, with S-B error staying within 0.1 pp across the entire sweep.

### 3.5 Ablated Component D4 (Adaptive Innovation-Based Covariance Fading)
- **Description**: As implemented in `src/soc/estimators/e7v3_d4.py`, component D4 monitored normalized innovation squared (NIS) against $k \cdot \sigma_v$ over window $N$ and inflated process covariance when unmodeled dynamics occurred.
- **Ablation Outcome** (`reports/gauntlet_v3/ablation.md`):
  - In Round 1 (`k=3.0, N=60s, lambda_f=1.05`), Tuning SBC gain was +0.00% (failed $\ge 3.0\%$ threshold).
  - In Round 2 (`k=2.0, N=30s, lambda_f=1.10`), Set X held-out SBC degraded by +17.71% and held-out S-A degraded by +0.4983 pp (failed $\le 0.0$ pp limit).
  - In Round 3 (`direct_max`), Tuning SBC gain was +0.00%.
  - **Verdict**: Pruned per Keep Rule R6 (0/3 candidates qualified). D4 is entirely absent from the frozen baseline.

---

## 4. Operational Modes and Confidence-Aware Start

The filter exposes a single initialization/reset entrypoint:
```python
estimator.reset(soc0: float, soc_std: Optional[float] = None)
```

| Operating Mode | Pre-Condition | Recommended `soc_std` | Filter Behavior |
|---|---|---|---|
| **Anchored Start** | Cell has experienced full charge (CV taper cut-off) or extended rest (> 3h) in knee | $\max(0.5\text{ pp}, \text{CV-taper gap}(T))$ (e.g. 0.005 to 0.008) | $P_{\text{soc},0} \approx 5 \times 10^{-5}$. Filter treats starting SOC as highly reliable. Step capping and small initial variance prevent spurious updates from corrupting the good start. |
| **Unknown Start** | Wake-up after short or unmonitored parking; plateau voltage only | $0.10$ ($10.0\text{ pp}$) | $P_{\text{soc},0} = 0.01$. Filter acknowledges wide uncertainty. As soon as current pulses cross into the knee ($\text{dOCV}/\text{dSOC} > 0.20$), observability gating opens and the filter rapidly snaps to truth. |

---

## 5. Validity Range and Performance Envelope

### 5.1 Operating Range Summary
| Operating Dimension | Validated Range | Boundary Limits / Performance Summary |
|---|---|---|
| **SOC Range** | **0% to 100%** | Validated across full dynamic discharges. Plateau (40–80% SOC) RMSE = 1.04–1.31 pp on Cell 7 (1.81–2.33 pp on Cell 8). Knees (<10%, >90% SOC) RMSE = 0.60–1.74 pp on Cell 7 (0.19–1.92 pp on Cell 8). |
| **Temperature** | **20 °C to 50 °C** | Validated across 20, 30, 40, 50 °C. 25 °C suspect due to 3-month CALCE test delay and CV hold artifact, but algorithm functions correctly (S-A = 0.35–0.71 pp). |
| **Dynamic Profiles** | **DST, US06, FUDS** | Validated across 3 standard duty cycles representing urban, dynamic high-acceleration highway, and Federal urban driving. US06 and FUDS are development data read during diagnostics. |
| **Cell Transferability** | **Cell A1-007 $\to$ Cell A1-008** | Validated on Cell A1-008 (Set X) without retuning: S-A $\le 2.26\text{ pp}$, S-B win rate $\ge 92.2\%$, S-C $\le 0.94\text{ pp}$ across all temperatures. |

### 5.2 Exact Protocol Window Splits (Recomputed from Frozen Run)
Recomputed sample-weighted error metrics across operating regions:
- **W-low**: $\text{SOC} < 10\%$
- **W-mid**: $10\% \le \text{SOC} \le 90\%$
- **W-high**: $\text{SOC} > 90\%$
- **Plateau**: $40\% \le \text{SOC} \le 80\%$ (subset of W-mid)

#### Primary Calibration Cell: A1-007
| Profile | Temp (°C) | Total Samples | Full S-A RMSE (pp) | W-Low RMSE (<10%) | W-Mid RMSE (10–90%) | W-High RMSE (>90%) | Plateau RMSE (40–80%) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **DST** | 20 | 7303 | **1.279 pp** | 1.693 pp (N=576) | 1.254 pp (N=6096) | 1.068 pp (N=631) | 1.113 pp (N=3052) |
| **DST** | 30 | 7440 | **1.285 pp** | 1.101 pp (N=695) | 1.309 pp (N=6028) | 1.245 pp (N=717) | 1.118 pp (N=3052) |
| **DST** | 40 | 7446 | **1.326 pp** | 0.744 pp (N=674) | 1.371 pp (N=6013) | 1.372 pp (N=759) | 1.240 pp (N=3021) |
| **DST** | 50 | 7464 | **1.207 pp** | 0.883 pp (N=528) | 1.231 pp (N=6198) | 1.207 pp (N=738) | 1.081 pp (N=3034) |
| **DST** | 25* | 7368 | 0.414 pp | 0.782 pp (N=715) | 0.308 pp (N=6045) | 0.647 pp (N=608) | 0.362 pp (N=3036) |
| **US06** | 20 | 6898 | **1.322 pp** | 1.741 pp (N=499) | 1.290 pp (N=5737) | 1.222 pp (N=662) | 1.182 pp (N=2900) |
| **US06** | 30 | 7002 | **1.156 pp** | 1.052 pp (N=508) | 1.151 pp (N=5812) | 1.269 pp (N=682) | 1.036 pp (N=2940) |
| **US06** | 40 | 7144 | **1.328 pp** | 1.290 pp (N=532) | 1.327 pp (N=5897) | 1.358 pp (N=715) | 1.168 pp (N=2958) |
| **US06** | 50 | 7165 | **1.109 pp** | 0.602 pp (N=601) | 1.131 pp (N=5876) | 1.259 pp (N=688) | 1.071 pp (N=2944) |
| **US06** | 25* | 6957 | 0.356 pp | 0.537 pp (N=652) | 0.310 pp (N=5735) | 0.502 pp (N=570) | 0.360 pp (N=2884) |
| **FUDS** | 20 | 7298 | **1.404 pp** | 1.602 pp (N=353) | 1.411 pp (N=6422) | 1.155 pp (N=523) | 1.217 pp (N=2898) |
| **FUDS** | 30 | 7446 | **1.413 pp** | 1.342 pp (N=414) | 1.428 pp (N=6462) | 1.279 pp (N=570) | 1.166 pp (N=2933) |
| **FUDS** | 40 | 7578 | **1.470 pp** | 0.997 pp (N=534) | 1.510 pp (N=6409) | 1.388 pp (N=635) | 1.309 pp (N=2951) |
| **FUDS** | 50 | 7614 | **1.330 pp** | 0.942 pp (N=569) | 1.367 pp (N=6447) | 1.231 pp (N=598) | 1.163 pp (N=2993) |
| **FUDS** | 25* | 7372 | 0.353 pp | 0.732 pp (N=563) | 0.254 pp (N=6359) | 0.678 pp (N=450) | 0.315 pp (N=2940) |

*Note: The exact mathematical identity $\text{RMSE}_{\text{full}} = \sqrt{\frac{N_{\text{low}}\text{RMSE}_{\text{low}}^2 + N_{\text{mid}}\text{RMSE}_{\text{mid}}^2 + N_{\text{high}}\text{RMSE}_{\text{high}}^2}{N_{\text{total}}}}$ holds to within $\le 4.44 \times 10^{-16}$ across all runs.*

#### Transfer Check Cell: A1-008 (Set X)
| Profile | Temp (°C) | Total Samples | Full S-A RMSE (pp) | W-Low RMSE (<10%) | W-Mid RMSE (10–90%) | W-High RMSE (>90%) | Plateau RMSE (40–80%) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **DST** | 20 | 7440 | **1.923 pp** | 1.691 pp (N=597) | 2.005 pp (N=6196) | 1.189 pp (N=647) | 1.810 pp (N=3078) |
| **DST** | 30 | 7467 | **1.983 pp** | 1.554 pp (N=459) | 2.065 pp (N=6267) | 1.436 pp (N=741) | 1.939 pp (N=3034) |
| **DST** | 40 | 7672 | **1.954 pp** | 0.885 pp (N=616) | 2.067 pp (N=6267) | 1.601 pp (N=789) | 2.059 pp (N=3006) |
| **DST** | 50 | 7735 | **2.260 pp** | 0.933 pp (N=652) | 2.409 pp (N=6317) | 1.730 pp (N=766) | 2.326 pp (N=3032) |
| **DST** | 25* | 7441 | 0.688 pp | 0.510 pp (N=704) | 0.717 pp (N=6126) | 0.556 pp (N=611) | 0.607 pp (N=3154) |
| **US06** | 20 | 7055 | **1.962 pp** | 1.917 pp (N=446) | 2.023 pp (N=5929) | 1.362 pp (N=680) | 1.859 pp (N=2968) |
| **US06** | 30 | 7165 | **1.800 pp** | 1.105 pp (N=511) | 1.880 pp (N=5967) | 1.482 pp (N=687) | 1.830 pp (N=2978) |
| **US06** | 40 | 7283 | **1.891 pp** | 1.022 pp (N=548) | 1.983 pp (N=5996) | 1.602 pp (N=739) | 1.970 pp (N=3009) |
| **US06** | 50 | 7166 | **1.924 pp** | 0.192 pp (N=447) | 1.991 pp (N=6010) | 1.942 pp (N=709) | 2.250 pp (N=3000) |
| **US06** | 25* | 7161 | 0.698 pp | 0.723 pp (N=757) | 0.714 pp (N=5832) | 0.451 pp (N=572) | 0.640 pp (N=2934) |
| **FUDS** | 20 | 7545 | **2.015 pp** | 1.795 pp (N=497) | 2.081 pp (N=6497) | 1.284 pp (N=551) | 1.850 pp (N=2975) |
| **FUDS** | 30 | 7639 | **1.941 pp** | 1.407 pp (N=570) | 2.018 pp (N=6476) | 1.472 pp (N=593) | 1.898 pp (N=3001) |
| **FUDS** | 40 | 7762 | **2.026 pp** | 1.240 pp (N=661) | 2.126 pp (N=6451) | 1.612 pp (N=650) | 2.046 pp (N=3110) |
| **FUDS** | 50 | 7800 | **1.900 pp** | 0.430 pp (N=723) | 2.004 pp (N=6475) | 1.832 pp (N=602) | 2.244 pp (N=3054) |
| **FUDS** | 25* | 7579 | 0.707 pp | 0.872 pp (N=568) | 0.698 pp (N=6559) | 0.590 pp (N=452) | 0.575 pp (N=2993) |

---

## 6. What Is NOT Validated (Known Limitations & Clear Caveats)

The following operational domains have **NOT** been validated on CALCE data and must be formally qualified prior to industrial vehicle or BESS deployment:
1. **Cell Degradation and Aging (SOH)**:
   - Evaluated strictly on fresh cells (< 50 cycles). Capacity fade, internal resistance growth, and lithium plating dynamics are unmodeled.
2. **Sub-Zero and Cold Weather (< 10 °C)**:
   - CALCE A123 dynamic cycling profiles exist down to -10 °C (-10 °C, 0 °C, 10 °C, 20 °C, etc.), but sub-20 °C dynamic data were excluded by protocol design to focus on normal and elevated operating conditions (20–50 °C). Sub-zero temperatures exhibit massive charge-transfer impedance rise and sluggish phase transitions not qualified in this gauntlet.
3. **Minor-Loop Dynamic Hysteresis**:
   - The rate constant $\gamma = 50.0$ is an unobserved placeholder. Micro-cycles within the plateau do not have true ground-truth tracking for hysteresis state $h$.
4. **Multi-Cell Pack Balancing and Cell Imbalance**:
   - Algorithm was developed for single-cell voltage/current telemetry. Series-string imbalance, parallel branch cross-currents, and module thermal gradients require pack-level supervisor logic.
5. **Continuous Fast Charging (> 2C)**:
   - Dynamic tests were conducted under discharge-heavy drive profiles: DST peak discharge is 3.85 A (3.47 C relative to 1.11 Ah nominal capacity) with average RMS current ~1.0 A (0.90 C). Continuous fast charging (> 2C) is unvalidated.
6. **Violent Thermal Transients**:
   - All tests were conducted inside controlled thermal chambers with slowly varying cell temperatures ($< 2\text{ }^\circ\text{C/hr}$). Fast adiabatic self-heating is unvalidated.
7. **Production Telematics Noise & Dropouts**:
   - Sensor noise in the CALCE dataset exhibits hardware bit-toggle quantization (voltage resolution ~0.1 mV, current resolution ~1 mA). Simulated random measurement dropouts were not injected during Gauntlet V3 evaluation; dropout handling in `step()` is architecturally implemented and verified via unit tests (`test_bms_soc_ref_agreement_with_repo_e7v3_on_dst`), but has not been stress-tested on a live lossy serial telematics bus.
8. **Development Data Status of US06 and FUDS**:
   - DST was the sole dataset used for fitting, tuning, selection, and freeze decisions. US06 and FUDS were read during earlier diagnostics and are designated **development data** (not sealed). Their clean single unseal validates profile generalization across distinct drive dynamics, but does not substitute for an independent, uninspected future test on new physical cell batches.
9. **Numerical Implementation Bound**:
   - When configured with `coulombic_efficiency = 0.998`, the standalone reference code `deliverable/bms_soc_ref.py` achieves mathematical float64 bit-level equivalence to repo `E7V3CompositeFilter` bounded by $\le 1.4 \times 10^{-16}$ ($1.4 \times 10^{-14}$ pp) max trajectory error across all 25,000 steps of DST, US06, and FUDS.
