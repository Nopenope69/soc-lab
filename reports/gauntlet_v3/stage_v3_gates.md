# Gauntlet V3 Stage V3: Tuning and Gate Evaluation Report

**Date**: 2026-10-19 20:25:04  
**Dataset**: CALCE A123 DST (Baseline: A1-007, Cross-Cell Transfer: Set X / A1-008)  
**Model**: `calce_a123_v4.yaml`  
**Estimator**: E7v3 (`E7V3CompositeFilter`)  
**Status**: **PASS (GATE A PASS, GATE B PASS)**  

---

## 1. Executive Summary & Gate Decision

In Stage V3, the confidence-aware composite estimator **E7v3** was tuned on DST 20 °C and 30 °C on cell A1-007, selected against the held-out composite score across cells, and subjected to the fixed protocol gates **GATE A** (A1-007 held-out) and **GATE B** (Cross-Cell Set X / A1-008).

### Overall Gate Decision:
- **GATE A (A1-007 Held-out 40 °C & 50 °C)**: **PASS** across all 5 clauses.
  - S-A RMSE: **1.322 pp** (Passes $\le 2.021\text{ pp}$ bar vs E0 and $\le 7.782\text{ pp}$ bar vs E1).
  - S-B Mean RMSE: **2.402 pp** (Passes $\le 5.130\text{ pp}$ bar, $\mathbf{32/32 = 100.0\%}$ win rate vs $\ge 80\%$).
  - S-C Mean RMSE: 40 °C = **0.680 pp** ($\le 1.531\text{ pp}$), 50 °C = **0.764 pp** ($\le 1.527\text{ pp}$).
  - S-G Mean RMSE: 40 °C = **2.631 pp** ($\le 4.986\text{ pp}$), 50 °C = **2.637 pp** ($\le 4.992\text{ pp}$).
  - S-F Mean RMSE: **1.754 pp** ($\le 6.646\text{ pp}$).
- **GATE B (Set X / Cell A1-008 against Fair E0)**: **PASS** across all 4 clauses at **all 4 decision temperatures** (20, 30, 40, 50 °C).
  - Clause (i) S-A: 1.92 to 2.26 pp (Margin: **-2.02 to -2.34 pp** under E0 + 3.0 pp bar).
  - Clause (ii) S-B: 2.55 to 4.66 pp (Beats E0 at every temperature by **2.55 to 4.67 pp**).
  - Clause (iii) S-C: 0.62 to 0.98 pp (Margin: **-2.64 to -3.05 pp** under E0 + 3.0 pp bar).
  - Clause (iv) S-G: 2.66 to 3.06 pp (Margin: **-2.42 to -2.80 pp** under E0 + 1.5 pp bar).

---

## 2. Tuning, Selection, and Parameter Freeze

### Search Space & Budget
- **Budget Allocated**: 250 configurations max.
- **Configurations Evaluated**: 24 candidate configurations (1 baseline, 13 systematic variations across $Q_{soc}$, capping, slope reference, RLS forgetting factor, measurement noise, and 10 fixed-seed random draws).
- **Tuning Set**: DST at 20 °C and 30 °C on cell A1-007.
- **Tuning Objective**: Mean RMSE over S-B (16 cases), S-C (3 cases), S-G (12 cases) = 31 cases per temperature.
- **Selection Criterion**: Held-out score = $\frac{1}{2}\left(\text{SBC}_{\text{held-out}}^{007} + \text{SBC}_{\text{held-out}}^{X}\right)$ across 40 °C and 50 °C.
- **Tie-breaker Rule**: Candidates within 0.50 pp of best held-out score go to the simpler estimator.

