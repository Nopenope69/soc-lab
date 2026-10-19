# Stage V2: Component D4 (Adaptive Covariance Fading) Ablation

**Date**: 2026-10-19 19:18:37  
**Dataset**: CALCE A123 DST (A1-007, Set X / A1-008)  
**Stage Decision**: **DROP**  

---

## 1. Keep Rule Criteria

Per Gauntlet V3 Protocol (applied to composite SBC across S-B, S-C, S-G):
- **Tuning SBC Improvement**: $\ge 3.0\%$ improvement on A1-007 tuning temperatures (20, 30 °C).
- **Held-Out SBC Degradation**: $\le 1.0\%$ degradation allowed on held-out temperatures (40, 50 °C) on A1-007 and Set X.
- **S-A Degradation**: $0.0\%$ degradation allowed on S-A held-out RMSE.
- **Action on Failure**: If no candidate satisfies the Keep Rule across $\le 3$ rounds, DROP D4. Estimator continues as clean E7v3.

---

## 2. Baseline vs D4 Candidates Evaluation Table

| Candidate / Round | Tuning SBC (pp) | Tuning Gain (%) | A1-007 Held SBC (pp) | Set X Held SBC (pp) | A1-007 Held SA (pp) | Set X Held SA (pp) | Verdict |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **E7v3 Baseline** | 2.7288 | -- | 2.4905 | 3.6944 | 2.3487 | 3.6903 | **BASELINE** |
| **Round 1 (D4_R1_default)** | 2.7288 | +0.00% | 2.4905 (+0.00%) | 3.6784 (-0.43%) | 2.3487 (+0.0000) | 3.6903 (+0.0000) | **DROP** |
| **Round 2 (D4_R2_fast)** | 2.7288 | +0.00% | 2.4905 (+0.00%) | 4.3486 (+17.71%) | 2.3487 (+0.0000) | 4.1885 (+0.4983) | **DROP** |
| **Round 3 (D4_R3_direct_max)** | 2.7288 | +0.00% | 2.4905 (+0.00%) | 3.6449 (-1.34%) | 2.3487 (+0.0000) | 3.6903 (+0.0000) | **DROP** |

---

## 3. Detailed Round Analysis

### Round 1: D4_R1_default
- **Configuration**: `k=3.0, N=60s, lambda_f=1.05/step, P_max=(10pp)^2, mode=step_factor`
- **Tuning SBC Gain**: `+0.00%` (Gate requirement: $\ge +3.0\%$) -> **FAIL**
- **A1-007 Held-Out SBC Delta**: `+0.00%` (Gate limit: $\le +1.0\%$) -> **PASS**
- **Set X Held-Out SBC Delta**: `-0.43%` (Gate limit: $\le +1.0\%$) -> **PASS**
- **Held-Out S-A Delta**: 007 = `+0.0000 pp`, Set X = `+0.0000 pp` (Gate limit: $\le 0.0\text{ pp}$) -> **PASS**
- **Decision**: **DROP**

### Round 2: D4_R2_fast
- **Configuration**: `k=2.0, N=30s, lambda_f=1.10/step, P_max=(10pp)^2, mode=step_factor`
- **Tuning SBC Gain**: `+0.00%` (Gate requirement: $\ge +3.0\%$) -> **FAIL**
- **A1-007 Held-Out SBC Delta**: `+0.00%` (Gate limit: $\le +1.0\%$) -> **PASS**
- **Set X Held-Out SBC Delta**: `+17.71%` (Gate limit: $\le +1.0\%$) -> **FAIL**
- **Held-Out S-A Delta**: 007 = `+0.0000 pp`, Set X = `+0.4983 pp` (Gate limit: $\le 0.0\text{ pp}$) -> **FAIL**
- **Decision**: **DROP**

### Round 3: D4_R3_direct_max
- **Configuration**: `k=3.0, N=60s, direct inflation P->min(P_max, (5pp)^2), mode=direct_max`
- **Tuning SBC Gain**: `+0.00%` (Gate requirement: $\ge +3.0\%$) -> **FAIL**
- **A1-007 Held-Out SBC Delta**: `+0.00%` (Gate limit: $\le +1.0\%$) -> **PASS**
- **Set X Held-Out SBC Delta**: `-1.34%` (Gate limit: $\le +1.0\%$) -> **PASS**
- **Held-Out S-A Delta**: 007 = `+0.0000 pp`, Set X = `+0.0000 pp` (Gate limit: $\le 0.0\text{ pp}$) -> **PASS**
- **Decision**: **DROP**

---

## 4. Stage V2 Conclusion

Component D4 is **DROPPED**. Neither candidate achieved the required $\ge 3.0\%$ gain without violating held-out degradation constraints. Estimator E7v3 carries forward into Stage V3 in its pure form (confidence-aware reset + scheduled $Q(T)/M(T)$ + RLS adaptation + observability gating).
