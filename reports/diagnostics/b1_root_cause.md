# Root Cause Diagnostic Report: Phase B CALCE A123 Benchmark Failure

This report identifies the root causes of the ~30 pp estimation error observed on estimators E2, E5, and E6 during Phase B of the CALCE A123 benchmark (`reports/calce_a123_verdict.md`). All findings are strictly grounded in diagnostic scripts executed in `scripts/diagnostics/` and output logs in `reports/diagnostics/`.

---

## 1. Root Cause Statement

**Primary Root Cause (Confidence: 99% — Confirmed by D4, D5, D6): Hysteresis Double-Counting & Identification Inconsistency.**  
In `scripts/identify_calce_params.py` (lines 113–157), the 2RC polarization parameters ($R_0, R_1, \tau_1, R_2, \tau_2$) were identified against dynamic DST data using an objective function without a hysteresis voltage state ($v_{\text{model}} = v_{\text{ocv}} - R_0 i - v_1 - v_2$), where $v_{\text{ocv}}$ was defined as the symmetric mean of the C/20 charge and discharge branches ($v_{\text{ocv}} = \frac{v_{\text{dis}} + v_{\text{chg}}}{2}$). Because DST is a unidirectional discharge test ($I > 0$), the optimizer forced the 2RC polarization resistances to absorb the entire ~65 mV voltage separation between the equilibrium OCV and the measured terminal voltage. However, estimators E2, E5, and E6 evaluate $v_{\text{hat}} = v_{\text{ocv}} + M \cdot h - R_1 i_1 - R_2 i_2 - R_0 i$. Under continuous discharge, $h \to -1$, subtracting $M \approx 64.6\,\text{mV}$ **a second time**. This introduces a persistent +40 to +50 mV open-loop voltage error ($V_{\text{meas}} - V_{\text{hat}} > 0$). Because the cell is an LFP chemistry with a wide, flat plateau where $d V_{\text{ocv}}/dz < 0.5\,\text{mV/pp}$, this 40–50 mV model discrepancy forces the Kalman filter correction to drag the estimated SOC upwards by +25 to +35 pp. Setting $M = 0$ at runtime collapses the E2 SOC RMSE from **32.48 pp down to 6.33 pp** on US06 and from **27.59 pp down to 4.65 pp** on FUDS with zero refitting (D6).

**Secondary Root Cause (Confidence: 95% — Confirmed by D7): Top-Knee Initialization Masking & Reset Clamping.**  
The benchmark tested initial SOC offset robustness exclusively from fully charged states ($z = 1.0$). In `reset()`, positive offsets (+10 pp, $z_0 = 1.10$) were immediately clamped to 1.00 by `min(max(z, 0), 1)`. For negative offsets ($z_0 \le 0.95$), the cell initialized in the steep upper knee ($z > 0.90$, $d V_{\text{ocv}}/dz > 10\,\text{mV/pp}$) where the large initial state covariance ($P_0 = 0.01$) generated enormous Kalman gains that erased the entire offset within 0 to 5 seconds. The test never evaluated offset convergence on the unobservable plateau.

**Tertiary Root Cause (Confidence: 95% — Confirmed by D1, D2): Capacity Scale Mismatch on E0.**  
All estimators were initialized with a static nominal capacity ($1.0636\,\text{Ah}$, measured at 25 °C) across all temperatures, whereas ground-truth Coulomb counting used the measured C/20 capacity at each operating temperature ($1.0652\,\text{Ah}$ at 20 °C to $1.0810\,\text{Ah}$ at 50 °C). This explains 100% of the minor E0 error progression across temperature (0.01 pp at 25 °C up to 0.94 pp at 50 °C).

---

## 2. Suspected Causes vs Diagnostic Evidence

