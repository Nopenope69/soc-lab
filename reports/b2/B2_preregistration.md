# Phase B2 Pre-Registration Protocol: CALCE A123 LFP Benchmark

**Pre-registration Status:** DRAFT PENDING HUMAN APPROVAL  
**Git Commit Hash:** `789e8d1`  
**Date & Time:** 2026-10-15 15:20 UTC  
**Cell Designation:** A123 1.11 Ah LFP (APR18650M1A-class), Cells `A1-007` and `A1-008`  
**Dataset Source:** CALCE Battery Research Group, University of Maryland  

> [!CAUTION]
> **EXPLICIT FREEZE DECLARATION:**  
> **Phase B2 evaluation has NOT been run. No results on US06 or FUDS are reported here as benchmark findings. Evaluation begins only after a human changes the status to APPROVED.**

---

## 1. Data Status & Sealing Declaration (Verbatim)

```text
US06 and FUDS were read during diagnostics D3-D7 and the M=0 ablation. They are NO LONGER SEALED.
They are development data. All parameter identification, tuning, variant selection and design decisions
in this task must use DST only. US06 and FUDS may be used for reporting only after the pre-registration
is frozen. A truly sealed test requires new data (FlexiPod or another LFP dataset) and is out of scope.
```

- **Open Development / Training Data:** Dynamic Stress Test (DST) at 20, 25, 30, 40, 50 °C. All parameter fitting (2RC resistances, time constants, OCV extraction), algorithm tuning, and variant selections are performed strictly on DST.
- **Unsealed Reporting Data:** US06 and FUDS drive cycles across temperatures. Used strictly for evaluation reporting after human protocol approval.
- **Truly Sealed Data:** Out of scope for this repository without independent cell datasets.

---

## 2. Estimator Suite & DST-Only Variant Selection

### 2.1 Complete Estimator Roster
1. **E0 (Unanchored Coulomb Counting):** Pure current integration using static nominal capacity ($1.0636\text{ Ah}$).
2. **E0 with Temperature-Scheduled Capacity ($Q(T)$):** Pure current integration using measured C/20 capacity at each operating temperature.
3. **E0 with Rest Anchor:** Coulomb counting with periodic OCV recalibration when relaxed ($|I| < 5\text{ mA}$ for $t > 1800\text{ s}$ outside the plateau).
4. **E1 (2RC EKF without Hysteresis — Key Baseline):** 3-state EKF ($x = [z, i_1, i_2]^T$) with $M = 0$. Serves as the primary closed-loop benchmark reference.
5. **E2 (2RC EKF with 1-State Hysteresis):** 4-state EKF ($x = [z, i_1, i_2, h]^T$) with continuous hysteresis dynamics.
6. **E5 v2 (Observability-Gated EKF — PRIMARY Variant):** 4-state EKF with adaptive observation covariance inflation and gain capping across the flat plateau ($|d\text{OCV}/dz| < 0.2\text{ mV/pp}$).
7. **E5 v1 (Observability-Gated EKF — REFERENCE Variant):** 4-state EKF with static innovation gating and covariance scaling.
8. **E6 (RBC-DEKF — Dual EKF with Voltage Bias State):** Exploratory row only. Jointly estimates states and a slow terminal voltage bias $\theta$. Not eligible for formal benchmark pass.

### 2.2 DST-Only Variant Selection Decision
Per Hard Rule 1, the superior E5 variant was chosen strictly from DST training performance on Cell A1-007 across gating temperatures:
- `E5 v1` DST Median Full-Run RMSE: **7.91 pp** (W-mid plateau RMSE: **8.79 pp**)
- `E5 v2` DST Median Full-Run RMSE: **5.83 pp** (W-mid plateau RMSE: **6.46 pp**)
- **Selected Primary Variant:** **`E5 v2`** (designated as primary for Rule 2 scoring). `E5 v1` is retained as a reference column.

---

## 3. Parameter Sets & Model Profiles

Three parameter configurations are pre-registered for Phase B2:

### 3.1 Baseline v2 Profile (`calce_a123_v2.yaml` / `calce_a123_a1008_v2.yaml`)
- **Residual Formulation:** Identified on DST only with hysteresis in the loop:
  $$v_{\text{model}} = v_{\text{ocv}}(z) + M(T) \cdot h(t) - R_0(T) \cdot i(t) - v_1(t) - v_2(t)$$
- **OCV Table:** Monotonized symmetric mean of C/20 charge and discharge branches ($v_{\text{ocv}} = \frac{v_{\text{dis}} + v_{\text{chg}}}{2}$).
- **Independent $R_0$ Measurement (Audit A1b):** Directly estimated from discrete 1-second current steps ($|\Delta I| \ge 1.0\text{ A}$) in DST Step 8:
  - A1-007: $[0.1578, 0.1570, 0.1531, 0.1524, 0.1525]\,\Omega$ across 20–50 °C.
  - Bounded within $\pm 30\%$ in the DST fit. Fitted $R_0$ moved only **+1.06% to +2.59%**, confirming no inflation.
