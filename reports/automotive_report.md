# SOC Estimation Benchmark Report

> Synthetic data. Software correctness and comparison only, not accuracy evidence.
> All cell, sensor and filter values are placeholders. Absolute errors are not expectations for any real cell.
> Note: E0 (Coulomb counting) passes scenarios without current sensor error by construction.

## Executive Metadata

- **Active Profile:** `automotive`
- **Git Commit:** `a6c9e0497d780be82e15946a5f15c066ce9ff089`
- **Git Dirty:** `false`
- **Configuration Hash:** `97b0e05757c09e25a0bec592eb471b33ce77eeb741cebee555f58c0706ae9178`
- **Scenarios Evaluated:** `12`
- **Random Seeds per Scenario:** `10`
- **Estimators Evaluated:** `3` (E0, E1, E2)
- **Temperature-Clamp Warnings:** `0`

## Resolved Duty Cycle Settings

| Scenario | Cycle Type | Pulse C-Rate | Rest Duration | Applied Current (A) | SOC Swing | Reversal Count | Total Duration | Initial SOC | SOC Limits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `t11_anchor_toggle [anchors off]` | `anchor_evaluation` | 2.0 C (source: profile) | 300 s (source: profile) | 200.0 A | 0.3 pp | 1 | 830 s | 100% | [40%, 60%] |
| `t11_anchor_toggle [full-charge only]` | `anchor_evaluation` | 2.0 C (source: profile) | 300 s (source: profile) | 200.0 A | 0.3 pp | 1 | 830 s | 100% | [40%, 60%] |
| `t11_anchor_toggle [rest anchor only]` | `rest_relaxation` | 0.5 C (source: scenario file) | 700 s (source: scenario file) | 50.0 A | 15.0 pp | 0 | 1060 s | 55% | [20%, 80%] |
| `t12_hysteresis_mismatch` | `plateau_stress` | 2.0 C (source: profile) | 60 s (source: scenario file) | 200.0 A | 30.1 pp | 6 | 3600 s | 50% | [35%, 65%] |
| `t1_static_ocv` | `static` | 2.0 C (source: profile) | 300 s (source: profile) | 200.0 A | 0.0 pp | 0 | 10 s | 50% | [40%, 60%] |
| `t3_t10_minor_loops` | `minor_loops` | 2.0 C (source: profile) | 60 s (source: scenario file) | 200.0 A | 10.1 pp | 15 | 3600 s | 50% | [45%, 55%] |
| `t4_plateau_stress` | `plateau_stress` | 2.0 C (source: profile) | 60 s (source: scenario file) | 200.0 A | 30.1 pp | 6 | 3600 s | 50% | [35%, 65%] |
| `t5_initial_soc_offset` | `knee_crossing` | 0.7 C (source: scenario file) | 300 s (source: profile) | 70.0 A | 7.0 pp | 0 | 360 s | 25% | [40%, 60%] |
| `t6_current_bias` | `pulse` | 0.2 C (source: scenario file) | 60 s (source: scenario file) | 20.0 A | 0.6 pp | 719 | 86400 s | 70% | [40%, 60%] |
| `t6_plateau_only` | `plateau_stress` | 2.0 C (source: profile) | 300 s (source: profile) | 200.0 A | 41.1 pp | 84 | 86400 s | 50% | [30%, 70%] |
| `t7_voltage_quant_noise` | `pulse` | 0.5 C (source: scenario file) | 30 s (source: scenario file) | 50.0 A | 0.8 pp | 3 | 300 s | 60% | [40%, 60%] |
| `t9_rest_relaxation` | `rest_relaxation` | 0.5 C (source: scenario file) | 600 s (source: scenario file) | 50.0 A | 0.8 pp | 0 | 660 s | 50% | [40%, 60%] |

> Note: For `t11_anchor_toggle [rest anchor only]`, a dedicated 1060 s cycle (360 s discharge at 50 A + 700 s rest) is resolved to allow complete OCV relaxation beyond the 600 s rest threshold, matching the duration table.

## Scenario Durations and Sample Counts

| Scenario | Duration (s) | Sample Count (kept) | Sample Period dt (s) | Dropped Samples | Truth SOC Min | Truth SOC Max | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `t11_anchor_toggle [anchors off]` | 830.0 s | 830 | 1.0 s | 0 | 99.68% | 100.01% | VALID |
| `t11_anchor_toggle [full-charge only]` | 830.0 s | 830 | 1.0 s | 0 | 99.68% | 100.01% | VALID |
| `t11_anchor_toggle [rest anchor only]` | 1060.0 s | 1060 | 1.0 s | 0 | 50.00% | 54.99% | VALID |
| `t12_hysteresis_mismatch` | 3600.0 s | 3600 | 1.0 s | 0 | 34.94% | 65.05% | VALID |
| `t1_static_ocv` | 10.0 s | 10 | 1.0 s | 0 | 50.00% | 50.00% | VALID |
| `t3_t10_minor_loops` | 3600.0 s | 3600 | 1.0 s | 0 | 44.94% | 55.05% | VALID |
| `t4_plateau_stress` | 3600.0 s | 3600 | 1.0 s | 0 | 34.94% | 65.05% | VALID |
| `t5_initial_soc_offset` | 360.0 s | 360 | 1.0 s | 0 | 18.00% | 24.98% | VALID |
| `t6_current_bias` | 86400.0 s | 8640 | 10.0 s | 0 | 69.43% | 70.00% | VALID |
| `t6_plateau_only` | 86400.0 s | 8640 | 10.0 s | 0 | 29.44% | 70.54% | VALID |
| `t7_voltage_quant_noise` | 300.0 s | 300 | 1.0 s | 0 | 59.16% | 60.00% | VALID |
| `t9_rest_relaxation` | 660.0 s | 660 | 1.0 s | 0 | 49.17% | 49.99% | VALID |

## Benchmark Metric Results

> Statistics computed across 10 random seeds: format is `mean ± std (worst)`.

