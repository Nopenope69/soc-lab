# Component Ablation and Keep Rule Ledger (Gauntlet V2)

Reference Baseline: Tuned `E2` (`tune_2`) on Stage V1 Model (`calce_a123_v4.yaml`).

## Keep Rule Criteria
A component is **KEPT** if:
1. Mean RMSE over S-B and S-C improves by $\ge 10\%$ relative on A1-007 held-out (40, 50 °C) **OR** on cross-cell set X (40, 50 °C);
2. Does not worsen the other set by more than $5\%$ relative;
3. S-A on A1-007 held-out does not worsen by more than $0.30\text{ pp}$;
4. S-F worst-case error on A1-007 held-out does not increase by more than $2.00\text{ pp}$.

---

## Reference Baseline Performance (Tuned E2)
- **A1-007 Held-out (40, 50 °C) Mean SBC RMSE:** `2.8253 pp`
- **A1-007 Held-out (40, 50 °C) Mean S-A RMSE:** `1.2442 pp`
- **A1-007 Held-out (40, 50 °C) S-F Worst-Case Error:** `6.4360 pp`
- **Cross-Cell Set X Held-out (40, 50 °C) Mean SBC RMSE:** `10.2816 pp`
- **Cross-Cell Set X Held-out (40, 50 °C) Mean S-A RMSE:** `7.0968 pp`
- **Cross-Cell Set X Held-out (40, 50 °C) S-F Worst-Case Error:** `25.2526 pp`

---

## Component Evaluation Log

### Round D1: `e5v4` (Observability Gate & Plateau Step Cap)
- **Implementation:** `src/soc/estimators/e5v4.py` (Class `E5V4ObservabilityEKF`)
- **Unit Tests:** `tests/test_e5v4.py` (8/8 passed, per-step runtime 0.38 ms < 5 ms)
- **Measured Metrics:**
  - A1-007 Held-out Mean SBC RMSE: `2.6058 pp` (**-7.77%** relative vs reference, improvement)
  - Cross-Cell Set X Held-out Mean SBC RMSE: `9.0435 pp` (**-12.04%** relative vs reference, **PASSES $\ge 10\%$ criterion**)
  - A1-007 Held-out Mean S-A RMSE: `1.2025 pp` (**-0.0417 pp** diff vs reference, **PASSES $\le +0.30$ pp**)
  - A1-007 Held-out S-F Worst-Case Error: `5.3344 pp` (**-1.1016 pp** diff vs reference, **PASSES $\le +2.00$ pp**)
  - Set X Held-out Mean S-A RMSE: `5.9455 pp` (improved from 7.0968 pp)
  - Set X Held-out S-F Worst-Case Error: `22.911 pp` (improved from 25.253 pp)
- **Clause Checks:**
  - Clause 1 ($\ge 10\%$ gain on 007 or X): **PASS** (-12.04% on Set X)
  - Clause 2 ($\le 5\%$ worsening on other): **PASS** (-7.77% on A1-007, strictly improved)
  - Clause 3 (S-A diff $\le +0.30\text{ pp}$): **PASS** (-0.0417 pp)
  - Clause 4 (S-F worst diff $\le +2.00\text{ pp}$): **PASS** (-1.1016 pp)
- **Verdict:** **KEEP** (Kept on Round 1)

### Round D2: `e4v2` (Online RLS Impedance Adaptation on R0 and R1)
- **Implementation:** `src/soc/estimators/e4v2_rls.py` (Class `E4V2RLSEKF`)
- **Unit Tests:** `tests/test_e4v2.py` (9/9 passed, per-step runtime 0.15 ms < 5 ms)
- **Measured Metrics:**
  - A1-007 Held-out Mean SBC RMSE: `2.7089 pp` (**-4.12%** relative vs reference, improvement)
  - Cross-Cell Set X Held-out Mean SBC RMSE: `6.0337 pp` (**-41.32%** relative vs reference, **PASSES $\ge 10\%$ criterion**)
  - A1-007 Held-out Mean S-A RMSE: `1.2651 pp` (**+0.0210 pp** diff vs reference, **PASSES $\le +0.30$ pp**)
  - A1-007 Held-out S-F Worst-Case Error: `6.1509 pp` (**-0.2850 pp** diff vs reference, **PASSES $\le +2.00$ pp**)
  - Set X Held-out Mean S-A RMSE: `1.5435 pp` (massive drop from 7.0968 pp)
  - Set X Held-out S-F Worst-Case Error: `7.961 pp` (massive drop from 25.253 pp)
- **Clause Checks:**
  - Clause 1 ($\ge 10\%$ gain on 007 or X): **PASS** (-41.32% on Set X)
  - Clause 2 ($\le 5\%$ worsening on other): **PASS** (-4.12% on A1-007, strictly improved)
  - Clause 3 (S-A diff $\le +0.30\text{ pp}$): **PASS** (+0.0210 pp)
  - Clause 4 (S-F worst diff $\le +2.00\text{ pp}$): **PASS** (-0.2850 pp)
### Round D3: `innovation_gating` (Plateau Innovation Gating)
- **Implementation:** `src/soc/estimators/innovation_gating.py` (Class `D3InnovationGatedEKF`)
- **Unit Tests:** `tests/test_innovation_gating.py` (8/8 passed, per-step runtime 0.15 ms < 5 ms)
- **Round 1 (`k_gate=2.0, sl_th=0.05, p_th=0.005`):**
  - A1-007 Held-out SBC RMSE: `2.7844 pp` (-1.45% relative)
  - Set X Held-out SBC RMSE: `9.8708 pp` (-4.00% relative)
  - Clause 1 check ($\ge 10\%$ improvement): **FAIL** (-4.00% < 10%)
- **Round 2 (`k_gate=1.5, sl_th=0.05, p_th=0.002`):**
  - A1-007 Held-out SBC RMSE: `2.8253 pp` (+0.00% relative)
  - Set X Held-out SBC RMSE: `10.1085 pp` (-1.68% relative)
  - Clause 1 check ($\ge 10\%$ improvement): **FAIL** (-1.68% < 10%)
- **Physical Root Cause:**
  - In partial cycling windows with initial offset (Scenario S-B), true SOC differs by $\pm 5$ to $\pm 10\text{ pp}$ from the initial estimate. On the flat LFP plateau ($20\% \le \text{SOC} \le 80\%$), large voltage residuals are precisely the signal needed for the filter to correct this offset.
  - Suppressing updates when innovation is large slows or prevents offset convergence, fundamentally contradicting the objective of S-B. Consequently, D3 cannot achieve the required $\ge 10\%$ gain on S-B and S-C.
- **Verdict:** **DROP** (Clause 1 not satisfied after 2 rounds).

---

## Summary of Component Decisions
| Component | Function | Set X SBC Diff | A1-007 SBC Diff | Keep Rule Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **D1: `e5v4`** | Observability Gating & Plateau Step Cap | **-12.04%** | **-7.77%** | **KEEP** |
| **D2: `e4v2`** | Online RLS Impedance Adaptation ($R_0, R_1$) | **-41.32%** | **-4.12%** | **KEEP** |
| **D3: `innovation_gating`** | Plateau Innovation Gating | **-4.00%** | **-1.45%** | **DROP** |
