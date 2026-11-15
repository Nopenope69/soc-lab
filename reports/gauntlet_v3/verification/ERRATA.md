# Verification Errata: Per-Profile E0 Baselines and Gate Confirmation

## 1. Context and Purpose

In `reports/gauntlet_v3/verification/VERIFICATION.md`, the summary comparison tables for the unsealed dynamic profiles (**US06** and **FUDS**) previously listed the **DST** baseline E0 values ($0.021\text{ pp}$ for S-A, $7.290\text{ pp}$ for S-B, $0.048\text{ pp}$ for S-C, $3.979\text{ pp}$ for S-G, and $1.633\text{ pp}$ for S-F) as placeholder columns across all profiles.

This errata document extracts the exact, profile-specific E0 fair baselines recorded directly in the frozen unseal artifact `reports/gauntlet_v3/stage_v5_unseal.json`, recalculates the pre-registered gate pass bars, and confirms that **100% of all gate verdicts remain PASS**.

---

## 2. Profile-Specific E0 Baselines and Verified Pass Bars

### 2.1 US06 Profile — Primary Performance (Cell A1-007)

| Temp (°C) | Clause | Specific E0 Baseline | E7v3 Metric | Pre-Registered Bar Formula | Recomputed Pass Bar | Verdict |
|:---:|:---|:---:|:---:|:---|:---:|:---:|
| 20 | (i) S-A RMSE | **0.013 pp** | 1.322 pp | $\le \text{E0} + 2.0\text{ pp}$ | $\le 2.013\text{ pp}$ | **PASS** |
| 30 | (i) S-A RMSE | **0.013 pp** | 1.156 pp | $\le \text{E0} + 2.0\text{ pp}$ | $\le 2.013\text{ pp}$ | **PASS** |
| 40 | (i) S-A RMSE | **0.014 pp** | 1.443 pp | $\le \text{E0} + 2.0\text{ pp}$ | $\le 2.014\text{ pp}$ | **PASS** |
| 50 | (i) S-A RMSE | **0.014 pp** | 1.128 pp | $\le \text{E0} + 2.0\text{ pp}$ | $\le 2.014\text{ pp}$ | **PASS** |
| 20 | (ii-a) S-B Group-Mean | **7.375 pp** | 3.291 pp | $\le 0.70 \times \text{E0}$ | $\le 5.162\text{ pp}$ | **PASS** |
| 30 | (ii-a) S-B Group-Mean | **7.347 pp** | 3.053 pp | $\le 0.70 \times \text{E0}$ | $\le 5.143\text{ pp}$ | **PASS** |
| 40 | (ii-a) S-B Group-Mean | **7.318 pp** | 2.829 pp | $\le 0.70 \times \text{E0}$ | $\le 5.123\text{ pp}$ | **PASS** |
| 50 | (ii-a) S-B Group-Mean | **7.287 pp** | 2.702 pp | $\le 0.70 \times \text{E0}$ | $\le 5.101\text{ pp}$ | **PASS** |
| 20 | (ii-b) S-C Mean | **0.039 pp** | 0.897 pp | $\le \text{E0} + 1.5\text{ pp}$ | $\le 1.539\text{ pp}$ | **PASS** |
| 30 | (ii-b) S-C Mean | **0.026 pp** | 0.871 pp | $\le \text{E0} + 1.5\text{ pp}$ | $\le 1.526\text{ pp}$ | **PASS** |
| 40 | (ii-b) S-C Mean | **0.043 pp** | 0.821 pp | $\le \text{E0} + 1.5\text{ pp}$ | $\le 1.543\text{ pp}$ | **PASS** |
| 50 | (ii-b) S-C Mean | **0.048 pp** | 0.858 pp | $\le \text{E0} + 1.5\text{ pp}$ | $\le 1.548\text{ pp}$ | **PASS** |
| 20 | (ii-c) S-G Mean | **3.996 pp** | 3.090 pp | $\le \text{E0} + 1.0\text{ pp}$ | $\le 4.996\text{ pp}$ | **PASS** |
| 30 | (ii-c) S-G Mean | **3.988 pp** | 2.740 pp | $\le \text{E0} + 1.0\text{ pp}$ | $\le 4.988\text{ pp}$ | **PASS** |
| 40 | (ii-c) S-G Mean | **3.982 pp** | 2.683 pp | $\le \text{E0} + 1.0\text{ pp}$ | $\le 4.982\text{ pp}$ | **PASS** |
| 50 | (ii-c) S-G Mean | **3.972 pp** | 2.541 pp | $\le \text{E0} + 1.0\text{ pp}$ | $\le 4.972\text{ pp}$ | **PASS** |
| 20 | (iii) S-F Mean | **1.568 pp** | 1.827 pp | $\le \text{E0} + 5.0\text{ pp}$ | $\le 6.568\text{ pp}$ | **PASS** |
| 30 | (iii) S-F Mean | **1.577 pp** | 1.627 pp | $\le \text{E0} + 5.0\text{ pp}$ | $\le 6.577\text{ pp}$ | **PASS** |
| 40 | (iii) S-F Mean | **1.590 pp** | 1.812 pp | $\le \text{E0} + 5.0\text{ pp}$ | $\le 6.590\text{ pp}$ | **PASS** |
| 50 | (iii) S-F Mean | **1.590 pp** | 1.593 pp | $\le \text{E0} + 5.0\text{ pp}$ | $\le 6.590\text{ pp}$ | **PASS** |

---