- **Amended Hysteresis Amplitude $M(T)$:** C/20 plateau-median half-gap corrected for $2 \times 55\text{ mA} \times R_0$:
  - A1-007: 20 °C: **27.01 mV**, 25 °C: **17.19 mV** (*flagged suspect*), 30 °C: **24.36 mV**, 40 °C: **21.55 mV**, 50 °C: **19.88 mV**.
  - A1-008: 20 °C: **24.38 mV**, 25 °C: **15.68 mV** (*flagged suspect*), 30 °C: **21.94 mV**, 40 °C: **19.17 mV**, 50 °C: **14.56 mV**.
  - **25 °C Anomaly:** Test conducted 3 months later with 5,097 s CV hold; marked *"unexplained, treated as suspect"*. $M$ is **NOT** averaged across temperatures.
- **Hysteresis Rate $\gamma$:** Unobservable under monotonic discharge profiles; designated **`50.0 (UNIDENTIFIED)`**.

### 3.2 Reference M=0 Profile (`calce_a123_v2_m0.yaml` / `calce_a123_a1008_v2_m0.yaml`)
- Evaluates $M = 0$ with OCV taken directly from the quasi-equilibrium C/20 discharge branch ($v_{\text{ocv}} = v_{\text{dis}}$).
- Serves as the ablation reference to confirm the physical value of explicit hysteresis modeling.

### 3.3 Single-Temperature Sensitivity Check
- Gating runs evaluated using the 25 °C parameter set across all temperatures (20, 30, 40, 50 °C) to quantify thermal mismatch degradation.

---

## 4. Open-Loop Model Gate & Window Definitions

### 4.1 Mandatory SOC Window Partitioning
All voltage residuals and estimator errors must be partitioned into three disjoint windows:
1. **W-mid (Operating Plateau):** $0.10 \le \text{truth SOC} \le 0.90$.
2. **W-low (Lower Knee):** $\text{truth SOC} < 0.10$.
3. **W-high (Upper Knee):** $\text{truth SOC} > 0.90$.
4. **Full Range:** Entire run from $z_{\text{start}}$ to cutoff.

### 4.2 Proposed W-mid Gate Definition
- **Gate Criteria on DST (W-mid window only):**
  - Voltage RMSE $\le 15.0\text{ mV}$
  - Absolute Voltage Bias $|\text{bias}| \le 5.0\text{ mV}$
- **Audit A3 Status (DST Cell A1-007):**
  - All temperatures pass RMSE $\le 15.0\text{ mV}$ (7.39 to 13.39 mV).
  - Temperatures 20, 25, 30, and 50 °C fail the 5.0 mV bias bar (+8.85, +9.77, +6.46, +5.14 mV) due to global least-squares fitting of lower-knee overpotentials.
  - **Action:** W-mid gate status is recorded as **FAILED** pending human confirmation to proceed or adjust tolerance.

### 4.3 Cutoff Diagnosis Findings
- Measured DST cutoff: ~7,322 s to 7,460 s at 20–30 °C.
- Model voltage under both old and v2 parameters **never crosses 2.0 V** (minimum model voltage is 2.36 V to 2.43 V).
- **Physical Root Cause:** Root causes **(b)** [OCV table floor clamped at 2.27 V] and **(d)** [cycler reaches 2.0 V dynamic cutoff when truth SOC is still at 2.6% to 3.4%, where equilibrium OCV $> 2.50\text{ V}$].

---

## 5. Phase B2 Execution Matrix

Phase B2 executes the following test scenarios across Cells A1-007 and A1-008:

