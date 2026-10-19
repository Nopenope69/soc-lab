# Gauntlet E0 Fairness & S-A Error Decomposition Audit

**Document ID:** GAUNTLET-E0-AUDIT-20261019  
**Target:** Ground truth vs E0, E1, and E7 in Matched Scenario S-A (DST Profile, Cell A1-007)  
**Dataset:** CALCE A123 26650 LFP  
**Audit Script:** `scripts/e0_audit.py` (data in `reports/gauntlet/e0_audit_data.csv`, traces in `reports/gauntlet/e0_soc_traces.csv`, plot in `reports/gauntlet/e0_audit_plot.png`)

---

## 1. Clarification on the Reported "5.918 pp"

> **Audit Finding:** The run **never** reported an E0 S-A RMSE of 5.918 pp.  
> The number **5.918 pp** was the **GATE 2 Clause (i) pass/fail threshold**:
> $$\text{Threshold} = \text{E0 RMSE} + 5.0\text{ pp} = 0.9184\text{ pp} + 5.000\text{ pp} = 5.9184\text{ pp}$$
> E0's actual held-out S-A RMSE was **0.918 pp** (0.901 pp at 40 °C, 0.935 pp at 50 °C). E7's observed S-A RMSE of **1.209 pp** was tested against this threshold and passed easily ($1.209\text{ pp} \le 5.918\text{ pp}$).

---

## 2. Per-Temperature Error Decomposition Table (S-A, Cell A1-007)

Every number below is derived from the execution of `scripts/e0_audit.py`:

| Parameter / Metric | 20 °C (Tune) | 25 °C (Suspect) | 30 °C (Tune) | 40 °C (Held-Out) | 50 °C (Held-Out) | Held-Out Mean (40 & 50 °C) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Truth Initial SOC** | 0.992193 | 0.979490 | 0.994736 | 0.997926 | 0.996369 | 0.997148 |
| **E0 Initial SOC** | 0.992193 | 0.979491 | 0.994736 | 0.997926 | 0.996369 | 0.997148 |
| **Initial SOC Difference (pp)** | +0.000005 | +0.000005 | +0.000010 | +0.000005 | +0.000005 | +0.000005 |
| **Truth Capacity $Q(T)$ (Ah)** | 1.065215 | 1.063562 | 1.073006 | 1.080190 | 1.080957 | 1.080574 |
| **E0 Capacity Used (Ah)** | 1.063562 | 1.063562 | 1.063562 | 1.063562 | 1.063562 | 1.063562 |
| **Capacity Discrepancy ($\Delta Q$, %)** | -0.155% | 0.000% | -0.880% | -1.539% | -1.609% | -1.574% |
| **Current Stream Identical?** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** |
| **Current Sign Identical?** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** |
| **Injected Faults in S-A?** | **0.000** | **0.000** | **0.000** | **0.000** | **0.000** | **0.000** |
| **E0 Total S-A RMSE (pp)** | **0.108** | **0.021** | **0.522** | **0.901** | **0.935** | **0.918** |
| **E0 Total S-A Bias (pp)** | -0.093 | -0.018 | -0.451 | -0.780 | -0.810 | -0.795 |
| ↳ *RMSE from Initial SOC Diff* | 0.000 pp | 0.000 pp | 0.000 pp | 0.000 pp | 0.000 pp | 0.000 pp |
| ↳ *RMSE from Capacity Difference* | 0.087 pp | 0.000 pp | 0.500 pp | 0.880 pp | 0.914 pp | 0.897 pp |
| ↳ *RMSE from Current Stream/Sign* | 0.000 pp | 0.000 pp | 0.000 pp | 0.000 pp | 0.000 pp | 0.000 pp |
| ↳ *RMSE from Injected Faults* | 0.000 pp | 0.000 pp | 0.000 pp | 0.000 pp | 0.000 pp | 0.000 pp |
| ↳ *RMSE from Step $\eta=0.998$ / $dt$* | 0.021 pp | 0.021 pp | 0.021 pp | 0.021 pp | 0.021 pp | 0.021 pp |
| **E0 RMSE with True $Q(T)$ (pp)** | **0.021** | **0.021** | **0.021** | **0.021** | **0.021** | **0.021** |
| **E1 Total S-A RMSE (pp)** | 4.610 | 2.634 | 4.254 | 4.269 | 3.774 | 4.021 |
| **E1 Total S-A Bias (pp)** | -4.006 | -1.932 | -3.765 | -3.839 | -3.302 | -3.570 |
| **E7 Total S-A RMSE (pp)** | 1.640 | 0.606 | 1.544 | 1.343 | 1.075 | 1.209 |
| **E7 Total S-A Bias (pp)** | -1.540 | +0.354 | -1.416 | -1.182 | -0.711 | -0.946 |
| **Truth Uncertainty: CV-Taper Gap (pp)** | **0.781** | **2.051** | **0.526** | **0.207** | **0.363** | **0.285** |
| **Is E7 Distinguishable from Taper Gap?** | **YES** | **NO** | **YES** | **YES** | **YES** | **YES** |

