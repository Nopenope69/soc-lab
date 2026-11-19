# Gustave Eiffel 105 Ah LFP Evaluation Specification (Frozen Prior to Test Unsealing)

> [!WARNING] Revision (V1.11 Provenance Notice)  
> The claim below that this specification was "frozen and committed prior to unsealing test cells" is **not supported by git history**.  
> As documented in [ge105_spec_provenance.md](file:///Users/tecbusiness/Desktop/random/SOC/reports/validation/ge105_spec_provenance.md), this document was first committed in commit `847843c` together with the sealed test results (`ge105_closed_loop_test.md`). The test evaluation script was edited until 92 seconds prior to that commit. While the edits were syntax and interface corrections only, the protocol requirement of committing the frozen specification to git before unsealing was violated.

> **Document ID:** SPEC-GE105-FROZEN-001  
> **Status:** FROZEN  
> **Date:** 2026-11-19  
> **Target Evaluation:** Held-Out Sealed Test Cells `BUGE390` and `BUGE391`  
> **Guarantee:** Frozen prior to unsealing test cells. Evaluated exactly once. No calibration, code, or hyperparameter modifications permitted post-unsealing.

---

## 1. Frozen Artifact Checksums (SHA-256)

All algorithms, models, reference implementations, and calibration files evaluated against the sealed test partition are strictly frozen under the following verified cryptographic hashes:

| Component / Artifact | Path | SHA-256 Checksum |
|:---|:---|:---|
| **E7v3 Estimator Implementation** | `src/soc/estimators/e7v3.py` | `057f4d8547b00c80306d1ddd55fbac42dc304448f306d4bbd2fdbbb77ab9154e` |
| **Estimator Base Class** | `src/soc/estimators/base.py` | `33817e762e359c214cd9824c7684202b0ff129c9ef86b6994cdaf5fd8d8e04da` |
| **Reference BMS Implementation** | `deliverable/bms_soc_ref.py` | `1e49223a5aed13554d2787d29e5a289b6541c7cabd7207480e195254001fb431` |
| **GE105 Calibration Container** | `deliverable/calibrations/ge105_v1.json` | `b5bb35137e08e1b6da985cbe03fb9d611748ad886d016783af530187cdb9111c` |
| **CALCE Calibration Container** | `deliverable/calibrations/calce_a123_v4.json` | `e2a4a75c120bf516cf16a048a1cb0e7ffce72c722aeb9dfd707c70c04297a783` |
| **CALCE Assumptions Profile** | `configs/assumptions/profiles/calce_a123_v4.yaml` | `3a3391e4f95ee967004d41f9c4d3a210a64c852715befbdfe26b53d74cc9c375` |
| **Gauntlet Scenarios Script** | `scripts/gauntlet_v3_scenarios.py` | `a2c8929bf4959217e770a14dcdacf1dee761feefed1eb17909a16e99427feceb` |
| **CALCE Manifest Hashes** | `data/manifests/calce_a123.sha256` | 52 verified lines intact |

---

## 2. Evaluation Scope & Cell Partitions

In accordance with `configs/validation/ge105_splits.yaml` and `reports/validation/ge105_protocol.md`:
- **Development Partition (Calibration & Exploration):** Cells `BUGE388` and `BUGE389`.
- **Sealed Test Partition (Held-Out Final Verification):** Cells `BUGE390` and `BUGE391`.
- **Available WLTC Segments in Test Partition:**
  - `BUGE390` 0 °C (`20230712_1137_full_0C_buge390_dattes.mat`): 2 segments (~90% and ~50% SOC).
  - `BUGE390` 40 °C (`20230721_2113_full_40C_buge390_dattes.mat`): 2 segments (~90% and ~50% SOC).
  - `BUGE391` 0 °C (`20230712_1137_full_0C_buge391_dattes.mat`): 2 segments (~90% and ~50% SOC).
  - `BUGE391` 40 °C (`20240201_1650_full_40C_buge391_dattes.mat`): 2 segments (~90% and ~50% SOC).
  - *(Note: `BUGE390` 25C and `BUGE391` 25C full tests date from 2023-06-27 and terminated at phase 166 without dynamic WLTC phases; documented in V1.1 inventory).*

---

## 3. Evaluation Scenarios & Protocol

Each dynamic WLTC segment is evaluated under the standardized protocol:
1. **Primary Timebase:** Resampled to 1.0 s uniform grid using exact sub-interval trapezoidal charge integration and voltage interpolation.
2. **Estimator Algorithms:**
   - **E0**: Baseline Coulomb Counting with nominal capacity $Q = 105.04\ \text{Ah}$ anchored to true initial SOC ($SOC_0$).
   - **E7v3 (CALCE Calibration)**: Cross-chemistry/scale baseline using `calce_a123_v4.json`.
   - **E7v3 (GE105 Calibration)**: Matched LFP container using `ge105_v1.json`.
3. **Perturbation Scenarios:**
   - Nominal initialization: $\hat{SOC}_0 = SOC_0$
   - Positive error perturbation: $\hat{SOC}_0 = \min(1.0, SOC_0 + 0.10)$ ($+10\ \text{pp}$)
   - Negative error perturbation: $\hat{SOC}_0 = \max(0.0, SOC_0 - 0.10)$ ($-10\ \text{pp}$)
4. **Reference Implementation Parity:**
   - `deliverable/bms_soc_ref.py` executed concurrently on every sample.
   - Parity requirement: $\max |SOC_{\text{python}} - SOC_{\text{ref}}| \le 10^{-12}$.
5. **Operating Envelope & Status Flags:**
   - Operational envelope for `ge105_v1.json`: $T \in [20.0, 45.0]\ ^\circ\text{C}$, $V \in [2.0, 3.7]\ \text{V}$, $I \in [-120.0, 120.0]\ \text{A}$.
   - At 40 °C: Flag must be strictly `['OK']`.
   - At 0 °C: Flag must be strictly `['OUT_OF_ENVELOPE']`.

---

## 4. Frozen Acceptance Criteria & Thresholds

To achieve validation pass on the held-out test cells:

1. **In-Envelope Tracking Accuracy (40 °C, Nominal Start):**
   - High SOC segment (~90% SOC): $\text{RMSE} \le 3.5\ \text{pp}$, $\text{Max Error} \le 5.0\ \text{pp}$.
   - Plateau SOC segment (~50% SOC): $\text{RMSE} \le 7.0\ \text{pp}$, $\text{Max Error} \le 16.0\ \text{pp}$ (due to flat LFP plateau slope $d\text{OCV}/d\text{SOC} < 1\ \text{mV}/\%$).
2. **Disturbance Recovery (+10 pp, -10 pp):**
   - Filter must demonstrate closed-loop convergence: final tracking error strictly less than initial perturbation ($|e_{\text{final}}| < 10.0\ \text{pp}$).
3. **Out-of-Envelope Behavior (0 °C):**
   - Must correctly self-report `OUT_OF_ENVELOPE` status flag on 100% of samples.
4. **Implementation Parity:**
   - 100% bitwise/double-precision parity with BMS reference implementation ($\max |\Delta| \le 10^{-12}$).
