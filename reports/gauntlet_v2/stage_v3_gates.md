# Stage V3 Gate Evaluation Report (E7v2 Composite)

**Estimator:** `E7v2` (`E7V2CompositeFilter`)  
**Tuned Parameter Set:** `cand_sl_0.3`  
**R3 Guarantee:** `truth_soc = start_soc - (np.cumsum(unmodified_current * dt) / (3600.0 * q_c20))`  

---

## 1. Tuned Parameters (DST 20 °C & 30 °C Selection)
- `process_noise_q_soc`: `2.9031433196504225e-08`
- `process_noise_q_rc`: `1.1198164932559382e-05`
- `process_noise_q_hysteresis`: `0.00017150882346504795`
- `measurement_noise_r_v`: `0.0008610323423725228`
- `e4_rls_forgetting_factor`: `0.999`
- `e5_slope_ref`: `0.3`
- `e5_cap_plateau`: `1e-05`
- `e5_cap_knee`: `0.01`
- `e5_sigma_ocv_model_v`: `0.02`

Tuning Objective (Mean SBC 20 °C & 30 °C): `2.6988 pp`  
Held-out Score (Mean 40 °C & 50 °C on A1-007 and Set X): `2.8534 pp`  
Total configurations tested in Stage V3: `23` (Budget limit: 100).

---

## 2. GATE A Evaluation (Cell A1-007)
*Evaluated on held-out decision temperatures: 40 °C and 50 °C (20 °C, 30 °C, and 25 °C reported).*

| Temperature | S-A E7v2 (pp) | S-A E0 (pp) | S-A E1 (pp) | Clause (i) Pass? | S-B E7v2 Mean (pp) | S-B E0 Mean (pp) | S-B 70% Limit | S-B Win Rate vs E0 | Clause (ii-a) Pass? | S-C Worst Error (pp) | Clause (ii-b) Pass? | S-F Worst Case (pp) | S-F E0 Worst | Clause (iii) Pass? |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **20 °C** (tune) | 1.827 | 0.021 | 5.816 | - | 3.099 | 7.290 | 5.103 | - | - | 1.862 | - | 6.005 | 9.505 | - |
| **25 °C** (suspect) | 0.818 | 0.021 | 3.268 | - | 2.453 | 7.209 | 5.046 | - | - | 3.758 | - | 3.960 | 9.605 | - |
| **30 °C** (tune) | 1.628 | 0.021 | 8.063 | - | 2.776 | 7.280 | 5.096 | - | - | 2.168 | - | 6.353 | 9.614 | - |
| **40 °C** (held-out) | 1.331 | 0.021 | 7.794 | **PASS** | 2.376 | 7.313 | 5.119 | - | - | 2.643 | **FAIL** | 5.489 | 9.560 | **PASS** |
| **50 °C** (held-out) | 1.145 | 0.021 | 5.769 | **PASS** | 2.572 | 7.345 | 5.142 | - | - | 3.509 | **FAIL** | 4.875 | 9.573 | **PASS** |

**Combined S-B Win Rate on Held-out (40 & 50 °C):** `32/32 (100.0%)` (Requirement: >= 26/32 = 80%)  
**GATE A Status:** **FAIL**

---

## 3. GATE B Evaluation (Cross-Cell Set X / A1-008)
*Evaluated across all decision temperatures: 20 °C, 30 °C, 40 °C, 50 °C.*

| Temperature | S-A E7v2 (pp) | S-A E0 (pp) | Limit (E0 + 3.0) | Clause (i) Pass? | S-B E7v2 Mean (pp) | S-B E0 Mean (pp) | Clause (ii) Pass? | S-C E7v2 Mean (pp) | S-C E0 Mean (pp) | Limit (E0 + 3.0) | Clause (iii) Pass? |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **20 °C** | 1.525 | 0.021 | 3.021 | **PASS** | 3.234 | 7.325 | **PASS** | 1.698 | 0.035 | 3.035 | **PASS** |
| **25 °C** (suspect) | 1.317 | 0.021 | 3.021 | - | 3.537 | 7.258 | - | 3.656 | 0.060 | 3.060 | - |
| **30 °C** | 1.352 | 0.021 | 3.021 | **PASS** | 3.102 | 7.371 | **PASS** | 2.002 | 0.034 | 3.034 | **PASS** |
| **40 °C** | 1.187 | 0.021 | 3.021 | **PASS** | 2.544 | 7.263 | **PASS** | 1.916 | 0.026 | 3.026 | **PASS** |
| **50 °C** | 1.278 | 0.021 | 3.021 | **PASS** | 3.977 | 7.254 | **PASS** | 3.799 | 0.026 | 3.026 | **FAIL** |

**GATE B Status:** **FAIL**

---

## 4. Overall Stage V3 Gate Conclusion
- **GATE A Verdict:** **FAIL**
- **GATE B Verdict:** **FAIL**
- **Composite Ready for Stage V4 Freeze:** **NO**
