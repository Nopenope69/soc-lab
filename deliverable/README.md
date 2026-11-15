# Standalone BMS Reference Deliverables

**Repository**: `/Users/tecbusiness/Desktop/random/SOC`  
**Package Scope**: Production-facing reference assets for SOC Estimation.

---

## 1. Certified Deliverables (In-Scope)

1. **`bms_soc_ref.py`**:
   Standalone, dependency-free reference implementation of the **E7v3 Confidence-Aware Composite EKF**. Verified to achieve exact numerical parity ($\le 10^{-12}$) against research filter `E7V3CompositeFilter` across 25,000+ dynamic drive-cycle steps.
2. **`calibration.py`**:
   Strictly validated, stdlib-only cell calibration contract defining `CellCalibration`, complete with monotonicity verification, dimension assertions, and SHA-256 integrity checks.
3. **`calibrations/`**:
   - `calce_a123_v4.json`: Complete 2D OCV, 2RC impedance tables, and gating thresholds for CALCE A123 26650 LFP cells (`DEVELOPMENT_VALIDATED_CALCE_20_50C`).
   - `flexipod_100ah_v1.json`: Extracted profile for FlexiPod 100 Ah cells (`NOT_VALIDATED: open-loop model gate FAIL`).
4. **`golden/`**:
   Deterministic verification vectors (`golden_synthetic_dynamic.csv`, `golden_synthetic_dropouts.csv`) providing bit-level regression tests for porting to C/Rust or target embedded BMS platforms.
5. **`READY_CRITERIA.md`**:
   Formal quality, safety, and operational guardrail specifications required prior to automotive or industrial deployment.

---

## 2. Exploratory / Out-of-Scope Artifacts

The following exploratory research artifacts remain in this directory from earlier proof-of-concept investigations but are formally **OUT OF SCOPE** for the core SOC research handover:
- `soh_phase6_*.json` & `soh_pulse_elasticnet.h`: Early State of Health (SOH) pulse-fitting artifacts.
- `edge_pkg/`: Historical packaging prototype.
- `example_synchronized_telemetry.json`: Sample multi-sensor telemetry log.

*(Experimental neural hybrid models E8, E9, E10 were relocated to `models/experimental/`).*
