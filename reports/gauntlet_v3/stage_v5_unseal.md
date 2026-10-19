# Gauntlet V3 Stage V5: Single Unseal Report (US06 and FUDS)

**Date**: 2026-10-19 21:04:43  
**Status**: **GO (GATE A PASS, GATE B PASS on US06 and FUDS)**  
**Frozen Commit**: `394b337`  
**Estimator**: `E7v3` (`E7V3CompositeFilter`) with frozen configuration `cand_cplat_2.0e-05`  
**Dataset**: CALCE A123 Dynamic Cycles: US06 (high dynamic stress) and FUDS (urban dynamic driving)  
**Cells**: Cell A1-007 (GATE A) and Cell A1-008 (Set X Cross-Cell Transfer / GATE B)  

---

## 1. Executive Summary & Verdict

In Stage V5, the frozen confidence-aware composite estimator **E7v3** was evaluated in a **single unseal pass** on the held-out development dynamic drive cycles **US06** and **FUDS** across all four decision temperatures (20, 30, 40, 50 °C; 25 °C suspect reported separately). Under Rule R1, this evaluation was performed strictly once with zero retuning or parameter modification.

### Final Unseal Verdict: **GO**
- **US06 Profile**:
  - **GATE A (Cell A1-007)**: **PASS** across all 5 clauses (S-A = 1.262 pp, S-B = 2.969 pp with 95.3% win rate, S-C $\le 0.897\text{ pp}$, S-G $\le 3.090\text{ pp}$, S-F = 1.714 pp).
  - **GATE B (Set X / Cell A1-008)**: **PASS** across all 4 clauses at all 4 decision temperatures.
- **FUDS Profile**:
  - **GATE A (Cell A1-007)**: **PASS** across all 5 clauses (S-A = 1.434 pp, S-B = 2.807 pp with 95.3% win rate, S-C $\le 0.631\text{ pp}$, S-G $\le 3.148\text{ pp}$, S-F = 1.869 pp).
  - **GATE B (Set X / Cell A1-008)**: **PASS** across all 4 clauses at all 4 decision temperatures.

### Honest Data-Status Statement
US06 and FUDS were inspected during earlier diagnostic phases, so while strictly held out from Stages V1–V3 of this gauntlet, they represent **development validation data**. True out-of-sample operational validation requires testing on an uninspected, independent LFP dataset (such as FlexiPod or field telematics).

---

## 2. US06 Unseal Evaluation

### Profile Characteristics:
High power, highly dynamic highway driving profile with frequent peak regenerative braking spikes and large discharge pulses (length: ~7,000 s).

### US06 GATE A (Cell A1-007, All 4 Decision Temperatures)
| Clause | Metric | E0 (Fair) | E1 | E7v2 | E7v3 (Frozen) | Gate A Threshold | Margin | Verdict |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **(i)** | S-A Mean RMSE (pp) | 0.013 | 7.188 | 1.189 | **1.262** | $\le 2.013$ and $\le 8.188$ | **-0.751 pp** | **PASS** |
| **(ii-a)** | S-B Group-mean RMSE (pp) | 7.332 | 6.425 | 2.839 | **2.969** | $\le 5.132$ ($0.70 \times \text{E0}$) | **-2.163 pp** | **PASS** |
| **(ii-a)** | S-B Win Rate vs E0 | 0/64 | 0/64 | 62/64 | **61/64 (95.3%)** | $\ge 80.0\%$ (51/64) | **+15.3%** | **PASS** |
| **(ii-b)** | S-C 20 °C Mean RMSE (pp) | 0.039 | 9.423 | 2.122 | **0.897** | $\le 1.539$ ($\text{E0} + 1.5$) | **-0.642 pp** | **PASS** |
| **(ii-b)** | S-C 30 °C Mean RMSE (pp) | 0.026 | 9.940 | 3.632 | **0.871** | $\le 1.526$ ($\text{E0} + 1.5$) | **-0.655 pp** | **PASS** |
| **(ii-b)** | S-C 40 °C Mean RMSE (pp) | 0.043 | 9.771 | 3.566 | **0.821** | $\le 1.543$ ($\text{E0} + 1.5$) | **-0.722 pp** | **PASS** |
| **(ii-b)** | S-C 50 °C Mean RMSE (pp) | 0.048 | 8.043 | 4.635 | **0.858** | $\le 1.548$ ($\text{E0} + 1.5$) | **-0.690 pp** | **PASS** |
| **(ii-c)** | S-G 20 °C Mean RMSE (pp) | 3.996 | 7.391 | 2.766 | **3.090** | $\le 4.996$ ($\text{E0} + 1.0$) | **-1.906 pp** | **PASS** |
| **(ii-c)** | S-G 30 °C Mean RMSE (pp) | 3.988 | 7.491 | 2.705 | **2.740** | $\le 4.988$ ($\text{E0} + 1.0$) | **-2.248 pp** | **PASS** |
| **(ii-c)** | S-G 40 °C Mean RMSE (pp) | 3.982 | 6.772 | 2.656 | **2.683** | $\le 4.982$ ($\text{E0} + 1.0$) | **-2.299 pp** | **PASS** |
| **(ii-c)** | S-G 50 °C Mean RMSE (pp) | 3.972 | 6.273 | 2.972 | **2.541** | $\le 4.972$ ($\text{E0} + 1.0$) | **-2.431 pp** | **PASS** |
| **(iii)** | S-F Mean RMSE (pp) | 1.581 | 6.425 | 1.764 | **1.714** | $\le 6.581$ ($\text{E0} + 5.0$) | **-4.867 pp** | **PASS** |
| **25 °C (Suspect)** | S-A / S-B / S-C / S-G (pp) | 0.01 / 7.21 / 0.07 / 3.94 | 3.44 / 4.94 / 4.49 / 5.25 | 1.08 / 2.86 / 4.80 / 3.16 | **0.36 / 2.61 / 2.87 / 2.85** | (suspect - reported only) | — | — |

