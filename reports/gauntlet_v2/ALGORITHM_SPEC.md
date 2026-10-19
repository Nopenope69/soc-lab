# Algorithm Specification: E7v2 Composite Adaptive SOC Estimator

**Status:** `CANDIDATE ALGORITHM SPECIFICATION (NO-GO AT STAGE V3 GATE A ii-b & GATE B iii)`  
**Chemistry:** Lithium Iron Phosphate (LFP / $\text{LiFePO}_4$)  
**Target Cell:** A123 Systems 1.11 Ah Cylindrical Cell (APR18650M1A-class)  
**Reference Implementation:** [`deliverable/bms_soc_ref.py`](file:///Users/tecbusiness/Desktop/random/SOC/deliverable/bms_soc_ref.py)  
**Verification Status:** Cross-verified against reference implementation to machine precision ($\max |\Delta \text{SOC}| = 0.00 \times 10^0$).

---

## 1. Overview and Architecture

The `E7v2` algorithm is an Extended Kalman Filter (EKF) observer designed for LFP battery cells. It combines:
1. **2RC Equivalent Circuit Network with 1-State Discrete Hysteresis:** Captures ohmic drop, two polarization relaxation processes, and open-circuit voltage hysteresis.
2. **Recursive Least Squares (RLS) Impedance Adaptation:** Continuously tracks high-frequency ohmic resistance and charge-transfer impedance scaling factor $\theta \in [0.5, 2.0]$ across differing cell instances.
3. **Observability Gating:** Scales Kalman gain corrections proportionally to the local thermodynamic observability $d\text{OCV}/d\text{SOC}$, suppressing observer overreaction on the flat LFP voltage plateau.
4. **Plateau Per-Step Correction Capping:** Limits the maximum single-step correction on the plateau to prevent sudden filter jerks from transient voltage modeling errors.
5. **Joseph-Form Covariance Stabilization:** Ensures positive semi-definiteness and numerical stability under gated/capped updates.

```
       +-------------------------------------------------------------+
       |                     Measurement Stream                      |
       |             [v_meas, i_meas, temp_c, dt_s]                  |
       +------------------------------+------------------------------+
                                      |
                      +---------------+---------------+
                      |                               |
                      v                               v
         +--------------------------+    +--------------------------+
         |   Online RLS Adapter     |    |   2RC + Hysteresis Model |
         |   Detect |dI| >= 1.0 A   |    |   Lookup OCV, R0, R1,    |
         |   Update theta in [0.5,2]|    |   R2, tau1, tau2         |
         +------------+-------------+    +------------+-------------+
                      |                               |
                      +---------------+---------------+
                                      |
                                      v
                        +---------------------------+
                        |   Terminal Voltage &      |
                        |   Innovation Calculation  |
                        |   v_hat, residual, H, S   |
                        +-------------+-------------+
                                      |
                                      v
                        +---------------------------+
                        |   Observability Gating    |
                        |   & Step Capping          |
                        |   g_slope, cap_plateau    |
                        +-------------+-------------+
                                      |
                                      v
                        +---------------------------+
                        |   Joseph Covariance &     |
                        |   State Time Propagation  |
                        +-------------+-------------+
                                      |
                                      v
                         [SOC, SOC_std, theta]
```

---

## 2. Mathematical Formulation

### 2.1 State Vector and Continuous-Time Dynamics

The system state vector $x \in \mathbb{R}^4$ is defined as:
$$
x_k = \begin{bmatrix} z_k \\ i_{1,k} \\ i_{2,k} \\ h_k \end{bmatrix} = \begin{bmatrix} \text{State of Charge (fraction } [0, 1]) \\ \text{Polarization current in branch 1 (A)} \\ \text{Polarization current in branch 2 (A)} \\ \text{Hysteresis normalized state } [-1, 1] \end{bmatrix}
$$

Sign convention: **Discharge current is positive ($I > 0$)**.

The continuous-time state evolution equations are:
$$
\frac{dz}{dt} = -\frac{\eta(I) I}{3600 Q_n}
$$
$$
\frac{di_1}{dt} = -\frac{1}{\tau_1} i_1 + \frac{1}{\tau_1} I
$$
$$
\frac{di_2}{dt} = -\frac{1}{\tau_2} i_2 + \frac{1}{\tau_2} I
$$
$$
\frac{dh}{dt} = -\left| \frac{\eta(I) I \gamma}{3600 Q_n} \right| h - \left| \frac{\eta(I) I \gamma}{3600 Q_n} \right| \text{sgn}(I)
$$
where:
- $Q_n = 1.06356\text{ Ah}$ is the measured nominal C/20 capacity.
- $\eta(I) = 0.998$ for charging ($I < 0$), and $\eta(I) = 1.0$ for discharging ($I \ge 0$).
- $\gamma = 50.0$ is the dimensionless hysteresis transition rate parameter.
- $\tau_1 = R_1 C_1$, $\tau_2 = R_2 C_2$ are polarization time constants.

### 2.2 Discrete-Time State Propagation

Given sampling period $\Delta t$:
$$
z_{k+1} = \text{clamp}\left( z_k - \frac{\eta_k I_k \Delta t}{3600 Q_n}, 0.0, 1.0 \right)
$$
$$
i_{1,k+1} = e^{-\Delta t / \tau_1} i_{1,k} + \left(1 - e^{-\Delta t / \tau_1}\right) I_k
$$
$$
i_{2,k+1} = e^{-\Delta t / \tau_2} i_{2,k} + \left(1 - e^{-\Delta t / \tau_2}\right) I_k
$$
For the hysteresis state $h$:
If $I_k = 0$: $h_{k+1} = h_k$.  
If $I_k \ne 0$:
$$
\alpha_k = \left| \frac{\eta_k I_k \gamma \Delta t}{3600 Q_n} \right|
$$
$$
h_{k+1} = \text{clamp}\left( e^{-\alpha_k} h_k - (1 - e^{-\alpha_k}) \text{sgn}(I_k), -1.0, 1.0 \right)
$$

The state transition Jacobian $F_k = \frac{\partial f}{\partial x}$ is diagonal:
$$
F_k = \text{diag}\left( \left[ 1.0, \; e^{-\Delta t / \tau_1}, \; e^{-\Delta t / \tau_2}, \; e^{-\alpha_k} \right] \right)
$$

The prior covariance propagates as:
$$
P_{k|k-1} = F_k P_{k-1|k-1} F_k^T + Q
$$
where $Q = \text{diag}([Q_{soc}, Q_{rc}, Q_{rc}, Q_h])$.

---

### 2.3 Online RLS Impedance Adaptation

When a discrete current pulse occurs ($|\Delta I_k| = |I_k - I_{k-1}| \ge 1.0\text{ A}$):
1. Regressor: $\phi_k = R_{0,base}(z_k, T_k) \cdot (I_k - I_{k-1})$.
2. Observation: $y_{meas,k} = -(V_k - V_{k-1})$.
3. Gain update:
   $$
   L_k = \frac{P_{rls,k-1} \phi_k}{\lambda + P_{rls,k-1} \phi_k^2}
   $$
4. Multiplier update:
   $$
   \theta_k = \text{clamp}\left( \theta_{k-1} + L_k (y_{meas,k} - \phi_k \theta_{k-1}), 0.5, 2.0 \right)
   $$
5. Covariance update:
   $$
   P_{rls,k} = \frac{P_{rls,k-1} - L_k \phi_k P_{rls,k-1}}{\lambda}
   $$
   with forgetting factor $\lambda = 0.999$.

Effective resistance parameters for the observer are:
$$
R_{0,eff} = \theta_k R_{0,base}(z_k, T_k)
$$
$$
R_{1,eff} = \theta_k R_{1,base}(z_k, T_k)
$$

---

### 2.4 Measurement Update, Observability Gating, and Step Capping

1. **Predicted Terminal Voltage:**
   $$
   \hat{V}_k = \text{OCV}(z_k, T_k) + M_h h_k - R_{1,eff} i_{1,k} - R_2 i_{2,k} - R_{0,eff} I_k
   $$
2. **Voltage Innovation (Residual):**
   $$
   \tilde{y}_k = V_k - \hat{V}_k
   $$
3. **Measurement Jacobian:**
   $$
   H_k = \left[ \frac{\partial \text{OCV}}{\partial z}(z_k, T_k), \; -R_{1,eff}, \; -R_2, \; M_h \right]
   $$
4. **Effective Measurement Variance:**
   $$
   R_{eff} = R_v + \sigma_{ocv}^2
   $$
5. **Innovation Covariance & Kalman Gain:**
   $$
   S_k = H_k P_{k|k-1} H_k^T + R_{eff}
   $$
   $$
   K_k = \frac{P_{k|k-1} H_k^T}{S_k} \in \mathbb{R}^4
   $$
6. **Observability Gating:**
   The thermodynamic slope $|d\text{OCV}/dz|$ controls the update scaling:
   $$
   g_{slope} = \min\left( 1.0, \; \frac{|\partial \text{OCV}/\partial z|}{\text{slope}_{ref}} \right)
   $$
   $$
   \Delta z_{raw} = K_k[0] \cdot \tilde{y}_k \cdot g_{slope}
   $$
7. **Plateau Step Capping:**
   $$
   \text{cap} = \text{cap}_{plateau} + (\text{cap}_{knee} - \text{cap}_{plateau}) \cdot g_{slope}
   $$
   $$
   \Delta z = \text{clamp}(\Delta z_{raw}, -\text{cap}, +\text{cap})
   $$
8. **Posterior State Correction:**
   $$
   x_{k|k} = \begin{bmatrix} \text{clamp}(z_k + \Delta z, 0.0, 1.0) \\ i_{1,k} + K_k[1] \tilde{y}_k \\ i_{2,k} + K_k[2] \tilde{y}_k \\ \text{clamp}(h_k + K_k[3] \tilde{y}_k, -1.0, 1.0) \end{bmatrix}
   $$

---

### 2.5 Numerically Stabilized Joseph-Form Covariance Update

To maintain positive definiteness when the SOC gain is non-linearly gated and capped, an effective Kalman gain $K_{eff} \in \mathbb{R}^4$ is constructed:
$$
K_{eff}[0] = \begin{cases} \frac{\Delta z}{\tilde{y}_k} & \text{if } |\tilde{y}_k| > 10^{-12} \\ 0.0 & \text{otherwise} \end{cases}
$$
$$
K_{eff}[1..3] = K_k[1..3]
$$

The posterior covariance is updated via Joseph's stabilized formulation:
$$
P_{k|k} = (I - K_{eff} H_k) P_{k|k-1} (I - K_{eff} H_k)^T + K_{eff} R_{eff} K_{eff}^T
$$
symmetrized as:
$$
P_{k|k} = \frac{1}{2} \left( P_{k|k} + P_{k|k}^T \right)
$$

---

## 3. Tuned Parameter Specification

| Parameter Name | Value | Unit | Rationale / Origin |
| :--- | :--- | :--- | :--- |
| `nominal_capacity_ah` | `1.06356167` | Ah | CALCE A1-007 measured C/20 discharge capacity at 25 °C |
| `coulombic_efficiency` | `0.998` | - | Empirical coulombic efficiency during charge pulses |
| `hysteresis_amplitude_v` | `0.02155` | V | Monotonized median half-gap between charge and discharge OCV |
| `hysteresis_gamma` | `50.0` | - | Dynamic hysteresis transition rate constant |
| `process_noise_q_soc` | `2.90314e-08` | - | Tuned on DST 20 °C & 30 °C |
| `process_noise_q_rc` | `1.11982e-05` | $\text{A}^2$ | Tuned on DST 20 °C & 30 °C |
| `process_noise_q_hysteresis` | `1.71509e-04` | - | Tuned on DST 20 °C & 30 °C |
| `measurement_noise_r_v` | `8.61032e-04` | $\text{V}^2$ | Tuned on DST 20 °C & 30 °C |
| `rls_forgetting_factor` | `0.999` | - | Memory window ~1000 s for online impedance tracking |
| `rls_di_threshold_a` | `1.0` | A | Current step threshold to trigger RLS parameter update |
| `rls_theta_min` | `0.5` | - | Minimum impedance scaling clamp |
| `rls_theta_max` | `2.0` | - | Maximum impedance scaling clamp |
| `e5_sigma_ocv_model_v` | `0.02` | V | OCV modeling uncertainty variance inflation |
| `e5_slope_ref` | `0.3` | V/unit SOC | Reference slope threshold for full observability gating |
| `e5_cap_plateau` | `1.0e-05` | fraction/step | Maximum SOC update per 1 Hz step on the flat plateau |
| `e5_cap_knee` | `0.01` | fraction/step | Maximum SOC update per 1 Hz step in the steep knees |

---

## 4. Parameter Tables (A123 APR18650M1A)

The model evaluates parameters across temperature grid:  
$T \in [-7.4, 0.6, 10.3, 20.1, 27.3, 32.0, 41.9, 52.4]\;^\circ\text{C}$  
and SOC grid:  
$z \in [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]$.

Between grid nodes, values are bilinearly interpolated with strict boundary clamping.

### 4.1 Equilibrium OCV Table (V)
| Temp (°C) | 0.00 | 0.05 | 0.10 | 0.20 | 0.30 | 0.40 | 0.50 | 0.60 | 0.70 | 0.80 | 0.90 | 0.95 | 1.00 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **-7.4** | 2.2780 | 2.9689 | 3.1292 | 3.2251 | 3.2653 | 3.2807 | 3.2890 | 3.2964 | 3.3082 | 3.3297 | 3.3472 | 3.3661 | 3.5594 |
| **0.6** | 2.3369 | 3.0740 | 3.1898 | 3.2416 | 3.2753 | 3.2902 | 3.2960 | 3.3010 | 3.3108 | 3.3362 | 3.3474 | 3.3619 | 3.5551 |
| **10.3** | 2.3131 | 3.0843 | 3.2024 | 3.2444 | 3.2771 | 3.2954 | 3.3005 | 3.3053 | 3.3128 | 3.3432 | 3.3529 | 3.3699 | 3.5381 |
| **20.1** | 2.2935 | 3.0866 | 3.2066 | 3.2471 | 3.2795 | 3.3001 | 3.3043 | 3.3081 | 3.3164 | 3.3439 | 3.3511 | 3.3655 | 3.5498 |
| **27.3** | 2.2544 | 3.0936 | 3.2089 | 3.2488 | 3.2810 | 3.3027 | 3.3062 | 3.3093 | 3.3184 | 3.3447 | 3.3502 | 3.3632 | 3.5488 |
| **32.0** | 2.3200 | 3.0854 | 3.2074 | 3.2474 | 3.2795 | 3.3021 | 3.3062 | 3.3097 | 3.3176 | 3.3434 | 3.3490 | 3.3616 | 3.5640 |
| **41.9** | 2.2826 | 3.0849 | 3.2085 | 3.2477 | 3.2793 | 3.3048 | 3.3086 | 3.3116 | 3.3200 | 3.3444 | 3.3496 | 3.3614 | 3.5694 |
| **52.4** | 2.2823 | 3.0834 | 3.2085 | 3.2467 | 3.2787 | 3.3065 | 3.3104 | 3.3131 | 3.3210 | 3.3441 | 3.3489 | 3.3601 | 3.5678 |

### 4.2 Impedance and Polarization Network Parameters
| Temp (°C) | $R_0\;(\Omega)$ | $R_1\;(\Omega)$ | $\tau_1\;(\text{s})$ | $R_2\;(\Omega)$ | $\tau_2\;(\text{s})$ |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **-7.4** | 0.26464 | 0.05039 | 39.45 | 0.09463 | 600.00 |
| **0.6** | 0.19804 | 0.04068 | 23.57 | 0.10817 | 600.00 |
| **10.3** | 0.17281 | 0.02288 | 27.90 | 0.04175 | 210.41 |
| **20.1** | 0.15951 | 0.02116 | 24.90 | 0.02722 | 599.98 |
| **27.3** | 0.15851 | 0.01960 | 22.51 | 0.02651 | 600.00 |
| **32.0** | 0.15500 | 0.01392 | 18.60 | 0.01899 | 218.24 |
| **41.9** | 0.15359 | 0.01130 | 16.53 | 0.01462 | 207.27 |
| **52.4** | 0.15371 | 0.00977 | 16.75 | 0.01128 | 600.00 |

---

## 5. Validation Status and Operating Envelope

### 5.1 What Is Formally Validated
1. **Dynamic Matched Cycling (Scenario S-A):**
   - Verified on full DST discharge profiles across 20, 30, 40, and 50 °C on both cell A1-007 and cell A1-008.
   - Estimation RMSE is consistently **$1.14 - 1.53$ percentage points (pp)**.
2. **Initial Offset Recovery (Scenario S-B):**
   - Verified across 32 held-out cases with initial offsets of $\pm 5$ pp and $\pm 10$ pp.
   - Achieved a **100% win rate (32/32 cases)** over pure Coulomb counting, reducing mean error from $7.3\text{ pp}$ to **$2.38 - 2.57\text{ pp}$**.
3. **Severe Sensor Fault Robustness (Scenario S-F):**
   - Verified against combined sensor faults: 200 mV voltage bias, 1.5 A current bias, 30-second dropouts, and 50 mV noise spikes.
   - Max error bounded to **$4.88 - 5.49\text{ pp}$**, whereas pure Coulomb counting drifts beyond $14.57\text{ pp}$.
4. **Cross-Cell Impedance Adaptation (Set X / Cell A1-008):**
   - Cell A1-008 displays significantly different impedance characteristics from A1-007. The online RLS estimator converged to $\theta \approx 0.63 - 0.72$, improving cross-cell performance by **$44.5\%$** over unadapted filters.

### 5.2 What Is NOT Validated
- **Sub-Zero Dynamic Operation:** Tested down to -7.4 °C in static tables, but dynamic cycling below 20 °C was excluded from decision gates per protocol R4.
- **High Continuous C-Rates:** Validated up to 2C peak pulses in DST. High continuous rates ($> 3\text{C}$) that generate significant internal core thermal gradients were not tested.
- **Multi-Cell Pack Inhomogeneity:** Validated on single cells only. Pack-level effects (series-string current bypass balancing, parallel branch recirculating currents, inter-cell thermal gradients) are untested.
- **Cell Aging Beyond CALCE Baseline:** Tested on pristine and moderately cycled cells ($< 5\%$ capacity loss). Severe degradation with degraded active material mass or thick SEI growth is not validated.

### 5.3 Known Failure Modes & Physical Root Cause
- **Partial Plateau Cycling Without Knees (Scenario S-C):**
  - **The Physical Dilemma:** On the flat LFP plateau ($20\% \le \text{SOC} \le 80\%$), the open-circuit voltage slope $d\text{OCV}/d\text{SOC}$ is extremely small ($0.5 - 1.5\text{ mV/pp}$).
  - A subtle voltage prediction discrepancy of merely $3 - 5\text{ mV}$ (inevitable from slight hysteresis relaxation error, dynamic polarization mismatch, or cell temperature gradients) translates into an apparent SOC innovation of $2 - 4\text{ pp}$.
  - In Scenario S-C (discharges initiated on the plateau with exact initial SOC knowledge), pure Coulomb counting (E0) has zero drift ($\text{RMSE} \approx 0.02\text{ pp}$). Any closed-loop feedback observer will gradually adjust its state in response to tiny voltage model errors, drifting to $1.8 - 3.5\text{ pp}$ error.
  - This fundamental physical property caused the failure of Gate A Clause (ii-b) and Gate B Clause (iii), leading to the `NO-GO(stage: Stage V3)` decision.