| Scenario | Variant | Estimator | RMSE | MAE | Max Err | P95 Err | Plateau RMSE | Conv 5% | Conv 2% | Drift 24h | Rev Spike | ms/step (med) | V Res (mV) | NIS | Pass All |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `t1_static_ocv` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | n/a (no reversals) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t1_static_ocv` | `matched` | **E1** | 1.28 ± 0.71 pp (w: 2.73 pp) | 1.10 ± 0.68 pp (w: 2.65 pp) | 2.32 ± 0.96 pp (w: 4.20 pp) | 2.03 ± 0.95 pp (w: 4.02 pp) | 1.28 ± 0.71 pp (w: 2.73 pp) | 1.0 ± 0.0 s (w: 1.0 s) | never | n/a (run too short) | n/a (no reversals) | 0.11 ± 0.00 ms (w: 0.12 ms) | 2.21 ± 0.46 | 0.16 ± 0.07 | n/a (no bars) |
| `t1_static_ocv` | `matched` | **E2** | 1.21 ± 0.66 pp (w: 2.54 pp) | 1.03 ± 0.63 pp (w: 2.47 pp) | 2.20 ± 0.90 pp (w: 3.96 pp) | 1.91 ± 0.88 pp (w: 3.77 pp) | 1.21 ± 0.66 pp (w: 2.54 pp) | 1.0 ± 0.0 s (w: 1.0 s) | never | n/a (run too short) | n/a (no reversals) | 0.11 ± 0.01 ms (w: 0.14 ms) | 2.22 ± 0.46 | 0.16 ± 0.07 | n/a (no bars) |
| `t1_static_ocv` | `mismatched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | n/a (no reversals) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t1_static_ocv` | `mismatched` | **E1** | 5.64 ± 0.89 pp (w: 7.53 pp) | 5.51 ± 0.92 pp (w: 7.43 pp) | 6.78 ± 1.01 pp (w: 8.74 pp) | 6.65 ± 0.98 pp (w: 8.56 pp) | 5.64 ± 0.89 pp (w: 7.53 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.12 ± 0.02 ms (w: 0.15 ms) | 2.59 ± 0.40 | 0.20 ± 0.07 | n/a (no bars) |
| `t1_static_ocv` | `mismatched` | **E2** | 5.17 ± 0.83 pp (w: 6.91 pp) | 5.07 ± 0.85 pp (w: 6.83 pp) | 6.21 ± 0.94 pp (w: 7.99 pp) | 6.09 ± 0.91 pp (w: 7.83 pp) | 5.17 ± 0.83 pp (w: 6.91 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.11 ± 0.01 ms (w: 0.12 ms) | 2.58 ± 0.41 | 0.20 ± 0.07 | n/a (no bars) |
| `t3_t10_minor_loops` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t3_t10_minor_loops` | `matched` | **E1** | 6.51 ± 0.13 pp (w: 6.66 pp) | 5.32 ± 0.10 pp (w: 5.44 pp) | 15.18 ± 0.23 pp (w: 15.42 pp) | 11.70 ± 0.44 pp (w: 12.40 pp) | 6.51 ± 0.13 pp (w: 6.66 pp) | never | never | n/a (run too short) | 15.17 ± 0.23 pp (w: 15.42 pp) | 0.07 ± 0.01 ms (w: 0.09 ms) | 12.13 ± 0.08 | 5.87 ± 0.08 | FAIL (t10_reversal_spike_max;t2_dynamic_max_error;t2_dynamic_rmse_max; max: 15.18 ± 0.23 pp (w: 15.42 pp), post-warmup: 15.18 ± 0.23 pp (w: 15.42 pp); bar uses full-run) |
| `t3_t10_minor_loops` | `matched` | **E2** | 0.41 ± 0.06 pp (w: 0.50 pp) | 0.30 ± 0.04 pp (w: 0.37 pp) | 3.24 ± 1.14 pp (w: 5.87 pp) | 0.75 ± 0.11 pp (w: 0.92 pp) | 0.41 ± 0.06 pp (w: 0.50 pp) | 1.2 ± 0.6 s (w: 3.0 s) | 42.6 ± 34.4 s (w: 105.0 s) | n/a (run too short) | 0.88 ± 0.29 pp (w: 1.51 pp) | 0.07 ± 0.01 ms (w: 0.09 ms) | 2.96 ± 0.03 | 0.35 ± 0.01 | FAIL (t2_dynamic_max_error; max: 3.24 ± 1.14 pp (w: 5.87 pp), post-warmup: 2.39 ± 0.25 pp (w: 2.84 pp); bar uses full-run) |
| `t3_t10_minor_loops` | `mismatched` | **E0** | 0.19 ± 0.00 pp (w: 0.19 pp) | 0.17 ± 0.00 pp (w: 0.17 pp) | 0.27 ± 0.00 pp (w: 0.27 pp) | 0.27 ± 0.00 pp (w: 0.27 pp) | 0.19 ± 0.00 pp (w: 0.19 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.26 ± 0.00 pp (w: 0.26 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t3_t10_minor_loops` | `mismatched` | **E1** | 16.55 ± 0.02 pp (w: 16.59 pp) | 13.71 ± 0.02 pp (w: 13.74 pp) | 29.79 ± 0.08 pp (w: 29.91 pp) | 28.34 ± 0.04 pp (w: 28.41 pp) | 16.55 ± 0.02 pp (w: 16.59 pp) | never | never | n/a (run too short) | 24.02 ± 0.03 pp (w: 24.07 pp) | 0.08 ± 0.01 ms (w: 0.11 ms) | 27.35 ± 0.04 | 29.79 ± 0.08 | FAIL (t10_reversal_spike_max;t2_dynamic_max_error;t2_dynamic_rmse_max; max: 29.79 ± 0.08 pp (w: 29.91 pp), post-warmup: 29.79 ± 0.08 pp (w: 29.91 pp); bar uses full-run) |
| `t3_t10_minor_loops` | `mismatched` | **E2** | 18.28 ± 0.03 pp (w: 18.31 pp) | 14.63 ± 0.02 pp (w: 14.66 pp) | 34.75 ± 0.12 pp (w: 34.97 pp) | 33.07 ± 0.05 pp (w: 33.17 pp) | 18.28 ± 0.03 pp (w: 18.31 pp) | never | never | n/a (run too short) | 28.15 ± 0.04 pp (w: 28.19 pp) | 0.08 ± 0.01 ms (w: 0.11 ms) | 37.19 ± 0.05 | 55.06 ± 0.14 | FAIL (t10_reversal_spike_max;t2_dynamic_max_error;t2_dynamic_rmse_max; max: 34.75 ± 0.12 pp (w: 34.97 pp), post-warmup: 34.75 ± 0.12 pp (w: 34.97 pp); bar uses full-run) |
| `t4_plateau_stress` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t4_plateau_stress` | `matched` | **E1** | 8.55 ± 0.03 pp (w: 8.63 pp) | 7.48 ± 0.03 pp (w: 7.54 pp) | 14.67 ± 0.31 pp (w: 15.20 pp) | 12.68 ± 0.08 pp (w: 12.83 pp) | 8.55 ± 0.03 pp (w: 8.63 pp) | 3428.5 ± 1.2 s (w: 3430.0 s) | never | n/a (run too short) | 10.58 ± 0.06 pp (w: 10.68 pp) | 0.07 ± 0.01 ms (w: 0.11 ms) | 10.72 ± 0.03 | 4.57 ± 0.03 | FAIL (t4_plateau_p95_max) |
| `t4_plateau_stress` | `matched` | **E2** | 0.55 ± 0.07 pp (w: 0.69 pp) | 0.44 ± 0.05 pp (w: 0.54 pp) | 2.68 ± 0.99 pp (w: 4.92 pp) | 1.04 ± 0.20 pp (w: 1.58 pp) | 0.55 ± 0.07 pp (w: 0.69 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 30.5 ± 31.9 s (w: 91.0 s) | n/a (run too short) | 0.80 ± 0.17 pp (w: 1.14 pp) | 0.08 ± 0.01 ms (w: 0.11 ms) | 3.31 ± 0.02 | 0.44 ± 0.01 | PASS |
| `t4_plateau_stress` | `mismatched` | **E0** | 0.50 ± 0.00 pp (w: 0.50 pp) | 0.44 ± 0.00 pp (w: 0.44 pp) | 0.79 ± 0.00 pp (w: 0.79 pp) | 0.79 ± 0.00 pp (w: 0.79 pp) | 0.50 ± 0.00 pp (w: 0.50 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.79 ± 0.00 pp (w: 0.79 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t4_plateau_stress` | `mismatched` | **E1** | 24.79 ± 0.03 pp (w: 24.83 pp) | 22.26 ± 0.03 pp (w: 22.30 pp) | 38.15 ± 0.12 pp (w: 38.40 pp) | 36.31 ± 0.05 pp (w: 36.39 pp) | 24.79 ± 0.03 pp (w: 24.83 pp) | 3544.8 ± 0.7 s (w: 3546.0 s) | never | n/a (run too short) | 32.68 ± 0.05 pp (w: 32.80 pp) | 0.08 ± 0.02 ms (w: 0.13 ms) | 27.52 ± 0.08 | 30.17 ± 0.17 | FAIL (t4_plateau_p95_max) |
| `t4_plateau_stress` | `mismatched` | **E2** | 30.27 ± 0.02 pp (w: 30.31 pp) | 27.33 ± 0.02 pp (w: 27.37 pp) | 43.52 ± 0.09 pp (w: 43.72 pp) | 42.36 ± 0.06 pp (w: 42.44 pp) | 30.27 ± 0.02 pp (w: 30.31 pp) | never | never | n/a (run too short) | 36.31 ± 0.06 pp (w: 36.43 pp) | 0.08 ± 0.01 ms (w: 0.09 ms) | 36.28 ± 0.04 | 52.38 ± 0.11 | FAIL (t4_plateau_p95_max) |
| `t5_initial_soc_offset` | `matched` | **E0** | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | FAIL (t5_converge_time_s) |
| `t5_initial_soc_offset` | `matched` | **E1** | 1.89 ± 0.08 pp (w: 2.02 pp) | 1.79 ± 0.10 pp (w: 1.95 pp) | 5.23 ± 1.67 pp (w: 8.21 pp) | 2.69 ± 0.02 pp (w: 2.72 pp) | 2.05 ± 0.11 pp (w: 2.21 pp) | 1.4 ± 0.5 s (w: 2.0 s) | 221.4 ± 2.2 s (w: 225.0 s) | n/a (run too short) | n/a (no reversals) | 0.09 ± 0.02 ms (w: 0.13 ms) | 3.36 ± 0.39 | 0.34 ± 0.03 | FAIL (t5_converge_time_s) |
| `t5_initial_soc_offset` | `matched` | **E2** | 0.50 ± 0.31 pp (w: 0.92 pp) | 0.26 ± 0.18 pp (w: 0.54 pp) | 4.96 ± 1.64 pp (w: 7.89 pp) | 0.92 ± 0.81 pp (w: 2.18 pp) | 0.59 ± 0.36 pp (w: 1.08 pp) | 1.4 ± 0.5 s (w: 2.0 s) | 8.1 ± 8.0 s (w: 23.0 s) | n/a (run too short) | n/a (no reversals) | 0.09 ± 0.01 ms (w: 0.11 ms) | 2.96 ± 0.55 | 0.26 ± 0.06 | PASS |
| `t5_initial_soc_offset` | `mismatched` | **E0** | 9.82 ± 0.00 pp (w: 9.82 pp) | 9.82 ± 0.00 pp (w: 9.82 pp) | 10.00 ± 0.00 pp (w: 10.00 pp) | 9.98 ± 0.00 pp (w: 9.98 pp) | 9.87 ± 0.00 pp (w: 9.87 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | FAIL (t5_converge_time_s) |
| `t5_initial_soc_offset` | `mismatched` | **E1** | 0.74 ± 0.03 pp (w: 0.80 pp) | 0.56 ± 0.04 pp (w: 0.62 pp) | 3.63 ± 1.69 pp (w: 6.65 pp) | 1.24 ± 0.16 pp (w: 1.39 pp) | 0.87 ± 0.04 pp (w: 0.94 pp) | 1.2 ± 0.4 s (w: 2.0 s) | 2.8 ± 2.2 s (w: 8.0 s) | n/a (run too short) | n/a (no reversals) | 0.09 ± 0.01 ms (w: 0.11 ms) | 2.91 ± 0.48 | 0.28 ± 0.08 | PASS |
| `t5_initial_soc_offset` | `mismatched` | **E2** | 4.04 ± 0.22 pp (w: 4.27 pp) | 3.89 ± 0.27 pp (w: 4.13 pp) | 5.17 ± 0.43 pp (w: 6.30 pp) | 4.88 ± 0.14 pp (w: 5.10 pp) | 4.10 ± 0.27 pp (w: 4.34 pp) | 89.5 ± 109.7 s (w: 272.0 s) | never | n/a (run too short) | n/a (no reversals) | 0.09 ± 0.01 ms (w: 0.11 ms) | 3.93 ± 0.56 | 0.56 ± 0.15 | FAIL (t5_converge_time_s) |
| `t6_current_bias` | `matched` | **E0** | 2.77 ± 0.01 pp (w: 2.79 pp) | 2.40 ± 0.01 pp (w: 2.41 pp) | 4.80 ± 0.01 pp (w: 4.83 pp) | 4.56 ± 0.01 pp (w: 4.59 pp) | 2.77 ± 0.01 pp (w: 2.79 pp) | 10.0 ± 0.0 s (w: 10.0 s) | never | -4.80 ± 0.01 pp (w: -4.78 pp) | 4.79 ± 0.01 pp (w: 4.82 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | FAIL (t6_drift_bess_per_day_max;t6_mean_error_bar_pp) |
| `t6_current_bias` | `matched` | **E1** | 0.42 ± 0.00 pp (w: 0.42 pp) | 0.41 ± 0.00 pp (w: 0.41 pp) | 1.54 ± 0.67 pp (w: 3.02 pp) | 0.55 ± 0.01 pp (w: 0.56 pp) | 0.42 ± 0.00 pp (w: 0.42 pp) | 10.0 ± 0.0 s (w: 10.0 s) | 12.0 ± 4.0 s (w: 20.0 s) | 0.20 ± 0.02 pp (w: 0.24 pp) | 1.01 ± 0.36 pp (w: 1.68 pp) | 0.08 ± 0.01 ms (w: 0.11 ms) | 2.23 ± 0.02 | 0.20 ± 0.00 | PASS |
| `t6_current_bias` | `matched` | **E2** | 0.49 ± 0.00 pp (w: 0.50 pp) | 0.48 ± 0.01 pp (w: 0.49 pp) | 1.50 ± 0.66 pp (w: 2.97 pp) | 0.64 ± 0.01 pp (w: 0.66 pp) | 0.49 ± 0.00 pp (w: 0.50 pp) | 10.0 ± 0.0 s (w: 10.0 s) | 12.0 ± 4.0 s (w: 20.0 s) | 0.07 ± 0.03 pp (w: 0.12 pp) | 0.79 ± 0.06 pp (w: 0.91 pp) | 0.07 ± 0.01 ms (w: 0.10 ms) | 2.04 ± 0.01 | 0.16 ± 0.00 | PASS |
| `t6_current_bias` | `mismatched` | **E0** | 2.93 ± 0.01 pp (w: 2.95 pp) | 2.54 ± 0.01 pp (w: 2.56 pp) | 5.07 ± 0.01 pp (w: 5.10 pp) | 4.82 ± 0.01 pp (w: 4.85 pp) | 2.93 ± 0.01 pp (w: 2.95 pp) | never | never | -5.06 ± 0.01 pp (w: -5.04 pp) | 5.07 ± 0.01 pp (w: 5.10 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | FAIL (t6_drift_bess_per_day_max;t6_mean_error_bar_pp) |
| `t6_current_bias` | `mismatched` | **E1** | 4.57 ± 0.01 pp (w: 4.59 pp) | 4.57 ± 0.01 pp (w: 4.59 pp) | 5.49 ± 0.31 pp (w: 6.18 pp) | 4.80 ± 0.04 pp (w: 4.86 pp) | 4.57 ± 0.01 pp (w: 4.59 pp) | 14567.0 ± 26547.9 s (w: 67880.0 s) | never | -0.01 ± 0.06 pp (w: 0.08 pp) | 5.45 ± 0.30 pp (w: 6.06 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 3.14 ± 0.01 | 0.39 ± 0.00 | FAIL (t6_mean_error_bar_pp) |
| `t6_current_bias` | `mismatched` | **E2** | 4.22 ± 0.01 pp (w: 4.23 pp) | 4.21 ± 0.01 pp (w: 4.23 pp) | 4.80 ± 0.24 pp (w: 5.29 pp) | 4.44 ± 0.03 pp (w: 4.50 pp) | 4.22 ± 0.01 pp (w: 4.23 pp) | 206.0 ± 406.4 s (w: 1230.0 s) | never | -0.10 ± 0.06 pp (w: -0.01 pp) | 4.74 ± 0.18 pp (w: 5.06 pp) | 0.07 ± 0.01 ms (w: 0.10 ms) | 3.27 ± 0.01 | 0.43 ± 0.00 | FAIL (t6_mean_error_bar_pp) |
| `t6_plateau_only` | `matched` | **E0** | 2.77 ± 0.01 pp (w: 2.78 pp) | 2.40 ± 0.01 pp (w: 2.41 pp) | 4.80 ± 0.01 pp (w: 4.81 pp) | 4.56 ± 0.01 pp (w: 4.57 pp) | 2.77 ± 0.01 pp (w: 2.78 pp) | 10.0 ± 0.0 s (w: 10.0 s) | never | -4.80 ± 0.01 pp (w: -4.76 pp) | 4.79 ± 0.01 pp (w: 4.81 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t6_plateau_only` | `matched` | **E1** | 2.17 ± 0.02 pp (w: 2.22 pp) | 1.82 ± 0.01 pp (w: 1.85 pp) | 14.10 ± 0.95 pp (w: 15.86 pp) | 3.18 ± 0.02 pp (w: 3.20 pp) | 2.17 ± 0.02 pp (w: 2.22 pp) | 832.0 ± 48.1 s (w: 920.0 s) | never | 0.87 ± 0.06 pp (w: 0.99 pp) | 6.61 ± 0.23 pp (w: 7.03 pp) | 0.08 ± 0.03 ms (w: 0.16 ms) | 13.93 ± 0.03 | 7.72 ± 0.03 | n/a (no bars) |
| `t6_plateau_only` | `matched` | **E2** | 0.36 ± 0.03 pp (w: 0.43 pp) | 0.30 ± 0.02 pp (w: 0.34 pp) | 4.02 ± 1.30 pp (w: 6.75 pp) | 0.56 ± 0.02 pp (w: 0.62 pp) | 0.36 ± 0.03 pp (w: 0.43 pp) | 30.0 ± 41.0 s (w: 130.0 s) | 260.0 ± 88.1 s (w: 410.0 s) | -0.05 ± 0.04 pp (w: 0.01 pp) | 0.69 ± 0.06 pp (w: 0.78 pp) | 0.08 ± 0.03 ms (w: 0.17 ms) | 3.14 ± 0.03 | 0.39 ± 0.01 | n/a (no bars) |
| `t6_plateau_only` | `mismatched` | **E0** | 3.01 ± 0.01 pp (w: 3.03 pp) | 2.58 ± 0.01 pp (w: 2.59 pp) | 6.06 ± 0.01 pp (w: 6.08 pp) | 5.22 ± 0.01 pp (w: 5.23 pp) | 3.01 ± 0.01 pp (w: 3.03 pp) | 85566.0 ± 4.9 s (w: 85570.0 s) | never | -5.01 ± 0.01 pp (w: -4.97 pp) | 6.03 ± 0.01 pp (w: 6.05 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t6_plateau_only` | `mismatched` | **E1** | 7.08 ± 0.03 pp (w: 7.12 pp) | 5.94 ± 0.02 pp (w: 5.97 pp) | 32.25 ± 0.56 pp (w: 33.09 pp) | 9.98 ± 0.02 pp (w: 10.00 pp) | 7.08 ± 0.03 pp (w: 7.12 pp) | never | never | -3.60 ± 0.17 pp (w: -3.38 pp) | 24.67 ± 0.63 pp (w: 25.43 pp) | 0.08 ± 0.03 ms (w: 0.15 ms) | 29.86 ± 0.04 | 35.47 ± 0.09 | n/a (no bars) |
| `t6_plateau_only` | `mismatched` | **E2** | 9.07 ± 0.03 pp (w: 9.13 pp) | 7.63 ± 0.03 pp (w: 7.68 pp) | 41.98 ± 0.30 pp (w: 42.47 pp) | 13.40 ± 0.06 pp (w: 13.53 pp) | 9.07 ± 0.03 pp (w: 9.13 pp) | never | never | -4.46 ± 0.19 pp (w: -4.15 pp) | 35.23 ± 0.18 pp (w: 35.46 pp) | 0.09 ± 0.03 ms (w: 0.16 ms) | 42.77 ± 0.04 | 72.85 ± 0.13 | n/a (no bars) |
| `t7_voltage_quant_noise` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t7_voltage_quant_noise` | `matched` | **E1** | 4.40 ± 0.51 pp (w: 5.00 pp) | 4.12 ± 0.51 pp (w: 4.75 pp) | 7.60 ± 1.58 pp (w: 11.99 pp) | 6.53 ± 0.78 pp (w: 7.46 pp) | 4.40 ± 0.51 pp (w: 5.00 pp) | 150.1 ± 10.6 s (w: 168.0 s) | never | n/a (run too short) | 6.85 ± 0.82 pp (w: 7.71 pp) | 0.07 ± 0.00 ms (w: 0.08 ms) | 5.47 ± 0.24 | 1.18 ± 0.10 | PASS |
| `t7_voltage_quant_noise` | `matched` | **E2** | 0.94 ± 0.35 pp (w: 1.83 pp) | 0.61 ± 0.20 pp (w: 0.97 pp) | 5.53 ± 2.60 pp (w: 11.10 pp) | 1.67 ± 0.74 pp (w: 3.60 pp) | 0.94 ± 0.35 pp (w: 1.83 pp) | 2.9 ± 2.9 s (w: 11.0 s) | 16.5 ± 18.0 s (w: 65.0 s) | n/a (run too short) | 1.28 ± 0.44 pp (w: 1.91 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 4.95 ± 0.16 | 0.96 ± 0.06 | FAIL (t7_error_rise_max) |
| `t7_voltage_quant_noise` | `mismatched` | **E0** | 0.03 ± 0.00 pp (w: 0.03 pp) | 0.03 ± 0.00 pp (w: 0.03 pp) | 0.04 ± 0.00 pp (w: 0.04 pp) | 0.04 ± 0.00 pp (w: 0.04 pp) | 0.03 ± 0.00 pp (w: 0.03 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.04 ± 0.00 pp (w: 0.04 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t7_voltage_quant_noise` | `mismatched` | **E1** | 5.58 ± 0.98 pp (w: 7.88 pp) | 4.85 ± 0.77 pp (w: 6.67 pp) | 8.81 ± 1.60 pp (w: 11.80 pp) | 8.07 ± 1.48 pp (w: 11.66 pp) | 5.58 ± 0.98 pp (w: 7.88 pp) | never | never | n/a (run too short) | 8.52 ± 1.27 pp (w: 11.66 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 8.64 ± 0.39 | 2.96 ± 0.26 | FAIL (t7_error_rise_max) |
| `t7_voltage_quant_noise` | `mismatched` | **E2** | 2.70 ± 0.39 pp (w: 3.55 pp) | 1.98 ± 0.24 pp (w: 2.43 pp) | 7.13 ± 1.26 pp (w: 10.55 pp) | 5.79 ± 1.00 pp (w: 8.06 pp) | 2.70 ± 0.39 pp (w: 3.55 pp) | 71.7 ± 6.9 s (w: 87.0 s) | never | n/a (run too short) | 3.14 ± 0.74 pp (w: 4.28 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 8.90 ± 0.23 | 3.13 ± 0.16 | FAIL (t7_error_rise_max) |
| `t9_rest_relaxation` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | n/a (no reversals) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t9_rest_relaxation` | `matched` | **E1** | 8.72 ± 0.16 pp (w: 9.00 pp) | 8.47 ± 0.18 pp (w: 8.73 pp) | 9.78 ± 0.14 pp (w: 10.04 pp) | 9.72 ± 0.13 pp (w: 9.96 pp) | 8.72 ± 0.16 pp (w: 9.00 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.20 ± 0.07 | 0.19 ± 0.01 | FAIL (t9_post_rest_step_error_max; max: 9.78 ± 0.14 pp (w: 10.04 pp), post-warmup: 9.78 ± 0.14 pp (w: 10.04 pp); bar uses full-run) |
| `t9_rest_relaxation` | `matched` | **E2** | 0.47 ± 0.15 pp (w: 0.75 pp) | 0.38 ± 0.17 pp (w: 0.65 pp) | 2.44 ± 0.68 pp (w: 3.88 pp) | 0.81 ± 0.23 pp (w: 1.16 pp) | 0.47 ± 0.15 pp (w: 0.75 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 5.8 ± 5.1 s (w: 14.0 s) | n/a (run too short) | n/a (no reversals) | 0.07 ± 0.00 ms (w: 0.07 ms) | 2.04 ± 0.06 | 0.16 ± 0.01 | FAIL (t9_post_rest_step_error_max; max: 2.44 ± 0.68 pp (w: 3.88 pp), post-warmup: 1.59 ± 0.45 pp (w: 2.43 pp); bar uses full-run) |
| `t9_rest_relaxation` | `mismatched` | **E0** | 0.04 ± 0.00 pp (w: 0.04 pp) | 0.04 ± 0.00 pp (w: 0.04 pp) | 0.04 ± 0.00 pp (w: 0.04 pp) | 0.04 ± 0.00 pp (w: 0.04 pp) | 0.04 ± 0.00 pp (w: 0.04 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | n/a (no reversals) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | PASS |
| `t9_rest_relaxation` | `mismatched` | **E1** | 12.29 ± 0.11 pp (w: 12.52 pp) | 11.45 ± 0.12 pp (w: 11.67 pp) | 14.63 ± 0.12 pp (w: 14.85 pp) | 14.55 ± 0.11 pp (w: 14.77 pp) | 12.29 ± 0.11 pp (w: 12.52 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.07 ± 0.00 ms (w: 0.08 ms) | 3.26 ± 0.07 | 0.42 ± 0.02 | FAIL (t9_post_rest_step_error_max; max: 14.63 ± 0.12 pp (w: 14.85 pp), post-warmup: 14.63 ± 0.12 pp (w: 14.85 pp); bar uses full-run) |
| `t9_rest_relaxation` | `mismatched` | **E2** | 7.04 ± 1.79 pp (w: 8.94 pp) | 6.41 ± 1.94 pp (w: 8.37 pp) | 11.03 ± 0.67 pp (w: 12.14 pp) | 9.94 ± 0.90 pp (w: 11.11 pp) | 7.04 ± 1.79 pp (w: 8.94 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.07 ± 0.00 ms (w: 0.07 ms) | 3.04 ± 0.15 | 0.37 ± 0.04 | FAIL (t9_post_rest_step_error_max; max: 11.03 ± 0.67 pp (w: 12.14 pp), post-warmup: 11.03 ± 0.67 pp (w: 12.14 pp); bar uses full-run) |
| `t11_anchor_toggle [anchors off]` | `matched` | **E0** | 5.00 ± 0.00 pp (w: 5.00 pp) | 5.00 ± 0.00 pp (w: 5.00 pp) | 5.00 ± 0.00 pp (w: 5.00 pp) | 5.00 ± 0.00 pp (w: 5.00 pp) | n/a | never | never | n/a (run too short) | 5.00 ± 0.00 pp (w: 5.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t11_anchor_toggle [anchors off]` | `matched` | **E1** | 0.02 ± 0.00 pp (w: 0.02 pp) | 0.02 ± 0.00 pp (w: 0.02 pp) | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.04 ± 0.00 pp (w: 0.04 pp) | n/a | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.06 ± 0.01 pp (w: 0.07 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 7.61 ± 0.06 | 0.16 ± 0.01 | n/a (no bars) |
| `t11_anchor_toggle [anchors off]` | `matched` | **E2** | 0.02 ± 0.00 pp (w: 0.02 pp) | 0.01 ± 0.00 pp (w: 0.02 pp) | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.03 ± 0.00 pp (w: 0.04 pp) | n/a | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.04 ± 0.00 pp (w: 0.04 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 7.58 ± 0.06 | 0.15 ± 0.01 | n/a (no bars) |
| `t11_anchor_toggle [anchors off]` | `mismatched` | **E0** | 5.00 ± 0.00 pp (w: 5.00 pp) | 5.00 ± 0.00 pp (w: 5.00 pp) | 5.00 ± 0.00 pp (w: 5.00 pp) | 5.00 ± 0.00 pp (w: 5.00 pp) | n/a | never | never | n/a (run too short) | 5.00 ± 0.00 pp (w: 5.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t11_anchor_toggle [anchors off]` | `mismatched` | **E1** | 0.12 ± 0.00 pp (w: 0.12 pp) | 0.11 ± 0.00 pp (w: 0.11 pp) | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.16 ± 0.01 pp (w: 0.17 pp) | n/a | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.08 ± 0.01 pp (w: 0.09 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 7.37 ± 0.06 | 0.15 ± 0.01 | n/a (no bars) |
| `t11_anchor_toggle [anchors off]` | `mismatched` | **E2** | 0.13 ± 0.00 pp (w: 0.13 pp) | 0.12 ± 0.00 pp (w: 0.12 pp) | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.20 ± 0.01 pp (w: 0.21 pp) | n/a | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.15 ± 0.01 pp (w: 0.17 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 7.37 ± 0.06 | 0.15 ± 0.01 | n/a (no bars) |
| `t11_anchor_toggle [full-charge only]` | `matched` | **E0** | 1.89 ± 0.00 pp (w: 1.89 pp) | 0.72 ± 0.00 pp (w: 0.73 pp) | 5.00 ± 0.00 pp (w: 5.00 pp) | 5.00 ± 0.00 pp (w: 5.00 pp) | n/a | 101.2 ± 35.1 s (w: 120.0 s) | 120.0 ± 0.0 s (w: 120.0 s) | n/a (run too short) | 0.01 ± 0.00 pp (w: 0.01 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t11_anchor_toggle [full-charge only]` | `matched` | **E1** | 0.02 ± 0.00 pp (w: 0.02 pp) | 0.02 ± 0.00 pp (w: 0.02 pp) | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.04 ± 0.00 pp (w: 0.04 pp) | n/a | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.06 ± 0.01 pp (w: 0.07 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 7.61 ± 0.06 | 0.16 ± 0.01 | n/a (no bars) |
| `t11_anchor_toggle [full-charge only]` | `matched` | **E2** | 0.02 ± 0.00 pp (w: 0.02 pp) | 0.01 ± 0.00 pp (w: 0.02 pp) | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.03 ± 0.00 pp (w: 0.04 pp) | n/a | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.04 ± 0.00 pp (w: 0.04 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 7.58 ± 0.06 | 0.15 ± 0.01 | n/a (no bars) |
| `t11_anchor_toggle [full-charge only]` | `mismatched` | **E0** | 1.89 ± 0.00 pp (w: 1.89 pp) | 0.74 ± 0.00 pp (w: 0.74 pp) | 5.00 ± 0.00 pp (w: 5.00 pp) | 4.99 ± 0.00 pp (w: 4.99 pp) | n/a | 1.0 ± 0.0 s (w: 1.0 s) | 120.0 ± 0.0 s (w: 120.0 s) | n/a (run too short) | 0.03 ± 0.00 pp (w: 0.03 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t11_anchor_toggle [full-charge only]` | `mismatched` | **E1** | 0.12 ± 0.00 pp (w: 0.12 pp) | 0.11 ± 0.00 pp (w: 0.11 pp) | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.16 ± 0.01 pp (w: 0.17 pp) | n/a | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.08 ± 0.01 pp (w: 0.09 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 7.37 ± 0.06 | 0.15 ± 0.01 | n/a (no bars) |
| `t11_anchor_toggle [full-charge only]` | `mismatched` | **E2** | 0.13 ± 0.00 pp (w: 0.13 pp) | 0.12 ± 0.00 pp (w: 0.12 pp) | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.20 ± 0.01 pp (w: 0.21 pp) | n/a | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.15 ± 0.01 pp (w: 0.17 pp) | 0.07 ± 0.00 ms (w: 0.07 ms) | 7.37 ± 0.06 | 0.15 ± 0.01 | n/a (no bars) |
| `t11_anchor_toggle [rest anchor only]` | `matched` | **E0** | 11.12 ± 0.02 pp (w: 11.14 pp) | 10.81 ± 0.01 pp (w: 10.83 pp) | 21.22 ± 0.20 pp (w: 21.62 pp) | 18.82 ± 0.25 pp (w: 18.96 pp) | 11.12 ± 0.02 pp (w: 11.14 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t11_anchor_toggle [rest anchor only]` | `matched` | **E1** | 16.63 ± 0.05 pp (w: 16.69 pp) | 15.95 ± 0.07 pp (w: 16.07 pp) | 18.90 ± 0.09 pp (w: 19.04 pp) | 18.81 ± 0.07 pp (w: 18.92 pp) | 16.63 ± 0.05 pp (w: 16.69 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.07 ± 0.00 ms (w: 0.08 ms) | 2.72 ± 0.07 | 0.29 ± 0.02 | n/a (no bars) |
| `t11_anchor_toggle [rest anchor only]` | `matched` | **E2** | 0.63 ± 0.17 pp (w: 1.00 pp) | 0.44 ± 0.12 pp (w: 0.71 pp) | 3.08 ± 1.08 pp (w: 5.29 pp) | 1.37 ± 0.47 pp (w: 2.58 pp) | 0.63 ± 0.17 pp (w: 1.00 pp) | 1.1 ± 0.3 s (w: 2.0 s) | 33.5 ± 53.8 s (w: 161.0 s) | n/a (run too short) | n/a (no reversals) | 0.07 ± 0.00 ms (w: 0.08 ms) | 2.12 ± 0.05 | 0.18 ± 0.01 | n/a (no bars) |
| `t11_anchor_toggle [rest anchor only]` | `mismatched` | **E0** | 11.39 ± 0.01 pp (w: 11.40 pp) | 10.88 ± 0.00 pp (w: 10.89 pp) | 22.89 ± 0.20 pp (w: 23.28 pp) | 21.27 ± 0.08 pp (w: 21.32 pp) | 11.39 ± 0.01 pp (w: 11.40 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t11_anchor_toggle [rest anchor only]` | `mismatched` | **E1** | 16.04 ± 0.03 pp (w: 16.09 pp) | 13.62 ± 0.07 pp (w: 13.75 pp) | 21.39 ± 0.04 pp (w: 21.46 pp) | 21.31 ± 0.04 pp (w: 21.37 pp) | 16.04 ± 0.03 pp (w: 16.09 pp) | never | never | n/a (run too short) | n/a (no reversals) | 0.07 ± 0.00 ms (w: 0.07 ms) | 4.35 ± 0.07 | 0.75 ± 0.03 | n/a (no bars) |
| `t11_anchor_toggle [rest anchor only]` | `mismatched` | **E2** | 8.74 ± 0.07 pp (w: 8.93 pp) | 7.30 ± 0.06 pp (w: 7.45 pp) | 14.12 ± 0.17 pp (w: 14.53 pp) | 13.89 ± 0.15 pp (w: 14.21 pp) | 8.74 ± 0.07 pp (w: 8.93 pp) | 676.3 ± 6.4 s (w: 690.0 s) | 849.3 ± 5.5 s (w: 856.0 s) | n/a (run too short) | n/a (no reversals) | 0.07 ± 0.00 ms (w: 0.07 ms) | 4.52 ± 0.03 | 0.81 ± 0.01 | n/a (no bars) |
| `t12_hysteresis_mismatch` | `matched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t12_hysteresis_mismatch` | `matched` | **E1** | 8.55 ± 0.03 pp (w: 8.60 pp) | 7.48 ± 0.02 pp (w: 7.51 pp) | 14.49 ± 0.27 pp (w: 15.08 pp) | 12.64 ± 0.09 pp (w: 12.83 pp) | 8.55 ± 0.03 pp (w: 8.60 pp) | 3429.4 ± 1.0 s (w: 3431.0 s) | never | n/a (run too short) | 10.60 ± 0.07 pp (w: 10.75 pp) | 0.07 ± 0.00 ms (w: 0.08 ms) | 10.72 ± 0.03 | 4.58 ± 0.03 | n/a (no bars) |
| `t12_hysteresis_mismatch` | `matched` | **E2** | 0.57 ± 0.07 pp (w: 0.67 pp) | 0.45 ± 0.05 pp (w: 0.53 pp) | 2.66 ± 0.66 pp (w: 3.92 pp) | 1.08 ± 0.16 pp (w: 1.40 pp) | 0.57 ± 0.07 pp (w: 0.67 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 72.6 ± 57.6 s (w: 188.0 s) | n/a (run too short) | 0.74 ± 0.11 pp (w: 1.01 pp) | 0.07 ± 0.00 ms (w: 0.08 ms) | 3.29 ± 0.04 | 0.43 ± 0.01 | n/a (no bars) |
| `t12_hysteresis_mismatch` | `mismatched` | **E0** | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.0 ± 0.0 s (w: 1.0 s) | 1.0 ± 0.0 s (w: 1.0 s) | n/a (run too short) | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 ms (w: 0.00 ms) | n/a | n/a | n/a (no bars) |
| `t12_hysteresis_mismatch` | `mismatched` | **E1** | 8.55 ± 0.03 pp (w: 8.60 pp) | 7.48 ± 0.02 pp (w: 7.51 pp) | 14.49 ± 0.27 pp (w: 15.08 pp) | 12.64 ± 0.09 pp (w: 12.83 pp) | 8.55 ± 0.03 pp (w: 8.60 pp) | 3429.4 ± 1.0 s (w: 3431.0 s) | never | n/a (run too short) | 10.60 ± 0.07 pp (w: 10.75 pp) | 0.07 ± 0.01 ms (w: 0.11 ms) | 10.72 ± 0.03 | 4.58 ± 0.03 | n/a (no bars) |
| `t12_hysteresis_mismatch` | `mismatched` | **E2** | 5.66 ± 0.09 pp (w: 5.81 pp) | 4.92 ± 0.06 pp (w: 5.03 pp) | 12.70 ± 0.82 pp (w: 14.12 pp) | 10.74 ± 0.44 pp (w: 11.45 pp) | 5.66 ± 0.09 pp (w: 5.81 pp) | 3370.8 ± 2.9 s (w: 3377.0 s) | never | n/a (run too short) | 8.51 ± 0.34 pp (w: 9.22 pp) | 0.07 ± 0.00 ms (w: 0.08 ms) | 5.67 ± 0.06 | 1.28 ± 0.03 | n/a (no bars) |
| *scheduled* | *n/a* | **E3** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |
| *scheduled* | *n/a* | **E4** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |
| *scheduled* | *n/a* | **E5** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |
| *scheduled* | *n/a* | **E6** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |
| *scheduled* | *n/a* | **E7** | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* | *not implemented* |

## Profile Bars & Pass/Fail Evaluation

Pass/fail criteria loaded from active profile `automotive`:

| Bar Name | Metric | Threshold | Window | Aggregation | Applied Scenarios | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `t1_ocv_error_max_mv` | `ocv_error_mv` | 5.0 mV | full table | max across temperatures | `t1_static_ocv` | Model OCV table error against reference |
| `t2_dynamic_rmse_max` | `rmse` | 2.00 pp | full scenario | worst seed | `smoke`, `t3_t10_minor_loops` | Dynamic cycling RMSE bar |
| `t2_dynamic_max_error` | `max_abs_error` | 5.00 pp | full scenario | worst seed | `smoke`, `t3_t10_minor_loops` | Dynamic cycling maximum error bar |
| `t4_plateau_p95_max` | `p95_error` | 3.00 pp | truth SOC in [0.20, 0.80] | worst seed | `t4_plateau_stress` | 95th percentile error on plateau |
| `t5_converge_time_s` | `converge_time_2pct` | 60.0 s | start to |error| <= 0.02 | worst seed | `t5_initial_soc_offset` | Convergence time from 10pp offset to within 2pp |
| `t6_drift_bess_per_day_max` | `drift_24h` | 1.00 pp | 86400 s (measured) | worst seed | `t6_current_bias` | 24-hour current bias drift bar |
| `t6_mean_error_bar_pp` | `mean_signed_error` | 1.00 pp | full scenario | worst seed | `t6_current_bias` | 24-hour current bias mean signed error bar |
| `t7_error_rise_max` | `error_rise` | 1.00 pp | full scenario | worst seed | `t7_voltage_quant_noise` | RMSE rise under sensor noise above clean baseline |
| `t9_post_rest_step_error_max` | `max_abs_error` | 2.00 pp | post-rest step | worst seed | `t9_rest_relaxation` | Max error during RC relaxation |
| `t10_reversal_spike_max` | `post_reversal_error_60s` | 3.00 pp | 60 s post-reversal | worst seed | `t3_t10_minor_loops` | Error spike after direction reversal |
| `t14_auto_max_ms_per_step` | `ms_per_step_median` | 5.0 ms | per step | worst seed | all scenarios | Median computation latency per step |

### Pass / Fail Matrix

| Estimator | Variant | `t11_anchor_toggle [anchors off]` | `t11_anchor_toggle [full-charge only]` | `t11_anchor_toggle [rest anchor only]` | `t12_hysteresis_mismatch` | `t1_static_ocv` | `t3_t10_minor_loops` | `t4_plateau_stress` | `t5_initial_soc_offset` | `t6_current_bias` | `t6_plateau_only` | `t7_voltage_quant_noise` | `t9_rest_relaxation` | Overall |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **E0** | `matched` | n/a | n/a | n/a | n/a | n/a | PASS | PASS | FAIL | FAIL | n/a | PASS | PASS | FAIL |
| **E0** | `mismatched` | n/a | n/a | n/a | n/a | n/a | PASS | PASS | FAIL | FAIL | n/a | PASS | PASS | FAIL |
| **E1** | `matched` | n/a | n/a | n/a | n/a | n/a | FAIL (full: 15.42 pp, post-warmup: 15.42 pp; bar uses full-run) | FAIL | FAIL | PASS | n/a | PASS | FAIL (full: 10.04 pp, post-warmup: 10.04 pp; bar uses full-run) | FAIL |
| **E1** | `mismatched` | n/a | n/a | n/a | n/a | n/a | FAIL (full: 29.91 pp, post-warmup: 29.91 pp; bar uses full-run) | FAIL | PASS | FAIL | n/a | FAIL | FAIL (full: 14.85 pp, post-warmup: 14.85 pp; bar uses full-run) | FAIL |
| **E2** | `matched` | n/a | n/a | n/a | n/a | n/a | FAIL (full: 5.87 pp, post-warmup: 2.84 pp; bar uses full-run) | PASS | PASS | PASS | n/a | FAIL | FAIL (full: 3.88 pp, post-warmup: 2.43 pp; bar uses full-run) | FAIL |
| **E2** | `mismatched` | n/a | n/a | n/a | n/a | n/a | FAIL (full: 34.97 pp, post-warmup: 34.97 pp; bar uses full-run) | FAIL | FAIL | FAIL | n/a | FAIL | FAIL (full: 12.14 pp, post-warmup: 12.14 pp; bar uses full-run) | FAIL |

**First Rung Meeting All Bars:** `None (all rungs failed at least one bar)`

## E2 vs E1 Head-to-Head Comparison

> Outcome is WIN, TIE, or LOSS based on Plateau RMSE (truth SOC in 20% to 80%). TIE is assigned when the absolute margin is within max(seed_std, tie_band_pp). If fewer than 10% of samples visit the plateau, 'n/a (plateau not visited)' is displayed.

| Scenario | Outcome (Matched) | E1 Plateau RMSE (m) | E2 Plateau RMSE (m) | Margin Matched | Outcome (Mismatched) | E1 Plateau RMSE (mis) | E2 Plateau RMSE (mis) | Margin Mismatched |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `t11_anchor_toggle [anchors off]` | **n/a (plateau not visited)** | n/a (plateau not visited) | n/a (plateau not visited) | n/a | **n/a (plateau not visited)** | n/a (plateau not visited) | n/a (plateau not visited) | n/a |
| `t11_anchor_toggle [full-charge only]` | **n/a (plateau not visited)** | n/a (plateau not visited) | n/a (plateau not visited) | n/a | **n/a (plateau not visited)** | n/a (plateau not visited) | n/a (plateau not visited) | n/a |
| `t11_anchor_toggle [rest anchor only]` | **WIN** | 16.63 pp | 0.63 pp | +16.00 pp | **WIN** | 16.04 pp | 8.74 pp | +7.30 pp |
| `t12_hysteresis_mismatch` | **WIN** | 8.55 pp | 0.57 pp | +7.98 pp | **WIN** | 8.55 pp | 5.66 pp | +2.88 pp |
| `t1_static_ocv` | **TIE** | 1.28 pp | 1.21 pp | +0.08 pp | **TIE** | 5.64 pp | 5.17 pp | +0.46 pp |
| `t3_t10_minor_loops` | **WIN** | 6.51 pp | 0.41 pp | +6.09 pp | **LOSS** | 16.55 pp | 18.28 pp | -1.73 pp |
| `t4_plateau_stress` | **WIN** | 8.55 pp | 0.55 pp | +8.00 pp | **LOSS** | 24.79 pp | 30.27 pp | -5.48 pp |
| `t5_initial_soc_offset` | **WIN** | 2.05 pp | 0.59 pp | +1.46 pp | **LOSS** | 0.87 pp | 4.10 pp | -3.23 pp |
| `t6_current_bias` | **TIE** | 0.42 pp | 0.49 pp | -0.08 pp | **TIE** | 4.57 pp | 4.22 pp | +0.36 pp |
| `t6_plateau_only` | **WIN** | 2.17 pp | 0.36 pp | +1.80 pp | **LOSS** | 7.08 pp | 9.07 pp | -1.99 pp |
| `t7_voltage_quant_noise` | **WIN** | 4.40 pp | 0.94 pp | +3.46 pp | **WIN** | 5.58 pp | 2.70 pp | +2.88 pp |
| `t9_rest_relaxation` | **WIN** | 8.72 pp | 0.47 pp | +8.25 pp | **WIN** | 12.29 pp | 7.04 pp | +5.26 pp |

## Parameter Mismatch Offset Analysis ("Mismatched Beats Matched")

> a parameter error can offset an unmodelled effect; this is not evidence of robustness.

| Scenario | Estimator | Matched RMSE | Mismatched RMSE | Margin (Matched - Mismatched) |
| :--- | :--- | :--- | :--- | :--- |
| `t11_anchor_toggle [rest anchor only]` | **E1** | 16.63 pp | 16.04 pp | +0.58 pp |
| `t5_initial_soc_offset` | **E1** | 1.89 pp | 0.74 pp | +1.15 pp |

## One-Factor-At-A-Time (OFAT) Parameter Sensitivity Sweep

> Evaluates E1 and E2 on `t3_t10_minor_loops`, `t4_plateau_stress`, `t5_initial_soc_offset`, and `t6_plateau_only` under isolated single-parameter perturbations for profile `automotive`.

### Combined Mismatch Parameter Specification

The combined mismatch variant applies all of the following simultaneous parameter offsets:
- `capacity`: -5.0% (`capacity_pct = -5.0%`)
- `R0`: +10.0% (`r0_pct = +10.0%`)
- `R1`: +10.0% (`r1_pct = +10.0%`)
- `R2`: +10.0% (`r2_pct = +10.0%`)
- `tau1`: 0.0% (`tau1_pct = 0.0%`)
- `tau2`: 0.0% (`tau2_pct = 0.0%`)
- `OCV offset`: +5.0 mV (`ocv_offset_mv = +5.0 mV`)
- `hysteresis amplitude M`: +10.0% (`hysteresis_amplitude_pct = +10.0%`)
- `hysteresis gamma`: +10.0% (`hysteresis_gamma_pct = +10.0%`)

### E1 Parameter Ranking by Effect Magnitude

| Rank | Parameter | Maximum Effect on RMSE |
| :--- | :--- | :--- |
| 1 | `R0` | 14.452 pp |
| 2 | `R2` | 11.856 pp |
| 3 | `R1` | 9.577 pp |
| 4 | `ocv_offset` | 6.123 pp |
| 5 | `capacity` | 0.311 pp |
| n/a | `hysteresis_M` | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_gamma` | n/a (E1 has no hysteresis state) |

### E1 Parameter Sensitivity Sweep

| Rank | Parameter | Sign | Size | Scenario | RMSE | Max Error | Plateau RMSE | Effect on RMSE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `R0` | `+` | `+20%` | `t3_t10_minor_loops` | 15.58 pp | 37.49 pp | 15.58 pp | 9.261 pp |
| 1 | `R0` | `-` | `-20%` | `t3_t10_minor_loops` | 14.89 pp | 42.34 pp | 14.89 pp | 8.572 pp |
| 1 | `R0` | `+` | `+20%` | `t4_plateau_stress` | 21.68 pp | 40.03 pp | 21.68 pp | 13.115 pp |
| 1 | `R0` | `-` | `-20%` | `t4_plateau_stress` | 23.02 pp | 39.66 pp | 23.02 pp | 14.452 pp |
| 1 | `R0` | `+` | `+20%` | `t5_initial_soc_offset` | 2.31 pp | 5.22 pp | 2.73 pp | 0.373 pp |
| 1 | `R0` | `-` | `-20%` | `t5_initial_soc_offset` | 4.13 pp | 19.32 pp | 4.55 pp | 2.196 pp |
| 1 | `R0` | `+` | `+20%` | `t6_plateau_only` | 5.50 pp | 40.09 pp | 5.50 pp | 3.352 pp |
| 1 | `R0` | `-` | `-20%` | `t6_plateau_only` | 5.39 pp | 39.93 pp | 5.39 pp | 3.235 pp |
| 2 | `R2` | `+` | `+20%` | `t3_t10_minor_loops` | 6.45 pp | 18.55 pp | 6.45 pp | 0.138 pp |
| 2 | `R2` | `-` | `-20%` | `t3_t10_minor_loops` | 13.08 pp | 23.44 pp | 13.08 pp | 6.760 pp |
| 2 | `R2` | `+` | `+20%` | `t4_plateau_stress` | 17.64 pp | 27.71 pp | 17.64 pp | 9.070 pp |
| 2 | `R2` | `-` | `-20%` | `t4_plateau_stress` | 20.42 pp | 32.05 pp | 20.42 pp | 11.856 pp |
| 2 | `R2` | `+` | `+20%` | `t5_initial_soc_offset` | 0.66 pp | 8.21 pp | 0.77 pp | 1.281 pp |
| 2 | `R2` | `-` | `-20%` | `t5_initial_soc_offset` | 3.18 pp | 8.21 pp | 3.36 pp | 1.244 pp |
| 2 | `R2` | `+` | `+20%` | `t6_plateau_only` | 3.76 pp | 27.87 pp | 3.76 pp | 1.604 pp |
| 2 | `R2` | `-` | `-20%` | `t6_plateau_only` | 5.21 pp | 23.06 pp | 5.21 pp | 3.055 pp |
| 3 | `R1` | `+` | `+20%` | `t3_t10_minor_loops` | 6.66 pp | 18.56 pp | 6.66 pp | 0.344 pp |
| 3 | `R1` | `-` | `-20%` | `t3_t10_minor_loops` | 11.84 pp | 23.36 pp | 11.84 pp | 5.522 pp |
| 3 | `R1` | `+` | `+20%` | `t4_plateau_stress` | 10.87 pp | 17.72 pp | 10.87 pp | 2.306 pp |
| 3 | `R1` | `-` | `-20%` | `t4_plateau_stress` | 18.14 pp | 27.99 pp | 18.14 pp | 9.577 pp |
| 3 | `R1` | `+` | `+20%` | `t5_initial_soc_offset` | 0.81 pp | 8.21 pp | 0.88 pp | 1.123 pp |
| 3 | `R1` | `-` | `-20%` | `t5_initial_soc_offset` | 3.03 pp | 8.21 pp | 3.28 pp | 1.091 pp |
| 3 | `R1` | `+` | `+20%` | `t6_plateau_only` | 2.92 pp | 21.65 pp | 2.92 pp | 0.768 pp |
| 3 | `R1` | `-` | `-20%` | `t6_plateau_only` | 3.98 pp | 23.21 pp | 3.98 pp | 1.827 pp |
| 4 | `ocv_offset` | `+` | `+2 mV` | `t3_t10_minor_loops` | 8.43 pp | 15.91 pp | 8.43 pp | 2.118 pp |
| 4 | `ocv_offset` | `-` | `-2 mV` | `t3_t10_minor_loops` | 7.30 pp | 14.15 pp | 7.30 pp | 0.980 pp |
| 4 | `ocv_offset` | `+` | `+5 mV` | `t3_t10_minor_loops` | 12.44 pp | 17.30 pp | 12.44 pp | 6.123 pp |
| 4 | `ocv_offset` | `-` | `-5 mV` | `t3_t10_minor_loops` | 11.05 pp | 17.86 pp | 11.05 pp | 4.733 pp |
| 4 | `ocv_offset` | `+` | `+2 mV` | `t4_plateau_stress` | 8.55 pp | 16.39 pp | 8.55 pp | 0.011 pp |
| 4 | `ocv_offset` | `-` | `-2 mV` | `t4_plateau_stress` | 8.75 pp | 14.52 pp | 8.75 pp | 0.187 pp |
| 4 | `ocv_offset` | `+` | `+5 mV` | `t4_plateau_stress` | 8.87 pp | 17.75 pp | 8.87 pp | 0.307 pp |
| 4 | `ocv_offset` | `-` | `-5 mV` | `t4_plateau_stress` | 9.40 pp | 16.89 pp | 9.40 pp | 0.831 pp |
| 4 | `ocv_offset` | `+` | `+2 mV` | `t5_initial_soc_offset` | 2.29 pp | 9.81 pp | 2.50 pp | 0.350 pp |
| 4 | `ocv_offset` | `-` | `-2 mV` | `t5_initial_soc_offset` | 1.58 pp | 6.61 pp | 1.70 pp | 0.354 pp |
| 4 | `ocv_offset` | `+` | `+5 mV` | `t5_initial_soc_offset` | 2.78 pp | 12.21 pp | 3.05 pp | 0.840 pp |
| 4 | `ocv_offset` | `-` | `-5 mV` | `t5_initial_soc_offset` | 1.14 pp | 4.21 pp | 1.21 pp | 0.798 pp |
| 4 | `ocv_offset` | `+` | `+2 mV` | `t6_plateau_only` | 2.78 pp | 14.26 pp | 2.78 pp | 0.631 pp |
| 4 | `ocv_offset` | `-` | `-2 mV` | `t6_plateau_only` | 2.46 pp | 11.04 pp | 2.46 pp | 0.304 pp |
| 4 | `ocv_offset` | `+` | `+5 mV` | `t6_plateau_only` | 4.64 pp | 16.59 pp | 4.64 pp | 2.491 pp |
| 4 | `ocv_offset` | `-` | `-5 mV` | `t6_plateau_only` | 5.80 pp | 8.99 pp | 5.80 pp | 3.652 pp |
| 5 | `capacity` | `+` | `+5%` | `t3_t10_minor_loops` | 6.26 pp | 14.80 pp | 6.26 pp | 0.061 pp |
| 5 | `capacity` | `-` | `-5%` | `t3_t10_minor_loops` | 6.38 pp | 14.88 pp | 6.38 pp | 0.064 pp |
| 5 | `capacity` | `+` | `+5%` | `t4_plateau_stress` | 8.34 pp | 14.94 pp | 8.34 pp | 0.226 pp |
| 5 | `capacity` | `-` | `-5%` | `t4_plateau_stress` | 8.81 pp | 15.14 pp | 8.81 pp | 0.243 pp |
| 5 | `capacity` | `+` | `+5%` | `t5_initial_soc_offset` | 1.92 pp | 8.21 pp | 2.08 pp | 0.021 pp |
| 5 | `capacity` | `-` | `-5%` | `t5_initial_soc_offset` | 1.96 pp | 8.21 pp | 2.12 pp | 0.021 pp |
| 5 | `capacity` | `+` | `+5%` | `t6_plateau_only` | 2.27 pp | 13.06 pp | 2.27 pp | 0.114 pp |
| 5 | `capacity` | `-` | `-5%` | `t6_plateau_only` | 2.46 pp | 13.29 pp | 2.46 pp | 0.311 pp |
| n/a | `combined mismatch` | `+/-` | `combined` | `t3_t10_minor_loops` | 16.59 pp | 29.91 pp | 16.59 pp | 10.272 pp |
| n/a | `combined mismatch` | `+/-` | `combined` | `t4_plateau_stress` | 24.80 pp | 37.94 pp | 24.80 pp | 16.239 pp |
| n/a | `combined mismatch` | `+/-` | `combined` | `t5_initial_soc_offset` | 0.73 pp | 6.65 pp | 0.85 pp | 1.209 pp |
| n/a | `combined mismatch` | `+/-` | `combined` | `t6_plateau_only` | 7.10 pp | 32.43 pp | 7.10 pp | 4.948 pp |
| n/a | `hysteresis_M` | `+` | `+30%` | `t3_t10_minor_loops` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_M` | `-` | `-30%` | `t3_t10_minor_loops` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_M` | `+` | `+30%` | `t4_plateau_stress` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_M` | `-` | `-30%` | `t4_plateau_stress` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_M` | `+` | `+30%` | `t5_initial_soc_offset` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_M` | `-` | `-30%` | `t5_initial_soc_offset` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_M` | `+` | `+30%` | `t6_plateau_only` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_M` | `-` | `-30%` | `t6_plateau_only` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_gamma` | `+` | `+50%` | `t3_t10_minor_loops` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_gamma` | `-` | `-50%` | `t3_t10_minor_loops` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_gamma` | `+` | `+50%` | `t4_plateau_stress` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_gamma` | `-` | `-50%` | `t4_plateau_stress` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_gamma` | `+` | `+50%` | `t5_initial_soc_offset` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_gamma` | `-` | `-50%` | `t5_initial_soc_offset` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_gamma` | `+` | `+50%` | `t6_plateau_only` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |
| n/a | `hysteresis_gamma` | `-` | `-50%` | `t6_plateau_only` | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) | n/a (E1 has no hysteresis state) |

### E2 Parameter Ranking by Effect Magnitude

| Rank | Parameter | Maximum Effect on RMSE |
| :--- | :--- | :--- |
| 1 | `R0` | 26.560 pp |
| 2 | `R2` | 25.173 pp |
| 3 | `R1` | 19.951 pp |
| 4 | `ocv_offset` | 8.402 pp |
| 5 | `hysteresis_M` | 4.236 pp |
| 6 | `hysteresis_gamma` | 1.597 pp |
| 7 | `capacity` | 0.553 pp |

### E2 Parameter Sensitivity Sweep

| Rank | Parameter | Sign | Size | Scenario | RMSE | Max Error | Plateau RMSE | Effect on RMSE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `R0` | `+` | `+20%` | `t3_t10_minor_loops` | 17.49 pp | 35.88 pp | 17.49 pp | 17.012 pp |
| 1 | `R0` | `-` | `-20%` | `t3_t10_minor_loops` | 12.61 pp | 40.52 pp | 12.61 pp | 12.133 pp |
| 1 | `R0` | `+` | `+20%` | `t4_plateau_stress` | 27.13 pp | 40.56 pp | 27.13 pp | 26.560 pp |
| 1 | `R0` | `-` | `-20%` | `t4_plateau_stress` | 19.54 pp | 37.95 pp | 19.54 pp | 18.967 pp |
| 1 | `R0` | `+` | `+20%` | `t5_initial_soc_offset` | 4.61 pp | 5.41 pp | 4.91 pp | 3.834 pp |
| 1 | `R0` | `-` | `-20%` | `t5_initial_soc_offset` | 3.36 pp | 18.80 pp | 3.87 pp | 2.581 pp |
| 1 | `R0` | `+` | `+20%` | `t6_plateau_only` | 6.58 pp | 38.86 pp | 6.58 pp | 6.190 pp |
| 1 | `R0` | `-` | `-20%` | `t6_plateau_only` | 4.15 pp | 38.21 pp | 4.15 pp | 3.758 pp |
| 2 | `R2` | `+` | `+20%` | `t3_t10_minor_loops` | 11.76 pp | 28.59 pp | 11.76 pp | 11.280 pp |
| 2 | `R2` | `-` | `-20%` | `t3_t10_minor_loops` | 11.13 pp | 19.75 pp | 11.13 pp | 10.660 pp |
| 2 | `R2` | `+` | `+20%` | `t4_plateau_stress` | 25.74 pp | 38.63 pp | 25.74 pp | 25.173 pp |
| 2 | `R2` | `-` | `-20%` | `t4_plateau_stress` | 16.23 pp | 25.41 pp | 16.23 pp | 15.659 pp |
| 2 | `R2` | `+` | `+20%` | `t5_initial_soc_offset` | 3.05 pp | 7.88 pp | 2.98 pp | 2.266 pp |
| 2 | `R2` | `-` | `-20%` | `t5_initial_soc_offset` | 2.20 pp | 7.89 pp | 2.47 pp | 1.417 pp |
| 2 | `R2` | `+` | `+20%` | `t6_plateau_only` | 5.81 pp | 36.58 pp | 5.81 pp | 5.420 pp |
| 2 | `R2` | `-` | `-20%` | `t6_plateau_only` | 3.52 pp | 19.73 pp | 3.52 pp | 3.131 pp |
| 3 | `R1` | `+` | `+20%` | `t3_t10_minor_loops` | 10.71 pp | 27.33 pp | 10.71 pp | 10.235 pp |
| 3 | `R1` | `-` | `-20%` | `t3_t10_minor_loops` | 9.72 pp | 20.49 pp | 9.72 pp | 9.244 pp |
| 3 | `R1` | `+` | `+20%` | `t4_plateau_stress` | 20.52 pp | 31.40 pp | 20.52 pp | 19.951 pp |
| 3 | `R1` | `-` | `-20%` | `t4_plateau_stress` | 13.26 pp | 21.21 pp | 13.26 pp | 12.692 pp |
| 3 | `R1` | `+` | `+20%` | `t5_initial_soc_offset` | 2.18 pp | 7.88 pp | 2.28 pp | 1.404 pp |
| 3 | `R1` | `-` | `-20%` | `t5_initial_soc_offset` | 2.04 pp | 7.89 pp | 2.34 pp | 1.257 pp |
| 3 | `R1` | `+` | `+20%` | `t6_plateau_only` | 4.44 pp | 31.18 pp | 4.44 pp | 4.049 pp |
| 3 | `R1` | `-` | `-20%` | `t6_plateau_only` | 2.49 pp | 20.36 pp | 2.49 pp | 2.098 pp |
| 4 | `ocv_offset` | `+` | `+2 mV` | `t3_t10_minor_loops` | 3.98 pp | 4.83 pp | 3.98 pp | 3.509 pp |
| 4 | `ocv_offset` | `-` | `-2 mV` | `t3_t10_minor_loops` | 4.04 pp | 6.41 pp | 4.04 pp | 3.562 pp |
| 4 | `ocv_offset` | `+` | `+5 mV` | `t3_t10_minor_loops` | 8.63 pp | 9.42 pp | 8.63 pp | 8.152 pp |
| 4 | `ocv_offset` | `-` | `-5 mV` | `t3_t10_minor_loops` | 8.88 pp | 12.11 pp | 8.88 pp | 8.402 pp |
| 4 | `ocv_offset` | `+` | `+2 mV` | `t4_plateau_stress` | 2.94 pp | 4.51 pp | 2.94 pp | 2.368 pp |
| 4 | `ocv_offset` | `-` | `-2 mV` | `t4_plateau_stress` | 2.80 pp | 6.60 pp | 2.80 pp | 2.229 pp |
| 4 | `ocv_offset` | `+` | `+5 mV` | `t4_plateau_stress` | 7.24 pp | 9.58 pp | 7.24 pp | 6.672 pp |
| 4 | `ocv_offset` | `-` | `-5 mV` | `t4_plateau_stress` | 7.38 pp | 12.19 pp | 7.38 pp | 6.810 pp |
| 4 | `ocv_offset` | `+` | `+2 mV` | `t5_initial_soc_offset` | 1.10 pp | 9.46 pp | 1.29 pp | 0.318 pp |
| 4 | `ocv_offset` | `-` | `-2 mV` | `t5_initial_soc_offset` | 0.72 pp | 6.31 pp | 0.83 pp | 0.060 pp |
| 4 | `ocv_offset` | `+` | `+5 mV` | `t5_initial_soc_offset` | 1.68 pp | 11.81 pp | 1.96 pp | 0.898 pp |
| 4 | `ocv_offset` | `-` | `-5 mV` | `t5_initial_soc_offset` | 1.74 pp | 3.96 pp | 1.94 pp | 0.956 pp |
| 4 | `ocv_offset` | `+` | `+2 mV` | `t6_plateau_only` | 0.98 pp | 3.17 pp | 0.98 pp | 0.592 pp |
| 4 | `ocv_offset` | `-` | `-2 mV` | `t6_plateau_only` | 1.98 pp | 9.06 pp | 1.98 pp | 1.591 pp |
| 4 | `ocv_offset` | `+` | `+5 mV` | `t6_plateau_only` | 2.81 pp | 7.81 pp | 2.81 pp | 2.428 pp |
| 4 | `ocv_offset` | `-` | `-5 mV` | `t6_plateau_only` | 4.42 pp | 14.11 pp | 4.42 pp | 4.038 pp |
| 5 | `hysteresis_M` | `+` | `+30%` | `t3_t10_minor_loops` | 2.67 pp | 9.22 pp | 2.67 pp | 2.198 pp |
| 5 | `hysteresis_M` | `-` | `-30%` | `t3_t10_minor_loops` | 1.98 pp | 6.03 pp | 1.98 pp | 1.505 pp |
| 5 | `hysteresis_M` | `+` | `+30%` | `t4_plateau_stress` | 4.81 pp | 8.34 pp | 4.81 pp | 4.236 pp |
| 5 | `hysteresis_M` | `-` | `-30%` | `t4_plateau_stress` | 3.03 pp | 6.83 pp | 3.03 pp | 2.463 pp |
| 5 | `hysteresis_M` | `+` | `+30%` | `t5_initial_soc_offset` | 1.11 pp | 7.67 pp | 1.22 pp | 0.331 pp |
| 5 | `hysteresis_M` | `-` | `-30%` | `t5_initial_soc_offset` | 1.04 pp | 8.05 pp | 1.20 pp | 0.262 pp |
| 5 | `hysteresis_M` | `+` | `+30%` | `t6_plateau_only` | 1.13 pp | 11.39 pp | 1.13 pp | 0.739 pp |
| 5 | `hysteresis_M` | `-` | `-30%` | `t6_plateau_only` | 0.67 pp | 4.20 pp | 0.67 pp | 0.284 pp |
| 6 | `hysteresis_gamma` | `+` | `+50%` | `t3_t10_minor_loops` | 1.45 pp | 6.18 pp | 1.45 pp | 0.975 pp |
| 6 | `hysteresis_gamma` | `-` | `-50%` | `t3_t10_minor_loops` | 1.92 pp | 5.36 pp | 1.92 pp | 1.444 pp |
| 6 | `hysteresis_gamma` | `+` | `+50%` | `t4_plateau_stress` | 1.52 pp | 5.41 pp | 1.52 pp | 0.946 pp |
| 6 | `hysteresis_gamma` | `-` | `-50%` | `t4_plateau_stress` | 2.17 pp | 6.87 pp | 2.17 pp | 1.597 pp |
| 6 | `hysteresis_gamma` | `+` | `+50%` | `t5_initial_soc_offset` | 0.81 pp | 7.89 pp | 0.95 pp | 0.030 pp |
| 6 | `hysteresis_gamma` | `-` | `-50%` | `t5_initial_soc_offset` | 1.33 pp | 7.89 pp | 1.55 pp | 0.547 pp |
| 6 | `hysteresis_gamma` | `+` | `+50%` | `t6_plateau_only` | 0.48 pp | 7.98 pp | 0.48 pp | 0.098 pp |
| 6 | `hysteresis_gamma` | `-` | `-50%` | `t6_plateau_only` | 0.33 pp | 3.12 pp | 0.33 pp | 0.055 pp |
| 7 | `capacity` | `+` | `+5%` | `t3_t10_minor_loops` | 0.46 pp | 2.32 pp | 0.46 pp | 0.016 pp |
| 7 | `capacity` | `-` | `-5%` | `t3_t10_minor_loops` | 0.51 pp | 2.98 pp | 0.51 pp | 0.030 pp |
| 7 | `capacity` | `+` | `+5%` | `t4_plateau_stress` | 0.85 pp | 2.95 pp | 0.85 pp | 0.275 pp |
| 7 | `capacity` | `-` | `-5%` | `t4_plateau_stress` | 0.36 pp | 3.28 pp | 0.36 pp | 0.211 pp |
| 7 | `capacity` | `+` | `+5%` | `t5_initial_soc_offset` | 0.79 pp | 7.88 pp | 0.93 pp | 0.011 pp |
| 7 | `capacity` | `-` | `-5%` | `t5_initial_soc_offset` | 0.77 pp | 7.89 pp | 0.91 pp | 0.009 pp |
| 7 | `capacity` | `+` | `+5%` | `t6_plateau_only` | 0.94 pp | 5.32 pp | 0.94 pp | 0.553 pp |
| 7 | `capacity` | `-` | `-5%` | `t6_plateau_only` | 0.90 pp | 5.62 pp | 0.90 pp | 0.509 pp |
| n/a | `combined mismatch` | `+/-` | `combined` | `t3_t10_minor_loops` | 18.31 pp | 34.88 pp | 18.31 pp | 17.835 pp |
| n/a | `combined mismatch` | `+/-` | `combined` | `t4_plateau_stress` | 30.26 pp | 43.45 pp | 30.26 pp | 29.689 pp |
| n/a | `combined mismatch` | `+/-` | `combined` | `t5_initial_soc_offset` | 3.66 pp | 6.30 pp | 3.62 pp | 2.877 pp |
| n/a | `combined mismatch` | `+/-` | `combined` | `t6_plateau_only` | 9.10 pp | 42.01 pp | 9.10 pp | 8.717 pp |

## T1 OCV Model Check

> Evaluates model OCV table error against reference plant OCV table across temperature calibration points.

| Variant | Temperature | Max Error (mV) | RMS Error (mV) | Bar Threshold | Margin to Bar | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `matched (0 mV)` | `15.0 C` | 0.00 mV | 0.00 mV | 5.0 mV | +5.00 mV | PASS |
| `matched (0 mV)` | `25.0 C` | 0.00 mV | 0.00 mV | 5.0 mV | +5.00 mV | PASS |
| `matched (0 mV)` | `35.0 C` | 0.00 mV | 0.00 mV | 5.0 mV | +5.00 mV | PASS |
| `mismatched (3 mV)` | `15.0 C` | 3.00 mV | 3.00 mV | 5.0 mV | +2.00 mV | PASS |
| `mismatched (3 mV)` | `25.0 C` | 3.00 mV | 3.00 mV | 5.0 mV | +2.00 mV | PASS |
| `mismatched (3 mV)` | `35.0 C` | 3.00 mV | 3.00 mV | 5.0 mV | +2.00 mV | PASS |
| `mismatched (5 mV)` | `15.0 C` | 5.00 mV | 5.00 mV | 5.0 mV | +0.00 mV | PASS |
| `mismatched (5 mV)` | `25.0 C` | 5.00 mV | 5.00 mV | 5.0 mV | +0.00 mV | PASS |
| `mismatched (5 mV)` | `35.0 C` | 5.00 mV | 5.00 mV | 5.0 mV | +0.00 mV | PASS |

## T6 Current Bias & Drift Diagnostics

> Evaluates estimator current bias drift over 24 hours under sensor current offset (0.2 A).

### `t6_current_bias`
- **SOC Range:** `[69.4%, 70.0%]`
- **Time on Plateau ([0.20, 0.80]):** `100.0%`

| Estimator | Variant | Drift 24h | Mean Signed Error | Status |
| :--- | :--- | :--- | :--- | :--- |
| **E0** | `matched` | -4.80 ± 0.01 pp (w: -4.78 pp) | -2.40 ± 0.01 pp (w: -2.38 pp) | FAIL |
| **E0** | `mismatched` | -5.06 ± 0.01 pp (w: -5.04 pp) | -2.54 ± 0.01 pp (w: -2.53 pp) | FAIL |
| **E1** | `matched` | 0.20 ± 0.02 pp (w: 0.24 pp) | 0.40 ± 0.01 pp (w: 0.40 pp) | PASS |
| **E1** | `mismatched` | -0.01 ± 0.06 pp (w: 0.08 pp) | -4.57 ± 0.01 pp (w: -4.56 pp) | FAIL |
| **E2** | `matched` | 0.07 ± 0.03 pp (w: 0.12 pp) | 0.48 ± 0.01 pp (w: 0.49 pp) | PASS |
| **E2** | `mismatched` | -0.10 ± 0.06 pp (w: -0.01 pp) | -4.21 ± 0.01 pp (w: -4.20 pp) | FAIL |

> Note: The 24-hour drift metric measures change in error over time (end error minus start error), so the drift bar evaluates stability over time and does not detect constant offsets.

### `t6_plateau_only`
- **SOC Range:** `[29.4%, 70.5%]`
- **Time on Plateau ([0.20, 0.80]):** `100.0%`
- **Current Sensor Offset:** `+0.20 A`
- **E0 Signed SOC Error Progression:**
  - $t = 0\text{ s}$: `-0.00 pp`
  - $t = 43200\text{ s}$ (12 h): `-2.41 pp`
  - $t = 86400\text{ s}$ (24 h): `-4.80 pp`
  - Total 24h Drift: `-4.80 pp` (exact match to theoretical $-0.20\text{ A} \times 86400 / (3600 \times 100) = -4.80\text{ pp}$)

| Estimator | Variant | Drift 24h | Mean Signed Error | Status |
| :--- | :--- | :--- | :--- | :--- |
| **E0** | `matched` | -4.80 ± 0.01 pp (w: -4.76 pp) | -2.40 ± 0.01 pp (w: -2.38 pp) | bar not applied |
| **E0** | `mismatched` | -5.01 ± 0.01 pp (w: -4.97 pp) | -2.53 ± 0.01 pp (w: -2.51 pp) | bar not applied |
| **E1** | `matched` | 0.87 ± 0.06 pp (w: 0.99 pp) | -0.38 ± 0.02 pp (w: -0.33 pp) | bar not applied |
| **E1** | `mismatched` | -3.60 ± 0.17 pp (w: -3.38 pp) | -5.01 ± 0.03 pp (w: -4.96 pp) | bar not applied |
| **E2** | `matched` | -0.05 ± 0.04 pp (w: 0.01 pp) | 0.30 ± 0.02 pp (w: 0.34 pp) | bar not applied |
| **E2** | `mismatched` | -4.46 ± 0.19 pp (w: -4.15 pp) | -3.88 ± 0.04 pp (w: -3.82 pp) | bar not applied |

> Note: The 24-hour drift metric measures change in error over time (end error minus start error), so the drift bar evaluates stability over time and does not detect constant offsets.

## T7 Sensor Noise Error Rise Diagnostic

> Evaluates estimator degradation under sensor quantization and ADC noise against a clean baseline with identical seed and duty.

| Estimator | Variant | Clean RMSE | Noisy RMSE | Signed Rise (Noisy - Clean) | Clipped Rise (for Bar) | Bar Threshold | Result | Max Error Rise |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **E0** | `matched` | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) | +0.00 ± 0.00 pp (0/10 negative) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.00 pp | **PASS** | 0.00 ± 0.00 pp (w: 0.00 pp) |
| **E0** | `mismatched` | 0.03 ± 0.00 pp (w: 0.03 pp) | 0.03 ± 0.00 pp (w: 0.03 pp) | +0.00 ± 0.00 pp (4/10 negative) | 0.00 ± 0.00 pp (w: 0.00 pp) | 1.00 pp | **PASS** | 0.00 ± 0.00 pp (w: 0.00 pp) |
| **E1** | `matched` | 4.68 ± 0.00 pp (w: 4.68 pp) | 4.40 ± 0.51 pp (w: 5.00 pp) | -0.28 ± 0.51 pp (6/10 negative) | 0.07 ± 0.10 pp (w: 0.32 pp) | 1.00 pp | **PASS** | 0.65 ± 1.40 pp (w: 4.81 pp) |
| **E1** | `mismatched` | 4.67 ± 0.00 pp (w: 4.67 pp) | 5.58 ± 0.98 pp (w: 7.88 pp) | +0.90 ± 0.98 pp (2/10 negative) | 0.92 ± 0.96 pp (w: 3.21 pp) | 1.00 pp | **FAIL** | 1.26 ± 1.52 pp (w: 4.16 pp) |
| **E2** | `matched` | 0.00 ± 0.00 pp (w: 0.00 pp) | 0.94 ± 0.35 pp (w: 1.83 pp) | +0.94 ± 0.35 pp (0/10 negative) | 0.94 ± 0.35 pp (w: 1.83 pp) | 1.00 pp | **FAIL** | 5.53 ± 2.60 pp (w: 11.10 pp) |
| **E2** | `mismatched` | 2.36 ± 0.00 pp (w: 2.36 pp) | 2.70 ± 0.39 pp (w: 3.55 pp) | +0.34 ± 0.39 pp (1/10 negative) | 0.35 ± 0.38 pp (w: 1.20 pp) | 1.00 pp | **FAIL** | 1.30 ± 1.25 pp (w: 4.72 pp) |

> **Metric definitions and physical behavior:**
> - **Clipped Rise:** Measures strictly positive error degradation (`max(0, noisy - clean)`) against the pass bar threshold of 1.00 pp.
> - **Signed Rise:** Measures actual net difference (`noisy_rmse - clean_rmse`).

## T11 Recalibration Anchor Modes & Verification

> T11 evaluates anchor triggering across three configurations: `anchors off`, `full-charge only`, and `rest anchor only`.

### Overrides Used for Full-Charge Anchor
In `configs/assumptions/scenarios/t11_anchor_toggle.yaml`, the following configuration overrides are applied relative to `base.yaml`:
- `duty.cycle_type`: `anchor_evaluation` (scripts a CCCV taper sequence)
- `duty.initial_soc`: `0.9967` (starts near top of charge)
- `duty.total_duration_s`: `830.0 s`
- `filter.initial_soc_offset`: `-0.05` (-5.0 pp starting offset to test anchor pull-in)
- `soc_definition.anchor_enabled`: `true`
- `soc_definition.full_charge_anchor_enabled`: `true`
- `soc_definition.full_charge_current_threshold_a`: `2.0 A` (raised from base default 0.5 A to match evaluation taper current)
- `soc_definition.rest_current_threshold_a`: `0.3 A` (raised from base default 0.1 A)
- `soc_definition.rest_duration_threshold_s`: `600.0 s`

| Configuration | Estimator | Variant | Anchor Events | Samples Anchored | First Anchor Time | Pre-Anchor Error | Post-Anchor Error | Error Change |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `t11_anchor_toggle [anchors off]` | **E0** | `matched` | 0 | 0 | never | n/a | n/a | n/a |
| `t11_anchor_toggle [anchors off]` | **E0** | `mismatched` | 0 | 0 | never | n/a | n/a | n/a |
| `t11_anchor_toggle [full-charge only]` | **E0** | `matched` | 1 | 1 | 120.0 s | 5.00 pp | 0.01 pp | -4.99 pp (error reduced) |
| `t11_anchor_toggle [full-charge only]` | **E0** | `mismatched` | 1 | 1 | 120.0 s | 4.98 pp | 0.01 pp | -4.97 pp (error reduced) |
| `t11_anchor_toggle [rest anchor only]` | **E0** | `matched` | 1 | 101 | 960.0 s | 10.00 pp | 17.96 pp | +7.96 pp (error introduced) |
| `t11_anchor_toggle [rest anchor only]` | **E0** | `mismatched` | 1 | 101 | 960.0 s | 9.74 pp | 20.98 pp | +11.25 pp (error introduced) |

## Transient Spike Anomaly Detection & Metric Warmup

> Flags any evaluation run where maximum absolute error exceeds 5.0 pp while RMSE remains below 1.0 pp, and evaluates the impact of initial metric warmup (`run.metric_warmup_s = 10.0 s`).

### T7 Seed 0 Initial Transients (E2 First 5 Steps)

| Step | Time (s) | Estimate SOC | True SOC | Signed Error (pp) | Kalman Gain K_soc | Voltage Residual (mV) | Innovation Var S (uV^2) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | 1.0 s | 0.6383 | 0.5999 | +3.84 pp | 9.5672 | +4.02 mV | 52.3 uV^2 |
| 1 | 2.0 s | 0.6674 | 0.5997 | +6.77 pp | 6.6687 | +4.38 mV | 75.0 uV^2 |
| 2 | 3.0 s | 0.6540 | 0.5996 | +5.44 pp | 4.0035 | -3.31 mV | 41.6 uV^2 |
| 3 | 4.0 s | 0.6263 | 0.5994 | +2.69 pp | 2.8667 | -9.61 mV | 35.0 uV^2 |
| 4 | 5.0 s | 0.6288 | 0.5993 | +2.95 pp | 2.2346 | +1.18 mV | 32.2 uV^2 |

> **Diagnostic Insight:** At step 0, initial state covariance $P_{0,\text{soc}} = 0.0100$ and measurement noise covariance $R_v = 2.50e-05\text{ V}^2$ produce an initial Kalman gain $K_{\text{soc}} = 9.5672$. When the first ADC quantization and measurement noise realization introduces a residual of +4.02\text{ mV}, the Kalman update immediately shifts by +3.84\text{ pp}. By step 1, the gain falls to 6.67 and error drops to +6.77\text{ pp}.

### t6_plateau_only Spike Windows (+/- 5 Samples)

- **Operating C-rate:** `2.0 C`
- **Applied Current Magnitude:** `200.00 A`

#### Seed 0 Window around t = 50 s

- **Window C-rate:** `2.0 C` | **Applied Current:** `200.00 A`

| Sample k | Time (s) | Dropout | Current (A) | Terminal Voltage (V) | Voltage Residual (mV) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | 10.0 s | False | 200.20 A | 3.0950 V | n/a |
| 1 | 20.0 s | False | 200.18 A | 3.0060 V | n/a |
| 2 | 30.0 s | False | 200.21 A | 2.9510 V | n/a |
| 3 | 40.0 s | False | 200.18 A | 2.9100 V | n/a |
| 4 | 50.0 s | False | 200.24 A | 2.8880 V | n/a |
| 5 | 60.0 s | False | 200.25 A | 2.8660 V | n/a |
| 6 | 70.0 s | False | 200.16 A | 2.8470 V | n/a |
| 7 | 80.0 s | False | 200.21 A | 2.8370 V | n/a |
| 8 | 90.0 s | False | 200.20 A | 2.8280 V | n/a |
| 9 | 100.0 s | False | 200.21 A | 2.8170 V | n/a |

#### Seed 0 Window around t = 120 s

- **Window C-rate:** `2.0 C` | **Applied Current:** `200.00 A`

| Sample k | Time (s) | Dropout | Current (A) | Terminal Voltage (V) | Voltage Residual (mV) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 6 | 70.0 s | False | 200.16 A | 2.8470 V | n/a |
| 7 | 80.0 s | False | 200.21 A | 2.8370 V | n/a |
| 8 | 90.0 s | False | 200.20 A | 2.8280 V | n/a |
| 9 | 100.0 s | False | 200.21 A | 2.8170 V | n/a |
| 10 | 110.0 s | False | 200.21 A | 2.8120 V | n/a |
| 11 | 120.0 s | False | 200.15 A | 2.8070 V | n/a |
| 12 | 130.0 s | False | 200.20 A | 2.8010 V | n/a |
| 13 | 140.0 s | False | 200.16 A | 2.7990 V | n/a |
| 14 | 150.0 s | False | 200.22 A | 2.7970 V | n/a |
| 15 | 160.0 s | False | 200.21 A | 2.7920 V | n/a |
| 16 | 170.0 s | False | 200.19 A | 2.7860 V | n/a |

### Impact of Metric Warmup Window (10 s)

| Scenario | Estimator | Variant | Max Error (Full, t >= 0 s) | Max Error (Warmup, t > 10 s) | Delta |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `t11_anchor_toggle [anchors off]` | **E1** | `matched` | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.07 ± 0.01 pp (w: 0.07 pp) | 0.26 ± 0.01 pp (w: 0.27 pp) |
| `t11_anchor_toggle [anchors off]` | **E2** | `matched` | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.06 ± 0.00 pp (w: 0.06 pp) | 0.26 ± 0.00 pp (w: 0.27 pp) |
| `t11_anchor_toggle [full-charge only]` | **E1** | `matched` | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.07 ± 0.01 pp (w: 0.07 pp) | 0.26 ± 0.01 pp (w: 0.27 pp) |
| `t11_anchor_toggle [full-charge only]` | **E2** | `matched` | 0.32 ± 0.00 pp (w: 0.32 pp) | 0.06 ± 0.00 pp (w: 0.06 pp) | 0.26 ± 0.00 pp (w: 0.27 pp) |
| `t11_anchor_toggle [rest anchor only]` | **E1** | `matched` | 18.90 ± 0.09 pp (w: 19.04 pp) | 18.90 ± 0.09 pp (w: 19.04 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) |
| `t11_anchor_toggle [rest anchor only]` | **E2** | `matched` | 3.08 ± 1.08 pp (w: 5.29 pp) | 1.95 ± 0.41 pp (w: 3.00 pp) | 1.13 ± 0.82 pp (w: 2.76 pp) |
| `t12_hysteresis_mismatch` | **E1** | `matched` | 14.49 ± 0.27 pp (w: 15.08 pp) | 14.49 ± 0.27 pp (w: 15.08 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) |
| `t12_hysteresis_mismatch` | **E2** | `matched` | 2.66 ± 0.66 pp (w: 3.92 pp) | 2.20 ± 0.48 pp (w: 3.10 pp) | 0.46 ± 0.54 pp (w: 1.55 pp) |
| `t1_static_ocv` | **E1** | `matched` | 2.32 ± 0.96 pp (w: 4.20 pp) | 2.32 ± 0.96 pp (w: 4.20 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) |
| `t1_static_ocv` | **E2** | `matched` | 2.20 ± 0.90 pp (w: 3.96 pp) | 2.20 ± 0.90 pp (w: 3.96 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) |
| `t3_t10_minor_loops` | **E1** | `matched` | 15.18 ± 0.23 pp (w: 15.42 pp) | 15.18 ± 0.23 pp (w: 15.42 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) |
| `t3_t10_minor_loops` | **E2** | `matched` | 3.24 ± 1.14 pp (w: 5.87 pp) | 2.39 ± 0.25 pp (w: 2.84 pp) | 0.85 ± 1.07 pp (w: 3.23 pp) |
| `t4_plateau_stress` | **E1** | `matched` | 14.67 ± 0.31 pp (w: 15.20 pp) | 14.67 ± 0.31 pp (w: 15.20 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) |
| `t4_plateau_stress` | **E2** | `matched` | 2.68 ± 0.99 pp (w: 4.92 pp) | 2.14 ± 0.67 pp (w: 3.16 pp) | 0.54 ± 0.96 pp (w: 2.89 pp) |
| `t5_initial_soc_offset` | **E1** | `matched` | 5.23 ± 1.67 pp (w: 8.21 pp) | 2.75 ± 0.02 pp (w: 2.79 pp) | 2.48 ± 1.67 pp (w: 5.49 pp) |
| `t5_initial_soc_offset` | **E2** | `matched` | 4.96 ± 1.64 pp (w: 7.89 pp) | 1.12 ± 0.97 pp (w: 2.60 pp) | 3.84 ± 0.96 pp (w: 5.91 pp) |
| `t6_current_bias` | **E1** | `matched` | 1.54 ± 0.67 pp (w: 3.02 pp) | 1.27 ± 0.35 pp (w: 1.91 pp) | 0.27 ± 0.55 pp (w: 1.59 pp) |
| `t6_current_bias` | **E2** | `matched` | 1.50 ± 0.66 pp (w: 2.97 pp) | 1.18 ± 0.32 pp (w: 1.69 pp) | 0.32 ± 0.54 pp (w: 1.45 pp) |
| `t6_plateau_only` | **E1** | `matched` | 14.10 ± 0.95 pp (w: 15.86 pp) | 14.10 ± 0.95 pp (w: 15.86 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) |
| `t6_plateau_only` | **E2** | `matched` | 4.02 ± 1.30 pp (w: 6.75 pp) | 3.87 ± 1.40 pp (w: 6.75 pp) | 0.15 ± 0.44 pp (w: 1.46 pp) |
| `t7_voltage_quant_noise` | **E1** | `matched` | 7.60 ± 1.58 pp (w: 11.99 pp) | 6.85 ± 0.82 pp (w: 7.71 pp) | 0.76 ± 1.48 pp (w: 4.90 pp) |
| `t7_voltage_quant_noise` | **E2** | `matched` | 5.53 ± 2.60 pp (w: 11.10 pp) | 2.72 ± 1.16 pp (w: 4.47 pp) | 2.81 ± 2.36 pp (w: 6.63 pp) |
| `t9_rest_relaxation` | **E1** | `matched` | 9.78 ± 0.14 pp (w: 10.04 pp) | 9.78 ± 0.14 pp (w: 10.04 pp) | 0.00 ± 0.00 pp (w: 0.00 pp) |
| `t9_rest_relaxation` | **E2** | `matched` | 2.44 ± 0.68 pp (w: 3.88 pp) | 1.59 ± 0.45 pp (w: 2.43 pp) | 0.85 ± 0.60 pp (w: 1.50 pp) |

### Flagged Transient Spike Runs

| Scenario | Estimator | Variant | Seed | Max Error | RMSE | Timestamp (s) | True SOC at t |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `t3_t10_minor_loops` | **E2** | `matched` | 9 | 5.87 pp | 0.48 pp | 1.0 s | 49.9% |
| `t5_initial_soc_offset` | **E2** | `matched` | 0 | 7.89 pp | 0.78 pp | 1.0 s | 25.0% |
| `t5_initial_soc_offset` | **E1** | `mismatched` | 0 | 6.65 pp | 0.73 pp | 1.0 s | 25.0% |
| `t5_initial_soc_offset` | **E2** | `matched` | 4 | 7.24 pp | 0.89 pp | 1.0 s | 25.0% |
| `t5_initial_soc_offset` | **E1** | `mismatched` | 4 | 5.94 pp | 0.69 pp | 1.0 s | 25.0% |
| `t5_initial_soc_offset` | **E2** | `matched` | 7 | 6.10 pp | 0.92 pp | 1.0 s | 25.0% |
| `t5_initial_soc_offset` | **E2** | `matched` | 8 | 5.84 pp | 0.89 pp | 1.0 s | 25.0% |
| `t6_plateau_only` | **E2** | `matched` | 0 | 5.47 pp | 0.39 pp | 120.0 s | 43.3% |
| `t6_plateau_only` | **E2** | `matched` | 3 | 6.75 pp | 0.43 pp | 50.0 s | 47.2% |
| `t7_voltage_quant_noise` | **E2** | `matched` | 0 | 6.77 pp | 0.74 pp | 2.0 s | 60.0% |
| `t7_voltage_quant_noise` | **E2** | `matched` | 6 | 6.05 pp | 0.65 pp | 1.0 s | 60.0% |
| `t7_voltage_quant_noise` | **E2** | `matched` | 9 | 6.85 pp | 0.81 pp | 2.0 s | 60.0% |
| `t11_anchor_toggle [rest anchor only]` | **E2** | `matched` | 0 | 5.29 pp | 1.00 pp | 1.0 s | 55.0% |

## Assumptions Audit Summary

- **Placeholder Parameters:** `63`
- **Assumed Parameters:** `22`
- **Zero-Constants Rule:** All physical parameters, sensor limits, and noise parameters are strictly loaded from YAML configuration.

---
*Report generated for SOC Benchmark Lab.*