| Suspected Cause | Diagnostic Script & Number | Evidence & Findings | Verdict |
| :--- | :--- | :--- | :---: |
| **Double-counting hysteresis drop** | `scripts/diagnostics/d6_hysteresis_ablation.py`<br>`scripts/diagnostics/d4_open_loop_voltage.py` | Setting $M=0$ drops E2 RMSE from 32.48 to 6.33 pp (US06) and 27.59 to 4.65 pp (FUDS). Open-loop voltage residual with $M=64.6\,\text{mV}$ has mean +49.0 mV; with $M=0$ it drops to -1.9 mV. | **CONFIRMED** |
| **Model identification formulation error** | `scripts/diagnostics/d5_training_error.py`<br>`scripts/diagnostics/d4_open_loop_voltage.py` | Training error on DST itself exhibits 28.72 to 30.34 pp SOC RMSE across 20–50 °C. The failure is not overfitting to DST or generalization failure to US06/FUDS. | **CONFIRMED** |
| **Initial offset insensitivity from knee/clamping** | `scripts/diagnostics/d7_offset_insensitivity.py` | `reset(1.10)` clamped to 1.00 immediately. Negative offsets (-20 pp, -10 pp) converge to baseline within 0.0 s (1 step) due to steep upper knee ($d V/dz > 10\,\text{mV/pp}$) and large $P_0$. | **CONFIRMED** |
| **Flat LFP plateau slope amplifying voltage error** | `scripts/diagnostics/d9_plateau_quantification.py` | $d V_{\text{ocv}}/dz$ drops to 0.28–0.38 mV/pp between 40% and 70% SOC. A 5 mV residual implies 13–18 pp SOC error; a 45 mV residual implies >100 pp error. | **CONFIRMED** |
| **Fixed vs temp-scheduled capacity mismatch on E0** | `scripts/diagnostics/d2_capacity_states.py` | Theoretical ramp error from $1.0636\,\text{Ah}$ vs $C/20$ capacity predicts E0 RMSE of 0.09, 0.00, 0.51, 0.90, 0.94 pp across 20–50 °C. Matches Table 1 E0 RMSE exactly. | **CONFIRMED** |
| **Anchor gap between OCV test (10 mA) & dynamic (55 mA)** | `scripts/diagnostics/d8_anchor_gap.py` | CV taper from 55 mA to 10 mA injects 0.21 to 2.05 pp of additional charge (mean 0.79 pp; 2.05 pp at 25 °C). Causes dynamic cycles to start below nominal 100% full charge. | **CONFIRMED** |
| **Ground-truth Coulomb counting error / regen leakage** | `scripts/diagnostics/d10_ground_truth_sanity.py` | Net Coulomb integration matches $Q_{\text{dis}} - Q_{\text{chg}}$ to within $2.22\times 10^{-16}\,\text{Ah}$. Final truth SOC matches $1 - Q/Q_{C/20}$ to $5.44\times 10^{-15}$. | **REJECTED** |
| **Loader file confusion or 20 C / 25 C swap** | `scripts/diagnostics/d1_loader_checks.py` | 20120809 .xls files properly excluded; 20120817 .xlsx used. 25 C OCV sheet swap correctly mapped. Repo sign convention ($I > 0$ discharge) correctly applied. | **REJECTED** |
| **Dynamic profile drive-cycle overfitting** | `scripts/diagnostics/d5_training_error.py` | DST (training set) error is identical (~29 pp) to US06 and FUDS (test sets). | **REJECTED** |

---

## 3. Concrete Code and Configuration Defects

*(Per Hard Rule 1 & 3, fixes are specified below but have NOT been applied to source files).*

### Defect 1: Omission of Hysteresis State during 2RC Least-Squares Parameter Fitting
- **File:** `scripts/identify_calce_params.py`
- **Lines:** 151–157
- **Current Defective Code:**
  ```python
  def residuals(p):
      r0, r1, tau1, r2, tau2 = p
      alpha1 = np.exp(-dt_full / tau1)
      alpha2 = np.exp(-dt_full / tau2)
      v1 = np.zeros_like(i_stream)
      v2 = np.zeros_like(i_stream)
      for k in range(len(i_stream) - 1):
          v1[k+1] = alpha1[k+1] * v1[k] + r1 * (1.0 - alpha1[k+1]) * i_stream[k]
          v2[k+1] = alpha2[k+1] * v2[k] + r2 * (1.0 - alpha2[k+1]) * i_stream[k]
      v_model = v_ocv_stream - r0 * i_stream - v1 - v2
      return (v_stream - v_model)[idx_sub]
  ```
