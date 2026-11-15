# E7v3 Confidence-Aware Composite Adaptive SOC Estimator: Canonical Algorithm Specification

**Status**: DEVELOPMENT VALIDATED (CALCE 20°C to 50°C development envelope; not field-validated)  
**Release Version**: 0.2.0-handover  
**Canonical Implementation**: `deliverable/bms_soc_ref.py` (standalone stdlib reference) / `src/soc/estimators/e7v3.py` (research prototype)  
**Combined Resolved Config Hash**: `18902f2c61efc3b36f0d62e2e424e298c6b886c19398a433bf9f7861eced2a70`

---

## 1. Operating Envelope & Cell Identification

- **Cell Chemistry & Geometry**: Lithium Iron Phosphate ($\text{LiFePO}_4$ / LFP) cylindrical cells: **A123 Systems ANR26650M1-A** (26650 form-factor, $26\text{ mm}$ diameter $\times 65\text{ mm}$ length, nominal $2.3\text{ Ah}$ rated at 1C, calibrated C/20 baseline $\sim 1.064\text{ to }1.081\text{ Ah}$ in test protocols).
- **Certified Operating Temperature Envelope**: **20 °C to 50 °C** (validated across DST, US06, and FUDS dynamic driving cycles on CALCE A123 cells A1-007 and A1-008).
- **Application Domain**: Stationary BESS and automotive auxiliary / micro-hybrid battery packs subjected to partial-SOC dynamic cycling.
- **Cold Temperature Advisory (< 15 °C)**: Evaluated at 10 °C, 0 °C, and -7.4 °C. No divergence or state explosion occurs, but convergence rate degrades due to a $> 4\times$ ohmic resistance surge and severe hysteresis broadening. Cold deployment requires an empirical sub-zero calibration matrix.

---

## 2. Core Architecture

The **E7v3** estimator unifies four tightly coupled mathematical mechanisms:

1. **Confidence-Aware State Initialization (`reset(soc0, soc_std)`)**:
   Sets initial covariance $P_{\text{soc},0} = \sigma_{\text{soc}}^2$. Protects accurate starts ($P_{\text{soc},0} \approx 2.5 \times 10^{-5}$ to $6.4 \times 10^{-5}$) from spurious drift on flat plateaus while permitting robust, rapid pull-in from unknown starts ($P_{\text{soc},0} = 0.01$).
2. **Plateau Step Capping & Observability Gating**:
   Scaled gain $g_{\text{slope}} = \min(1.0, |\partial \text{OCV}/\partial z| / 0.20)$ throttles Kalman updates on flat plateaus ($|\partial \text{OCV}/\partial z| < 0.05\text{ V/unit}$) and enforces a hard step cap ($\text{cap}_{\text{plateau}} = 2.0 \times 10^{-5}\text{ /s}$), eliminating sensor-noise aliasing and erroneous voltage corrections.
3. **Online RLS Impedance Adaptation**:
   Recursive Least Squares tracks cell-to-cell resistance variation and aging ($\theta_k \in [0.5, 2.0]$) triggered by active current pulses ($|\Delta i_k| \ge 1.0\text{ A}$), ensuring robust cross-cell transfer without cell-specific re-tuning.
4. **Joseph-Form Stabilized Covariance Update**:
   Updates covariance via an effective gain formulation $K_{\text{soc,eff}} = \Delta z_{\text{eff}} / r_k$, maintaining exact covariance consistency, symmetry, and positive definiteness when corrections are bounded by step caps.

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

## 3. Mathematical Equations

### 3.1 State Vector and Plant Model
The discrete state vector $\mathbf{x}_k \in \mathbb{R}^4$ is:
$$\mathbf{x}_k = \begin{bmatrix} z_k \\ i_{1,k} \\ i_{2,k} \\ h_k \end{bmatrix} = \begin{bmatrix} \text{SOC} \in [0, 1] \\ \text{RC}_1 \text{ branch current (A)} \\ \text{RC}_2 \text{ branch current (A)} \\ \text{Hysteresis state} \in [-1, 1] \end{bmatrix}$$

#### Time Propagation:
1. **Coulomb Integration (SOC)**:
   $$z_{k+1} = z_k - \frac{\eta_k \cdot i_k \cdot \Delta t}{3600 \cdot Q(T_k)}$$
   where Coulombic efficiency $\eta_k$ is:
   $$\eta_k = \begin{cases} 1.0, & i_k \ge 0 \text{ (discharge)} \\ 0.998, & i_k < 0 \text{ (charge)} \end{cases}$$
   and $Q(T_k)$ is the temperature-scheduled C/20 capacity in Ah.

