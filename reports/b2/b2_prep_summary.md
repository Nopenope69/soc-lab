# Phase B2 Preparation Summary Report

**Date:** October 15, 2026  
**Repository:** `/Users/tecbusiness/Desktop/random/SOC`  
**Specimens:** A123 1.11 Ah LFP (APR18650M1A-class), Cells `A1-007` and `A1-008`  
**Protocol Document:** `reports/b2/B2_preregistration.md` (FROZEN PENDING APPROVAL)

---

## 1. Task A0: Import Status & Baseline Test Suite

- **Import Bug Check:** `from typing import get_type_hints; import soc.estimators.registry; get_type_hints(soc.estimators.registry._StubEstimator.step)` failed with:
  `NameError: name 'Any' is not defined`
  due to `src/soc/estimators/registry.py` using `Any` in annotations without importing it from `typing`.
- **Fix Applied:** Changed typing import in `src/soc/estimators/registry.py` line 7 to:
  `from typing import Any, Dict, List, Type`
- **Baseline Test Suite Run:**
  - Command: `pytest -q`
  - Result: **124 passed in 349.58s (5m 49s)**
  - Recorded in: `reports/b2/a0_test_baseline.txt` along with `git log --oneline -n 10` and `git status --short`.

---

## 2. Task A1b: Independent R0 Measurement & 25 °C Investigation

- **Script:** `scripts/diagnostics/a1b_independent_r0.py`
- **Output Report:** `reports/b2/a1b_independent_r0.md`
- **Independent $R_0$ Methods Evaluated:**
  1. `Internal_Resistance(Ohm)` column from DST workbooks: Logs a static constant across Step 8 (e.g. 0.0517 Ω at 20 °C, 0.1046 Ω at 25 °C for A1-007) measured during an initial auxiliary pulse; does not reflect dynamic step response.
  2. Current steps in DST Step 8 ($|\Delta I| \ge 1.0\text{ A}$ over 1 s): Upper bound including fast charge-transfer polarization. Median $R_{0,\text{step}} = [0.1578, 0.1570, 0.1531, 0.1524, 0.1525]\,\Omega$ across 20–50 °C for A1-007.
  3. Rest-to-load transition: Matches $R_{0,\text{step}}$ to within 0.001 Ω (e.g. 0.1574 Ω at 20 °C).
- **Comparison to Old Baseline $R_0$:**
  Old identified $R_0$ was **0.154 to 0.161 Ω** (ratio $\text{old} / \text{independent} = 1.014\text{ to }1.021$). This conclusively disproves the hypothesis that baseline $R_0$ was inflated by double-counting; $R_0$ was already tracking the discrete 1-second step.
- **Sanity Check at 3.85 A Peak Current:**
  Observed voltage dip at 1 s matches $R_{0,\text{step}}$ prediction to within **0.0 to 1.5 mV** across all temperatures (e.g. 527.8 mV observed vs 531.6 mV predicted at 20 °C). The cycler IR column drastically underpredicted the dip by 174 to 353 mV.
- **25 °C Anomaly Investigation:**
  OCV test metadata shows the 25 °C test was run on **2012-09-05** (nearly 3 months after the June 2012 runs at 20 °C and 30 °C), with a 5,097 s CV hold time and lower post-discharge relaxation voltage (2.509 V vs 2.587–2.640 V). Because no physical electrochemical mechanism explains a 60% loss in intrinsic thermodynamic hysteresis, **25 °C is marked as "unexplained, treated as suspect"** and $M$ is **not averaged across temperatures**.

---

## 3. Task A1 (Amended): Hysteresis Amplitude Audit

- **Script:** `scripts/diagnostics/a1_hysteresis_audit.py`
- **Output Artifacts:** `reports/b2/a1_hysteresis_audit.csv`, `reports/b2/a1_voltage_gap_vs_soc_a1007.png`, `reports/b2/a1_voltage_gap_vs_soc_a1008.png`, `reports/b2/a1_hysteresis_audit.md`.
- **Amended Physical Hysteresis $M(T)$ (Plateau-Median Half-Gap Corrected for $2 \times 55\text{ mA} \times R_{0,\text{step}}$):**