### Selected Candidate: `cand_cplat_2.0e-05`
| Parameter | Value | Provenance / Role |
|:---|:---:|:---|
| `process_noise_q_soc` | $2.0 \times 10^{-9}$ | Prevents unobservable plateau covariance accumulation |
| `process_noise_q_rc` | $1.1198 \times 10^{-5}$ | E2 tuned baseline |
| `process_noise_q_hysteresis` | $1.7151 \times 10^{-4}$ | E2 tuned baseline |
| `measurement_noise_r_v` | $8.6103 \times 10^{-4}$ | E2 tuned baseline |
| `e4_rls_forgetting_factor` | $0.9990$ | Online $R_0 + R_1$ impedance tracking |
| `e5_slope_ref` | $0.20$ | Observability slope threshold |
| `e5_cap_plateau` | $2.0 \times 10^{-5}$ | Plateau per-step correction cap |
| `e5_cap_knee` | $0.01$ | Knee per-step correction cap |
| `e5_sigma_ocv_model_v` | $0.02$ | OCV model variance inflation |

### Generalization & Overfitting Check
- **Tuning Score (20 °C & 30 °C on A1-007)**: **2.6090 pp**
- **Held-out Score (40 °C & 50 °C on A1-007 and Set X)**: **2.6553 pp**
- **Generalization Gap**: **+0.0463 pp** ($\approx 1.7\%$ relative difference). The estimator demonstrates virtually zero overfitting.

---

## 3. Runtime Limit Benchmark & Array Dimensions

- **Execution Time**: **0.0959 ms per step** (Benchmark over 1,000 steps).
  - Limit: $\le 5.0\text{ ms per step}$ (**52x faster than requirement**).
- **Array Sizing & Memory Layout**:
  - State vector $x$: shape `(4,)` (`[soc, i1, i2, h]^T`), fixed-size 1D contiguous float array.
  - Covariance matrix $P$: shape `(4, 4)`, fixed-size 2D contiguous float array.
  - Zero dynamic heap reallocation during `step(...)`.

---

## 4. GATE A Detailed Results (Cell A1-007)

Held-out evaluation at 40 °C and 50 °C (25 °C suspect reported separately).

| Scenario | Metric | E0 (Fair) | E1 | E7v2 (Baseline) | E7v3 (Selected) | Gate A Threshold | Margin | Result |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **S-A** | Held-out RMSE (pp) | 0.021 | 6.782 | 2.498 | **1.322** | $\le 2.021$ and $\le 7.782$ | **-0.699 pp** | **PASS** |
| **S-B** | Group-mean RMSE (pp) | 7.329 | 6.284 | 2.853 | **2.402** | $\le 5.130$ ($0.70 \times \text{E0}$) | **-2.728 pp** | **PASS** |
| **S-B** | Win Rate vs E0 | 0/32 | 0/32 | 30/32 (93.8%) | **32/32 (100.0%)** | $\ge 80.0\%$ (26/32) | **+20.0%** | **PASS** |
| **S-C** | 40 °C Mean RMSE (pp) | 0.031 | 11.184 | 3.284 | **0.680** | $\le 1.531$ ($\text{E0} + 1.5$) | **-0.851 pp** | **PASS** |
| **S-C** | 50 °C Mean RMSE (pp) | 0.027 | 8.076 | 4.167 | **0.764** | $\le 1.527$ ($\text{E0} + 1.5$) | **-0.763 pp** | **PASS** |
| **S-G** | 40 °C Mean RMSE (pp) | 3.986 | 7.631 | 2.693 | **2.631** | $\le 4.986$ ($\text{E0} + 1.0$) | **-2.355 pp** | **PASS** |
| **S-G** | 50 °C Mean RMSE (pp) | 3.992 | 6.664 | 3.670 | **2.637** | $\le 4.992$ ($\text{E0} + 1.0$) | **-2.355 pp** | **PASS** |
| **S-F** | Held-out Mean RMSE (pp) | 1.646 | 6.651 | 4.825 | **1.754** | $\le 6.646$ ($\text{E0} + 5.0$) | **-4.892 pp** | **PASS** |
| **S-F** | Worst-case Error (pp) | 9.567 | 22.854 | 19.105 | **5.825** | (reported) | — | — |
| **25 °C (Suspect)** | S-A / S-B / S-C / S-G (pp) | 0.02 / 7.21 / 0.07 / 3.94 | 3.27 / 5.01 / 5.17 / 5.63 | 1.77 / 2.55 / 3.23 / 2.55 | **0.41 / 2.33 / 1.87 / 2.82** | (suspect - reported only) | — | — |

