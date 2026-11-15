> **SUPERSEDED:** This historical specification has been superseded by the canonical specification at [docs/ALGORITHM_SPEC.md](file:///Users/tecbusiness/Desktop/random/SOC/docs/ALGORITHM_SPEC.md).

STATUS: GATE-PASSED

# E7v3 Confidence-Aware Composite Adaptive Estimator: Algorithm Specification

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
   where $\eta_k = 1.0$ if $i_k \ge 0$ (discharge) and $\eta_k = \eta_{\text{coulomb}} = 1.0$ if $i_k < 0$ (charge). $Q(T_k)$ is the temperature-scheduled C/20 capacity in Ah.

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

### 3.1 Temperature-Scheduled Capacity $Q(T)$
Measured C/20 capacity from D8 anchor gap protocol for A123 Cell A1-007:
| Temperature (°C) | Capacity $Q(T)$ (Ah) | Capacity (As) | CV-Taper Gap (pp) |
|---|---|---|---|
| 20.0 | 1.065215 | 3834.77 | 0.781 pp |
| 25.0 (suspect) | 1.063562 | 3828.82 | 0.941 pp |
| 30.0 | 1.073006 | 3862.82 | 0.654 pp |
| 40.0 | 1.080190 | 3888.68 | 0.490 pp |
| 50.0 | 1.080957 | 3891.44 | 0.385 pp |

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

| Operating Dimension | Validated Range | Boundary Limits / Degradation Characteristics |
|---|---|---|
| **SOC Range** | **10% to 90%** | Plateau (40–80% SOC): RMSE $\approx 1.6 - 1.7\text{ pp}$. Knees (<20%, >80% SOC): RMSE $\approx 1.1 - 1.4\text{ pp}$. Full range validated without runaway divergence. |
| **Temperature** | **20 °C to 50 °C** | Validated across 20, 30, 40, 50 °C. 25 °C flagged suspect due to 3-month CALCE test delay and CV hold artifact, but algorithm functions correctly (S-A = 1.31 pp). |
| **Dynamic Profiles** | **DST, US06, FUDS** | Validated across 3 standard duty cycles representing urban, dynamic high-acceleration highway, and Federal urban driving. |
| **Cell Transferability** | **Cell A1-007 $\to$ Cell A1-008** | Validated on Cell A1-008 (Set X) without retuning: S-A $\le 1.95\text{ pp}$, S-B $\le 2.94\text{ pp}$, S-C $\le 0.81\text{ pp}$ across all temperatures. |

### Regional Operating Window Errors (S-A RMSE)
- **DST**: W-low (10–30% SOC) = 1.188 pp; W-mid (40–80% SOC) = 1.733 pp; W-high (85–95% SOC) = 1.382 pp.
- **US06**: W-low = 1.115 pp; W-mid = 1.625 pp; W-high = 1.473 pp.
- **FUDS**: W-low = 1.221 pp; W-mid = 1.769 pp; W-high = 1.440 pp.

---

## 6. What Is NOT Validated (Known Limitations)

The following operational domains have **NOT** been validated on CALCE data and must be formally qualified prior to industrial vehicle or BESS deployment:
1. **Cell Degradation and Aging (SOH)**:
   - Evaluated strictly on fresh cells (< 50 cycles). Capacity fade, internal resistance growth, and lithium plating dynamics are unmodeled.
2. **Sub-Zero and Cold Weather (< 10 °C)**:
   - CALCE A123 dynamic cycling profiles only exist down to 20 °C. Sub-zero temperatures (-20 °C to 0 °C) exhibit massive charge-transfer impedance rise and sluggish phase transitions not captured in the 20–50 °C gate.
3. **Minor-Loop Dynamic Hysteresis**:
   - The rate constant $\gamma = 50.0$ is an unobserved placeholder. Micro-cycles within the plateau do not have true ground-truth tracking for hysteresis state $h$.
4. **Multi-Cell Pack Balancing and Cell Imbalance**:
   - Algorithm was developed for single-cell voltage/current telemetry. Series-string imbalance, parallel branch cross-currents, and module thermal gradients require pack-level supervisor logic.
5. **Fast Charging (> 2C)**:
   - Dynamic tests were conducted under discharge-heavy drive profiles (DST/US06/FUDS) with peak currents $\le 3\text{C}$ and average currents $\le 1\text{C}$. Continuous high-power fast charging (3C–5C) is unvalidated.
6. **Violent Thermal Transients**:
   - All tests were conducted inside controlled thermal chambers with slowly varying cell temperatures ($< 2\text{ }^\circ\text{C/hr}$). Fast adiabatic self-heating is unvalidated.
7. **Production Telematics Noise & Dropout**:
   - Tested under simulated 1% dropout and Gaussian sensor noise; production vehicle bus dropouts, CAN quantization, and current sensor zero-point drift exceeding $\pm 20\text{ mA}$ require field characterization.
8. **Sealed Blind Hold-Out Dataset**:
   - US06 and FUDS are development data read during earlier diagnostic runs (not sealed). Truly blinded validation requires a fresh independent test run on new cell batches.