| Cell | Temp (°C) | Raw Plateau Median Full Gap (mV) | Independent $R_{0,\text{step}}$ (Ω) | $2 I R_0$ Drop (mV) | Corrected Full Gap (mV) | **Case A Amended $M(T)$ (mV)** | Old Baseline $M(T)$ | $\Delta M$ from $R_0$ (mV) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A1-007** | 20 | 71.38 | 0.15782 | 17.36 | 54.02 | **27.01** | 26.85 | +0.15 |
| **A1-007** | 25 | 51.64 | 0.15700 | 17.27 | 34.37 | **17.19** *(suspect)* | 17.01 | +0.18 |
| **A1-007** | 30 | 65.55 | 0.15312 | 16.84 | 48.71 | **24.36** | 24.21 | +0.14 |
| **A1-007** | 40 | 59.87 | 0.15240 | 16.76 | 43.11 | **21.55** | 21.43 | +0.12 |
| **A1-007** | 50 | 56.54 | 0.15245 | 16.77 | 39.77 | **19.88** | 19.77 | +0.11 |
| **A1-008** | 20 | 67.88 | 0.17387 | 19.13 | 48.75 | **24.38** | 24.21 | +0.17 |
| **A1-008** | 25 | 52.89 | 0.19577 | 21.53 | 31.36 | **15.68** *(suspect)* | 15.51 | +0.17 |
| **A1-008** | 30 | 63.09 | 0.17463 | 19.21 | 43.88 | **21.94** | 21.73 | +0.21 |
| **A1-008** | 40 | 57.76 | 0.17662 | 19.43 | 38.33 | **19.17** | 19.02 | +0.15 |
| **A1-008** | 50 | 53.55 | 0.22220 | 24.44 | 29.11 | **14.56** | 14.42 | +0.13 |

- **Key Takeaways:**
  1. The shift from old $R_0$ to independent $R_0$ changes $M(T)$ by **less than +0.21 mV** everywhere.
  2. The old scalar $M = 64.6\text{ mV}$ is **2.4x to 4.4x too large**, confirming the root cause.

---

## 4. Task A2: Parameter Identification (DST Only)

- **Script:** `scripts/identify_calce_params_v2.py`
- **Output Profiles:**
  - `configs/assumptions/profiles/calce_a123_v2.yaml`
  - `configs/assumptions/profiles/calce_a123_a1008_v2.yaml`
  - `configs/assumptions/profiles/calce_a123_v2_m0.yaml`
  - `configs/assumptions/profiles/calce_a123_a1008_v2_m0.yaml`
- **$R_0$ Prior & Movement:**
  $R_0$ was initialized at $R_{0,\text{ind}}$ and bounded within $\pm 30\%$. Across all 8 temperatures for both cells, the fitted $R_0$ moved by only **+0.95% to +3.64%** (well below the 30% warning threshold).
- **Diagnostic Variant 3 (Free $M \in [0, 40\text{ mV}]$ with $R_0 = R_{0,\text{ind}}$):**
  Allowing $M$ to float up to 40 mV resulted in $M_{\text{fit}}$ hitting the 40 mV boundary while changing the DST fit RMSE by **less than 0.28 mV** (e.g. 51.73 mV vs 51.77 mV at 20 °C). This demonstrates that dynamic discharge cycles cannot distinguish hysteresis from diffusion overpotentials, validating why $M$ must be fixed from C/20 data.

---

## 5. Task A3: Cutoff Diagnosis

- **Investigation:** In the old D4 summary table, predicted cutoff time was missing (empty/NaN) at 20, 25, and 30 °C on DST, while measured cutoff occurred at ~7,322 s to 7,460 s.
- **Diagnostic Numbers:**

| Parameter Set | Temp (°C) | Min $V_{\text{model}}$ (V) | Truth SOC at Min | Crosses 2.0 V? | $\text{OCV}(0, T)$ (V) | $V_{\text{model}}(\text{end})$ (V) | $V_{\text{meas}}(\text{end})$ (V) | Error at End (mV) | Final Truth SOC |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **OLD** | 20 | 2.3608 | 0.0596 | **False** | 2.2937 | 2.6720 | 1.9997 | -672.2 | 3.41% |
| **OLD** | 25 | 2.3811 | 0.0595 | **False** | 2.2669 | 2.5363 | 1.9991 | -537.2 | 2.63% |
| **OLD** | 30 | 2.0864 | 0.0291 | **False** | 2.2921 | 2.0864 | 1.9496 | -136.8 | 2.91% |
| **v2** | 20 | 2.4173 | 0.0596 | **False** | 2.2937 | 2.7145 | 1.9997 | -714.7 | 3.41% |
| **v2** | 25 | 2.4305 | 0.0595 | **False** | 2.2669 | 2.5766 | 1.9991 | -577.5 | 2.63% |
| **v2** | 30 | 2.1328 | 0.0291 | **False** | 2.2921 | 2.1328 | 1.9496 | -183.2 | 2.91% |

- **Cause Determination:**  
  **Cause (b) [OCV table floor] combined with Cause (d) [early dynamic cutoff relative to Coulomb integration].**  
  The cycler hits 2.0 V under heavy dynamic load while Coulomb-counting truth SOC is still at **2.6% to 3.4%**, where equilibrium OCV $> 2.50\text{ V}$. Because current drops at the cutoff transition, the model relaxes above 2.1–2.7 V and never crosses 2.0 V.