### Single-Sentence Cause
> **Cause Statement:** The reported 5.918 pp is not E0's error but the Clause (i) pass/fail threshold ($E0 + 5.0\text{ pp} = 0.918\text{ pp} + 5.0\text{ pp} = 5.918\text{ pp}$); E0's actual held-out S-A RMSE is 0.918 pp (0.108 pp at 20 °C, 0.021 pp at 25 °C, 0.522 pp at 30 °C, 0.901 pp at 40 °C, 0.935 pp at 50 °C), caused entirely by E0 using the single 25 °C nominal capacity $1.06356\text{ Ah}$ while truth used temperature-scheduled $Q(T)$ (up to $1.08096\text{ Ah}$, a $-1.61\%$ difference), with zero contribution from initial SOC, current stream, or fault errors.

---

## 3. Truth Uncertainty vs Estimator Accuracy

Rule R3 defines the ground truth initial SOC as $z_0 = 1 - \text{CV-taper gap}(T)$ using values from `reports/diagnostics/d8_anchor_gap.csv`. This taper gap represents the unmeasured charge entering the cell during the constant-voltage phase before the cycler cuts off:
- **At 25 °C (Suspect):** The taper gap is **$2.051\text{ pp}$** (due to an atypical 3,486-second CV hold). E7's observed S-A RMSE at 25 °C is **$0.606\text{ pp}$**. Because $0.606\text{ pp} < 2.051\text{ pp}$, E7's error is **completely indistinguishable** from ground truth setup uncertainty. This validates Rule R4's exclusion of 25 °C from gate decisions.
- **At 40 °C & 50 °C (Held-out Decision Temperatures):** The taper gaps are **$0.207\text{ pp}$** and **$0.363\text{ pp}$** (mean $0.285\text{ pp}$). E7's S-A RMSE of **$1.209\text{ pp}$** exceeds the taper gap ($1.209 > 0.285\text{ pp}$), confirming that E7's error on decision temperatures is statistically distinguishable from truth anchor uncertainty.

---

## 4. Formal Audit Classification

We evaluate the three protocol classifications:

### Classification (A): Scenario-Construction Bug in E0 Capacity
- **Evidence for (A):** The scenario runner passed `base_params` (containing a single static 25 °C nominal capacity $1.06356\text{ Ah}$) to `E0CoulombCounting`, whereas ground truth was integrated using temperature-scheduled C/20 capacity $Q(T)$ ($1.08019\text{ Ah}$ at 40 °C, $1.08096\text{ Ah}$ at 50 °C). If E0 was intended to represent an ideal Coulomb-counting reference that integrates the exact same capacity as the truth, then this parameter mismatch is a scenario-construction handicap.
- **Fix under (A):** Configure E0 in the scenario runner with `replace(base_params, nominal_capacity_ah=data.cap_c20)`. This reduces E0's S-A RMSE from $0.918\text{ pp}$ to $0.021\text{ pp}$.
- **Impact of Fix on GATE 2 Clause (ii):** As demonstrated by the audit script, when E0 is given the true $Q(T)$, **E7 still beats E0 in exactly 30 of 38 cases (78.95%)**. Not a single loss case changes! In all 8 loss cases (S-C partial windows, S-D rest inversions, and S-B +5 pp offset at 60% SOC), E0's RMSE is even smaller ($0.01\text{--}0.25\text{ pp}$), making it even harder for E7 to beat. Therefore, fixing E0 under (A) leaves Clause (ii) failed.

### Classification (B): Realistic Static Estimator Baseline
- **Evidence for (B):** In a production BMS deployment, no estimator (neither E0, E1, nor E7) has access to the exact laboratory C/20 capacity table unless an online capacity observer is implemented. In the Gauntlet protocol, all estimators (E0 through E7) were evaluated symmetrically using the exact same parameter object `base_params`. E0's $0.918\text{ pp}$ RMSE is real and reflects the physical consequence of temperature-dependent capacity expansion ($+1.6\%$) against a fixed nominal rating. Furthermore, 5.918 pp was never an error measurement, but the gate formula threshold ($E0 + 5.0\text{ pp}$).

### Conclusion & Mechanical Decision
Whether classified as **(A)** (scenario-construction capacity mismatch) or **(B)** (symmetric nominal calibration across all estimators):
1. Under **(A)**: Fixing E0 to use $Q(T)$ produces identical Clause (ii) win rate: **$30 / 38 = 78.95\% < 80.0\%$ (FAIL)**. Per Step 3 rules (*"If E7 fails, END as NO-GO(estimator) and write the analysis"*), the run terminates as **`NO-GO(estimator)`**.
2. Under **(B)**: Per Step 3 rules (*"If classification is (B) or (C): do not rerun anything and do not touch the gate. END as NO-GO(estimator)"*), the run terminates as **`NO-GO(estimator)`**.

Both branches yield the identical, unambiguous scientific conclusion: **`NO-GO(estimator)`**.

---
*Report generated autonomously by Antigravity under CALCE A123 Gauntlet Protocol.*
