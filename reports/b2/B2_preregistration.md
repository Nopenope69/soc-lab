# Phase B2 Pre-Registration: CALCE A123 LFP Benchmark Protocol

**Document Status:** FROZEN PENDING HUMAN APPROVAL  
**Git Commit Hash:** PENDING_COMMIT  
**Date:** October 15, 2026  
**Cell Chemistry & Specimen:** A123 1.11 Ah LFP (APR18650M1A-class), Cells `A1-007` and `A1-008`  
**Dataset Source:** CALCE Battery Research Group, University of Maryland  

---

## 1. Data Status & Sealing Declaration

> [!IMPORTANT]
> **DATA STATUS (RECORDED VERBATIM):**  
> *US06 and FUDS were read during diagnostics D3-D7 and the M=0 ablation. They are NO LONGER SEALED. They are development data. All parameter identification, tuning, variant selection and design decisions in this task must use DST only. US06 and FUDS may be used for reporting only after the pre-registration is frozen. A truly sealed test requires new data (FlexiPod or another LFP dataset) and is out of scope.*

- **Training & Design Set (Open):** Dynamic Stress Test (DST) drive cycles across temperatures. Used exclusively for parameter identification, RC parameter fitting, OCV extraction, filter tuning, and variant selection.
- **Reporting / Evaluation Set (Unsealed Development Data):** US06 and FUDS drive cycles across temperatures. May only be evaluated after this pre-registration protocol is formally frozen and approved.
- **Truly Sealed Status:** Fully out of scope without acquiring independent external cells (e.g. Oxford, McMaster, or FlexiPod).

---

## 2. Estimator List & Variant Selection Rules

### Evaluated Estimator Suite:
1. **E0 (Coulomb Counting Reference):** Pure current integration using temperature-scheduled capacity $Q(T)$ without closed-loop voltage feedback.
2. **E0 with Periodic OCV Recalibration at Rest (Rest Anchor):** Coulomb counting with rest-detection and OCV-anchor reset when $|I| < 5\text{ mA}$ for $t > 1800\text{ s}$ outside the plateau ($z < 0.20$ or $z > 0.80$).
3. **E1 (2RC Extended Kalman Filter — Key Reference):** Standard 2RC equivalent circuit model without hysteresis ($M = 0$). Serves as the primary closed-loop baseline.
4. **E2 (2RC EKF with 1-State Hysteresis):** Full 4-state EKF ($x = [z, i_1, i_2, h]^T$) with continuous hysteresis dynamics.
5. **E5 v1 (Observability-Gated EKF — Conservative):** Implements covariance inflation and innovation gating when $|d\text{OCV}/dz| < \text{threshold}$ to prevent plateau divergence.
6. **E5 v2 (Observability-Gated EKF — Adaptive):** Implements adaptive observation covariance scaling and Kalman gain capping across the plateau.
7. **E6 (RBC-DEKF — Dual EKF with Bias State):** Exploratory row only. Estimates a dynamic voltage bias state $\theta$ alongside states. (Exploratory status: not eligible to claim official benchmark pass).

### Variant Selection Rule (E5 v1 vs E5 v2):
- **Rule:** Variant selection must strictly use **DST training data only**.
- **Numerical Selection Metric:** The better variant is defined as $\text{argmin}_{v \in \{\text{v1}, \text{v2}\}} \left( \text{median}(\text{RMSE}_{\text{DST, gating}}(v)) \right)$ on baseline runs across gating temperatures (20, 25, 30, 40, 50 °C) on Cell A1-007.
- **Selection Decision from A3 Identification:**
  - `E5 v1` DST Median Full-Run RMSE: **7.92 pp** (W-mid: **8.79 pp**)
  - `E5 v2` DST Median Full-Run RMSE: **5.84 pp** (W-mid: **6.47 pp**)
  - **Selected Better Variant:** **`E5 v2`**.

---

## 3. Capacity Specification & Fault Stress Cases

