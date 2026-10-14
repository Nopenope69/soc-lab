# CALCE A123 26650 LFP Real-Data Benchmark Verdict

**Overall Verdict: FAIL**

## 1. Executive Summary & Fixed Pass Rules Evaluation

| Rule | Description | Target Threshold | Measured Performance | Verdict |
| :--- | :--- | :--- | :--- | :---: |
| **Rule 1 (Accuracy)** | Best of E2, E5 v1, E5 v2, E6 median RMSE on baseline gating cases | $\le 2.0$ pp | Best: `E6` with 24.47 pp | **FAIL** |
| **Rule 2 (No Harm & Benefit)** | Better E5 (E5 v1) within 0.3 pp of E2 in $\ge 80\%$ baseline cases AND $\ge 30\%$ RMSE reduction in $\pm 5$ mV OCV | No harm $\ge 80\%$, Benefit $\ge 30\%$ | No harm: 100.0% (10/10), Benefit: 6.7% | **FAIL** |
| **Rule 3 (Recovery)** | Under $\pm 10$ pp initial offset, better E5 within 2 pp of E2 average RMSE | Average diff $\le 2.0$ pp | E2: 31.02 pp, E5 v1: 29.07 pp (diff: 1.95 pp) | **PASS** |
| **Rule 4 (Cell Transfer)** | Best estimator (E6) on Cell A1-008 with A1-007 parameters vs own fit | Transfer ratio $\le 1.5\times$ | A1-007 fit: 15.75 pp, Own fit: 23.09 pp (ratio: 0.68x) | **PASS** |

### Detailed Rule Analysis
- **Rule 1 (Accuracy):** Evaluated across 10 gating cases (20, 25, 30, 40, 50 C on US06 and FUDS for Cell A1-007 without faults).
  - `E2` median RMSE: **31.14 pp**
  - `E5 v1` median RMSE: **29.38 pp**
  - `E5 v2` median RMSE: **30.96 pp**
  - `E6` median RMSE: **24.47 pp**
  - Verdict: **FAIL**. Best estimator `E6` achieved median RMSE of 24.47 pp (requirement: $\le 2.0$ pp).
- **Rule 2 (No Harm & Benefit):** Better variant selected was `E5 v1`.
  - Baseline parity: `E5 v1` stayed within 0.3 pp of E2 in 10 of 10 cases (100.0%). Requirement was $\ge 80\%$. (**PASS**)
  - Benefit under $\pm 5$ mV OCV mismatch: E2 average RMSE = 30.94 pp, `E5 v1` average RMSE = 28.86 pp (6.7% reduction). Requirement was $\ge 30\%$. (**FAIL**)
- **Rule 3 (Recovery):** Under $\pm 10$ pp initial offset injection, `E5 v1` maintained an average RMSE difference of 1.95 pp relative to E2 (requirement: $\le 2.0$ pp). (**PASS**)
- **Rule 4 (Cell Transfer):** Evaluated cross-specimen transfer on Cell A1-008 across gating temperatures. `E6` achieved 15.75 pp with zero-refit A1-007 parameters versus 23.09 pp with its own fit (ratio: 0.68x, requirement: $\le 1.5\times$). (**PASS**)

## 2. Experimental Scope & Ground Truth Accounting
- **Specimens:** A123 ANR26650M1-A LiFePO4 cells (`A1-007` and `A1-008`).
- **Gating Temperatures (enforced by pass rules):** 20, 25, 30, 40, and 50 C.
- **Informational Temperatures (reported only, excluded from pass rules):** -10, 0, and 10 C.
- **Profiles:** DST (Step 8, used for fitting and tuning), US06 (Step 16, sealed test), FUDS (Step 24, sealed test).
- **Ground Truth SOC Protocol:** Evaluated via continuous Coulomb integration from full-charge CV-end anchor (Step 5/13/21 cutoff at C/20 current = 0.055 A, SOC = 1.0000), normalized to measured C/20 discharge capacity at that temperature. In accordance with physical reality, no empty anchor and no forced closure to 0 were applied.

