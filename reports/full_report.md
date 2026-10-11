# SOC Estimation Benchmark Report

> Synthetic data. Software correctness and comparison only, not accuracy evidence.

## Executive Metadata

- **Active Profile:** `automotive`
- **Git Commit:** `4b413b25066c16826c5ee2082d80865361635b74`
- **Configuration Hash:** `7b9295c6c848b422834e1abb9c188b4626b666da359a3116ec8b9284763c2c03`
- **Scenarios Evaluated:** `8`
- **Random Seeds per Scenario:** `10`
- **Estimators Evaluated:** `3` (E0, E1, E2)
- **Temperature-Clamp Warnings:** `0`

## Benchmark Metric Results

> Statistics computed across 10 random seeds: format is `mean ± std (worst)`.

| Scenario | Variant | Estimator | RMSE | MAE | Max Err | P95 Err | Plateau RMSE | Conv 5% | Conv 2% | Drift 24h | Rev Spike | ms/step (med) | V Res (mV) | NIS | Pass All |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `t1_static_ocv` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t1_static_ocv` | `matched` | **E1** | 1.28 ± 0.71 pp (w: 2.73 pp) | 1.10 ± 0.68 pp (w: 2.65 pp) | 2.32 ± 0.96 pp (w: 4.20 pp) | 2.03 ± 0.95 pp (w: 4.02 pp) | 1.28 ± 0.71 pp (w: 2.73 pp) | 1.0 ± 0.0 s (w: 1.0 s) | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.21 ± 0.46 | 0.16 ± 0.07 | PASS |
| `t1_static_ocv` | `matched` | **E2** | 1.21 ± 0.66 pp (w: 2.54 pp) | 1.03 ± 0.63 pp (w: 2.47 pp) | 2.20 ± 0.90 pp (w: 3.96 pp) | 1.91 ± 0.88 pp (w: 3.77 pp) | 1.21 ± 0.66 pp (w: 2.54 pp) | 1.0 ± 0.0 s (w: 1.0 s) | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.22 ± 0.46 | 0.16 ± 0.07 | PASS |
| `t1_static_ocv` | `mismatched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t1_static_ocv` | `mismatched` | **E1** | 5.63 ± 0.89 pp (w: 7.53 pp) | 5.51 ± 0.92 pp (w: 7.43 pp) | 6.78 ± 1.01 pp (w: 8.74 pp) | 6.65 ± 0.98 pp (w: 8.56 pp) | 5.63 ± 0.89 pp (w: 7.53 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.59 ± 0.40 | 0.20 ± 0.07 | PASS |
| `t1_static_ocv` | `mismatched` | **E2** | 5.25 ± 0.83 pp (w: 7.01 pp) | 5.14 ± 0.86 pp (w: 6.93 pp) | 6.30 ± 0.95 pp (w: 8.11 pp) | 6.18 ± 0.92 pp (w: 7.94 pp) | 5.25 ± 0.83 pp (w: 7.01 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.58 ± 0.41 | 0.20 ± 0.07 | PASS |
| `t3_t10_minor_loops` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t3_t10_minor_loops` | `matched` | **E1** | 12.67 ± 0.09 pp (w: 12.83 pp) | 12.05 ± 0.13 pp (w: 12.25 pp) | 15.19 ± 0.11 pp (w: 15.33 pp) | 15.10 ± 0.11 pp (w: 15.27 pp) | 12.67 ± 0.09 pp (w: 12.83 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.86 ± 0.04 | 0.32 ± 0.01 | FAIL (t2_dynamic_max_error;t2_dynamic_rmse_max) |
| `t3_t10_minor_loops` | `matched` | **E2** | 0.51 ± 0.17 pp (w: 0.95 pp) | 0.41 ± 0.16 pp (w: 0.80 pp) | 2.67 ± 1.61 pp (w: 6.55 pp) | 0.89 ± 0.20 pp (w: 1.30 pp) | 0.51 ± 0.17 pp (w: 0.95 pp) | 1.2 ± 0.6 s (w: 3.0 s) | 4.5 ± 6.2 s (w: 22.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.16 ± 0.04 | 0.18 ± 0.01 | FAIL (t2_dynamic_max_error) |
| `t3_t10_minor_loops` | `mismatched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t3_t10_minor_loops` | `mismatched` | **E1** | 12.67 ± 0.09 pp (w: 12.83 pp) | 12.05 ± 0.13 pp (w: 12.25 pp) | 15.19 ± 0.11 pp (w: 15.33 pp) | 15.10 ± 0.11 pp (w: 15.27 pp) | 12.67 ± 0.09 pp (w: 12.83 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.86 ± 0.04 | 0.32 ± 0.01 | FAIL (t2_dynamic_max_error;t2_dynamic_rmse_max) |
| `t3_t10_minor_loops` | `mismatched` | **E2** | 0.51 ± 0.17 pp (w: 0.95 pp) | 0.41 ± 0.16 pp (w: 0.80 pp) | 2.67 ± 1.61 pp (w: 6.55 pp) | 0.89 ± 0.20 pp (w: 1.30 pp) | 0.51 ± 0.17 pp (w: 0.95 pp) | 1.2 ± 0.6 s (w: 3.0 s) | 4.5 ± 6.2 s (w: 22.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.16 ± 0.04 | 0.18 ± 0.01 | FAIL (t2_dynamic_max_error) |
| `t4_plateau_stress` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t4_plateau_stress` | `matched` | **E1** | 12.83 ± 0.06 pp (w: 12.92 pp) | 12.34 ± 0.10 pp (w: 12.47 pp) | 15.48 ± 0.08 pp (w: 15.64 pp) | 15.33 ± 0.08 pp (w: 15.41 pp) | 12.83 ± 0.06 pp (w: 12.92 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.57 ± 0.08 | 0.26 ± 0.02 | FAIL (t4_plateau_p95_max) |
| `t4_plateau_stress` | `matched` | **E2** | 0.39 ± 0.09 pp (w: 0.55 pp) | 0.29 ± 0.08 pp (w: 0.40 pp) | 2.15 ± 0.96 pp (w: 4.78 pp) | 0.79 ± 0.26 pp (w: 1.20 pp) | 0.39 ± 0.09 pp (w: 0.55 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 2.8 ± 3.0 s (w: 11.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.08 ms) | 2.08 ± 0.05 | 0.17 ± 0.01 | PASS |
| `t4_plateau_stress` | `mismatched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t4_plateau_stress` | `mismatched` | **E1** | 12.83 ± 0.06 pp (w: 12.92 pp) | 12.34 ± 0.10 pp (w: 12.47 pp) | 15.48 ± 0.08 pp (w: 15.64 pp) | 15.33 ± 0.08 pp (w: 15.41 pp) | 12.83 ± 0.06 pp (w: 12.92 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.57 ± 0.08 | 0.26 ± 0.02 | FAIL (t4_plateau_p95_max) |
| `t4_plateau_stress` | `mismatched` | **E2** | 0.39 ± 0.09 pp (w: 0.55 pp) | 0.29 ± 0.08 pp (w: 0.40 pp) | 2.15 ± 0.96 pp (w: 4.78 pp) | 0.79 ± 0.26 pp (w: 1.20 pp) | 0.39 ± 0.09 pp (w: 0.55 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 2.8 ± 3.0 s (w: 11.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.08 ± 0.05 | 0.17 ± 0.01 | PASS |
| `t5_initial_soc_offset` | `matched` | **E0** | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | FAIL (t5_converge_time_s) |
| `t5_initial_soc_offset` | `matched` | **E1** | 1.57 ± 0.04 pp (w: 1.63 pp) | 1.48 ± 0.04 pp (w: 1.55 pp) | 5.23 ± 1.67 pp (w: 8.21 pp) | 2.54 ± 0.05 pp (w: 2.67 pp) | 2.05 ± 0.11 pp (w: 2.21 pp) | 1.4 ± 0.5 s (w: 2.0 s) | 221.4 ± 2.2 s (w: 225.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.87 ± 0.19 | 0.27 ± 0.01 | PASS |
| `t5_initial_soc_offset` | `matched` | **E2** | 0.32 ± 0.19 pp (w: 0.58 pp) | 0.13 ± 0.07 pp (w: 0.23 pp) | 4.96 ± 1.64 pp (w: 7.89 pp) | 0.62 ± 0.50 pp (w: 1.35 pp) | 0.59 ± 0.36 pp (w: 1.08 pp) | 1.4 ± 0.5 s (w: 2.0 s) | 8.1 ± 8.0 s (w: 23.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.67 ± 0.25 | 0.24 ± 0.03 | PASS |
| `t5_initial_soc_offset` | `mismatched` | **E0** | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | FAIL (t5_converge_time_s) |
| `t5_initial_soc_offset` | `mismatched` | **E1** | 1.57 ± 0.04 pp (w: 1.63 pp) | 1.48 ± 0.04 pp (w: 1.55 pp) | 5.23 ± 1.67 pp (w: 8.21 pp) | 2.54 ± 0.05 pp (w: 2.67 pp) | 2.05 ± 0.11 pp (w: 2.21 pp) | 1.4 ± 0.5 s (w: 2.0 s) | 221.4 ± 2.2 s (w: 225.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.87 ± 0.19 | 0.27 ± 0.01 | PASS |
| `t5_initial_soc_offset` | `mismatched` | **E2** | 0.32 ± 0.19 pp (w: 0.58 pp) | 0.13 ± 0.07 pp (w: 0.23 pp) | 4.96 ± 1.64 pp (w: 7.89 pp) | 0.62 ± 0.50 pp (w: 1.35 pp) | 0.59 ± 0.36 pp (w: 1.08 pp) | 1.4 ± 0.5 s (w: 2.0 s) | 8.1 ± 8.0 s (w: 23.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.67 ± 0.25 | 0.24 ± 0.03 | PASS |
| `t6_current_bias` | `matched` | **E0** | 0.12 ± 0.00 pp (w: 0.12 pp) | 0.10 ± 0.00 pp (w: 0.10 pp) | 0.20 ± 0.00 pp (w: 0.20 pp) | 0.19 ± 0.00 pp (w: 0.19 pp) | 0.12 ± 0.00 pp (w: 0.12 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | -4.79 ± 0.02 pp (w: -4.76 pp) | 0.20 ± 0.00 pp (w: 0.20 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | FAIL (t6_drift_bess_per_day_max) |
| `t6_current_bias` | `matched` | **E1** | 0.42 ± 0.03 pp (w: 0.47 pp) | 0.35 ± 0.02 pp (w: 0.39 pp) | 1.45 ± 0.68 pp (w: 3.02 pp) | 0.72 ± 0.05 pp (w: 0.81 pp) | 0.42 ± 0.03 pp (w: 0.47 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.2 ± 0.4 s (w: 2.0 s) | 19.45 ± 3.71 pp (w: 25.84 pp) | 1.08 ± 0.15 pp (w: 1.38 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.22 ± 0.03 | 0.19 ± 0.01 | FAIL (t6_drift_bess_per_day_max) |
| `t6_current_bias` | `matched` | **E2** | 0.41 ± 0.04 pp (w: 0.47 pp) | 0.39 ± 0.05 pp (w: 0.47 pp) | 1.36 ± 0.72 pp (w: 2.97 pp) | 0.57 ± 0.04 pp (w: 0.63 pp) | 0.41 ± 0.04 pp (w: 0.47 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.2 ± 0.4 s (w: 2.0 s) | 7.91 ± 4.51 pp (w: 14.03 pp) | 0.68 ± 0.05 pp (w: 0.80 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.03 ± 0.02 | 0.16 ± 0.00 | FAIL (t6_drift_bess_per_day_max) |
| `t6_current_bias` | `mismatched` | **E0** | 0.12 ± 0.00 pp (w: 0.12 pp) | 0.10 ± 0.00 pp (w: 0.10 pp) | 0.20 ± 0.00 pp (w: 0.20 pp) | 0.19 ± 0.00 pp (w: 0.19 pp) | 0.12 ± 0.00 pp (w: 0.12 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | -4.79 ± 0.02 pp (w: -4.76 pp) | 0.20 ± 0.00 pp (w: 0.20 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | FAIL (t6_drift_bess_per_day_max) |
| `t6_current_bias` | `mismatched` | **E1** | 0.42 ± 0.03 pp (w: 0.47 pp) | 0.35 ± 0.02 pp (w: 0.39 pp) | 1.45 ± 0.68 pp (w: 3.02 pp) | 0.72 ± 0.05 pp (w: 0.81 pp) | 0.42 ± 0.03 pp (w: 0.47 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.2 ± 0.4 s (w: 2.0 s) | 19.45 ± 3.71 pp (w: 25.84 pp) | 1.08 ± 0.15 pp (w: 1.38 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.22 ± 0.03 | 0.19 ± 0.01 | FAIL (t6_drift_bess_per_day_max) |
| `t6_current_bias` | `mismatched` | **E2** | 0.41 ± 0.04 pp (w: 0.47 pp) | 0.39 ± 0.05 pp (w: 0.47 pp) | 1.36 ± 0.72 pp (w: 2.97 pp) | 0.57 ± 0.04 pp (w: 0.63 pp) | 0.41 ± 0.04 pp (w: 0.47 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.2 ± 0.4 s (w: 2.0 s) | 7.91 ± 4.51 pp (w: 14.03 pp) | 0.68 ± 0.05 pp (w: 0.80 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.03 ± 0.02 | 0.16 ± 0.00 | FAIL (t6_drift_bess_per_day_max) |
| `t7_voltage_quant_noise` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t7_voltage_quant_noise` | `matched` | **E1** | 4.40 ± 0.51 pp (w: 5.00 pp) | 4.12 ± 0.51 pp (w: 4.75 pp) | 7.60 ± 1.58 pp (w: 11.99 pp) | 6.53 ± 0.78 pp (w: 7.46 pp) | 4.40 ± 0.51 pp (w: 5.00 pp) | 150.1 ± 10.6 s (w: 168.0 s) | never | n/a (run too short) | 6.85 ± 0.82 pp (w: 7.71 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 5.47 ± 0.24 | 1.18 ± 0.10 | FAIL (t7_error_rise_max) |
| `t7_voltage_quant_noise` | `matched` | **E2** | 0.94 ± 0.35 pp (w: 1.83 pp) | 0.61 ± 0.20 pp (w: 0.97 pp) | 5.53 ± 2.60 pp (w: 11.10 pp) | 1.67 ± 0.74 pp (w: 3.60 pp) | 0.94 ± 0.35 pp (w: 1.83 pp) | 2.9 ± 2.9 s (w: 11.0 s) | 16.5 ± 18.0 s (w: 65.0 s) | n/a (run too short) | 1.28 ± 0.44 pp (w: 1.91 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 4.95 ± 0.16 | 0.96 ± 0.06 | FAIL (t7_error_rise_max) |
| `t7_voltage_quant_noise` | `mismatched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t7_voltage_quant_noise` | `mismatched` | **E1** | 4.40 ± 0.51 pp (w: 5.00 pp) | 4.12 ± 0.51 pp (w: 4.75 pp) | 7.60 ± 1.58 pp (w: 11.99 pp) | 6.53 ± 0.78 pp (w: 7.46 pp) | 4.40 ± 0.51 pp (w: 5.00 pp) | 150.1 ± 10.6 s (w: 168.0 s) | never | n/a (run too short) | 6.85 ± 0.82 pp (w: 7.71 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 5.47 ± 0.24 | 1.18 ± 0.10 | FAIL (t7_error_rise_max) |
| `t7_voltage_quant_noise` | `mismatched` | **E2** | 0.94 ± 0.35 pp (w: 1.83 pp) | 0.61 ± 0.20 pp (w: 0.97 pp) | 5.53 ± 2.60 pp (w: 11.10 pp) | 1.67 ± 0.74 pp (w: 3.60 pp) | 0.94 ± 0.35 pp (w: 1.83 pp) | 2.9 ± 2.9 s (w: 11.0 s) | 16.5 ± 18.0 s (w: 65.0 s) | n/a (run too short) | 1.28 ± 0.44 pp (w: 1.91 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 4.95 ± 0.16 | 0.96 ± 0.06 | FAIL (t7_error_rise_max) |
| `t9_rest_relaxation` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t9_rest_relaxation` | `matched` | **E1** | 8.72 ± 0.16 pp (w: 9.00 pp) | 8.47 ± 0.18 pp (w: 8.73 pp) | 9.78 ± 0.14 pp (w: 10.04 pp) | 9.72 ± 0.13 pp (w: 9.96 pp) | 8.72 ± 0.16 pp (w: 9.00 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.20 ± 0.07 | 0.19 ± 0.01 | FAIL (t9_post_rest_step_error_max) |
| `t9_rest_relaxation` | `matched` | **E2** | 0.47 ± 0.15 pp (w: 0.75 pp) | 0.38 ± 0.17 pp (w: 0.65 pp) | 2.44 ± 0.68 pp (w: 3.88 pp) | 0.81 ± 0.23 pp (w: 1.16 pp) | 0.47 ± 0.15 pp (w: 0.75 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 5.8 ± 5.1 s (w: 14.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.04 ± 0.06 | 0.16 ± 0.01 | FAIL (t9_post_rest_step_error_max) |
| `t9_rest_relaxation` | `mismatched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t9_rest_relaxation` | `mismatched` | **E1** | 8.72 ± 0.16 pp (w: 9.00 pp) | 8.47 ± 0.18 pp (w: 8.73 pp) | 9.78 ± 0.14 pp (w: 10.04 pp) | 9.72 ± 0.13 pp (w: 9.96 pp) | 8.72 ± 0.16 pp (w: 9.00 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.20 ± 0.07 | 0.19 ± 0.01 | FAIL (t9_post_rest_step_error_max) |
| `t9_rest_relaxation` | `mismatched` | **E2** | 0.47 ± 0.15 pp (w: 0.75 pp) | 0.38 ± 0.17 pp (w: 0.65 pp) | 2.44 ± 0.68 pp (w: 3.88 pp) | 0.81 ± 0.23 pp (w: 1.16 pp) | 0.47 ± 0.15 pp (w: 0.75 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 5.8 ± 5.1 s (w: 14.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.04 ± 0.06 | 0.16 ± 0.01 | FAIL (t9_post_rest_step_error_max) |
| `t11_anchor_toggle` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t11_anchor_toggle` | `matched` | **E1** | 8.75 ± 0.09 pp (w: 8.91 pp) | 8.53 ± 0.11 pp (w: 8.70 pp) | 9.83 ± 0.10 pp (w: 10.00 pp) | 9.76 ± 0.10 pp (w: 9.93 pp) | 8.75 ± 0.09 pp (w: 8.91 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.20 ± 0.06 | 0.19 ± 0.01 | PASS |
| `t11_anchor_toggle` | `matched` | **E2** | 0.45 ± 0.16 pp (w: 0.81 pp) | 0.35 ± 0.16 pp (w: 0.71 pp) | 2.73 ± 1.19 pp (w: 5.38 pp) | 0.79 ± 0.26 pp (w: 1.34 pp) | 0.45 ± 0.16 pp (w: 0.81 pp) | 1.3 ± 0.9 s (w: 4.0 s) | 3.8 ± 2.8 s (w: 8.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.08 ms) | 2.07 ± 0.05 | 0.17 ± 0.01 | PASS |
| `t11_anchor_toggle` | `mismatched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t11_anchor_toggle` | `mismatched` | **E1** | 8.75 ± 0.09 pp (w: 8.91 pp) | 8.53 ± 0.11 pp (w: 8.70 pp) | 9.83 ± 0.10 pp (w: 10.00 pp) | 9.76 ± 0.10 pp (w: 9.93 pp) | 8.75 ± 0.09 pp (w: 8.91 pp) | never | never | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.20 ± 0.06 | 0.19 ± 0.01 | PASS |
| `t11_anchor_toggle` | `mismatched` | **E2** | 0.45 ± 0.16 pp (w: 0.81 pp) | 0.35 ± 0.16 pp (w: 0.71 pp) | 2.73 ± 1.19 pp (w: 5.38 pp) | 0.79 ± 0.26 pp (w: 1.34 pp) | 0.45 ± 0.16 pp (w: 0.81 pp) | 1.3 ± 0.9 s (w: 4.0 s) | 3.8 ± 2.8 s (w: 8.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.07 ± 0.05 | 0.17 ± 0.01 | PASS |
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

| Estimator | Variant | `t11_anchor_toggle` | `t1_static_ocv` | `t3_t10_minor_loops` | `t4_plateau_stress` | `t5_initial_soc_offset` | `t6_current_bias` | `t7_voltage_quant_noise` | `t9_rest_relaxation` | Overall |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **E0** | `matched` | n/a | PASS | PASS | PASS | FAIL | FAIL | PASS | PASS | FAIL |
| **E0** | `mismatched` | n/a | PASS | PASS | PASS | FAIL | FAIL | PASS | PASS | FAIL |
| **E1** | `matched` | n/a | PASS | FAIL | FAIL | PASS | FAIL | FAIL | FAIL | FAIL |
| **E1** | `mismatched` | n/a | PASS | FAIL | FAIL | PASS | FAIL | FAIL | FAIL | FAIL |
| **E2** | `matched` | n/a | PASS | FAIL | PASS | PASS | FAIL | FAIL | FAIL | FAIL |
| **E2** | `mismatched` | n/a | PASS | FAIL | PASS | PASS | FAIL | FAIL | FAIL | FAIL |

**First Rung Meeting All Bars:** `None (all rungs failed at least one bar)`

## T1 OCV Model Check

> Evaluates model OCV table error against reference plant OCV table across temperature calibration points.

| Variant | Temperature | Max Error (mV) | RMS Error (mV) | Bar Threshold | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `matched` | `15.0 C` | 0.00 mV | 0.00 mV | 5.0 mV | PASS |
| `matched` | `25.0 C` | 0.00 mV | 0.00 mV | 5.0 mV | PASS |
| `matched` | `35.0 C` | 0.00 mV | 0.00 mV | 5.0 mV | PASS |
| `mismatched` | `15.0 C` | 3.00 mV | 3.00 mV | 5.0 mV | PASS |
| `mismatched` | `25.0 C` | 3.00 mV | 3.00 mV | 5.0 mV | PASS |
| `mismatched` | `35.0 C` | 3.00 mV | 3.00 mV | 5.0 mV | PASS |

## Diagnostic Observations

### Hysteresis Diagnostic Evaluation
- **Target Scenario:** `t4_plateau_stress`
- **Seeds Evaluated:** `10` (indices: `[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]`)
- **Plant Hysteresis Amplitude:** `15.0 mV`

- **`matched` variant:** E1 Plateau RMSE = `12.83 pp`, E2 Plateau RMSE = `0.39 pp` (E2 beats E1 by 12.44 pp)
- **`mismatched` variant:** E1 Plateau RMSE = `12.83 pp`, E2 Plateau RMSE = `0.39 pp` (E2 beats E1 by 12.44 pp)

> *Clarification on previous smoke report:* The previously displayed values (0.69 pp and 1.24 pp) occurred because matched and mismatched runs were averaged together across estimators (E2: (0.15 + 1.24)/2 = 0.695 pp; E1: (1.29 + 1.19)/2 = 1.24 pp). In this report, all diagnostic values are strictly partitioned by variant and match the corresponding rows in the benchmark results table.

## Assumptions Audit Summary

- **Placeholder Parameters:** `57`
- **Assumed Parameters:** `21`
- **Zero-Constants Rule:** All physical parameters, sensor limits, and noise parameters are strictly loaded from YAML configuration.

---
*Report generated for SOC Benchmark Lab.*