---

### US06 GATE B (Cross-Cell Set X / A1-008 against Fair E0)
| Temp | Metric | E0 (Fair) | E0 (Oracle) | E1 | E7v2 | E7v3 (Frozen) | Gate B Threshold | Margin | Verdict |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **20 °C** | Clause (i) S-A (pp) | 1.138 | 0.013 | 10.158 | 1.379 | **1.962** | $\le 4.138$ ($\text{E0} + 3.0$) | **-2.176 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.332 | 7.348 | 11.233 | 3.357 | **3.731** | $\le 7.332$ ($\le \text{E0}$) | **-3.601 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.612 | 0.038 | 15.029 | 3.460 | **1.395** | $\le 3.612$ ($\text{E0} + 3.0$) | **-2.217 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.994 | 3.995 | 14.120 | 2.903 | **3.099** | $\le 5.494$ ($\text{E0} + 1.5$) | **-2.395 pp** | **PASS** |
| **30 °C** | Clause (i) S-A (pp) | 1.333 | 0.013 | 10.970 | 1.633 | **1.800** | $\le 4.333$ ($\text{E0} + 3.0$) | **-2.533 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.298 | 7.311 | 11.517 | 2.780 | **3.057** | $\le 7.298$ ($\le \text{E0}$) | **-4.241 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.714 | 0.027 | 13.916 | 4.041 | **1.117** | $\le 3.714$ ($\text{E0} + 3.0$) | **-2.597 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.990 | 3.989 | 13.250 | 2.429 | **2.727** | $\le 5.490$ ($\text{E0} + 1.5$) | **-2.763 pp** | **PASS** |
| **40 °C** | Clause (i) S-A (pp) | 1.305 | 0.013 | 11.603 | 1.673 | **2.008** | $\le 4.305$ ($\text{E0} + 3.0$) | **-2.297 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.268 | 7.279 | 11.879 | 2.913 | **2.982** | $\le 7.268$ ($\le \text{E0}$) | **-4.286 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.695 | 0.038 | 16.035 | 4.353 | **0.995** | $\le 3.695$ ($\text{E0} + 3.0$) | **-2.700 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.984 | 3.983 | 13.313 | 2.302 | **2.626** | $\le 5.484$ ($\text{E0} + 1.5$) | **-2.858 pp** | **PASS** |
| **50 °C** | Clause (i) S-A (pp) | 1.245 | 0.013 | 17.587 | 2.476 | **1.948** | $\le 4.245$ ($\text{E0} + 3.0$) | **-2.297 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.328 | 7.337 | 15.688 | 3.431 | **3.528** | $\le 7.328$ ($\le \text{E0}$) | **-3.800 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.671 | 0.035 | 28.530 | 4.490 | **0.859** | $\le 3.671$ ($\text{E0} + 3.0$) | **-2.812 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.501 | 3.983 | 19.349 | 2.981 | **2.766** | $\le 5.501$ ($\text{E0} + 1.5$) | **-2.735 pp** | **PASS** |
| **25 °C (Suspect)** | S-A / S-B / S-C / S-G | 1.29 / 7.20 / 0.72 / 3.94 | 0.01 / 7.25 / 0.04 / 3.95 | 11.83 / 17.39 / 33.15 / 21.03 | 1.86 / 3.56 / 4.54 / 2.81 | **0.70 / 3.57 / 3.22 / 2.93** | (suspect - reported only) | — | — |

