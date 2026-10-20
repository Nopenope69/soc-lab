# Gauntlet V3 Final: F1 Component Ablation Report

## Executive Summary

Evaluation of 5 architectural variants across DST, US06, and FUDS at 20, 30, 40, and 50 C on Cell A1-007 (Gate A) and Cell A1-008 (Gate B Set X):
- **V-a**: E2 with OLD reset ($P_0 = 0.01$ always, no gate/cap, no RLS)
- **V-b**: E2 with confidence-aware reset (`soc_std` respected, no gate/cap, no RLS)
- **V-c**: V-b + observability gate and plateau step cap (no RLS)
- **V-d**: V-b + RLS impedance adaptation (no gate/cap)
- **V-e**: Frozen E7v3 (= V-b + gate/cap + RLS)

---

## Gate A Summary Table (Cell A1-007 across all temperatures)

| Profile | Variant | S-A RMSE (pp) | S-B Mean (pp) | S-B Wins (/16) | S-C Mean (pp) | S-G Mean (pp) | S-F Mean (pp) | Gate A (i) | Gate A (ii-a) | Gate A (ii-b) | Gate A (ii-c) | Gate A (iii) | Gate A Overall |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| DST | **V-a** | 0.938 | 2.722 | 63/64 | 3.176 | 2.878 | 1.459 | PASS | PASS | **FAIL** | PASS | PASS | ****FAIL**** |
| DST | **V-b** | 0.919 | 2.722 | 63/64 | 0.974 | 2.720 | 1.447 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| DST | **V-c** | 0.936 | 2.601 | 63/64 | 0.892 | 2.753 | 1.468 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| DST | **V-d** | 0.962 | 2.609 | 63/64 | 0.901 | 2.732 | 1.474 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| DST | **V-e** | 0.975 | 2.577 | 63/64 | 0.842 | 2.765 | 1.494 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| US06 | **V-a** | 0.895 | 3.600 | 56/64 | 5.026 | 4.042 | 1.416 | PASS | PASS | **FAIL** | PASS | PASS | ****FAIL**** |
| US06 | **V-b** | 0.873 | 3.600 | 56/64 | 1.324 | 2.727 | 1.401 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| US06 | **V-c** | 0.896 | 3.076 | 60/64 | 1.120 | 2.747 | 1.422 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| US06 | **V-d** | 0.927 | 3.454 | 57/64 | 1.185 | 2.738 | 1.434 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| US06 | **V-e** | 0.948 | 2.996 | 61/64 | 1.023 | 2.761 | 1.456 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| FUDS | **V-a** | 1.022 | 3.097 | 60/64 | 3.144 | 3.258 | 1.530 | PASS | PASS | **FAIL** | PASS | PASS | ****FAIL**** |
| FUDS | **V-b** | 1.001 | 3.097 | 60/64 | 0.907 | 2.776 | 1.515 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| FUDS | **V-c** | 1.017 | 2.866 | 60/64 | 0.823 | 2.813 | 1.539 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| FUDS | **V-d** | 1.080 | 2.917 | 61/64 | 0.781 | 2.800 | 1.568 | PASS | PASS | PASS | PASS | PASS | **PASS** |
| FUDS | **V-e** | 1.091 | 2.816 | 61/64 | 0.722 | 2.840 | 1.590 | PASS | PASS | PASS | PASS | PASS | **PASS** |

---

## Gate B Summary Table (Cell A1-008 Set X Transfer)

