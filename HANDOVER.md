# SOC Estimation Lab: Formal Research Handover

## Status Block

> **SOC Estimation Lab - Research Handover. E7v3 is the current research candidate. It has demonstrated promising results on CALCE A123 development datasets across the documented 20-50 C envelope. It has not been field-validated. Transfer to FlexiPod has been investigated, but the open-loop 2RC model gate failed. FlexiPod deployment is not approved. The standalone BMS reference implementation requires a validated cell-calibration interface, reproducible packaging and target-platform qualification before integration.**

---

## 1. Algorithmic Value Proposition

Battery engineers frequently ask: *"If Coulomb counting is computationally trivial, why deploy a composite Kalman filter?"*

### Where E7v3 Provides Definite Value
1. **Recovery from Unknown or Confidently Wrong Initial SOC**:
   Pure Coulomb counting possesses zero corrective feedback: if the battery boots with a 20 pp or 50 pp error, Coulomb counting preserves that exact error indefinitely until an anchor fires or the pack hits hard cutoff. E7v3 continuously evaluates observable voltage gradients outside the flat plateau, driving the estimate toward truth during active driving without requiring rest periods.
2. **Anchor-Free Drift Attenuation**:
   In applications with continuous partial-SOC cycling where cells rarely reach full charge ($100\%$) or rest long enough to equilibrate, current sensor zero-point drift accumulates linearly. E7v3 continuously leverages transient overpotential dynamics and knee transitions to bound integration error.

### Where Coulomb Counting Is Superior
On nominal duty cycles with known initial state, accurate current sensing, and known capacity $Q(T)$, **fair anchored Coulomb counting is as good or better than any Kalman filter**. In flat LFP plateaus ($0.12\text{--}0.25\text{ mV/pp}$), voltage provides almost zero observability; Kalman filter innovation updates in this region risk injecting sensor noise rather than information. E7v3 addresses this by explicitly gating innovation in the plateau.

---

## 2. Initialization & Recovery Contract

The BMS firmware must interact with `BmsSocEstimatorRef` following a strict operational contract:

### 2.1 Power-Up SOC Sources
When the BMS microcontroller boots:
1. **Relaxed Rest Anchor (Preferred)**: If pack terminal current has remained $< 10\text{ mA}$ for $\ge 3600\text{ s}$, look up equilibrium OCV at ambient temperature $T$. Set:
   ```python
   soc0 = calibration.invert_ocv(v_measured, temp_c)
   soc_std = 0.01  # 1 pp confidence
   estimator.reset(soc0, soc_std=soc_std)
   ```
2. **NVRAM Saved State (Clean Shutdown)**: If power-down was clean and sleep duration was short ($< 24\text{ hours}$):
   ```python
   soc0 = nvram.read_last_soc()
   soc_std = 0.02  # 2 pp confidence
   estimator.reset(soc0, soc_std=soc_std)
   ```
3. **Lost / Corrupt / Brownout Recovery**: If NVRAM is corrupt or sleep duration is unknown, **never default to 100% or 0%**:
   ```python
   soc0 = 0.50     # Mid-plateau nominal
   soc_std = 0.20   # High uncertainty (P0 = 0.04)
   estimator.reset(soc0, soc_std=soc_std)
   ```

### 2.2 Recovery Time Horizon
When initialized with an uncalibrated or wrong start ($|e_0| = 20\text{ to }50\text{ pp}$), convergence to within $\pm 5\text{ pp}$ of truth SOC is governed by dynamic excitation:
- **Median Convergence Time**: **~44 minutes**
- **90th Percentile Convergence Time**: **~77 minutes**
- **Lower Knee Snap Guarantee**: At the $2.5\text{ V}$ discharge cutoff ($z \le 0.05$), the steep lower knee slope ($> 50\text{ mV/pp}$) provides near-infinite observability, snapping all estimators to **$0.0\text{ pp}$ error** and preventing over-discharge regardless of prior tracking offset.

---

## 3. Explicit Boundary: SOC vs SOH