## 3. Informational Temperatures & Sub-Zero Delivered Capacity
### Sub-Zero (-10 C) Delivered Capacity Under Dynamic Load
At -10 C, severe electrolyte freezing and solid-state diffusion kinetics cause the terminal voltage to reach the 2.0 V cutoff long before the thermodynamic C/20 capacity is exhausted:
- **Cell A1-007 at -10 C:**
  - Measured C/20 Capacity: **1.0600 Ah**
  - Dynamic DST Delivered Capacity: **0.7351 Ah** (**69.4%** of C/20 capacity)
  - Cutoff Final SOC: **0.3065** (30.6% unextracted capacity remaining)
- **Cell A1-008 at -10 C:**
  - Measured C/20 Capacity: **1.0791 Ah**
  - Dynamic DST Delivered Capacity: **0.4366 Ah** (**40.5%** of C/20 capacity)
  - Cutoff Final SOC: **0.5955** (59.5% unextracted capacity remaining)

## 4. Hardware Artifact Note: 10 C OCV Discontinuity
> [!NOTE]
> **10 C OCV Interruption Handling:** In row 5449 of both 10 C OCV spreadsheets, a 6-hour hardware interruption during the discharge branch created a non-monotonic time jump (-94 s) and +24 mV voltage relaxation. Per plan specifications, this artifact was **not repaired** or smoothed; rather, the affected SOC range `[0.75, 0.78]` was explicitly **excluded from OCV and hysteresis identification**, marked in the configuration YAML note, and documented here. Dynamic drive cycles (DST, US06, FUDS) were unaffected by this interruption.

## 5. Fault Injection Accounting: Real Model Error vs Injected Perturbations
> [!IMPORTANT]
> **Injected Faults Sit on Top of Real Model Error:** In synthetic benchmarks, estimator models are compared against perfect simulation plants with zero unmodeled dynamics. In this real laboratory dataset, equivalent circuit models (2RC + hysteresis) already suffer from real electrochemical model discrepancy (solid-state diffusion limitations, temperature gradients, concentration polarization). All injected sensor and model perturbations (initial SOC offset, current sensor bias, OCV shift) sit strictly on top of this real physical model error.

## 6. Limitations of the Benchmark Dataset
> [!WARNING]
> **Full-Discharge Profile Limitation:** All dynamic cycles in the CALCE A123 dataset are full discharges from 100% full charge down to the 2.0 V cutoff after a complete CC-CV recharge. Consequently, the battery current is predominantly unidirectional discharging ($I > 0$). **Minor-loop hysteresis behavior is barely exercised**, and the minor-loop decay parameter $\gamma$ remains unobserved and unexcited in these tests.

## 7. Complete Experimental Results Tables

### Table 1: Baseline Evaluation on Cell A1-007 (No Injected Faults)

| Temp (C) | Scope | Profile | E0 RMSE (pp) | E2 RMSE (pp) | E5 v1 RMSE (pp) | E5 v2 RMSE (pp) | E6 RMSE (pp) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| -10 | Informational | US06 | 0.13 | 17.86 | 10.31 | 15.91 | 17.26 |
| -10 | Informational | FUDS | 0.13 | 18.51 | 4.01 | 16.02 | 13.51 |
| 0 | Informational | US06 | 0.26 | 26.27 | 16.00 | 25.31 | 22.48 |
| 0 | Informational | FUDS | 0.26 | 17.83 | 4.81 | 15.31 | 20.30 |
| 10 | Informational | US06 | 1.11 | 23.34 | 21.61 | 23.81 | 22.48 |
| 10 | Informational | FUDS | 1.09 | 22.85 | 7.63 | 19.48 | 18.33 |
| 20 | Gating | US06 | 0.10 | 32.60 | 31.88 | 32.85 | 25.21 |
| 20 | Gating | FUDS | 0.11 | 27.83 | 24.53 | 28.77 | 23.92 |
| 25 | Gating | US06 | 0.01 | 32.48 | 31.90 | 32.55 | 25.01 |
| 25 | Gating | FUDS | 0.02 | 27.59 | 24.07 | 28.19 | 21.81 |
| 30 | Gating | US06 | 0.51 | 34.55 | 31.91 | 33.85 | 26.76 |
| 30 | Gating | FUDS | 0.52 | 29.81 | 26.87 | 28.36 | 23.13 |
| 40 | Gating | US06 | 0.89 | 32.47 | 31.93 | 33.92 | 25.33 |
| 40 | Gating | FUDS | 0.91 | 28.39 | 26.38 | 27.85 | 21.68 |
| 50 | Gating | US06 | 0.94 | 35.06 | 34.30 | 35.17 | 26.68 |
| 50 | Gating | FUDS | 0.95 | 29.37 | 26.55 | 29.38 | 22.16 |