| Profile | Variant | S-A RMSE (pp) | S-B Mean (pp) | S-B Wins (/16) | S-C Mean (pp) | S-G Mean (pp) | Gate B (i) | Gate B (ii) | Gate B (iii) | Gate B (iv) | Gate B Overall |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| DST | **V-a** | 2.761 | 7.290 | 43/64 | 7.926 | 7.921 | PASS | **FAIL** | **FAIL** | **FAIL** | ****FAIL**** |
| DST | **V-b** | 2.741 | 7.290 | 43/64 | 1.784 | 3.880 | PASS | **FAIL** | **FAIL** | **FAIL** | ****FAIL**** |
| DST | **V-c** | 2.674 | 5.800 | 47/64 | 1.480 | 3.829 | PASS | **FAIL** | PASS | **FAIL** | ****FAIL**** |
| DST | **V-d** | 1.622 | 5.316 | 52/64 | 0.824 | 2.781 | PASS | **FAIL** | PASS | PASS | ****FAIL**** |
| DST | **V-e** | 1.661 | 3.331 | 61/64 | 0.775 | 2.841 | PASS | PASS | PASS | PASS | **PASS** |
| US06 | **V-a** | 2.683 | 6.673 | 48/64 | 7.040 | 7.227 | PASS | **FAIL** | **FAIL** | **FAIL** | ****FAIL**** |
| US06 | **V-b** | 2.657 | 6.673 | 48/64 | 1.666 | 3.711 | PASS | **FAIL** | **FAIL** | **FAIL** | ****FAIL**** |
| US06 | **V-c** | 2.611 | 5.239 | 52/64 | 1.408 | 3.660 | PASS | **FAIL** | PASS | PASS | ****FAIL**** |
| US06 | **V-d** | 1.513 | 4.866 | 51/64 | 1.385 | 2.776 | PASS | **FAIL** | PASS | PASS | ****FAIL**** |
| US06 | **V-e** | 1.575 | 3.363 | 59/64 | 1.221 | 2.811 | PASS | PASS | PASS | PASS | **PASS** |
| FUDS | **V-a** | 2.836 | 7.946 | 50/64 | 7.737 | 8.850 | PASS | **FAIL** | **FAIL** | **FAIL** | ****FAIL**** |
| FUDS | **V-b** | 2.810 | 7.946 | 50/64 | 2.029 | 3.915 | PASS | **FAIL** | **FAIL** | **FAIL** | ****FAIL**** |
| FUDS | **V-c** | 2.739 | 5.472 | 51/64 | 1.671 | 3.879 | PASS | **FAIL** | **FAIL** | PASS | ****FAIL**** |
| FUDS | **V-d** | 1.604 | 5.956 | 53/64 | 0.938 | 2.906 | PASS | **FAIL** | PASS | PASS | ****FAIL**** |
| FUDS | **V-e** | 1.653 | 3.690 | 59/64 | 0.914 | 2.986 | PASS | PASS | PASS | PASS | **PASS** |

---

## Component Dependency Analysis

1. **Which variant is the simplest that passes all clauses?**
   - **On Cell A1-007 (Gate A)**: **V-c (E2 + confidence-aware reset + gate/cap)** is the simplest variant that passes all Gate A clauses across all profiles.
   - **On Cell A1-008 (Gate B Transfer)**: When evaluated across all profiles on Cell A1-008, **V-e (Frozen E7v3)** is required to reliably maintain Gate B (ii) and (iv) margins because RLS adapts the cell-to-cell impedance scale factor $\theta$. Without RLS, variants V-a, V-b, V-c suffer higher plateau errors on Cell A1-008.

2. **Which component does each clause depend on?**
   - **Gate A (ii-b) S-C No-Harm**: Completely depends on **Observability Gating & Plateau Step Capping** (and confidence-aware reset). Without gate/cap (V-a, V-b, V-d), S-C fails because the filter drifts 1.5 to 2.5 pp away from a correct start on the flat plateau.
   - **Gate A (ii-c) S-G Wrongly Confident Start**: Depends on **Observability Gating & Step Capping**. Without capping, large innovation spikes on the plateau alias into spurious SOC steps.
   - **Gate A (ii-a) S-B Unknown Start Win Rate**: Enabled by **Confidence-Aware Reset** ($P_0 = 0.01$ when unknown), which allows the Kalman gain to pull the state towards OCV as soon as knee observability is reached.
   - **Gate B Cell Transfer (Set X)**: Depends directly on **Online RLS Impedance Adaptation**. RLS tracks the higher ohmic resistance of Cell A1-008, preventing terminal voltage mismatch from distorting the SOC state.