- **Nominal Scheduled Capacity $Q(T)$:** All estimators and the ground-truth Coulomb counter must use the measured C/20 discharge capacity at the operating temperature:
  - 20 °C: **1.0652 Ah**
  - 25 °C: **1.0636 Ah**
  - 30 °C: **1.0730 Ah**
  - 40 °C: **1.0802 Ah**
  - 50 °C: **1.0810 Ah**
- **Capacity Mismatch Stress Case:** Injected parameter error of $\pm 3.0\%$ on estimator capacity ($\tilde{Q} = Q(T) \times (1 \pm 0.03)$) to evaluate sensitivity to capacity degradation and sizing errors.

---

## 4. Ground Truth Definition & Anchor Uncertainty

- **Start SOC Correction:**
  Because the dynamic profiles were initiated after a CV charge taper down to 55 mA ($0.055\text{ A}$), while the C/20 OCV characterization tapered to 10 mA ($0.010\text{ A}$), dynamic cycles start below nominal 100% full charge by the taper charge gap $\Delta z_{\text{taper}}(T)$ quantified in Diagnostic D8:
  $$z_{\text{start}}(T) = 1.0 - \Delta z_{\text{taper}}(T)$$
  - 20 °C: $\Delta z = 0.78\text{ pp} \implies z_{\text{start}} = 0.9922$
  - 25 °C: $\Delta z = 2.05\text{ pp} \implies z_{\text{start}} = 0.9795$ (Re-verified: 25 °C experienced a deeper 3,485 s CV taper)
  - 30 °C: $\Delta z = 0.53\text{ pp} \implies z_{\text{start}} = 0.9947$
  - 40 °C: $\Delta z = 0.21\text{ pp} \implies z_{\text{start}} = 0.9979$
  - 50 °C: $\Delta z = 0.36\text{ pp} \implies z_{\text{start}} = 0.9964$
- **Truth Uncertainty:**  
  Coulomb counting integration numerical error is negligible ($< 10^{-14}\text{ Ah}$). Sensor quantization, thermal drift, and CV taper boundary uncertainty establish an experimental truth uncertainty of **$\pm 0.8\text{ pp}$**. Differences within $\pm 0.8\text{ pp}$ are indistinguishable from truth noise.

---

## 5. Scenario Matrix & Initial Conditions

### Scenarios:
1. **Scenario (a) — Full Profile from Initial Full Charge:**  
   Dynamic profile run from $z_{\text{start}}(T)$ down to the 2.0 V cutoff.
2. **Scenario (b) — Mid-Plateau Windows with Initial Offsets:**  
   Windows starting at truth $\text{SOC} \in \{0.80, 0.60, 0.40, 0.20\}$ with initial estimator offsets of $\Delta z_0 \in \{-10\text{ pp}, -5\text{ pp}, +5\text{ pp}, +10\text{ pp}\}$.  
   **Initialization Rule:** The 2RC polarization states ($i_1, i_2$) and hysteresis state ($h$) must NOT be initialized to zero; they are extracted from the continuous truth-driven simulation run at that exact timestamp.  
   **$h$ Convention:** Continuous tracking ($h \approx -1.0$ under discharge).
3. **Scenario (c) — Truncated Plateau-Only Windows (80% down to 30% SOC):**  
   Evaluates estimator performance strictly on the unobservable plateau without assistance from knee boundaries.
4. **Scenario (d) — Unknown-Start After Extended Rest:**  
   Initial SOC inferred from 1-hour relaxed open-circuit voltage with initial state uncertainty $P_0 = (0.10)^2$.

### Fault Injections:
- **Current Bias:** $\pm 10\text{ mA}$ (0.94% of nominal capacity) and $\pm 50\text{ mA}$ (4.70% of nominal capacity).
- **OCV Table Offset:** $\pm 5\text{ mV}$ and $\pm 10\text{ mV}$.
- **Capacity Mismatch:** $\pm 3.0\%$.