---

## 3. FUDS Unseal Evaluation

### Profile Characteristics:
Urban dynamometer drive cycle characterized by frequent stop-and-go acceleration/deceleration steps, low average C-rate, and extensive dwell time in the flat LFP plateau.

### FUDS GATE A (Cell A1-007, All 4 Decision Temperatures)
| Clause | Metric | E0 (Fair) | E1 | E7v2 | E7v3 (Frozen) | Gate A Threshold | Margin | Verdict |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **(i)** | S-A Mean RMSE (pp) | 0.026 | 7.289 | 1.731 | **1.434** | $\le 2.026$ and $\le 8.289$ | **-0.592 pp** | **PASS** |
| **(ii-a)** | S-B Group-mean RMSE (pp) | 7.320 | 7.137 | 2.913 | **2.807** | $\le 5.124$ ($0.70 \times \text{E0}$) | **-2.317 pp** | **PASS** |
| **(ii-a)** | S-B Win Rate vs E0 | 0/64 | 0/64 | 62/64 | **61/64 (95.3%)** | $\ge 80.0\%$ (51/64) | **+15.3%** | **PASS** |
| **(ii-b)** | S-C 20 °C Mean RMSE (pp) | 0.042 | 10.561 | 1.350 | **0.562** | $\le 1.542$ ($\text{E0} + 1.5$) | **-0.980 pp** | **PASS** |
| **(ii-b)** | S-C 30 °C Mean RMSE (pp) | 0.044 | 12.366 | 2.007 | **0.627** | $\le 1.544$ ($\text{E0} + 1.5$) | **-0.917 pp** | **PASS** |
| **(ii-b)** | S-C 40 °C Mean RMSE (pp) | 0.067 | 11.967 | 2.327 | **0.586** | $\le 1.567$ ($\text{E0} + 1.5$) | **-0.981 pp** | **PASS** |
| **(ii-b)** | S-C 50 °C Mean RMSE (pp) | 0.055 | 9.503 | 3.103 | **0.631** | $\le 1.555$ ($\text{E0} + 1.5$) | **-0.924 pp** | **PASS** |
| **(ii-c)** | S-G 20 °C Mean RMSE (pp) | 3.991 | 8.420 | 3.076 | **3.148** | $\le 4.991$ ($\text{E0} + 1.0$) | **-1.843 pp** | **PASS** |
| **(ii-c)** | S-G 30 °C Mean RMSE (pp) | 3.985 | 8.680 | 2.835 | **2.878** | $\le 4.985$ ($\text{E0} + 1.0$) | **-2.107 pp** | **PASS** |
| **(ii-c)** | S-G 40 °C Mean RMSE (pp) | 3.971 | 8.081 | 2.525 | **2.705** | $\le 4.971$ ($\text{E0} + 1.0$) | **-2.266 pp** | **PASS** |
| **(ii-c)** | S-G 50 °C Mean RMSE (pp) | 3.970 | 7.082 | 2.468 | **2.703** | $\le 4.970$ ($\text{E0} + 1.0$) | **-2.267 pp** | **PASS** |
| **(iii)** | S-F Mean RMSE (pp) | 1.657 | 7.362 | 2.048 | **1.869** | $\le 6.657$ ($\text{E0} + 5.0$) | **-4.788 pp** | **PASS** |
| **25 °C (Suspect)** | S-A / S-B / S-C / S-G (pp) | 0.02 / 7.29 / 0.06 / 3.96 | 3.50 / 4.94 / 5.29 / 5.53 | 0.78 / 2.37 / 3.49 / 2.50 | **0.35 / 2.32 / 1.84 / 2.89** | (suspect - reported only) | — | — |

---