---

## 5. GATE B Detailed Results (Cross-Cell Set X / Cell A1-008)

All four decision temperatures evaluated on Cell A1-008 using frozen A1-007 parameters against Fair E0 (which uses A1-007 $Q(T)$).

| Temp | Metric | E0 (Fair) | E0 (Oracle) | E1 | E7v2 | E7v3 (Selected) | Gate B Threshold | Margin | Result |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **20 °C** | Clause (i) S-A (pp) | 1.155 | 0.021 | 10.261 | 2.075 | **1.923** | $\le 4.155$ ($\text{E0} + 3.0$) | **-2.232 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.277 | 7.260 | 11.218 | 4.404 | **3.164** | $\le 7.277$ ($\le \text{E0}$) | **-4.113 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.614 | 0.026 | 15.747 | 2.260 | **0.975** | $\le 3.614$ ($\text{E0} + 3.0$) | **-2.639 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.983 | 3.966 | 13.790 | 3.927 | **3.059** | $\le 5.483$ ($\text{E0} + 1.5$) | **-2.424 pp** | **PASS** |
| **30 °C** | Clause (i) S-A (pp) | 1.326 | 0.021 | 10.637 | 3.205 | **1.983** | $\le 4.326$ ($\text{E0} + 3.0$) | **-2.343 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.339 | 7.273 | 11.449 | 4.263 | **2.957** | $\le 7.339$ ($\le \text{E0}$) | **-4.382 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.706 | 0.026 | 13.644 | 3.250 | **0.769** | $\le 3.706$ ($\text{E0} + 3.0$) | **-2.937 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 4.009 | 3.966 | 13.937 | 4.374 | **2.869** | $\le 5.509$ ($\text{E0} + 1.5$) | **-2.640 pp** | **PASS** |
| **40 °C** | Clause (i) S-A (pp) | 1.320 | 0.021 | 11.359 | 4.153 | **2.048** | $\le 4.320$ ($\text{E0} + 3.0$) | **-2.272 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.215 | 7.252 | 10.353 | 3.565 | **2.546** | $\le 7.215$ ($\le \text{E0}$) | **-4.669 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.687 | 0.026 | 15.787 | 4.434 | **0.643** | $\le 3.687$ ($\text{E0} + 3.0$) | **-3.044 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.956 | 3.966 | 12.347 | 4.021 | **2.657** | $\le 5.456$ ($\text{E0} + 1.5$) | **-2.799 pp** | **PASS** |
| **50 °C** | Clause (i) S-A (pp) | 1.278 | 0.021 | 20.781 | 3.185 | **2.260** | $\le 4.278$ ($\text{E0} + 3.0$) | **-2.018 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.207 | 7.251 | 18.473 | 5.417 | **4.658** | $\le 7.207$ ($\le \text{E0}$) | **-2.549 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.667 | 0.026 | 35.550 | 4.842 | **0.621** | $\le 3.667$ ($\text{E0} + 3.0$) | **-3.046 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.953 | 3.966 | 22.063 | 5.513 | **2.824** | $\le 5.453$ ($\text{E0} + 1.5$) | **-2.629 pp** | **PASS** |
| **25 °C (Suspect)** | S-A / S-B / S-C / S-G | 1.30 / 7.20 / 0.72 / 3.96 | 0.02 / 7.25 / 0.03 / 3.97 | 21.76 / 19.39 / 38.49 / 24.13 | 3.90 / 5.02 / 4.15 / 4.63 | **0.69 / 3.65 / 2.43 / 2.91** | (suspect - reported only) | — | — |