### 2.2 FUDS Profile — Primary Performance (Cell A1-007)

| Temp (°C) | Clause | Specific E0 Baseline | E7v3 Metric | Pre-Registered Bar Formula | Recomputed Pass Bar | Verdict |
|:---:|:---|:---:|:---:|:---|:---:|:---:|
| 20 | (i) S-A RMSE | **0.025 pp** | 1.404 pp | $\le \text{E0} + 2.0\text{ pp}$ | $\le 2.025\text{ pp}$ | **PASS** |
| 30 | (i) S-A RMSE | **0.026 pp** | 1.413 pp | $\le \text{E0} + 2.0\text{ pp}$ | $\le 2.026\text{ pp}$ | **PASS** |
| 40 | (i) S-A RMSE | **0.026 pp** | 1.572 pp | $\le \text{E0} + 2.0\text{ pp}$ | $\le 2.026\text{ pp}$ | **PASS** |
| 50 | (i) S-A RMSE | **0.026 pp** | 1.346 pp | $\le \text{E0} + 2.0\text{ pp}$ | $\le 2.026\text{ pp}$ | **PASS** |
| 20 | (ii-a) S-B Group-Mean | **7.393 pp** | 2.916 pp | $\le 0.70 \times \text{E0}$ | $\le 5.175\text{ pp}$ | **PASS** |
| 30 | (ii-a) S-B Group-Mean | **7.338 pp** | 2.940 pp | $\le 0.70 \times \text{E0}$ | $\le 5.136\text{ pp}$ | **PASS** |
| 40 | (ii-a) S-B Group-Mean | **7.280 pp** | 2.718 pp | $\le 0.70 \times \text{E0}$ | $\le 5.096\text{ pp}$ | **PASS** |
| 50 | (ii-a) S-B Group-Mean | **7.269 pp** | 2.652 pp | $\le 0.70 \times \text{E0}$ | $\le 5.088\text{ pp}$ | **PASS** |
| 20 | (ii-b) S-C Mean | **0.042 pp** | 0.562 pp | $\le \text{E0} + 1.5\text{ pp}$ | $\le 1.542\text{ pp}$ | **PASS** |
| 30 | (ii-b) S-C Mean | **0.044 pp** | 0.627 pp | $\le \text{E0} + 1.5\text{ pp}$ | $\le 1.544\text{ pp}$ | **PASS** |
| 40 | (ii-b) S-C Mean | **0.067 pp** | 0.586 pp | $\le \text{E0} + 1.5\text{ pp}$ | $\le 1.567\text{ pp}$ | **PASS** |
| 50 | (ii-b) S-C Mean | **0.055 pp** | 0.631 pp | $\le \text{E0} + 1.5\text{ pp}$ | $\le 1.555\text{ pp}$ | **PASS** |
| 20 | (ii-c) S-G Mean | **3.991 pp** | 3.148 pp | $\le \text{E0} + 1.0\text{ pp}$ | $\le 4.991\text{ pp}$ | **PASS** |
| 30 | (ii-c) S-G Mean | **3.985 pp** | 2.878 pp | $\le \text{E0} + 1.0\text{ pp}$ | $\le 4.985\text{ pp}$ | **PASS** |
| 40 | (ii-c) S-G Mean | **3.971 pp** | 2.705 pp | $\le \text{E0} + 1.0\text{ pp}$ | $\le 4.971\text{ pp}$ | **PASS** |
| 50 | (ii-c) S-G Mean | **3.970 pp** | 2.703 pp | $\le \text{E0} + 1.0\text{ pp}$ | $\le 4.970\text{ pp}$ | **PASS** |
| 20 | (iii) S-F Mean | **1.644 pp** | 1.923 pp | $\le \text{E0} + 5.0\text{ pp}$ | $\le 6.644\text{ pp}$ | **PASS** |
| 30 | (iii) S-F Mean | **1.656 pp** | 1.840 pp | $\le \text{E0} + 5.0\text{ pp}$ | $\le 6.656\text{ pp}$ | **PASS** |
| 40 | (iii) S-F Mean | **1.663 pp** | 1.937 pp | $\le \text{E0} + 5.0\text{ pp}$ | $\le 6.663\text{ pp}$ | **PASS** |
| 50 | (iii) S-F Mean | **1.667 pp** | 1.775 pp | $\le \text{E0} + 5.0\text{ pp}$ | $\le 6.667\text{ pp}$ | **PASS** |

---

### 2.3 Cross-Cell Transfer (Cell A1-008)

Across both US06 and FUDS profiles on uncalibrated transfer Cell A1-008, all clauses also pass:
- **US06**: S-A RMSEs are $1.80\text{ to }2.01\text{ pp}$ (against pass bars $\le 3.64\text{ to }3.83\text{ pp}$, PASS); S-B group means are $2.98\text{ to }3.73\text{ pp}$ (against bars $\le 7.27\text{ to }7.33\text{ pp}$, PASS).
- **FUDS**: S-A RMSEs are $1.93\text{ to }2.13\text{ pp}$ (against pass bars $\le 3.66\text{ to }3.85\text{ pp}$, PASS); S-B group means are $3.37\text{ to }4.35\text{ pp}$ (against bars $\le 7.19\text{ to }7.28\text{ pp}$, PASS).

## 3. Final Conclusion

Substituting the exact profile-specific E0 baselines confirms that every single pre-registered clause is passed with substantial margin. The overall **GO** validation verdict is fully confirmed and mathematically verified.
