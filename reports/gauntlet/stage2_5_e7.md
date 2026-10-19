# Gauntlet Stage 2.5: E7 Composite & Final Gate Report

## 1. Executive Summary
- **Verdict:** `NO-GO(estimator)`
- **Primary Cause:** E7 fails GATE 2 Clause (ii) individual case win rate (78.9% vs mandatory >= 80.0%).
- **Root Physical Cause:** **Unobservability on the LFP operating plateau**.
  On the flat two-phase transition of LiFePO4 (dOCV/dSOC approx 175 mV/unit), voltage measurement noise and model bias create an unobservable null space where pure Coulomb counting (E0) with zero sensor bias maintains a flat trajectory across partial windows, whereas feedback estimators encounter state drift in small-offset mid-plateau windows.
- **Optional E7b Status:** Tested and **DROPPED** (achieved -2.2% relative improvement, failing the mandatory >= 20.0% threshold).

## 2. Gate 2 Breakdown

- **Clause (i) Matched S-A Non-Inferiority:** **PASS**
  - E7 S-A: `1.209 pp` vs E0 + 5.0 pp (`5.918 pp`) AND E1 + 1.0 pp (`5.021 pp`)
- **Clause (ii) S-B, S-C, S-D Superiority:** **FAIL**
  - Group-mean RMSE: `2.578 pp` vs 0.70x E0 (`4.365 pp`, ratio = `0.413`) -> **PASS** on mean
  - Individual Case Wins: `30 / 38` (`78.9%`) vs required >= 80.0% -> **FAIL** (short by 1 case: needs 31/38 = 81.6%)
- **Clause (iii) S-F Fault Sensitivity:** **PASS**
  - E7 S-F Mean: `1.570 pp` vs E0 S-F Mean + 5.0 pp (`7.013 pp`)

## 3. Runtime & Memory Benchmark
- **Benchmark Duration:** 0.740 s over 10,000 steps
- **Per-Step Runtime:** `0.0740 ms/step` (Limit: <= 5.0 ms/step) -> **PASS** (69x faster than ceiling)
- **Memory Allocations:** Fixed size at initialisation (`x`: 4 states, `P`: 4x4 covariance matrix).

## 4. Final Disposition
Per protocol rule: *'If E7 (or E7b) fails GATE 2: END as NO-GO(estimator). Report the gate breakdown, the failure mode, and whether the cause is unobservability, parameter error, or sensor error. Do not proceed.'*
Single unseal of US06 and FUDS in Stage 4 is strictly prohibited.
Proceeding immediately to failure diagnosis, design note, and FINAL.md.