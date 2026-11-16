> **SUPERSEDED:** This historical specification has been superseded by the canonical specification at [docs/ALGORITHM_SPEC.md](../../../../../../../../docs/ALGORITHM_SPEC.md).

STATUS: GO (development-data validation on CALCE; not field-validated)

# E7v3 Confidence-Aware Composite Adaptive Estimator: Algorithm Specification (v3.2 Close-Out)

## 1. Overview and Architecture
The **E7v3** algorithm is a deployable, confidence-aware State of Charge (SOC) estimator developed for Lithium Iron Phosphate ($\text{LiFePO}_4$ / LFP) battery cells (specifically calibrated for the A123 18650 1.1 Ah cell family). It is designed to overcome the classical operational vulnerabilities of LFP SOC estimation:
1. **Wrong-Start Recovery**: Guaranteed convergence within bounded time without unbounded noise amplification when initialized with large state uncertainty.
2. **Start-Confidence Protection (No-Harm)**: Explicit initial covariance tuning to prevent drift or degradation away from an accurate start.
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
   with $\gamma = 50.0$ (calibrated rate parameter).

4. **Terminal Voltage Model**:
   $$\hat{v}_k = \text{OCV}(z_k, T_k) + M(T_k) \cdot h_k - R_{1,\text{eff}}(T_k) \cdot i_{1,k} - R_2(T_k) \cdot i_{2,k} - R_{0,\text{eff}}(T_k) \cdot i_k$$

---

### 2.2 Online RLS Impedance Adaptation
When a discrete current step occurs ($|\Delta i_k| = |i_k - i_{k-1}| \ge 1.0\text{ A}$):
$$\Delta v_k = v_k - v_{k-1}$$
$$\phi_k = -R_0(T_k) \cdot \Delta i_k$$
$$K_{\text{RLS}} = \frac{P_{\text{RLS},k-1} \cdot \phi_k}{\lambda + \phi_k^2 \cdot P_{\text{RLS},k-1}}$$
$$\theta_k = \operatorname{clip}\left(\theta_{k-1} + K_{\text{RLS}} \cdot (\Delta v_k - \phi_k \cdot \theta_{k-1}), 0.5, 2.0\right)$$
$$P_{\text{RLS},k} = \frac{P_{\text{RLS},k-1} - K_{\text{RLS}} \cdot \phi_k \cdot P_{\text{RLS},k-1}}{\lambda}$$
with forgetting factor $\lambda = 0.9990$.

Effective resistances are scaled online:
$$R_{0,\text{eff}}(T_k) = \theta_k \cdot R_0(T_k), \quad R_{1,\text{eff}}(T_k) = \theta_k \cdot R_1(T_k)$$

---

### 2.3 Observability Gating & Plateau Step Capping
The Kalman innovation is:
$$r_k = v_k - \hat{v}_k$$
Observation Jacobian:
$$\mathbf{H}_k = \begin{bmatrix} \left.\frac{\partial \text{OCV}}{\partial z}\right|_{z_k, T_k} & -R_{1,\text{eff}} & -R_2 & M(T_k) \end{bmatrix}$$
Standard Kalman gain:
$$\mathbf{K} = \mathbf{P}_k^- \mathbf{H}_k^T \left( \mathbf{H}_k \mathbf{P}_k^- \mathbf{H}_k^T + R_v \right)^{-1}$$
Raw SOC correction:
$$\Delta z_{\text{raw}} = K_{\text{soc}} \cdot r_k$$

#### Slope Gating:
$$g_{\text{slope}} = \min\left(1.0, \frac{\left|\left.\frac{\partial \text{OCV}}{\partial z}\right|_{z_k, T_k}\right|}{\text{slope\_ref}}\right), \quad \text{slope\_ref} = 0.20\text{ V/unit}$$

#### Plateau Step Cap:
$$\text{cap}_k = \text{cap}_{\text{plateau}} + (\text{cap}_{\text{knee}} - \text{cap}_{\text{plateau}}) \cdot g_{\text{slope}}$$
$$\text{cap}_{\text{plateau}} = 2.0 \times 10^{-5}\text{ /s}, \quad \text{cap}_{\text{knee}} = 0.01\text{ /s}$$

#### Bounded SOC Correction:
$$\Delta z_{\text{eff}} = \operatorname{clip}\left(\Delta z_{\text{raw}} \cdot g_{\text{slope}}, -\text{cap}_k \cdot \Delta t, +\text{cap}_k \cdot \Delta t\right)$$
$$z_k^+ = \operatorname{clip}\left(z_k^- + \Delta z_{\text{eff}}, 0.0, 1.0\right)$$

