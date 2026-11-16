# ERRATA: SOH Phase 6.1 Production Qualification Report

> **Status Notice**: The evaluation presented in `reports/soh_phase6_1_production_qualification_report.md` as "Experimental Benchmark (CALCE & MIT/Stanford Physical Cell LOBO)" does **NOT** evaluate physical cycler data files from experimental laboratories. All referenced cohorts were synthetically generated in software via analytical equations.

---

## 1. Provenance Audit Findings

In `reports/soh_phase6_1_production_qualification_report.md` (Table 2 and associated narrative), results are presented for what was labeled:
- "CALCE CS2 physical cells"
- "MIT Severson fast-charging physical cells"

A code-level provenance audit of `src/soh/data/real_cell_adapters.py` revealed that these cohorts were generated entirely in-memory using closed-form analytical degradation formulas and seeded random number generators (`np.random.default_rng(202)`). No raw `.csv`, `.mat`, or cycler test logs were read or processed.

### Exact Mathematical Formulas Used to Synthesize Cohorts

#### CALCE A123 Synthetic Cohort
- **Capacity Fade**:
  $$\Delta C(k) = 0.00045 \cdot k + 0.000008 \cdot k^{1.35}$$
  $$\text{SOH}_C(k) = \max(0.60, \min(1.0, 1.0 - \Delta C(k)))$$
- **Resistance Growth**:
  $$\Delta R(k) = 0.0008 \cdot k + 0.000015 \cdot k^{1.30}$$
  $$\text{SOH}_R(k) = \frac{1.0}{1.0 + \Delta R(k)}$$
- **Signal Traces**: Synthesized linear sweeps ($V \in [2.5, 3.6]\text{ V}$, $I = -1.1\text{ A}$, $T = 25.0^\circ\text{C}$).

#### MIT/Stanford Fast-Charging Synthetic Cohort
- **Capacity Fade (with artificial knee-point at cycle $n_{\text{knee}} = 45$)**:
  $$\text{fade}_{\text{linear}}(k) = 0.0008 \cdot k$$
  $$\text{fade}_{\text{knee}}(k) = \frac{0.035}{1.0 + \exp\left(-\text{clip}\left(\frac{k - 45}{4.0}, -10, 10\right)\right)}$$
  $$\text{SOH}_C(k) = \max(0.50, \min(1.0, 1.0 - (\text{fade}_{\text{linear}} + \text{fade}_{\text{knee}})))$$
- **Resistance Growth**:
  $$R_{\text{mult}}(k) = 1.0 + 0.005 \cdot k + 0.05 \cdot \left(\frac{k}{45}\right)^2$$
  $$\text{SOH}_R(k) = \frac{1.0}{R_{\text{mult}}(k)}$$
- **Signal Traces**: Synthesized linear sweeps ($V \in [2.5, 3.6]\text{ V}$, $I = -4.0\text{ A}$, $T = 30.0^\circ\text{C}$).

---

## 2. Status Reclassification

1. **Table 2 Reclassification**:
   The metrics reported in Table 2 must be classified as **Simulation Validation (`SIM_VALIDATED`)**, not physical experimental benchmark.
2. **Resistance SOH ($SOH_R$)**:
   $SOH_R$ ground truth remains **UNVALIDATED** on physical cells. The reported resistance metrics reflect fitting to synthetic reciprocal growth functions.
3. **Selective Risk & Abstention**:
   The architectural handling of selective estimation (abstaining under `INSUFFICIENT_INFORMATION`) is valid code logic, but its numerical error performance is verified only against simulated trajectories.
