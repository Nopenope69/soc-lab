> **NOTICE:** Please see [FROZEN_SPEC_ERRATA.md](file:///Users/tecbusiness/Desktop/random/SOC/reports/gauntlet_v3/FROZEN_SPEC_ERRATA.md) for errata and clarifications regarding Coulombic efficiency, initial RC/hysteresis covariances, and combined configuration hashes.

# Gauntlet V3 Freeze Specification (Stage V4)

**Status**: FROZEN  
**Date**: 2026-10-19 20:34:00  
**Baseline Git Commit**: `e15987bae40f4a4c2da4e0623ee9fe62023b12c3`  
**Full Test Suite**: 205 passed in 375.17s (0 failures, 0 errors)  

---

## 1. Frozen Estimator & Architecture

- **Estimator Class**: `E7V3CompositeFilter`
- **File**: `src/soc/estimators/e7v3.py`
- **SHA-256**: `057f4d8547b00c80306d1ddd55fbac42dc304448f306d4bbd2fdbbb77ab9154e`
- **Architecture**:
  1. **2RC Equivalent Circuit + Differential Hysteresis Base Model**: State vector $x = [z, i_1, i_2, h]^T \in \mathbb{R}^4$.
  2. **Confidence-Aware Start**: Initial covariance $P_0 = \text{diag}([(\sigma_{\text{soc},0})^2, (\sigma_{i,0})^2, (\sigma_{i,0})^2, (\sigma_{h,0})^2])$ configured via `reset(soc0, soc_std)`.
  3. **Online RLS Impedance Tracking**: Adapts $\theta(t)$ scaling $R_0$ and $R_1$ simultaneously on current steps $|\Delta I| \ge 1.0\text{ A}$ with forgetting factor $\lambda = 0.9990$.
  4. **Observability Gating & Plateau Step Capping**:
     - Slope gating $g_{\text{slope}} = \min(1.0, |d\text{OCV}/dz| / s_{\text{ref}})$ with $s_{\text{ref}} = 0.20\text{ V/unit}$.
     - Per-step SOC correction capped by $\text{cap} = \text{cap}_{\text{plateau}} + (\text{cap}_{\text{knee}} - \text{cap}_{\text{plateau}}) g_{\text{slope}}$, where $\text{cap}_{\text{plateau}} = 2.0 \times 10^{-5}$ and $\text{cap}_{\text{knee}} = 0.01$.
     - Variance inflation $R_{\text{eff}} = R_v + \sigma_{\text{ocv}}^2$ with $\sigma_{\text{ocv}} = 0.02\text{ V}$.
     - Joseph-form covariance update preserving symmetry and positive definiteness under step capping.
  5. **Temperature-Scheduled Capacity & Hysteresis**:
     - C/20 capacity $Q(T)$ lookup with linear interpolation and boundary clamping.
     - Hysteresis half-gap $M(T)$ lookup with linear interpolation and boundary clamping.

---

## 2. Parameter Files & Provenance (SHA-256 Hashes)

| File | SHA-256 Hash | Role |
|:---|:---:|:---|
| `configs/assumptions/profiles/calce_a123_v4.yaml` | `3a3391e4f95ee967004d41f9c4d3a210a64c852715befbdfe26b53d74cc9c375` | Calibrated base 2RC OCV and RC tables |
| `reports/diagnostics/d8_anchor_gap.csv` | `a254d22c18141c2e880582519d14a1b6cb06cb8fc1b818d70087926f16648009` | D8 C/20 capacity and CV-taper anchor gaps |
| `src/soc/estimators/e7v3.py` | `057f4d8547b00c80306d1ddd55fbac42dc304448f306d4bbd2fdbbb77ab9154e` | Frozen estimator implementation |
| `src/soc/estimators/base.py` | `33817e762e359c214cd9824c7684202b0ff129c9ef86b6994cdaf5fd8d8e04da` | ParamSet definition and estimator protocol |
| `scripts/gauntlet_v3_scenarios.py` | `a2c8929bf4959217e770a14dcdacf1dee761feefed1eb17909a16e99427feceb` | Scenarios S-A, S-B, S-C, S-G, S-F builder |
| `reports/gauntlet_v3/stage_v3_results.json` | `b5534c32113d320a2277de3297318226aca8b88ae8f324327419ba8df714bfc4` | Frozen Stage V3 validation run results |

---

## 3. Frozen Estimator Parameters

### Scalar Tunings
```json
{
  "process_noise_q_soc": 2.0e-09,
  "process_noise_q_rc": 1.1198164932559382e-05,
  "process_noise_q_hysteresis": 0.00017150882346504795,
  "measurement_noise_r_v": 0.0008610323423725228,
  "e4_rls_forgetting_factor": 0.9990,
  "e5_slope_ref": 0.20,
  "e5_cap_plateau": 2.0e-05,
  "e5_cap_knee": 0.01,
  "e5_sigma_ocv_model_v": 0.02,
  "hysteresis_gamma": 50.0,
  "coulombic_efficiency": 1.0,
  "initial_rc_current_std_a": 0.0,
  "initial_hysteresis_std": 0.0
}
```

### Temperature Grids & Interpolation Tables
- **Temperature Grid (°C)**: `[20.0, 25.0, 30.0, 40.0, 50.0]`
- **Capacity Table $Q(T)$ (Ah)**:
  `[1.065214687790664, 1.0635616695823449, 1.0730061548855323, 1.0801900610401025, 1.0809567995408316]`
- **Hysteresis Amplitude Table $M(T)$ (V)**:
  `[0.02701, 0.01719, 0.02436, 0.02155, 0.01988]`
- **Linear Interpolation**: $f(T) = f_k + \frac{T - T_k}{T_{k+1} - T_k} (f_{k+1} - f_k)$ with flat boundary clamping for $T < 20$ °C and $T > 50$ °C.

### Confidence-Aware Initialization Modes
- **Anchored / Known Start (S-A, S-C, S-F)**:
  $\sigma_{\text{soc},0} = \max(0.005, \text{CV-taper gap}(T))$.
  (20 °C: 0.005; 25 °C: 0.005; 30 °C: 0.005; 40 °C: 0.005; 50 °C: 0.005).
- **Unknown Start (S-B)**:
  $\sigma_{\text{soc},0} = 0.10$ ($10\text{ pp}$).
- **Wrongly Confident Start (S-G)**:
  $\sigma_{\text{soc},0} = 0.005$ ($0.5\text{ pp}$).

---

## 4. Scenario Definitions (Verbatim)

### Scenario S-A: Full Profile from Truth Start
- Evaluates full cycle from known start SOC $z_0 = 1.0 - \text{gap}(T)$.
- Initialized with `soc_std = max(0.5 pp, CV-taper gap(T))`. No faults injected.

### Scenario S-B: Unknown Start Recovery (16 cases / temperature)
- Starts at truth SOC $z \in \{0.80, 0.60, 0.40, 0.20\}$.
- Injected start offsets $\Delta z_0 \in \{-10, -5, +5, +10\}\text{ pp}$.
- Initialized with `soc_std = 10 pp` ($0.10$). RC and hysteresis states initialized from truth model.

### Scenario S-C: Partial Plateau Windows with Exact Start (3 cases / temperature)
- Partial cycling windows: $90 \to 40\%$, $80 \to 30\%$, $70 \to 20\%$ truth SOC.
- Exact start: offset $= 0.0\text{ pp}$.
- Initialized with `soc_std = max(0.5 pp, CV-taper gap(T))`. Tests plateau drift immunity.

### Scenario S-G: Wrongly Confident Start (12 cases / temperature)
- Starts at truth SOC $z \in \{0.80, 0.60, 0.40\}$.
- Injected start offsets $\Delta z_0 \in \{-5, -3, +3, +5\}\text{ pp}$.
- Initialized with `soc_std = 0.5 pp` ($0.005$). Tests recovery without error amplification.

### Scenario S-F: Sensor Fault Injection (10 cases / temperature)
- Starts from known start with `soc_std = max(0.5 pp, CV-taper gap(T))`.
- Faults:
  - Current sensor bias: $\pm 10\text{ mA}, \pm 50\text{ mA}$ (4 cases).
  - Voltage sensor offset: $\pm 5\text{ mV}, \pm 10\text{ mV}$ (4 cases).
  - Capacity calibration error: $\pm 3\%$ (2 cases).

---

## 5. Gate Text (Verbatim from Protocol)

### GATE A (A1-007; held-out 40 and 50 C in V3, all four decision temperatures in V5):
```
 (i)    S-A RMSE <= E0 + 2.0 pp AND <= E1 + 1.0 pp.
 (ii-a) S-B group-mean RMSE <= 0.70 x E0 group-mean AND beats E0 in >= 80% of S-B cases.
 (ii-b) S-C mean RMSE per temperature <= E0 + 1.5 pp.
 (ii-c) S-G mean RMSE per temperature <= E0 + 1.0 pp (never meaningfully worse than doing nothing).
 (iii)  S-F mean RMSE <= E0 + 5.0 pp.
```

### GATE B (Set X; 20, 30, 40, 50 C), against fair E0:
```
 (i)   S-A <= E0 + 3.0 pp.
 (ii)  S-B group-mean <= E0 group-mean at every temperature.
 (iii) S-C mean <= E0 + 3.0 pp.
 (iv)  S-G mean <= E0 + 1.5 pp.
```

---

## 6. Freeze Commitment

This specification is **FROZEN**.  
Under Rule R1, US06 and FUDS may be evaluated exactly once in Stage V5 against this frozen specification.  
No parameter, threshold, scenario definition, or algorithm code may be modified, retuned, or rerun after this freeze.