> [!WARNING]
> **This repository estimates State of Charge (SOC) ONLY.**
> - State variable $z_k \in [0, 1]$ represents the fraction of usable capacity currently remaining in the cell.
> - E7v3 does **NOT** track battery State of Health (SOH), capacity degradation, or calendar/cycle aging.
> - While E7v3 adaptively estimates high-frequency polarization resistance $R_0$ via RLS for filtering precision, this fast dynamic estimate must not be confused with electrochemical degradation aging.
> - Long-term capacity fade ($Q$) must be supplied to `CellCalibration` by an independent, qualified SOH tracking service.
> - **SOH Evaluation Findings (Task V2 / UConn Dataset 5):** Laboratory evaluation of pulse-based SOH estimation demonstrated that:
>   1. The pulse ElasticNet (`soh_pulse_v2`) has **not been shown to outperform ridge regression or cycle-count baselines** on UConn REIL Dataset 5.
>   2. **$SOH_R$ shows no evidence of skill** (ground-truth label and features are derived from the identical Step 20 pulse; a trivial baseline matches or beats the model).
>   3. The embedded C export (`deliverable/edge_pkg/soh_pulse_elasticnet_v2.h`) was exported from the 11-feature post-hoc candidate modified after unsealing and is strictly **`UNQUALIFIED`**.
>   4. **Nothing is validated for 100 Ah cells** (all real degradation data are strictly confined to 1.2 Ah cylindrical LithiumWerks 18650 power cells).

---

## 4. Open Decisions Register (Hardening Pass)

The following architectural decisions were resolved during the hardening pass:

| Decision ID | Area | Resolution Implemented | Safety / Architectural Justification |
|:---|:---|:---|:---|
| **DEC-01** | Measurement Dropouts | Zero current propagation with covariance inflation; assertion of `DROPOUT` flag | Prevents un-gated open-loop drift while transparently alerting downstream BMS monitors |
| **DEC-02** | Invalid / Non-Physical Inputs | Flag-only guard (`V_OUT_OF_RANGE`, `I_OUT_OF_RANGE`); preserve step cap | Halting execution or clamping cap caused bit-level divergence on cutoff transitions; flags allow BMS supervisor to intervene |
| **DEC-03** | Deprecated E7 Stub | Mark unversioned `E7` as deprecated alias raising `NotImplementedError` directing to `e7v3` | Eliminates ambiguity between historical stub and certified `e7v3` research candidate |
| **DEC-04** | Experimental Neural Models | Relocated `.pt` and `.txt` weights out of `deliverable/` to `models/experimental/` | Keeps BMS delivery footprint dependency-free, standard-library only, and free of unvalidated ML artifacts |
| **DEC-05** | FlexiPod Baselines | Retain explicit NO-GO verdict; added nominal-capacity E0 baseline | Prevents unvalidated vehicle deployment while honestly documenting Coulomb-counting capacity mismatch |
| **DEC-06** | Reference Parity Discrepancy on Non-CALCE Calibrations | Documented discrepancy in reports; deferred code alignment | `deliverable/bms_soc_ref.py` uses the calibration file's capacity and temperature-dependent $Q(T)$ table directly, whereas research `src/soc/estimators/e7v3.py` linearly scales CALCE's $Q(T)$ curve by nominal capacity. On non-CALCE calibrations (e.g. GE105), they diverge by up to 3.61 pp when perturbed in-envelope and up to 9.82 pp out-of-envelope. A future refactor must align them (either by updating research e7v3 or the reference implementation). |

---

## 5. Handover Ownership & Team Responsibilities

| Role / Responsibility | Team / Contact | Key Deliverables Owned |
|:---|:---|:---|
| **Algorithm Research & Core Theory** | Antigravity Battery Estimation Team | `src/soc/`, `docs/ALGORITHM_SPEC.md`, `configs/assumptions/` |
| **Embedded BMS Integration** | Embedded Firmware Group | `deliverable/bms_soc_ref.py`, `deliverable/golden/`, MicroPython / C porting |
| **Cell Characterization & Calibration** | Electrochemical Testing Laboratory | `deliverable/calibration.py`, `deliverable/calibrations/*.json`, HPPC / OCV extraction |
| **Vehicle Transfer Qualification** | Vehicle Powertrain Engineering | FlexiPod 2RC re-identification, thermal coupling, field validation gates |

---

## 6. System Status & Scope Notes (Hardening 2)

- **Remaining Useful Life (RUL):** Design specification only (`docs/rul_subsystem_design.md`). There is **zero executable code for RUL in `src/soh/`**.
- **FlexiPod Dataset:** Contains beginning-of-life (BOL) characterization data only (`reports/flexipod1/`); no cycle degradation data or aged cell measurements.
- **HPPC Cohort:** Analytical simulation generated via `StandardizedHppcCohortGenerator` (`src/soh/data/pulse_hppc_cohort.py`), not physically measured test-bench hardware.
- **SOH Research Status (Task V2 / UConn):** Pulse ElasticNet has not been shown to outperform ridge or cycle-count baselines on UConn; SOH_R shows no evidence of skill; the C export (`soh_pulse_elasticnet_v2.h`) comes from the 11-feature post-hoc candidate and is `UNQUALIFIED`; and nothing is validated for 100 Ah cells.

