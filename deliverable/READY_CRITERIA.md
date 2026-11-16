# Production READY Criteria for SOC Estimators

**Target Chemistries**: LFP (Lithium Iron Phosphate) Cells and Packs  
**Algorithms**: E7v3 (Composite Adaptive EKF), E8-LGBM (Physics-Guided Residual LightGBM), E8-GRU, E9-TCN-UKF, E10-PINN-AEKF  
**Status**: Formal Quality & Safety Specification (No criteria relaxed)

---

## 1. Safety & Architecture Criteria

1. **No Silent Fallback (Operational Status Transparency)**
   - Every estimator step returns an explicit, observable execution record:
     - `model_loaded: bool`: True if neural/tree weights were successfully located and loaded.
     - `fallback_active: bool`: True if the estimator had to delegate to the underlying physics filter due to missing weights, sensor dropout, or input range violations.
   - Transparent or unflagged degradation to physics integration or Coulomb counting without assertion of `fallback_active=True` is strictly prohibited.

2. **Input-Range Guardrails (Out-of-Distribution Protection)**
   - All incoming telemetry measurements ($I_k, V_k, T_k$) must be validated against the certified envelope of the loaded calibration file prior to inference.
   - The operational bounds are defined in the calibration JSON (e.g., `calce_a123_v4.json` specifies `temp_min_c`, `temp_max_c`, `v_min_v`, `v_max_v`, `i_min_a`, `i_max_a`). Hardcoded bounds must not be used.
   - If any observable quantity falls outside the calibration envelope, the algorithm must assert `OUT_OF_ENVELOPE` in `status_flags`. For hybrid estimators (E8–E10), this also triggers `fallback_active=True` and routes computation to the physical filter backbone.

3. **Physics-Tied Residual Clamping (`PROPOSED`)**
   - Tree and neural corrections must be bounded by a dynamic confidence envelope tied directly to the physics filter's own estimation error standard deviation:
     $$\Delta z_{\text{clamp}} = \min\left(0.25, \, k_{\sigma} \cdot \sigma_{\text{soc}}\right) \quad \text{with } k_{\sigma} = 3.0$$
   - This ensures that when the physical Kalman filter has converged ($\sigma_{\text{soc}} \approx 0.005$–$0.015$), residual corrections are restricted to $\le 1.5\text{ to } 4.5\text{ pp}$, preventing non-physical jumps from unmodeled dynamics. Conversely, during uncalibrated starts ($\sigma_{\text{soc}} \ge 0.08$), up to 25 pp of correction is permitted to accelerate recovery.

---

## 2. Validation & Deployment Criteria (Unchanged & Unrelaxed)

4. **Pack-Level Thermal Gradients**
   - Validate filter behavior when cell temperatures diverge across modules ($\Delta T > 5\text{ }^\circ\text{C}$ across pack). Enforce module-level or cell-level parameter scheduling.

5. **Cell Aging Beyond Fresh Baseline**
   - Characterize capacity fade ($Q < 80\%\text{ SOH}$), internal resistance growth ($R_0 > 2\times\text{ BOL}$), and subtle OCV flattening in aged cells. Couple estimator with an online SOH/capacity tracking loop.

6. **Sustained Partial-SOC Cycling**
   - Validate packs cycled strictly between 30% and 70% SOC for 3+ weeks without top or bottom knee entry under realistic AFE sensor noise.

7. **Real BMS Current Sensor Imperfections**
   - Validate performance against production shunt or Hall-effect sensors exhibiting $\pm 10\text{ to } 50\text{ mA}$ thermal zero-point drift, 1/f noise, and ADC quantization.

8. **High-Frequency Inverter Ripple**
   - Characterize filter response to 100 Hz - 20 kHz current ripple from traction inverters or power electronics, verifying that anti-aliasing hardware filters protect terminal voltage sampling.


---

## Errata

- **Envelope bounds (Hardening 2):** Earlier versions of criterion 2 cited specific E8 neural-model training bounds (15–35 °C, ±4.5 A, 1.90–3.75 V). The correct operational envelope is defined by the loaded calibration file. For `calce_a123_v4.json`, the certified E7v3 envelope is: temperature 20–50 °C, voltage 2.0–3.7 V, current −20 A to +50 A.
- **Criteria count:** The "7 criteria" reference in historical reports (`reports/gauntlet_v3/archive/ALGORITHM_SPEC_v3.3.md`) reflects an earlier count; this document lists 8 criteria.
- **`model_loaded` / `fallback_active` for E7v3:** E7v3 is a pure physics filter with no external weight files and no fallback path. These fields are constant `True` / `False` respectively. Criterion 1 applies primarily to hybrid estimators (E8–E10) that load trained weights and can delegate to the underlying physics filter.