### Table 2: Fault Injection Performance on Cell A1-007 (Gating Temperatures Average RMSE)

| Fault Category | Injected Fault Condition | Stress? | E0 (pp) | E2 (pp) | E5 v1 (pp) | E5 v2 (pp) | E6 (pp) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline** | None (No Injected Fault) | No | 0.50 | 31.02 | 29.03 | 31.09 | 24.17 |
| Soc Offset | `soc_offset_+10pp` | No | 0.50 | 31.02 | 29.03 | 31.09 | 24.17 |
| Soc Offset | `soc_offset_-10pp` | No | 10.19 | 31.01 | 29.10 | 31.09 | 24.83 |
| Current Bias | `current_bias_+10mA` | No | 1.59 | 32.20 | 30.09 | 32.44 | 24.70 |
| Current Bias | `current_bias_-10mA` | No | 0.60 | 29.53 | 27.82 | 30.12 | 23.94 |
| Current Bias | `current_bias_+50mA` | Yes | 5.64 | 36.13 | 33.58 | 36.76 | 26.63 |
| Current Bias | `current_bias_-50mA` | Yes | 4.97 | 23.98 | 23.10 | 25.66 | 21.69 |
| Ocv Offset | `ocv_offset_+5mV` | No | 0.50 | 28.59 | 26.61 | 28.89 | 23.14 |
| Ocv Offset | `ocv_offset_-5mV` | No | 0.50 | 33.30 | 31.12 | 33.59 | 25.84 |
| Ocv Offset | `ocv_offset_+10mV` | Yes | 0.50 | 25.83 | 24.18 | 26.63 | 21.13 |
| Ocv Offset | `ocv_offset_-10mV` | Yes | 0.50 | 35.29 | 32.99 | 36.05 | 26.65 |

### Table 3: Cell Transfer Evaluation on Cell A1-008