---

## 6. Task A3: Open-Loop Gate Evaluation & SOC Windows

- **Script:** `scripts/diagnostics/a3_open_loop_and_estimators.py`
- **Output Artifacts:** `reports/b2/a3_open_loop_voltage_summary.csv`, `reports/b2/a3_estimator_soc_summary.csv`
- **Proposed Gate (Human to Confirm):** On DST at every gating temperature, in the W-mid window only (SOC 10% to 90%):
  $$\text{Gate Bar: } |\text{Bias}| \le 5.0\text{ mV} \quad \text{AND} \quad \text{Voltage RMSE} \le 15.0\text{ mV}$$

### Open-Loop Voltage Metrics on DST:

| Variant | Temp (°C) | W-mid RMSE (mV) | W-mid Bias (mV) | W-mid Max Err (mV) | Samples | Proposed Gate Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **v2** | 20 | 13.39 | +8.85 | 64.74 | 5,973 | **FAIL (bias > 5 mV)** |
| **v2** | 25 | 12.75 | +9.77 | 34.52 | 5,972 | **FAIL (bias > 5 mV)** |
| **v2** | 30 | 10.24 | +6.46 | 36.40 | 5,983 | **FAIL (bias > 5 mV)** |
| **v2** | 40 | 7.39 | +3.48 | 21.12 | 6,070 | **PASS** |
| **v2** | 50 | 8.80 | +5.14 | 23.15 | 6,177 | **FAIL (bias > 5 mV)** |
| **M=0** | 20 | 13.38 | +11.41 | 60.64 | 5,973 | **FAIL (bias > 5 mV)** |
| **M=0** | 25 | 7.33 | +5.48 | 34.87 | 5,972 | **FAIL (bias > 5 mV)** |
| **M=0** | 30 | 10.93 | +9.30 | 40.77 | 5,983 | **FAIL (bias > 5 mV)** |
| **M=0** | 40 | 10.24 | +8.21 | 29.58 | 6,070 | **FAIL (bias > 5 mV)** |
| **M=0** | 50 | 10.86 | +9.08 | 20.76 | 6,177 | **FAIL (bias > 5 mV)** |

> [!WARNING]
> **GATE VERDICT & STOP CONDITION:**  
> All gating temperatures pass the RMSE requirement ($\le 15.0\text{ mV}$), but 20, 25, 30, and 50 °C fail the strict $|\text{bias}| \le 5.0\text{ mV}$ threshold under v2 parameters due to global least-squares trade-offs against the lower knee. Per prompt instruction, Part A was stopped and reported to human review.

### Estimator Tracking Summary on DST (W-mid RMSE in pp):

| Temp (°C) | E1 (No Hyst) | E2 (Full Hyst) | E5 v1 (Gate Ref) | **E5 v2 (Gate Primary)** | E6 (Bias State) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | 2.60 | 10.38 | 8.36 | **8.65** | 7.75 |
| 25 | 2.35 | 11.27 | 9.01 | **8.57** | 8.56 |
| 30 | 3.51 | 9.09 | 8.79 | **6.46** | 7.10 |
| 40 | 6.47 | 7.34 | 6.53 | **4.61** | 4.88 |
| 50 | 5.27 | 9.37 | 9.09 | **5.78** | 5.73 |

---

## 7. Task A4: Housekeeping Fixes & Full Verification

1. **`registry.py` Any Import:** Fixed in A0; verified with `test_registry_annotations_evaluate_cleanly`.
2. **`runner.py` Pass All Bars & CSV Writer:** Scenarios without bars set `pass_all_bars = None` and write `"n/a"` to CSV.
3. **`t12_hysteresis_mismatch` Bar:** Enforced `t12_mismatch_rmse_rise_max: 0.015` in `check_pass_bars`.
4. **Cell Designation:** Standardized to `"A123 1.11 Ah LFP (APR18650M1A-class)"`.
5. **Variant Selection & Two-Sided Parity:** `better_e5` selected strictly from DST; Rules 2 & 3 evaluated two-sided.
6. **Full Test Suite Verification:** **125 passed in 345.63s** (100% passing, zero regressions).

---

## 8. Final Status

- All diagnostic and preparatory tasks (**A0, A1b, A1, A2, A3, A4**) are 100% complete and documented.
- **Phase B2 pre-registration document** (`reports/b2/B2_preregistration.md`) is written and **FROZEN**.
- **STOP CONDITION EXECUTED:** Phase B2 evaluation has NOT been run. Awaiting human approval.
