# TEMPEST 280 Ah Prismatic LFP Cell Characterisation Specification (Frozen)

**Date:** 2026-11-19  
**Specification Status:** **FROZEN PRIOR TO EVALUATION**  
**Dataset:** TEMPEST project 280 Ah LFP prismatic cell dataset (`tempest_zenodo`, Zenodo [19632939](https://zenodo.org/records/19632939))  
**DOI:** UNVERIFIED  
**Licence:** UNVERIFIED  
**Subject Cell:** Single commercial 280 Ah LFP prismatic cell ("LIC")  
**Scope:** Characterisation only (capacity vs temperature, 2RC equivalent circuit identification from HPPC, open-loop voltage simulation gates). Zero aging or SOH degradation data.

---

## 1. Study Boundaries & Governance Classification

1. **Single Cell Limitation:** This dataset evaluates exactly **one physical cell** under laboratory chamber characterisation conditions (15 °C, 20 °C, 25 °C, 30 °C, and 35 °C).
2. **No Sealed Test Set:** Because all data originate from a single physical specimen, there is no sealed-cell split.
3. **No SOH Evidence:** All files are beginning-of-life characterisation tests. No cycling degradation or calendar aging data exist in this dataset.
4. **Governance Rule & Classification:**
   Under the 5-point governance rule:
   - (a) Real files with verified manifest hashes: **PASS** (`data/manifests/tempest_zenodo.sha256`).
   - (b) Every evaluation script tracked and reproduced from a clean shell: **PASS**.
   - (c) Spec committed before evaluation: **PASS** (this document).
   - (d) Held-out result that beats a fair baseline on an independent reference: To be evaluated under LOTO and alternate-SOC schemes.
   - (e) Enough data to support the claim, counted in independent units (cells, not repeated rows): **FAIL**. One cell cannot satisfy sample size requirements.
   Therefore, per Rule 8, all models and parameter calibrations on this dataset are classified as **`DEVELOPMENT`**.

---

## 2. Held-Out Validation Schemes

To guard against over-parameterisation on a single cell, two systematic cross-validation schemes are pre-registered:

### 2.1 Scheme 1: Leave-One-Temperature-Out (LOTO) Cross-Validation
- **Objective:** Evaluate how well 2RC parameters identified across four chamber temperatures interpolate to a fifth held-out temperature.
- **Folds:** 5 rotations across the tested temperatures ($T \in \{15, 20, 25, 30, 35\}\ ^\circ\text{C}$):
  1. `LOTO_15C`: Fit on $\{20, 25, 30, 35\}\ ^\circ\text{C}$; validate held-out on $15\ ^\circ\text{C}$.
  2. `LOTO_20C`: Fit on $\{15, 25, 30, 35\}\ ^\circ\text{C}$; validate held-out on $20\ ^\circ\text{C}$.
  3. `LOTO_25C`: Fit on $\{15, 20, 30, 35\}\ ^\circ\text{C}$; validate held-out on $25\ ^\circ\text{C}$.
  4. `LOTO_30C`: Fit on $\{15, 20, 25, 35\}\ ^\circ\text{C}$; validate held-out on $30\ ^\circ\text{C}$.
  5. `LOTO_35C`: Fit on $\{15, 20, 25, 30\}\ ^\circ\text{C}$; validate held-out on $35\ ^\circ\text{C}$.

### 2.2 Scheme 2: Alternate-SOC-Point Holdout Cross-Validation
- **Objective:** Evaluate parameter smoothness and interpolation accuracy across the state-of-charge domain at each temperature.
- **Folds:** Interleaved 2-fold cross-validation on the 10-point HPPC setpoint grid ($\text{SOC} \in \{0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.25, 0.15, 0.05\}$):
  1. `ALT_ODD_FIT`: Fit on odd indices ($\text{SOC} \in \{0.95, 0.75, 0.55, 0.35, 0.15\}$); validate held-out on even indices ($\text{SOC} \in \{0.85, 0.65, 0.45, 0.25, 0.05\}$).
  2. `ALT_EVEN_FIT`: Fit on even indices ($\text{SOC} \in \{0.85, 0.65, 0.45, 0.25, 0.05\}$); validate held-out on odd indices ($\text{SOC} \in \{0.95, 0.75, 0.55, 0.35, 0.15\}$).

---

## 3. Open-Loop Model Acceptance Gates

The acceptance thresholds follow the pre-registered open-loop model gate established in [reports/flexipod1/model_gate.md](file:///Users/tecbusiness/Desktop/random/SOC/reports/flexipod1/model_gate.md#L13-L20):

1. **Terminal Voltage Bias:**
   $$|\text{Bias}| = \left| \frac{1}{N} \sum_{k=1}^N (\hat{V}_k - V_k) \right| \le 2.0\text{ mV}$$

2. **Terminal Voltage Root-Mean-Square Error (RMSE):**
   $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{k=1}^N (\hat{V}_k - V_k)^2} \le 6.0\text{ mV}$$

3. **Implied State-of-Charge Error:**
   $$\text{Implied SOC Error} = \frac{|\hat{V}_k - V_k|}{\left| \frac{\mathrm{d}OCV}{\mathrm{d}SOC}(z_k) \right|} \times 100\% \le 2.5\text{ percentage points (pp)}$$

*Note on Plateau Sensitivity:* On the flat central plateau of an LFP cell ($20\% \le \text{SOC} \le 80\%$), the slope $\frac{\mathrm{d}OCV}{\mathrm{d}SOC}$ is typically very small ($< 50\text{ mV per unit SOC}$), which amplifies small voltage discrepancies into substantial implied SOC errors. Implied SOC error must be reported separately from terminal voltage error, accompanied by the local plateau slope $\frac{\mathrm{d}OCV}{\mathrm{d}SOC}$.

---

## 4. Evaluation Metrics

For each test segment (10 s HPPC pulse discharge and relaxation, and full HPPC sequence):
- **Voltage Bias ($\text{mV}$):** Mean terminal voltage residual $\hat{V}_k - V_k$.
- **Voltage RMSE ($\text{mV}$):** Root-mean-square terminal voltage residual.
- **Maximum Voltage Error ($\text{mV}$):** $\max |\hat{V}_k - V_k|$.
- **Implied SOC Error ($\text{pp}$):** Mean and 95th percentile implied SOC discrepancy.
- **Plateau Slope ($\text{mV/pp}$ and $\text{V/unit}$):** Evaluated from relaxed HPPC rest voltages between 20% and 80% SOC.

---

## 5. Comparator Baselines

Performance on the held-out validation schemes will be benchmarked against three pre-registered baselines:

1. **Constant-Parameter Baseline (Temperature-Invariant Mean):**
   - A single temperature-invariant 2RC ECM parameter set obtained by averaging identified parameters across all temperatures.
   - Evaluates whether temperature-dependent scheduling provides measurable accuracy gain over an un-scheduled linear ECM.

2. **CALCE A123 Rescaled Baseline (Post-Hoc Comparator):**
   - Reference calibration `deliverable/calibrations/calce_a123_v4.json` (1.1 Ah cylindrical cell), rescaled by cell nominal capacity ratio ($\frac{280.0\ \text{Ah}}{1.1\ \text{Ah}}$) for impedance ($R \propto \frac{1}{Q}$, $C \propto Q$).
   - Labelled strictly as a post-hoc cross-chemistry/format comparator.

3. **Gustave Eiffel GE105 Rescaled Baseline (Post-Hoc Comparator):**
   - Reference calibration `deliverable/calibrations/ge105_v1.json` (105 Ah prismatic cell), rescaled by capacity ratio ($\frac{280.0\ \text{Ah}}{105.04\ \text{Ah}}$).
   - Labelled strictly as a post-hoc cross-cell comparator.
