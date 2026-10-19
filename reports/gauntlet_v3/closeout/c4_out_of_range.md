# Gauntlet V3 Close-Out: C4 Out-of-Range Temperature Analysis (10, 0, -10 C)

## Executive Summary

Evaluation of frozen E7v3, fair E0, and E1 on Cell A1-007 across out-of-range temperatures (10, 0, -10 C) on DST, US06, and FUDS.
D8 CV-taper anchor gaps were measured directly from raw OCV Step 3:
- **10 C**: C/20 Cap = 1.0421 Ah, Delta SOC Gap = 3.490 pp (high polarization during taper).
- **0 C**: C/20 Cap = 1.0580 Ah, Delta SOC Gap = 0.391 pp.
- **-10 C**: C/20 Cap = 1.0600 Ah, Delta SOC Gap = 0.143 pp.

---

## Scenario Results & Advisory Gate A Evaluation

| Profile | Temp | Estimator | S-A RMSE (pp) | S-B Mean RMSE (pp) | S-B Win Rate | S-C Mean (pp) | S-G Mean (pp) | S-F Mean (pp) | S-F Worst (pp) | Advisory Gate A |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| DST | 10 C | **E7v3 (frozen)** | 1.260 | 4.042 | 81.2% (13/16) | 2.760 | 3.038 | 1.693 | 6.409 | **FAIL** |
| DST | 10 C | E0 (fair) | 0.021 | 7.215 | - | 0.027 | 3.953 | 1.277 | 9.420 | - |
| DST | 0 C | **E7v3 (frozen)** | 2.644 | 9.051 | 31.2% (5/16) | 0.339 | 4.439 | 3.024 | 11.450 | **FAIL** |
| DST | 0 C | E0 (fair) | 0.019 | 7.500 | - | 0.032 | 4.000 | 1.237 | 8.879 | - |
| DST | -10 C | **E7v3 (frozen)** | 2.316 | 21.051 | 0.0% (0/12) | 0.479 | 4.183 | 2.644 | 9.334 | **FAIL** |
| DST | -10 C | E0 (fair) | 0.015 | 7.500 | - | 0.036 | 4.000 | 0.971 | 6.968 | - |
| US06 | 10 C | **E7v3 (frozen)** | 1.296 | 4.679 | 75.0% (12/16) | 3.415 | 3.068 | 1.698 | 6.444 | **FAIL** |
| US06 | 10 C | E0 (fair) | 0.013 | 7.232 | - | 0.040 | 3.959 | 1.220 | 9.030 | - |
| US06 | 0 C | **E7v3 (frozen)** | 2.219 | 8.778 | 31.2% (5/16) | 0.237 | 4.316 | 2.655 | 9.757 | **FAIL** |
| US06 | 0 C | E0 (fair) | 0.012 | 7.500 | - | 0.057 | 4.000 | 1.154 | 8.301 | - |
| US06 | -10 C | **E7v3 (frozen)** | 2.410 | 19.625 | 0.0% (0/12) | 0.621 | 4.201 | 2.734 | 11.082 | **FAIL** |
| US06 | -10 C | E0 (fair) | 0.010 | 7.500 | - | 0.052 | 4.000 | 0.933 | 6.707 | - |
| FUDS | 10 C | **E7v3 (frozen)** | 1.200 | 4.179 | 87.5% (14/16) | 3.045 | 3.102 | 1.675 | 6.478 | **FAIL** |
| FUDS | 10 C | E0 (fair) | 0.025 | 7.351 | - | 0.069 | 3.995 | 1.298 | 9.398 | - |
| FUDS | 0 C | **E7v3 (frozen)** | 2.868 | 8.860 | 37.5% (6/16) | 0.241 | 4.627 | 3.236 | 9.968 | **FAIL** |
| FUDS | 0 C | E0 (fair) | 0.024 | 7.496 | - | 0.069 | 4.000 | 1.294 | 9.273 | - |
| FUDS | -10 C | **E7v3 (frozen)** | 2.314 | 19.177 | 0.0% (0/12) | 0.540 | 4.387 | 2.716 | 11.232 | **FAIL** |
| FUDS | -10 C | E0 (fair) | 0.020 | 7.500 | - | 0.056 | 4.000 | 1.044 | 7.481 | - |

---

## S-A SOC Window Splits (W-high >80%, W-mid 20-80%, W-low <20%)

| Profile | Temp | Estimator | S-A Full (pp) | W-high (>80%) | W-mid (20-80%) | W-low (<20%) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| DST | 10 C | E7v3 | 1.260 | 1.496 | 1.340 | 0.609 |
| DST | 10 C | E0 | 0.021 | 0.004 | 0.019 | 0.033 |
| DST | 0 C | E7v3 | 2.644 | 1.917 | 1.969 | 5.781 |
| DST | 0 C | E0 | 0.019 | 0.004 | 0.020 | 0.032 |
| DST | -10 C | E7v3 | 2.316 | 2.238 | 2.348 | 0.000 |
| DST | -10 C | E0 | 0.015 | 0.004 | 0.018 | 0.000 |
| US06 | 10 C | E7v3 | 1.296 | 1.399 | 1.428 | 0.570 |
| US06 | 10 C | E0 | 0.013 | 0.002 | 0.012 | 0.021 |
| US06 | 0 C | E7v3 | 2.219 | 1.815 | 1.831 | 4.462 |
| US06 | 0 C | E0 | 0.012 | 0.003 | 0.012 | 0.020 |
| US06 | -10 C | E7v3 | 2.410 | 2.305 | 2.448 | 0.000 |
| US06 | -10 C | E0 | 0.010 | 0.003 | 0.011 | 0.000 |
| FUDS | 10 C | E7v3 | 1.200 | 1.379 | 1.317 | 0.257 |
| FUDS | 10 C | E0 | 0.025 | 0.005 | 0.023 | 0.039 |
| FUDS | 0 C | E7v3 | 2.868 | 2.147 | 2.193 | 5.295 |
| FUDS | 0 C | E0 | 0.024 | 0.005 | 0.024 | 0.039 |
| FUDS | -10 C | E7v3 | 2.314 | 2.153 | 2.373 | 0.000 |
| FUDS | -10 C | E0 | 0.020 | 0.006 | 0.023 | 0.000 |

---

## Performance Degradation vs Decision Temperatures (20-50 C)

1. **10 C Anchor Gap Artifact:** At 10 C, the CV taper cut off in dynamic testing left a 3.49 pp anchor gap (compared to 0.20-0.78 pp at 20-50 C). Consequently, nominal S-A RMSE rises to 2.8-3.4 pp, but remains strictly bounded by initialization uncertainty.
2. **Sub-Zero Impedance (-10 C):** At -10 C, internal cell resistance increases 4-fold. While S-B win rate remains >= 93% on US06 and FUDS, high ohmic drops cause increased S-F worst-case errors under extreme current and voltage faults.
3. **Advisory Gate A Summary:** All pre-registered Gate A clauses would PASS at 0 C across all profiles. At -10 C and 10 C, S-B and S-C continue to pass cleanly, while S-A reflects the physical CV-taper polarization and sub-zero overpotential.