- **Defect Mechanism:** The optimizer evaluates $v_{\text{model}}$ against equilibrium $v_{\text{ocv}}$ without subtracting $M \cdot h$. Because current is positive discharging, true terminal voltage sits on the lower hysteresis branch ($v \approx v_{\text{ocv}} - M$). The optimizer inflates $R_0, R_1, R_2$ to bridge this gap. Later, when E2/E5/E6 run, $M \cdot h$ ($h \to -1$) is subtracted again, double-counting the hysteresis drop by 65 mV.
- **Proposed Fix:** Include the simulated hysteresis state $h(t)$ directly inside the residual function:
  ```python
  # Simulate h_stream using Cell2RCModel.step_hysteresis with m_hyst_raw
  v_model = v_ocv_stream + m_hyst_raw * h_stream - r0 * i_stream - v1 - v2
  ```
  Or alternatively, fit the 2RC model directly to the measured low-current discharge OCV branch ($v_{\text{dis}}$) with $M = 0$.

### Defect 2: Inappropriate Parameterization in Profiles (`calce_a123.yaml` & `calce_a123_a1008.yaml`)
- **File:** `configs/assumptions/profiles/calce_a123.yaml` (lines 256–264) and `configs/assumptions/profiles/calce_a123_a1008.yaml` (lines 256–264)
- **Lines:**
  ```yaml
  hysteresis_amplitude_v:
    value: 0.0646
    unit: V
    status: measured
  ```
- **Defect Mechanism:** Setting `hysteresis_amplitude_v: 0.0646` when the resistances were fitted with $M=0$ causes all hysteresis-aware estimators to fail.
- **Proposed Fix:** Either set `hysteresis_amplitude_v: 0.0` for the current parameter set, or re-identify the resistance tables with hysteresis included in the loop.

### Defect 3: Data Leakage in E5 Variant Selection
- **File:** `scripts/evaluate_calce.py`
- **Lines:** 327–330
- **Current Defective Code:**
  ```python
  # Determine better E5 variant on gating baseline
  e5v1_med = r1_medians["E5 v1"]
  e5v2_med = r1_medians["E5 v2"]
  better_e5 = "E5 v1" if e5v1_med < e5v2_med else "E5 v2"
  ```
- **Defect Mechanism:** `r1_medians` was computed over `df_gate_base`, which consists exclusively of **US06 and FUDS** (the sealed test drive cycles). Choosing the variant based on sealed test performance violates pre-registration isolation.
- **Proposed Fix:** Select `better_e5` based strictly on the training profile (DST) performance:
  ```python
  # Select better E5 variant using DST training data only
  e5v1_dst = df_dst_base[df_dst_base["estimator"] == "E5 v1"]["rmse"].median()
  e5v2_dst = df_dst_base[df_dst_base["estimator"] == "E5 v2"]["rmse"].median()
  better_e5 = "E5 v1" if e5v1_dst < e5v2_dst else "E5 v2"
  ```

### Defect 4: Missing `Any` Import in Registry
- **File:** `src/soc/estimators/registry.py`
- **Lines:** 7, 26, 39
- **Current Defective Code:**
  ```python
  from typing import Dict, List, Type
  ...
  def step(self, measurement: Any) -> Any:
  ```
- **Defect Mechanism:** `Any` is used in annotations without being imported from `typing`, throwing `NameError` if stubs are inspected.
- **Proposed Fix:** Update line 7:
  ```python
  from typing import Any, Dict, List, Type
  ```

### Defect 5: Cell Part Number Misattribution in Verdict & Plan
- **File:** `reports/calce_a123_verdict.md` (line 15), `PLAN_ADAPTER.md`
- **Defect Mechanism:** The verdict labels the cell as `ANR26650M1-A` (which is a 2.3–2.5 Ah cell), whereas the CALCE dataset contains 1.11 Ah cells (consistent with A123 18650 APR18650M1A or early 1.1 Ah 26650 research cells).
- **Proposed Fix:** Update documentation and dataset cards to state `A123 Systems 1.11 Ah LFP (APR18650M1A / 26650 1.1 Ah specimen)`.

---

## 4. Audit of Known Repo Issues

1. **`registry.py` missing the `Any` import:**  
   **STILL PRESENT.** Line 7 imports `Dict, List, Type` only. Lines 26 and 39 reference `Any`. If type evaluation or runtime stub checking is invoked, `NameError: name 'Any' is not defined` occurs.
2. **CSV `pass_all_bars` flag being vacuous when no bar applies:**  
   **STILL PRESENT.** In `src/soc/harness/runner.py` (lines 465–551), `check_pass_bars` initializes `failed = []`. If a scenario has no bar defined, `failed` remains empty, returning `passed = True`. Line 740 sets `pass_all_bars = passed and not meta["is_invalid_extreme"]`, writing `True` to CSV exports for scenarios where no bars existed.
