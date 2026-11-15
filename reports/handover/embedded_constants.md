# Audit of Embedded Constants in Source Tree

**Repository**: `/Users/tecbusiness/Desktop/random/SOC`  
**Date**: 2026-11-15  
**Audit Mechanism**: Abstract Syntax Tree (AST) scanner (`tests/test_no_hardcoded_constants.py`)  
**Allowlist Registry**: `tests/allowlisted_constants.json`  

---

## 1. Context & Purpose

The SOC Estimation Lab enforces strict configuration hygiene to prevent undocumented "magic numbers" from skewing research reproducibility. The repository AST scanner previously verified that numeric literals in `src/soc/` were constrained to fundamental unit transforms (`{0, 1, 2, -1, 3600, 1000, 60}`).

However, historical development bypassed this check in several estimator implementations by wrapping numeric values in string-literal constructors (e.g. `float("0.02")`, `int("4")`). 

In this handover hardening pass:
1. `tests/test_no_hardcoded_constants.py` was extended to intercept all `float("..")` and `int("..")` string-literal calls.
2. An explicit allowlist file (`tests/allowlisted_constants.json`) was generated with architectural justifications for each entry.
3. Because `src/soc/estimators/e7v3.py` is frozen under **Hard Rule R1**, its embedded values are cataloged below.

---

## 2. Non-Trivial Parameters in Frozen E7v3 (`src/soc/estimators/e7v3.py`)

`E7V3CompositeFilter` is frozen with SHA-256 `057f4d8547b00c80306d1ddd55fbac42dc304448f306d4bbd2fdbbb77ab9154e`. The following embedded values remain in the frozen file:

| Category | Constant Identifier | Embedded Value | Engineering Role | Phase 2 Extraction Status |
|:---|:---|:---:|:---|:---|
| **Structural** | `_DIM` | `int("4")` | State dimension $[z, v_{rc1}, v_{rc2}, v_h]^T$ | Retained in `bms_soc_ref.py` |
| **Numerical** | `_EPS_ZERO` | `float("1e-12")` | Numerical covariance flooring | Retained in `bms_soc_ref.py` |
| **Gating** | `_SOC_KNEE` | `float("0.02")` | Lower knee transition threshold ($2\%\text{ SOC}$) | Extracted to `CellCalibration.soc_knee` |
| **Gating** | `_SOC_OBS_THRESH` | `float("0.2")` | Plateau observability boundary ($20\%\text{ SOC}$) | Extracted to `CellCalibration.soc_obs_thresh` |
| **Gating** | `_STEP_CAP_PLATEAU`| `float("1e-5")` | Max innovation step in low-slope plateau | Extracted to `CellCalibration.step_cap_plateau` |
| **Gating** | `_SLOPE_CUTOFF` | `float("0.01")` | OCV slope threshold ($10\text{ mV/pp}$) for gating | Extracted to `CellCalibration.slope_cutoff` |
| **Calibration**| `_Q_REF` | `float("1.0635616695823449")` | CALCE reference capacity at 20 °C | Extracted to `calce_a123_v4.json` |
| **Calibration**| `_M_REF` | `float("0.02155")` | CALCE reference hysteresis at 20 °C | Extracted to `calce_a123_v4.json` |
| **Calibration**| Temperature Grid | `[20.0, 25.0, 30.0, 40.0, 50.0]` | Ambient temperatures for $Q(T), M(T)$ | Extracted to `calce_a123_v4.json` |
| **Calibration**| Capacity Grid | `[1.0652..., 1.0635..., ...]` | $Q(T)$ values across temperature grid | Extracted to `calce_a123_v4.json` |
| **Calibration**| Hysteresis Grid | `[0.02701, 0.01719, ...]` | $M(T)$ half-gap across temperature grid | Extracted to `calce_a123_v4.json` |

> [!NOTE]
> In Phase 2, all tuning and cell-specific constants were factored out into `deliverable/calibration.py` (`CellCalibration`) and serialized in `deliverable/calibrations/calce_a123_v4.json`. The standalone deliverable reference (`deliverable/bms_soc_ref.py`) consumes this configuration cleanly, eliminating all embedded calibration constants from the integration path while preserving exact bit-level parity ($< 10^{-12}$) with the frozen research file.

---

## 3. Other Non-Trivial Parameters in `src/soc/`

### 3.1 Legacy & Intermediate Estimators
- `e2_anchored.py`: Voltage full-charge threshold `float("3.58")` V, duration `float("60.0")` s, hysteresis step `float("0.055")` V.
- `e2_rate_hyst.py`: Embedded 3-rate hysteresis tables across temperatures (`0.01482` to `0.03569` V).
- `e4_rls_r0.py` / `e4v2_rls.py`: RLS covariance scaling and forgetting factor initialization.
- `e5v3.py` / `e5v4.py` / `e7v2.py`: Historical prototype gating thresholds matching the E7v3 parameters.
- `innovation_gating.py`: Innovation gate threshold `float("2.5")` $\sigma$, cutoff `float("0.0004")` V$^2$.

### 3.2 Experimental Neural Hybrid Estimators (`E8`, `E9`, `E10`)
- `e8_residual_gru.py` / `e8_residual_lgbm.py`: Feature scaling boundaries:
  - Current range: `float("-2.5")` A to `float("4.5")` A
  - Voltage range: `float("1.90")` V to `float("3.75")` V
  - Temperature range: `float("15.0")` °C to `float("35.0")` °C
  - Residual bound clamp: `float("0.25")` (25 pp)
  - Window size: `int("32")`, feature count: `int("13")`
- `e9_tcn_ukf.py`: Temporal convolutional network receptive field hyperparameters (kernel size `int("3")`, channels `int("32")`, layers `int("5")`).
- `e10_pinn_aekf.py`: Physics loss weighting factor `float("0.15")`, learning rate `float("1e-6")`.

### 3.3 Data Ingestion (`calce_loader.py`)
- Column indices: Voltage (col 8), Current (col 16), Relative Time (col 24), Step Index (col 5), Cycle Count (col 7), Ambient Temp (col 10).
- Physical bounds: Plausible voltage limits `[float("2.0"), float("3.6")]` V, nominal capacity plausibility `[float("0.75"), float("0.78")]` Ah (for A123 26650 unconditioned fresh cells).

### 3.4 Runtime Sentinels (`runner.py`, `plant.py`, `metrics.py`, `report.py`)
- Standard IEEE floating-point representations: `float("nan")` for uninitialized measurements or invalid metrics, and `float("inf")` for unbounded errors.

---

## 4. Remediation Recommendations for Production Deployment

1. **Cell Parameter Decoupling**: Any estimator promoted to production candidate status must follow the pattern established in `deliverable/calibration.py`, taking all cell characteristics from external configuration files.
2. **Feature Scaler Packaging**: Experimental neural models (E8, E9, E10) must serialize their input/output scalers alongside model weights rather than relying on embedded numeric bounds.
