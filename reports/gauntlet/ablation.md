# Gauntlet Ablation Log (Stage 1.5 & Stage 2.5)

## Keep Rule Definition (Fixed)
A component or change is **KEPT** only if, on the held-out temperatures (40 and 50 °C, DST):
1. **BCD Performance:** Improves mean RMSE over scenarios S-B, S-C, S-D by $\ge 1.0\text{ pp}$ (absolute) against the best estimator so far.
2. **S-A Non-Inferiority:** Does not worsen matched scenario S-A by more than $0.3\text{ pp}$ (two-sided).
3. **S-F Robustness:** Does not increase the worst-case error in S-F by more than $2.0\text{ pp}$.
Otherwise, it is **DROPPED**.

## Baseline Reference (E2 on v3 model)
- Held-Out Temperatures: 40 °C and 50 °C (DST)
- **Mean BCD RMSE:** 3.29 pp (40 °C: 2.64 pp, 50 °C: 3.93 pp)
- **Mean S-A RMSE:** 1.70 pp (40 °C: 1.34 pp, 50 °C: 2.06 pp)
- **Worst-Case S-F Error:** 16.53 pp (40 °C: 14.16 pp, 50 °C: 16.53 pp)

---

## Component Evaluation Log (Stage 1.5)

| Round | Component | Implementation | BCD Mean RMSE (pp) | Delta BCD (pp) | S-A Mean RMSE (pp) | Delta S-A (pp) | S-F Worst Error (pp) | Delta S-F (pp) | Decision | Reason / Notes |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| 1 | C1 (E3 UKF) | 4-state UKF (`e3_ukf.py`) | 3.209 | -0.078 | 1.597 | -0.103 | 13.540 | -2.987 | **DROP** | BCD improvement of 0.078 pp misses the required $\ge 1.0\text{ pp}$ threshold. Runtime: 0.228 ms/step. |
| 2 | C2 (E4 RLS R0) | Online RLS scalar multiplier on R0 (`e4_rls_r0.py`) | 3.002 | -0.285 | 1.473 | -0.227 | 16.491 | -0.036 | **DROP** | BCD improvement of 0.285 pp misses the required $\ge 1.0\text{ pp}$ threshold. Runtime: 0.073 ms/step. |