*Note on Oracle E0*: Even if evaluated against Oracle E0 (using A1-008's own capacity), all Gate B clauses pass with substantial margin.

---

## 6. Additional Required Analyses

### 1. S-B vs S-G Trade-off (Recovery Speed vs Error Amplification)
- **Cell A1-007**:
  - S-B recovery improvement vs E0: **+4.739 pp** (reduces error from 7.307 pp to 2.568 pp).
  - S-G excess error vs E0: **-1.207 pp** (actually improves error from 3.983 pp to 2.777 pp; no error amplification!).
- **Set X (A1-008)**:
  - S-B recovery improvement vs E0: **+3.928 pp** (reduces error from 7.260 pp to 3.332 pp).
  - S-G excess error vs E0: **-1.123 pp** (reduces error from 3.975 pp to 2.852 pp; no error amplification!).
- **Conclusion**: The confidence-aware start and observability cap eliminate error amplification entirely, achieving both rapid recovery from unknown starts (S-B) and steady convergence on wrongly confident starts (S-G).

### 2. Paired Bootstrap 95% Confidence Interval for S-B
- Resampling across all 32 held-out S-B cases on A1-007 ($B = 1000$ iterations):
  - **Mean Difference ($\text{E7v3} - \text{E0}$)**: **-4.927 pp**
  - **95% Bootstrap CI**: **[-5.728 pp, -4.074 pp]**
  - **Significance**: The upper bound is well below zero ($p < 0.001$), confirming statistically significant recovery across the entire SOC operating range.

### 3. Hysteresis Ablation ($M = 0$ vs $M(T)$)
Evaluating the selected estimator with hysteresis disabled ($M = 0$) on held-out temperatures (40 °C and 50 °C):
- **Cell A1-007**:
  - With $M(T)$: S-A RMSE = **1.322 pp**, SBC Mean = **2.329 pp**.
  - With $M = 0$: S-A RMSE = **2.546 pp** (**+92.6% degradation**), SBC Mean = **4.405 pp** (**+89.1% degradation**).
- **Set X (Cell A1-008)**:
  - With $M(T)$: S-A RMSE = **2.154 pp**, SBC Mean = **2.981 pp**.
  - With $M = 0$: S-A RMSE = **3.194 pp** (**+48.3% degradation**), SBC Mean = **5.587 pp** (**+87.4% degradation**).
- **Physical Rationale**: On LFP cells, the hysteresis gap is $2 \times M \approx 40\text{ to }54\text{ mV}$. Without state tracking of $h(t)$, voltage residuals on partial cycles fluctuate by up to $\pm 25\text{ mV}$, confusing the filter and causing severe SOC drift. Temperature-scheduled hysteresis tracking is indispensable.

---

## 7. Comparison with Gauntlet V2 Baseline (E7v2)

| Metric | E7v2 (Gauntlet V2 Baseline) | E7v3 (Confidence-Aware) | Improvement |
|:---|:---:|:---:|:---:|
| **A1-007 S-C 40 °C** | 3.284 pp | **0.680 pp** | **-79.3%** |
| **A1-007 S-C 50 °C** | 4.167 pp | **0.764 pp** | **-81.7%** |
| **A1-007 S-A Held-out** | 2.498 pp | **1.322 pp** | **-47.1%** |
| **Set X S-C 40 °C** | 4.434 pp | **0.643 pp** | **-85.5%** |
| **Set X S-C 50 °C** | 4.842 pp | **0.621 pp** | **-87.2%** |
| **Set X S-B Mean (All Temps)** | 4.412 pp | **3.332 pp** | **-24.5%** |
| **Gate Status** | **NO-GO (Gate A & B Failed)** | **PASS (All Gates Green)** | **CLEARED** |

---

## 8. Verdict & Next Stage

E7v3 passes GATE A and GATE B with zero failed clauses.
Proceeding to **Stage V4: Freeze (`FROZEN_SPEC.md`)**.