---

## 6. Proposed Performance Bars (Human to Confirm)

All bars are formulated relative to reference estimators (E0 and E1) rather than unachievable absolute thresholds:

| Case / Scenario | Proposed Bar | Proposed Value | Justification from A3 Evidence |
| :--- | :--- | :---: | :--- |
| **Matched Case (a): Full Run** | Estimator RMSE within $X$ pp of E0 | **$X \le 6.0\text{ pp}$** *(PROPOSED)* | E0 has 0.1–0.9 pp RMSE. On DST under v2, E1 achieves 2.2–5.8 pp RMSE. Implied voltage noise floor allows ~6.0 pp. |
| **Matched Case (a): Full Run** | Estimator RMSE no worse than E1 by more than $Y$ | **$Y \le 2.0\text{ pp}$** *(PROPOSED)* | E1 is the 2RC closed-loop reference. E2 and E5 must remain within 2.0 pp of E1. |
| **Stress & Offset (b)–(d)** | Estimator RMSE below unanchored E0 by at least $Z\%$ | **$Z \ge 30\%$** *(PROPOSED)* | Under $\pm 50\text{ mA}$ bias or $\pm 10\text{ pp}$ offset, E0 drifts by 5–10 pp. Closed loop must beat E0 by $\ge 30\%$. |
| **E5 Parity (Rule 2)** | E5 RMSE within 0.3 pp of E2 (Two-sided) | **$\|\text{RMSE}(E5) - \text{RMSE}(E2)\| \le 0.3\text{ pp}$** in $\ge 80\%$ cases *(PROPOSED)* | True non-inferiority requires two-sided bound ($|E5 - E2| \le 0.3\text{ pp}$). |

### Mandatory Window Partitioning:
For all voltage and SOC error reporting:
- **W-mid:** Truth SOC between 10% and 90% (the active operating plateau).
- **W-low:** Truth SOC below 10% (lower knee).
- **W-high:** Truth SOC above 90% (upper knee).

---

## 7. Rules 3 & 4 Enhancements

1. **Rule 3 (Recovery on Plateau Only):** Initial offset convergence must be scored exclusively on Scenario (b) plateau windows ($z_0 \in [0.20, 0.80]$). Knee-clamping ($z > 0.90$ or $z < 0.10$) is excluded.
2. **Rule 4 (Cell Transfer & Identification Sanity Condition):**
   - Transfer Ratio: $\text{RMSE}(\text{A1-008 with A1-007 params}) / \text{RMSE}(\text{A1-008 own fit}) \le 1.5\times$.
   - **Sanity Condition:** $\text{RMSE}(\text{Own Fit}) \le \text{RMSE}(\text{Transferred Fit}) \times 1.0$. If a cell's own parameter fit produces larger error than a transferred fit from a foreign cell, the result is recorded as an **"IDENTIFICATION FAILURE"**, not a PASS.

---

## 8. Reporting Requirements

All summary tables must present:
1. Benchmark rows for both **E0** and **E1** alongside E2, E5 v1, E5 v2, and E6.
2. Training data (**DST**) results displayed side-by-side with test data (**US06, FUDS**).
3. The three-way SOC window breakdown (**W-mid, W-low, W-high**).
4. Truth uncertainty bounds ($\pm 0.8\text{ pp}$) clearly annotated.

---

## 9. Acknowledged Physical & Dataset Limits

1. **Absence of Current Reversals:** The CALCE dynamic test profiles consist of unidirectional discharge pulses with zero regenerating charge pulses during drive cycles. The minor-loop hysteresis decay parameter $\gamma$ and internal scanning curves are mathematically unobservable. Parameter $\gamma = 50.0$ is designated as **UNIDENTIFIED**.
2. **Deferred Estimators:** Estimators E3 (Unscented Kalman Filter), E4 (Particle Filter), and E7 (Neural/Hybrid Networks) are deferred to subsequent development phases.