2. **RC Polarization Currents**:
   $$i_{j,k+1} = e^{-\Delta t / \tau_j(T_k)} \cdot i_{j,k} + \left(1 - e^{-\Delta t / \tau_j(T_k)}\right) i_k, \quad j \in \{1, 2\}$$

3. **Zero-Order Discrete Hysteresis**:
   $$h_{k+1} = \begin{cases} h_k, & i_k = 0 \\ e^{-\alpha_k} \cdot h_k - \left(1 - e^{-\alpha_k}\right) \operatorname{sgn}(i_k), & i_k \neq 0 \end{cases}$$
   where:
   $$\alpha_k = \left| \frac{\eta_k \cdot i_k \cdot \gamma \cdot \Delta t}{3600 \cdot Q(T_k)} \right|, \quad \gamma = 50.0$$

4. **Terminal Voltage Model**:
   $$\hat{v}_k = \text{OCV}(z_k, T_k) + M(T_k) \cdot h_k - R_{1,\text{eff}}(T_k) \cdot i_{1,k} - R_2(T_k) \cdot i_{2,k} - R_{0,\text{eff}}(T_k) \cdot i_k$$

---

### 3.2 Online RLS Impedance Adaptation
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

### 3.3 Observability Gating & Plateau Step Capping
The Kalman innovation is:
$$r_k = v_k - \hat{v}_k$$
Observation Jacobian:
$$\mathbf{H}_k = \begin{bmatrix} \left.\frac{\partial \text{OCV}}{\partial z}\right|_{z_k, T_k} & -R_{1,\text{eff}} & -R_2 & M(T_k) \end{bmatrix}$$
Standard Kalman gain:
$$\mathbf{K} = \mathbf{P}_k^- \mathbf{H}_k^T \left( \mathbf{H}_k \mathbf{P}_k^- \mathbf{H}_k^T + R_v + \sigma_{\text{ocv}}^2 \right)^{-1}$$
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
$$K_{\text{soc,eff}} = \begin{cases} \frac{\Delta z_{\text{eff}}}{r_k}, & |r_k| > 10^{-12} \\ 0, & |r_k| \le 10^{-12} \end{cases}$$
$$\mathbf{K}_{\text{eff}} = \begin{bmatrix} K_{\text{soc,eff}} \\ K_{\text{rc1}} \\ K_{\text{rc2}} \\ K_h \end{bmatrix}$$
$$\mathbf{P}_k^+ = (\mathbf{I} - \mathbf{K}_{\text{eff}} \mathbf{H}_k) \mathbf{P}_k^- (\mathbf{I} - \mathbf{K}_{\text{eff}} \mathbf{H}_k)^T + \mathbf{K}_{\text{eff}} (R_v + \sigma_{\text{ocv}}^2) \mathbf{K}_{\text{eff}}^T$$

---

## 4. Frozen Parameter Set

| Parameter | Value | Unit | Provenance |
|:---|:---:|:---:|:---|
| `nominal_capacity_ah` | $1.06356$ | Ah | D8 anchor gap analysis at 25 °C |
| `coulombic_efficiency` | $0.998$ | - | Calibrated charge/discharge integration |
| `hysteresis_gamma` | $50.0$ | - | Rate-dependent differential hysteresis loop |
| `process_noise_q_soc` | $2.0 \times 10^{-9}$ | - | SOC drift random walk |
| `process_noise_q_rc` | $1.1198 \times 10^{-5}$ | $\text{A}^2$ | Polarization current state noise |
| `process_noise_q_hysteresis` | $1.7151 \times 10^{-4}$ | - | Hysteresis state noise |
| `measurement_noise_r_v` | $8.6103 \times 10^{-4}$ | $\text{V}^2$ | Voltage sensor variance |
| `e4_rls_forgetting_factor` | $0.9990$ | - | RLS adaptation rate |
| `rls_di_threshold_a` | $1.0$ | A | Minimum current transition for RLS update |
| `rls_theta_min`, `rls_theta_max` | $0.5, 2.0$ | - | Hard bounding envelope for impedance factor $\theta$ |
| `e5_slope_ref` | $0.20$ | V/unit | Threshold for uninhibited voltage observability |
| `e5_cap_plateau` | $2.0 \times 10^{-5}$ | 1/s | Maximum permitted correction on flat plateau |
| `e5_cap_knee` | $0.01$ | 1/s | Maximum permitted correction in knees |
| `e5_sigma_ocv_model_v` | $0.02$ | V | Model uncertainty variance inflation |
| `initial_soc_std` | $0.10$ | fraction | Default initial uncertainty ($10\text{ pp}$) |
| `initial_rc_current_std_a` | $0.10$ | A | Initial polarization uncertainty ($100\text{ mA}$) |
| `initial_hysteresis_std` | $0.10$ | fraction | Initial hysteresis uncertainty ($10\%$) |
