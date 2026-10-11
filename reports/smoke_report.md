# SOC Estimation Benchmark Report

> Synthetic data. Software correctness and comparison only, not accuracy evidence.

## Executive Metadata

- **Active Profile:** `automotive`
- **Git Commit:** `cb780e44fa743e76ace12086ad121af7d9d8db49`
- **Configuration Hash:** `0e6ede89d4009b1d4c00ac3bec2bbf24a556ab1701e8d93ecd830fb21db20c80`
- **Temperature-Clamp Warnings:** `0`

## Benchmark Metric Results

| Scenario | Variant | Estimator | RMSE | MAE | Max Err | P95 Err | Plateau RMSE | Conv 5% | Conv 2% | Drift 24h | Rev Spike | ms/step (med) | V Res (mV) | NIS | Pass All |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `smoke` | `matched` | **E0** | 0.00 pp | 0.00 pp | 0.00 pp | 0.00 pp | 0.00 pp | 1.0 s | 1.0 s | 0.08 pp | 0.00 pp | 0.00 ms | n/a | n/a | PASS |
| `smoke` | `matched` | **E1** | 1.29 pp | 1.19 pp | 1.84 pp | 1.81 pp | 1.29 pp | 1.0 s | 1.0 s | -340.32 pp | 1.84 pp | 0.07 ms | 2.97 | 0.34 | PASS |
| `smoke` | `matched` | **E2** | 0.15 pp | 0.11 pp | 0.46 pp | 0.29 pp | 0.15 pp | 1.0 s | 1.0 s | -87.97 pp | 0.30 pp | 0.07 ms | 2.10 | 0.17 | PASS |
| `smoke` | `mismatched` | **E0** | 0.03 pp | 0.02 pp | 0.04 pp | 0.04 pp | 0.03 pp | 1.0 s | 1.0 s | 10.90 pp | 0.04 pp | 0.00 ms | n/a | n/a | PASS |
| `smoke` | `mismatched` | **E1** | 1.19 pp | 1.08 pp | 2.57 pp | 1.67 pp | 1.19 pp | 1.0 s | 3.0 s | -1862.85 pp | 1.75 pp | 0.07 ms | 4.86 | 0.92 | PASS |
| `smoke` | `mismatched` | **E2** | 1.24 pp | 1.06 pp | 2.55 pp | 1.89 pp | 1.24 pp | 1.0 s | 3.0 s | -1515.43 pp | 0.96 pp | 0.07 ms | 4.35 | 0.73 | PASS |
| *scheduled* | *n/a* | **E3** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |
| *scheduled* | *n/a* | **E4** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |
| *scheduled* | *n/a* | **E5** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |
| *scheduled* | *n/a* | **E6** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |
| *scheduled* | *n/a* | **E7** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |

## Profile Bars & Pass/Fail Evaluation

Pass/fail criteria loaded from active profile `automotive`:

| Bar Name | Threshold | Applied Scenarios | Description |
| :--- | :--- | :--- | :--- |
| `t1_ocv_error_max_mv` | 5.0 mV | `t1_static_ocv` | Model OCV table error against reference |
| `t2_dynamic_rmse_max` | 2.00 pp | `smoke`, `t3_t10_minor_loops` | Dynamic cycling RMSE bar |
| `t2_dynamic_max_error` | 5.00 pp | `smoke`, `t3_t10_minor_loops` | Dynamic cycling maximum error bar |
| `t4_plateau_p95_max` | 3.00 pp | `t4_plateau_stress` | 95th percentile error on plateau |
| `t5_converge_time_s` | 60.0 s | `t5_initial_soc_offset` | Convergence time from 10pp offset |
| `t6_drift_bess_per_day_max` | 1.00 pp | `t6_current_bias` | 24-hour current bias drift bar |
| `t7_error_rise_max` | 1.00 pp | `t7_voltage_quant_noise` | Max error rise under sensor noise |
| `t9_post_rest_step_error_max` | 2.00 pp | `t9_rest_relaxation` | Max error during RC relaxation |
| `t10_reversal_spike_max` | 3.00 pp | `t3_t10_minor_loops` | Error spike after direction reversal |
| `t14_auto_max_ms_per_step` | 5.0 ms | all scenarios | Median computation latency per step |

### Pass / Fail Matrix

| Estimator | Variant | `smoke` | Overall |
| :--- | :--- | :--- | :--- |
| **E0** | `matched` | PASS | **PASS** |
| **E0** | `mismatched` | PASS | **PASS** |
| **E1** | `matched` | PASS | **PASS** |
| **E1** | `mismatched` | PASS | **PASS** |
| **E2** | `matched` | PASS | **PASS** |
| **E2** | `mismatched` | PASS | **PASS** |

**First Rung Meeting All Bars:** `E0 (matched)`

## T1 OCV Model Check

> Evaluates model OCV table error against reference plant OCV table across temperature calibration points.

| Temperature | Max Error (mV) | RMS Error (mV) | Bar Threshold | Result |
| :--- | :--- | :--- | :--- | :--- |
| `15.0 C` | 0.00 mV | 0.00 mV | 5.0 mV | PASS |
| `25.0 C` | 0.00 mV | 0.00 mV | 5.0 mV | PASS |
| `35.0 C` | 0.00 mV | 0.00 mV | 5.0 mV | PASS |

## Diagnostic Observations

- **Hysteresis Performance:** With plant hysteresis active (15.0 mV), E2 achieved plateau RMSE 0.69 pp vs E1 1.24 pp.

## Assumptions Audit Summary

- **Placeholder Parameters:** `56`
- **Assumed Parameters:** `20`
- **Zero-Constants Rule:** All physical parameters, sensor limits, and noise parameters are strictly loaded from YAML configuration.

---
*Report generated for SOC Benchmark Lab.*
