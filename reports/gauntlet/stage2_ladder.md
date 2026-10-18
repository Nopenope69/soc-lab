# Gauntlet Stage 2: Estimator Ladder & Tuning Report

## 1. Executive Summary
- **Selected Estimator:** `E2` (Config: `tune_2`)
- **Held-Out Mean BCD RMSE (40 & 50 °C):** 2.578 pp
- **Tuning-versus-Held-Out Gap:** +0.226 pp
- **GATE 2 Status:** **FAILED**
  - Clause (i) S-A Non-Inferiority: PASS
  - Clause (ii) BCD Superiority (<= 0.70x E0 and >= 80% individual wins): FAIL
  - Clause (iii) S-F Robustness: PASS

## 2. Candidate Estimator Comparison Table

| Estimator | Selected Config | Tune BCD (20 & 30 °C) | Held-Out BCD (40 & 50 °C) | Generalization Gap | Held-Out S-A RMSE | Held-Out S-F Worst |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| E0 | baseline | 6.170 pp | 6.236 pp | +0.066 pp | 0.918 pp | 10.468 pp |
| E0_recal | baseline | 6.170 pp | 6.236 pp | +0.066 pp | 0.918 pp | 10.468 pp |
| E1 | baseline | 6.400 pp | 5.335 pp | -1.065 pp | 4.021 pp | 12.820 pp |
| E2 | tune_2 | 2.351 pp | 2.578 pp | +0.226 pp | 1.209 pp | 4.648 pp |
| E3 | tune_6 | 2.626 pp | 2.656 pp | +0.030 pp | 1.464 pp | 7.859 pp |
| E4 | tune_6 | 2.589 pp | 2.482 pp | -0.107 pp | 1.447 pp | 5.235 pp |
| e5v3 | tune_1 | 2.432 pp | 2.362 pp | -0.069 pp | 1.394 pp | 5.060 pp |
| e6v2 | tune_2 | 2.624 pp | 2.974 pp | +0.350 pp | 3.281 pp | 11.111 pp |

## 3. Detailed Temperature Breakdown (BCD Mean RMSE, pp)

| Estimator | 20 °C (Tune) | 25 °C (Suspect) | 30 °C (Tune) | 40 °C (Held-Out) | 50 °C (Held-Out) |
|:---|:---:|:---:|:---:|:---:|:---:|
| E0 | 6.183 | 6.185 | 6.157 | 6.224 | 6.248 |
| E0_recal | 6.183 | 6.185 | 6.157 | 6.224 | 6.248 |
| E1 | 6.673 | 4.514 | 6.127 | 5.574 | 5.097 |
| E2 | 2.489 | 2.411 | 2.213 | 2.255 | 2.901 |
| E3 | 2.911 | 1.981 | 2.340 | 2.202 | 3.109 |
| E4 | 2.773 | 2.333 | 2.405 | 2.187 | 2.777 |
| e5v3 | 2.538 | 2.392 | 2.325 | 2.193 | 2.532 |
| e6v2 | 2.685 | 2.888 | 2.563 | 2.670 | 3.278 |

## 4. GATE 2 Evaluation Verification

- **Clause (i) S-A Non-Inferiority:**
  - Thresholds: <= E0 + 5.0 pp (5.918 pp) AND <= E1 + 1.0 pp (5.021 pp)
  - Observed Winner S-A: `1.209 pp` -> **PASS**
- **Clause (ii) BCD Recovery:**
  - Threshold: <= 0.70 x E0 BCD (4.365 pp) AND >= 80% individual case wins
  - Observed Winner BCD: `2.578 pp` (41.3% of E0) -> **PASS**
  - Individual Case Wins: `30 / 38` (78.9%) -> **FAIL**
- **Clause (iii) S-F Fault Sensitivity:**
  - Threshold: <= E0 S-F Mean + 5.0 pp (7.013 pp)
  - Observed Winner S-F Mean: `1.570 pp` -> **PASS**

## 5. Hysteresis Ablation ($M = 0$ vs $M(T)$)

- **With Calibrated $M(T)$:** Held-out BCD = `2.578 pp`, S-A = `1.209 pp`
- **With $M = 0$ (Ablated):** Held-out BCD = `5.417 pp`, S-A = `3.547 pp`
- **Finding:** Hysteresis modeling **HELPS** on DST (Delta BCD = -2.839 pp).

## 6. Voltage-Implied Error Floor
The fundamental plateau limit: model voltage bias divided by local open-circuit slope $|d\text{OCV}/d\text{SOC}|$.

| Temperature | W-mid Voltage Bias (mV) | Mean Plateau Slope (mV/unit SOC) | Implied SOC Floor (pp) | Actual S-A RMSE (pp) |
|:---:|:---:|:---:|:---:|:---:|
| 20 °C | 0.48 | 178.3 | 0.269 | 1.640 |
| 25 °C | 0.35 | 176.7 | 0.198 | 0.606 |
| 30 °C | 0.54 | 174.0 | 0.310 | 1.544 |
| 40 °C | 0.49 | 175.4 | 0.279 | 1.343 |
| 50 °C | 0.55 | 178.4 | 0.308 | 1.075 |