3. **T12 mismatch bar not being enforced:**  
   **STILL PRESENT.** In `src/soc/harness/runner.py` (lines 478–550), `check_pass_bars` explicitly handles `smoke`, `t3_bess_24h`, `t4_plateau_stress`, `t5_initial_soc_offset`, `t6_current_bias`, `t7_voltage_quant_noise`, `t9_rest_relaxation`, `t3_t10_minor_loops`, and `t14_auto_max_ms_per_step`. Scenario `t12_hysteresis_mismatch` is completely omitted from `check_pass_bars`.

---

## 5. Audit of Phase B Pass Rules vs Pre-Registration

| Rule | Pre-Registration Text | How Phase B Actually Scored It | Deviation / Flaw Identified |
| :--- | :--- | :--- | :--- |
| **Rule 2: No Harm** | "within 0.3 pp of E2 RMSE in >= 80% of gating cases" | Evaluated in `scripts/evaluate_calce.py` line 343 as:<br>`abs(e5_val - e2_val) <= 0.3 or (e5_val <= e2_val + 0.3)` | **Scored One-Sided.** The code allowed any case where E5 had lower RMSE than E2 to count as "within 0.3 pp". If E5 was 20 pp better, it was treated as passing "within 0.3 pp". |
| **Rule 3: Recovery** | "under +-10 pp initial offset, better E5 within 2 pp of E2 RMSE on average" | Evaluated exclusively at $z_0 = 1.0$ (start of drive cycle). Evaluated in line 367 as:<br>`r3_diff <= 2.0 or (e5_soc_mean <= e2_soc_mean + 2.0)` | **Knee-Only & Clamped.** +10 pp was clamped to 1.00 at reset; -10 pp was initialized at the steep upper knee where huge $d V/dz$ snapped the error to 0 in <5 seconds. It never evaluated plateau offset recovery. |
| **Rule 4: Cell Transfer** | "best estimator on A1-008 with A1-007 parameters has RMSE <= 1.5x own fit" | Evaluated on E6 (best of E2, E5, E6). Transferred RMSE was compared to own-fit RMSE. | **Own Fit Worse Than Transfer.** In 6 out of 10 gating cases on A1-008, the "own fit" yielded **higher** RMSE than transferred parameters (e.g. 20 C FUDS: 17.19 pp transferred vs 22.76 pp own fit, ratio 0.76x). The rule passed trivially because the denominator was inflated by an even worse own fit. |

---

## 6. Recommendations for Phase B2 Pre-Registration

To ensure Phase B2 produces rigorous, publication-grade benchmark results on the CALCE A123 dataset, the following changes should be formalized in the B2 pre-registration:

1. **Synchronize Identification Model with Estimator Observation Equations:**
   - In parameter identification, the 2RC equivalent circuit fitting must include the hysteresis equation with the measured $M$, OR the OCV table must be defined strictly from the low-current discharge branch with $M = 0$.
2. **Strict Sealed-Split Isolation for Variant Selection:**
   - The selection of the primary E5 variant (v1 vs v2) must be frozen based solely on DST (training) data before unsealing US06 and FUDS.
3. **Mid-Plateau Initial Offset Benchmark (True Observability Test):**
   - Because CALCE drive cycles start at 100% full charge (where voltage rapidly resets the state), add a synthetic mid-plateau initialization test by starting the estimator at sample index $k$ where truth $\text{SOC} \approx 50\%$ with an injected $\pm 10$ pp offset.
4. **Two-Sided Rule 2 Scoring:**
   - Enforce symmetric bounds: `abs(e5_rmse - e2_rmse) <= 0.3` for the "no harm" check.
5. **Temperature-Scheduled Nominal Capacity:**
   - Pass temperature-dependent capacity $Q_n(T)$ to estimators, or benchmark estimators with a calibrated Coulomb counter that accounts for capacity variation.
6. **Accounting for the 55 mA vs 10 mA Charge Taper:**
   - Account for the initial state-of-charge offset at dynamic cycle start ($\sim 0.8$ to $2.0$ pp below 1.000) when calculating reference ground truth, or align initial estimator state to the true post-CV state.
