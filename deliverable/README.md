# Standalone BMS Reference Deliverables

**Repository**: `/Users/tecbusiness/Desktop/random/SOC`  
**Package Scope**: Production-facing reference assets for SOC Estimation and Edge Deployment.

---

## 1. Certified Deliverables (In-Scope)

1. **`bms_soc_ref.py`**:
   Standalone, dependency-free reference implementation of the **E7v3 Confidence-Aware Composite EKF**. Verified to achieve exact numerical parity ($\le 10^{-12}$) against research filter `E7V3CompositeFilter` across 25,000+ dynamic drive-cycle steps. Supports optional `capacity_scale` ($SOH_C$) input.
2. **`calibration.py`**:
   Strictly validated, stdlib-only cell calibration contract defining `CellCalibration`, complete with monotonicity verification, dimension assertions, and SHA-256 integrity checks.
3. **`calibrations/`**:
   - `calce_a123_v4.json`: Complete 2D OCV, 2RC impedance tables, and gating thresholds for CALCE A123 LiFePO4 cells (measured capacity about 1.06 Ah (A1-007) and about 1.09 Ah (A1-008) at 25 C, format unverified) (`DEVELOPMENT_VALIDATED_CALCE_20_50C`).
   - `flexipod_100ah_v1.json`: Extracted profile for FlexiPod 100 Ah cells (`NOT_VALIDATED: open-loop model gate FAIL`).
4. **`golden/`**:
   Deterministic verification vectors (`golden_synthetic_dynamic.csv`, `golden_synthetic_dropouts.csv`) providing bit-level regression tests for porting to C/Rust or target embedded BMS platforms.
5. **`edge_pkg/`**:
   Self-contained embedded C library (`bms_soc_edge.h`, `bms_soc_edge.c`, `soh_pulse_elasticnet.h`, `soh_pulse_elasticnet.c`, `soh_edge_types.h`) implementing fixed-memory, MISRA-C/C99 compliant state estimation with ASAN/UBSAN test harness.
6. **`READY_CRITERIA.md`**:
   Formal quality, safety, and operational guardrail specifications required prior to automotive or industrial deployment.

---

## 2. Relocated Historical Artifacts

Historical SOH qualification audit JSON files and telemetry logs previously in this directory have been relocated to `reports/soh/` alongside an explanatory README.