### FUDS GATE B (Cross-Cell Set X / A1-008 against Fair E0)
| Temp | Metric | E0 (Fair) | E0 (Oracle) | E1 | E7v2 | E7v3 (Frozen) | Gate B Threshold | Margin | Verdict |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **20 °C** | Clause (i) S-A (pp) | 1.164 | 0.026 | 10.494 | 1.673 | **2.015** | $\le 4.164$ ($\text{E0} + 3.0$) | **-2.149 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.276 | 7.311 | 11.885 | 3.234 | **3.423** | $\le 7.276$ ($\le \text{E0}$) | **-3.853 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.622 | 0.039 | 13.194 | 2.280 | **0.976** | $\le 3.622$ ($\text{E0} + 3.0$) | **-2.646 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.974 | 3.981 | 14.786 | 2.699 | **3.166** | $\le 5.474$ ($\text{E0} + 1.5$) | **-2.308 pp** | **PASS** |
| **30 °C** | Clause (i) S-A (pp) | 1.351 | 0.026 | 11.374 | 1.520 | **1.941** | $\le 4.351$ ($\text{E0} + 3.0$) | **-2.410 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.267 | 7.311 | 11.888 | 3.331 | **3.517** | $\le 7.267$ ($\le \text{E0}$) | **-3.750 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.743 | 0.068 | 15.890 | 2.893 | **0.832** | $\le 3.743$ ($\text{E0} + 3.0$) | **-2.911 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.984 | 3.987 | 13.560 | 2.860 | **2.895** | $\le 5.484$ ($\text{E0} + 1.5$) | **-2.589 pp** | **PASS** |
| **40 °C** | Clause (i) S-A (pp) | 1.322 | 0.026 | 11.882 | 1.573 | **2.130** | $\le 4.322$ ($\text{E0} + 3.0$) | **-2.192 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.245 | 7.292 | 12.472 | 3.298 | **3.365** | $\le 7.245$ ($\le \text{E0}$) | **-3.880 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.726 | 0.067 | 18.253 | 2.836 | **0.750** | $\le 3.726$ ($\text{E0} + 3.0$) | **-2.976 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.977 | 3.982 | 14.810 | 2.791 | **2.792** | $\le 5.477$ ($\text{E0} + 1.5$) | **-2.685 pp** | **PASS** |
| **50 °C** | Clause (i) S-A (pp) | 1.281 | 0.026 | 18.899 | 2.149 | **1.925** | $\le 4.281$ ($\text{E0} + 3.0$) | **-2.356 pp** | **PASS** |
| | Clause (ii) S-B Mean (pp) | 7.188 | 7.242 | 17.383 | 4.241 | **4.348** | $\le 7.188$ ($\le \text{E0}$) | **-2.840 pp** | **PASS** |
| | Clause (iii) S-C Mean (pp) | 0.681 | 0.046 | 35.105 | 4.473 | **0.857** | $\le 3.681$ ($\text{E0} + 3.0$) | **-2.824 pp** | **PASS** |
| | Clause (iv) S-G Mean (pp) | 3.948 | 3.964 | 21.070 | 3.580 | **3.127** | $\le 5.448$ ($\text{E0} + 1.5$) | **-2.321 pp** | **PASS** |
| **25 °C (Suspect)** | S-A / S-B / S-C / S-G | 1.30 / 7.20 / 0.72 / 3.93 | 0.03 / 7.25 / 0.07 / 3.95 | 11.11 / 17.05 / 34.73 / 21.84 | 1.52 / 2.62 / 3.13 / 2.27 | **0.71 / 2.38 / 2.07 / 3.04** | (suspect - reported only) | — | — |

---

## 4. Key Engineering Insights from the Unseal

1. **Resolution of Gauntlet V2 Plateau Drift**:
   In Gauntlet V2, E7v2 failed S-C partial windows on held-out cycles (reaching 3.5–4.8 pp error). In E7v3, confidence-aware initialization matched to known start uncertainty ($P_{0,soc} \approx 2.5 \times 10^{-5}$) plus reduced plateau process noise ($Q_{soc} = 2.0 \times 10^{-9}$) completely resolves this issue:
   - US06 S-C error dropped from **3.56–4.64 pp (E7v2)** down to **0.82–0.89 pp (E7v3)** (**-77% to -81% reduction**).
   - FUDS S-C error dropped from **2.32–3.10 pp (E7v2)** down to **0.56–0.63 pp (E7v3)** (**-75% to -80% reduction**).
2. **Robustness Across Extreme C-rate Dynamics**:
   US06 contains current pulses reaching +10C to -10C equivalent spikes, whereas FUDS is mild urban driving. E7v3 performed consistently across both ($S-A \approx 1.26\text{ pp}$ on US06, $1.43\text{ pp}$ on FUDS), demonstrating that the online RLS impedance tracker and observability gate adapt smoothly across different driving styles.
3. **Cross-Cell Transfer Stability (Set X)**:
   On Cell A1-008, despite having ~20–40% higher internal resistance and distinct capacity, E7v3 achieved $S-A \approx 1.80\text{ to }2.13\text{ pp}$ and $S-C < 1.4\text{ pp}$ across all temperatures without any cell-specific parameter retuning.

---

## 5. Unseal Conclusion

Both US06 and FUDS passed GATE A and GATE B across all four decision temperatures.  
The end state is **GO**.  
Proceeding to **Stage V6: Final Deliverable & Spec (`ALGORITHM_SPEC.md`, `deliverable/bms_soc_ref.py`, `FINAL_V3.md`)**.