| Temp (C) | Scope | Profile | Estimator | A1-007 Params RMSE (pp) | Own Fit RMSE (pp) | Transfer Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| -10 | Informational | US06 | E2 | 10.53 | 13.53 | 0.78x |
| -10 | Informational | US06 | E5 v1 | 1.73 | 8.47 | 0.20x |
| -10 | Informational | US06 | E5 v2 | 3.50 | 14.00 | 0.25x |
| -10 | Informational | US06 | E6 | 8.40 | 12.63 | 0.67x |
| -10 | Informational | FUDS | E2 | 8.30 | 12.99 | 0.64x |
| -10 | Informational | FUDS | E5 v1 | 3.64 | 4.12 | 0.88x |
| -10 | Informational | FUDS | E5 v2 | 3.29 | 12.69 | 0.26x |
| -10 | Informational | FUDS | E6 | 4.38 | 8.53 | 0.51x |
| 0 | Informational | US06 | E2 | 18.37 | 26.82 | 0.69x |
| 0 | Informational | US06 | E5 v1 | 13.07 | 15.89 | 0.82x |
| 0 | Informational | US06 | E5 v2 | 18.36 | 25.01 | 0.73x |
| 0 | Informational | US06 | E6 | 21.96 | 15.31 | 1.43x |
| 0 | Informational | FUDS | E2 | 8.21 | 20.40 | 0.40x |
| 0 | Informational | FUDS | E5 v1 | 1.70 | 4.43 | 0.38x |
| 0 | Informational | FUDS | E5 v2 | 4.84 | 15.84 | 0.31x |
| 0 | Informational | FUDS | E6 | 7.58 | 12.54 | 0.60x |
| 10 | Informational | US06 | E2 | 6.30 | 27.79 | 0.23x |
| 10 | Informational | US06 | E5 v1 | 16.22 | 25.99 | 0.62x |
| 10 | Informational | US06 | E5 v2 | 21.31 | 26.17 | 0.81x |
| 10 | Informational | US06 | E6 | 19.52 | 21.37 | 0.91x |
| 10 | Informational | FUDS | E2 | 2.96 | 17.57 | 0.17x |
| 10 | Informational | FUDS | E5 v1 | 4.76 | 10.05 | 0.47x |
| 10 | Informational | FUDS | E5 v2 | 6.92 | 23.60 | 0.29x |
| 10 | Informational | FUDS | E6 | 2.09 | 15.53 | 0.13x |
| 20 | Gating | US06 | E2 | 31.56 | 27.71 | 1.14x |
| 20 | Gating | US06 | E5 v1 | 28.36 | 25.54 | 1.11x |
| 20 | Gating | US06 | E5 v2 | 30.60 | 27.90 | 1.10x |
| 20 | Gating | US06 | E6 | 24.09 | 25.94 | 0.93x |
| 20 | Gating | FUDS | E2 | 24.40 | 27.01 | 0.90x |
| 20 | Gating | FUDS | E5 v1 | 17.96 | 12.39 | 1.45x |
| 20 | Gating | FUDS | E5 v2 | 26.94 | 23.07 | 1.17x |
| 20 | Gating | FUDS | E6 | 17.19 | 22.76 | 0.76x |
| 25 | Gating | US06 | E2 | 19.78 | 28.98 | 0.68x |
| 25 | Gating | US06 | E5 v1 | 20.17 | 29.04 | 0.69x |
| 25 | Gating | US06 | E5 v2 | 26.15 | 28.08 | 0.93x |
| 25 | Gating | US06 | E6 | 8.86 | 26.11 | 0.34x |
| 25 | Gating | FUDS | E2 | 24.92 | 27.24 | 0.91x |
| 25 | Gating | FUDS | E5 v1 | 14.40 | 11.73 | 1.23x |
| 25 | Gating | FUDS | E5 v2 | 18.67 | 26.33 | 0.71x |
| 25 | Gating | FUDS | E6 | 9.63 | 18.87 | 0.51x |
| 30 | Gating | US06 | E2 | 30.77 | 33.04 | 0.93x |
| 30 | Gating | US06 | E5 v1 | 28.13 | 31.35 | 0.90x |
| 30 | Gating | US06 | E5 v2 | 30.51 | 34.09 | 0.90x |
| 30 | Gating | US06 | E6 | 20.83 | 25.81 | 0.81x |
| 30 | Gating | FUDS | E2 | 23.43 | 29.74 | 0.79x |
| 30 | Gating | FUDS | E5 v1 | 19.07 | 25.92 | 0.74x |
| 30 | Gating | FUDS | E5 v2 | 26.63 | 29.50 | 0.90x |
| 30 | Gating | FUDS | E6 | 13.13 | 21.30 | 0.62x |
| 40 | Gating | US06 | E2 | 28.32 | 32.09 | 0.88x |
| 40 | Gating | US06 | E5 v1 | 28.73 | 31.83 | 0.90x |
| 40 | Gating | US06 | E5 v2 | 28.24 | 33.09 | 0.85x |
| 40 | Gating | US06 | E6 | 17.77 | 24.69 | 0.72x |
| 40 | Gating | FUDS | E2 | 23.43 | 27.87 | 0.84x |
| 40 | Gating | FUDS | E5 v1 | 23.50 | 25.17 | 0.93x |
| 40 | Gating | FUDS | E5 v2 | 25.29 | 27.82 | 0.91x |
| 40 | Gating | FUDS | E6 | 14.97 | 20.92 | 0.72x |
| 50 | Gating | US06 | E2 | 15.77 | 31.78 | 0.50x |
| 50 | Gating | US06 | E5 v1 | 13.39 | 31.63 | 0.42x |
| 50 | Gating | US06 | E5 v2 | 14.37 | 33.69 | 0.43x |
| 50 | Gating | US06 | E6 | 7.12 | 24.81 | 0.29x |
| 50 | Gating | FUDS | E2 | 19.02 | 23.04 | 0.83x |
| 50 | Gating | FUDS | E5 v1 | 13.83 | 24.83 | 0.56x |
| 50 | Gating | FUDS | E5 v2 | 2.75 | 25.29 | 0.11x |
| 50 | Gating | FUDS | E6 | 23.94 | 19.67 | 1.22x |
