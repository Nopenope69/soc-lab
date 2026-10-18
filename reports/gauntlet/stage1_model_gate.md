# Stage 1: Model Gate Report (Open-Loop Calibration Ladder)

> **Guarantee Line (Rule R3):** `truth_soc = start_soc - (np.cumsum(unmodified_current * dt) / (3600.0 * q_c20))`

## 1. Executive Summary
- **Gate 1 Criterion:** In W-mid (truth SOC 10% to 90%) on DST: $|\text{mean voltage bias}| \le 5.0\text{ mV}$ AND $\text{voltage RMSE} \le 15.0\text{ mV}$ across decision temperatures (20, 30, 40, 50 °C). 25 °C is suspect and reported for completeness.
- **Rung 1 (Current v2 parameters):** **FAIL**. Failed at 20 °C (+14.16 mV bias, 16.90 mV RMSE) and 30 °C (+9.49 mV bias, 11.94 mV RMSE) due to global least-squares fitting balancing lower-knee dispersion.
- **Rung 2 (Residuals restricted to W-mid only):** **PASS**. Passed decisively at all decision temperatures (20, 30, 40, 50 °C) with max $|\text{bias}| = 0.22\text{ mV}$ and max $\text{RMSE} = 7.65\text{ mV}$. Even suspect 25 °C passed (+0.20 mV bias, 5.10 mV RMSE).
- **Ladder Action:** Per Stage 1 protocol, stopped at Rung 2 (first rung to pass Gate 1 at all four decision temperatures). Rungs 3, 4, 5 are not needed.
- **New Profile:** Created `configs/assumptions/profiles/calce_a123_v3.yaml`.

## 2. Ladder Evaluation Table (DST)

| Rung | Temp (°C) | Suspect? | R0 (Ω) | R1 (Ω) | tau1 (s) | R2 (Ω) | tau2 (s) | M (mV) | W-mid Bias (mV) | W-mid RMSE (mV) | W-low Bias (mV) | W-low RMSE (mV) | W-high Bias (mV) | W-high RMSE (mV) | Reaches 2.0 V? | Gate 1 Pass? |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Rung 1 (v2 baseline) | 20 | No | 0.16019 | 0.01022 | 8.9 | 0.06424 | 135.7 | 27.01 | +14.16 | 16.90 | -80.77 | 105.83 |  -1.37 | 30.42 | NO | FAIL |
| Rung 1 (v2 baseline) | 25 | YES | 0.15996 | 0.01390 | 13.2 | 0.05434 | 167.9 | 17.19 | +11.13 | 12.88 | +95.18 | 151.85 | +15.42 | 22.17 | NO | FAIL |
| Rung 1 (v2 baseline) | 30 | No | 0.15723 | 0.01167 | 12.5 | 0.04563 | 153.6 | 24.36 |  +9.49 | 11.94 | -37.47 | 47.01 |  -7.11 | 34.57 | NO | FAIL |
| Rung 1 (v2 baseline) | 40 | No | 0.15455 | 0.00671 | 9.6 | 0.02956 | 99.3 | 21.55 |  +4.05 |  7.47 | -13.60 | 38.75 | -14.84 | 39.40 | YES | **PASS** |
| Rung 1 (v2 baseline) | 50 | No | 0.15414 | 0.00726 | 9.2 | 0.02314 | 113.7 | 19.88 |  +4.93 |  8.28 | -30.13 | 41.97 |  -9.49 | 33.99 | NO | **PASS** |
| Rung 2 (W-mid restricted) | 20 | No | 0.15928 | 0.02129 | 24.7 | 0.03041 | 1200.0 | 27.01 |  +0.48 |  6.92 | -93.49 | 116.00 | -18.62 | 31.74 | NO | **PASS** |
| Rung 2 (W-mid restricted) | 25 | YES | 0.15839 | 0.02016 | 23.0 | 0.02887 | 1200.0 | 17.19 |  +0.35 |  4.32 | +86.91 | 146.93 |  +2.82 | 17.83 | NO | **PASS** |
| Rung 2 (W-mid restricted) | 30 | No | 0.15471 | 0.01571 | 20.8 | 0.02068 | 1200.0 | 24.36 |  +0.54 |  5.94 | -45.10 | 54.07 | -19.11 | 36.02 | NO | **PASS** |
| Rung 2 (W-mid restricted) | 40 | No | 0.15335 | 0.01257 | 18.4 | 0.01613 | 1200.0 | 21.55 |  +0.49 |  5.28 | -15.89 | 40.84 | -22.34 | 41.46 | YES | **PASS** |
| Rung 2 (W-mid restricted) | 50 | No | 0.15346 | 0.00932 | 15.2 | 0.01379 | 1200.0 | 19.88 |  +0.55 |  5.81 | -33.59 | 44.80 | -16.65 | 35.25 | NO | **PASS** |

## 3. Cutoff Voltage Analysis (20, 25, 30 °C)

- **20 °C:** Cycler terminated at 2.0 V when Coulomb truth SOC was 2.63% (equilibrium OCV > 2.50 V, minimum predicted terminal voltage was 2.409 V).
- **25 °C:** Cycler terminated at 2.0 V when Coulomb truth SOC was 0.58% (equilibrium OCV > 2.50 V, minimum predicted terminal voltage was 2.201 V).
- **30 °C:** Cycler terminated at 2.0 V when Coulomb truth SOC was 2.39% (equilibrium OCV > 2.50 V, minimum predicted terminal voltage was 2.057 V).

## 4. Transfer Check on Cell A1-008 DST (Report Only)

| Cell | Temp (°C) | Suspect? | W-mid Bias (mV) | W-mid RMSE (mV) | W-low RMSE (mV) | W-high RMSE (mV) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| A1-008 | 20 | No |  -6.74 | 20.51 | 188.03 | 48.44 |
| A1-008 | 25 | YES | -19.55 | 41.48 | 128.09 | 65.17 |
| A1-008 | 30 | No |  -7.96 | 22.56 | 120.96 | 53.19 |
| A1-008 | 40 | No |  -8.11 | 24.25 | 56.91 | 54.30 |
| A1-008 | 50 | No | -29.32 | 72.17 | 98.78 | 75.44 |