#### Effective Gain Formulation and Joseph Stabilized Covariance Update:
To prevent covariance under-reporting when $\Delta z$ is capped:
$$K_{\text{soc,eff}} = \begin{cases} \frac{\Delta z_{\text{eff}}}{r_k}, & |r_k| > 10^{-12} \\ 0, & |r_k| \le 10^{-12} \end{cases}$$
$$\mathbf{K}_{\text{eff}} = \begin{bmatrix} K_{\text{soc,eff}} \\ K_{\text{rc1}} \\ K_{\text{rc2}} \\ K_h \end{bmatrix}$$
$$\mathbf{P}_k^+ = (\mathbf{I} - \mathbf{K}_{\text{eff}} \mathbf{H}_k) \mathbf{P}_k^- (\mathbf{I} - \mathbf{K}_{\text{eff}} \mathbf{H}_k)^T + \mathbf{K}_{\text{eff}} R_v \mathbf{K}_{\text{eff}}^T$$

---

## 3. Parameter Tables (Freeze Commit `394b337`)

### 3.1 Scalar Filter Tuning Parameters
| Parameter | Value | Unit | Description |
|:---|:---:|:---:|:---|
| `process_noise_q_soc` | $2.0 \times 10^{-9}$ | - | SOC random walk variance per second |
| `process_noise_q_rc` | $1.1198 \times 10^{-5}$ | $\text{A}^2$ | RC current state noise variance |
| `process_noise_q_hysteresis` | $1.7151 \times 10^{-4}$ | - | Hysteresis state noise variance |
| `measurement_noise_r_v` | $8.6103 \times 10^{-4}$ | $\text{V}^2$ | Voltage sensor measurement variance |
| `e4_rls_forgetting_factor` | $0.9990$ | - | RLS memory forgetting factor $\lambda$ |
| `e5_slope_ref` | $0.20$ | V/unit | OCV slope threshold for full observability |
| `e5_cap_plateau` | $2.0 \times 10^{-5}$ | 1/s | Maximum permitted SOC correction rate on flat plateau |
| `e5_cap_knee` | $0.01$ | 1/s | Maximum permitted SOC correction rate in knees |
| `e5_sigma_ocv_model_v` | $0.02$ | V | Model uncertainty standard deviation |

### 3.2 Temperature-Scheduled Scalar Tables
From D8 Anchor Gap table and Stage V0/V1 audit:
| Temp (°C) | C/20 Capacity $Q(T)$ (Ah) | Hysteresis Half-Gap $M(T)$ (V) | CV-Taper Gap (pp) |
|:---:|:---:|:---:|:---:|
| 20.0 | 1.065215 | 0.02701 | 0.78069 |
| 25.0 (suspect) | 1.063562 | 0.01719 | 2.05095 |
| 30.0 | 1.073006 | 0.02436 | 0.52642 |
| 40.0 | 1.080190 | 0.02155 | 0.20743 |
| 50.0 | 1.080957 | 0.01988 | 0.36315 |

---

## 4. Initialization and Confidence-Aware Reset API
The estimator must be initialized using the standard API:
```python
estimator.reset(soc0: float, soc_std: Optional[float] = None)
```
- **Anchored Start (e.g. CV end, long rest > 3 hr)**:
  `soc_std = max(0.005, CV_taper_gap(T) / 100.0)`  ($\approx 0.5\text{ to } 0.8\text{ pp}$)
  Sets $P_{\text{soc},0} \approx 2.5 \times 10^{-5}$ to $6.4 \times 10^{-5}$.
- **Unknown Start (e.g. power cycle mid-cycle)**:
  `soc_std = 0.10` ($10\text{ pp}$)
  Sets $P_{\text{soc},0} = 0.01$.

---

## 5. Measured Convergence Characteristics (Replacing "Rapid Snaps to Truth")

Quantitative evaluation across 672 cases on DST, US06, and FUDS (Cells A1-007 and A1-008; 20, 30, 40, 50 °C):

| Metric | Scenario S-B (Unknown Start, $\sigma_{z,0}=10\text{ pp}$) | Scenario S-G (Wrongly Confident, $\sigma_{z,0}=0.5\text{ pp}$) |
|:---|:---:|:---:|
| **Total Test Cases** | 384 cases | 288 cases |
| **Convergence Rate ($|e| < 2\text{ pp}$ for $\ge 60\text{ s}$)** | **100.0% (384/384)** | **100.0% (288/288)** |
| **Never-Converged Fraction** | **0.0% (0/384)** | **0.0% (0/288)** |
| **Overall Median Convergence Time** | **783.9 s (13.1 min)** | **2655.2 s (44.3 min)** |
| **Overall 90th Percentile (p90) Time** | **3334.3 s (55.6 min)** | **4644.2 s (77.4 min)** |
| **Mean End-of-Window Error** | **0.627 pp** | **0.627 pp** |
| **95th Percentile End-of-Window Error** | **1.338 pp** | **1.342 pp** |