| Test ID | Scenario Name | Profile | Temperatures (°C) | Initial Condition / Fault Injection | Evaluated Estimators |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **B2-T1** | Matched Full Profile | DST, US06, FUDS | 20, 25, 30, 40, 50 | Nominal $z_{\text{start}}(T)$ from CV taper | E0, E0-sched, E1, E2, E5 v1, E5 v2, E6 |
| **B2-T2** | Mid-Plateau Windows | DST, US06, FUDS | 25, 40 | Starts at $z_0 \in \{0.8, 0.6, 0.4, 0.2\}$; $\Delta z_0 \in \{\pm 5, \pm 10\text{ pp}\}$ | E1, E2, E5 v2 |
| **B2-T3** | Truncated Plateau Window | DST, US06, FUDS | 20, 25, 30, 40, 50 | Evaluated strictly on $z \in [0.30, 0.80]$ | E1, E2, E5 v2 |
| **B2-T4** | Current Sensor Bias | US06, FUDS | 25 | $I_{\text{err}} \in \{\pm 10\text{ mA}, \pm 50\text{ mA}\}$ | E0-sched, E1, E2, E5 v2 |
| **B2-T5** | OCV Table Offset | US06, FUDS | 25 | $V_{\text{err}} \in \{\pm 5\text{ mV}, \pm 10\text{ mV}\}$ | E1, E2, E5 v2 |
| **B2-T6** | Capacity Error | US06, FUDS | 25 | $\tilde{Q} \in \{\pm 3.0\%\}$ | E0, E1, E2, E5 v2 |
| **B2-T7** | Cell-to-Cell Transfer | DST, US06, FUDS | 20, 25, 30, 40, 50 | A1-008 evaluated with A1-007 parameters | E1, E2, E5 v2 |
| **B2-T8** | Thermal Mismatch Check | DST, US06, FUDS | 20, 30, 40, 50 | 25 °C parameter profile applied cross-temperature | E2, E5 v2 |

---

## 6. Pass/Fail Decision Rules & Numerical Bars

### Rule 1: Tracking Accuracy on Operating Plateau (W-mid)
- **Primary Metric:** Operating plateau SOC RMSE (W-mid, 10% to 90% SOC).
- **Bar:** For matched runs (B2-T1), Primary Estimator `E5 v2` must achieve:
  $$\text{RMSE}_{\text{mid}} \le 6.0\text{ pp}$$
  across all gating temperatures on US06 and FUDS.

### Rule 2: Two-Sided Non-Inferiority to Baseline E2
- **Metric:** Difference between primary variant `E5 v2` and `E2`:
  $$|\text{RMSE}_{\text{mid}}(\text{E5 v2}) - \text{RMSE}_{\text{mid}}(\text{E2})| \le 1.0\text{ pp}$$
  must hold in $\ge 80\%$ of all gating runs. (Scored two-sided per Task A4).

### Rule 3: Plateau Recovery from Offset (No Knee Assistance)
- **Metric:** On Scenario B2-T2 windows starting at $z_0 \in [0.20, 0.80]$, with $\Delta z_0 = \pm 10\text{ pp}$:
  $$\text{Error at } t = 600\text{ s} \le 3.0\text{ pp}$$
  $$\text{RMSE over window} < \text{RMSE}(\text{E0-sched}) \times 0.70$$

### Rule 4: Cell Transfer & Identification Sanity Condition
- **Transfer Ratio:** $\text{RMSE}(\text{A1-008 with A1-007 params}) / \text{RMSE}(\text{A1-008 own fit}) \le 1.50\times$.
- **Sanity Gate:** $\text{RMSE}(\text{Own Fit}) \le \text{RMSE}(\text{Transferred Fit}) \times 1.00$. If a cell's own fit produces higher error than a transferred foreign fit, the run is flagged as an **IDENTIFICATION FAILURE**.

---

## 7. Execution Command

When approved by a human reviewer, Phase B2 benchmark evaluation will be executed via:

```bash
python scripts/evaluate_calce.py --profile calce_a123_v2 --output reports/b2/calce_a123_b2_verdict.md
```

---

## 8. Summary of Diagnostics & Current State

| Audit / Gate Item | Finding / Result | Status |
| :--- | :--- | :---: |
| **A0: Imports & Baseline Tests** | Fixed `Any` import in `registry.py`. Full test suite: 125 passed in 345s. | **PASSED** |
| **A1b: Independent $R_0$** | Step-based $R_0 = 0.155\text{--}0.158\,\Omega$ (matches baseline within 1–2%). | **PASSED** |
| **A1: Hysteresis Gap Audit** | Amended $M(T) \approx 17\text{--}27\text{ mV}$. 25 °C anomaly flagged as suspect. | **PASSED** |
| **A2: Parameter Identification** | Re-identified with $h$ in residual. Fitted $R_0$ moved $< 2.6\%$ from independent $R_0$. | **PASSED** |
| **A3: Open-Loop Voltage Gate** | W-mid RMSE passes ($\le 13.4\text{ mV}$); W-mid bias fails ($+5\text{ to }+9.8\text{ mV}$). | **FAILED (Reported)** |
| **A3: Cutoff Diagnosis** | Resolved: Causes (b) & (d). Cycler reaches 2.0 V at 2.6–3.4% SOC where OCV $> 2.5\text{ V}$. | **CONFIRMED** |
| **A4: Housekeeping & Tests** | None/NA in CSV, $t_{12}$ mismatch bar enforced, 18650 designation corrected. | **PASSED** |
| **B: Pre-Registration Freeze** | Document frozen pending human approval. Zero US06/FUDS evaluations executed. | **STOPPED** |
