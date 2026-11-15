# Embedded BMS Golden Reference Vectors

This directory contains deterministic, bit-accurate golden test vectors generated from `deliverable/bms_soc_ref.py` for porting and validating the E7v3 SOC algorithm in low-level target environments (e.g. C, C++, Rust, or fixed-point firmware).

## File Manifest

1. **`golden_synthetic_dynamic.csv`**:
   - **Steps**: 500 samples
   - **Initial State**: $SOC_0 = 0.85$, $\sigma_0 = 0.005$ (0.5 pp)
   - **Content**: Dynamic discharge pulses (1.5 A), charge pulses (-0.5 A), sinusoidal transitions ($\pm 2.0\text{ A}$), and resting plateaus under fluctuating ambient temperature ($25^\circ\text{C} \pm 5^\circ\text{C}$).
   - **Purpose**: Validates 2RC dynamics, RLS impedance tracking $\theta$, observability slope gating, plateau step capping, and Joseph-form covariance stabilization.

2. **`golden_synthetic_dropouts.csv`**:
   - **Steps**: 200 samples
   - **Initial State**: $SOC_0 = 0.70$, $\sigma_0 = 0.02$ (2.0 pp)
   - **Content**: Signal dropouts including NaN voltage (steps 40–49), NaN current (steps 100–104), and NaN temperature (steps 150–154).
   - **Purpose**: Validates pure Coulomb counting fallback on missing voltage, stale current hold and timeout behavior, temperature sample holding, and status flag telemetry.

## Vector Column Schema

| Column | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `step` | Integer | - | Monotonic sample index $k$ |
| `time_s` | Float | s | Elapsed time |
| `dt_s` | Float | s | Step sample interval $\Delta t$ |
| `voltage_v` | Float | V | Terminal voltage input (`nan` if dropped) |
| `current_a` | Float | A | Terminal current input (`nan` if dropped, $>0$ discharge) |
| `temp_c` | Float | °C | Cell surface temperature input (`nan` if dropped) |
| `soc_est` | Float | fraction | Reference estimated state of charge |
| `soc_std` | Float | fraction | Reference estimated 1-$\sigma$ uncertainty $\sqrt{P_{00}}$ |
| `theta` | Float | dimensionless | Estimated RLS ohmic impedance scaling factor |
| `delta_soc_applied` | Float | fraction | Gated and capped measurement correction applied |
| `status_flags` | String | - | Pipe-separated status flags (e.g. `OK`, `DROPOUT`, `TEMP_INVALID`) |

## Parity Acceptance Criterion

Embedded target implementations running in double-precision floating point (IEEE-754 binary64) should agree with `soc_est` to within:
$$\max |SOC_{\text{target}} - SOC_{\text{golden}}| \le 1.0 \times 10^{-12}$$

For single-precision floating point (IEEE-754 binary32), refer to [`reports/handover/float32_sensitivity.md`](../../reports/handover/float32_sensitivity.md) for expected numerical drift bounds.