### Convergence Time by Region and Offset:
- **By Offset Size**:
  - $3\text{ pp}$ offset (S-G): Median = 2258.2 s (~37.6 min), p90 = 4082.9 s
  - $5\text{ pp}$ offset (S-B): Median = 387.9 s (~6.5 min), p90 = 3277.5 s
  - $5\text{ pp}$ offset (S-G): Median = 3115.9 s (~51.9 min), p90 = 5244.9 s
  - $10\text{ pp}$ offset (S-B): Median = 946.0 s (~15.8 min), p90 = 3545.6 s
- **By Start SOC (S-B)**:
  - $z_0 = 0.80$: Median = 365.3 s
  - $z_0 = 0.60$ (dead-flat plateau): Median = **1684.7 s (~28.1 min)** (slowest region)
  - $z_0 = 0.40$: Median = 245.4 s
  - $z_0 = 0.20$ (lower knee): Median = 858.5 s
- **Variance Reduction Decomposition vs E0**:
  - S-B: **86.6%** of error sum-of-squares reduction occurs on the plateau; **13.4%** in the knees.
  - S-G: **78.5%** of reduction occurs on the plateau; **21.5%** in the knees.

*Key Takeaway*: E7v3 does **not** "rapidly snap to truth" on the flat plateau. When wrongly confident, it takes 44 minutes median to converge; when correctly initialized with unknown covariance, it takes 13 minutes median. Convergence is deliberate and rate-limited to guarantee zero noise amplification.

---

## 6. Multi-Segment Continuous Drift (C3 Results)

Over continuous 9-hour cycling (CC-CV charge $\to$ rest $\to$ DST $\to$ rest $\to$ CC-CV charge $\to$ US06 $\to$ rest $\to$ CC-CV charge $\to$ FUDS $\to$ rest):
- **Unanchored E0**: Under $\pm 20\text{ mA}$ sensor bias, open-loop Coulomb counting drifts to **$\pm 15.8\text{ to } 19.8\text{ pp}$** end error.
- **Unanchored E7v3**: Voltage feedback during charges and knee entries bounds final end error to **$-0.85\text{ pp}$** on A1-007 and **$-1.18\text{ pp}$** on A1-008.
- **Drift Reduction**: E7v3 reduces end-of-test drift by **$+14.9\text{ to }+18.9\text{ pp}$** relative to E0 under persistent bias.
- **Anchored Variant**: External reset at CV ends (`reset(1 - gap(T), soc_std)`) clears accumulated cycle drift completely, bounding intra-cycle RMSE under 1.5 pp.

---

## 7. Out-of-Range Temperature Behavior (C4 Results: 10, 0, -10 °C)

- **10 °C**: S-A RMSE remains well controlled (1.20 to 1.30 pp). S-B achieves 75-88% win rate vs E0. S-C mean rises to 2.76-3.42 pp due to a physical 3.49 pp CV-taper polarization gap.
- **0 °C**: S-A RMSE rises to 2.22-2.87 pp, driven by W-low impedance rise (W-low RMSE reaches 4.46-5.78 pp). S-B win rate drops to 31-38%.
- **-10 °C**: Massive 4x internal impedance rise causes cell voltage to hit the discharge cutoff limit (2.0 V) prematurely. S-B win rate drops to 0.0% without thermal pre-heating.

---

## 8. What a Field Validation Must Measure

Deploying E7v3 in production automotive or BESS hardware requires validating operating conditions not represented in single-cell laboratory cycler datasets:
1. **Current-Sensor Bias and 1/f Drift**: CALCE laboratory cyclers have micro-amp measurement accuracy. Field BMS hardware (Hall effect or shunt sensors) typically exhibits $\pm 10\text{ to } 50\text{ mA}$ zero-point bias, thermal drift across $-40\text{ to }+85\text{ }^\circ\text{C}$, and ADC quantization noise.
2. **Capacity Fade and Coulombic Efficiency Loss**: The algorithm must be coupled with an online capacity estimation loop or SOH estimator to update $Q(T)$ as the pack ages from 100% to 80% SOH.
3. **Sub-Zero Operation and Lithium Plating**: At temperatures below 0 °C, charge acceptance drops dramatically and internal impedance rises exponentially. Field validation must enforce BMS charge current derating tables to avoid lithium plating.
4. **Thermal Gradients and Heat Soak**: In multi-module BESS or automotive packs, spatial temperature gradients ($\Delta T > 5\text{ }^\circ\text{C}$) exist across the pack. The filter must evaluate per-cell or per-module temperature sensor inputs.
5. **Multi-Day Partial Cycling Without Anchors**: Applications that cycle between 30% and 70% SOC for weeks without full recharge must be verified for long-term drift stability.
6. **Real Electrochemical Rests**: Lab tests switch abruptly between active cycling and rest; field validation must quantify OCV relaxation dynamics over 1 to 24 hours.
7. **Pack-Level Cell Spread & Balancing**: Series-connected cells diverge due to self-discharge and capacity mismatch; validation must verify filter tracking during passive bleed or active balancing.
