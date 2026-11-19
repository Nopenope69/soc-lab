# Project Memory: SOC Estimation & SOH Validation Lab

**Last Updated:** 2026-11-20  
**Current Active Branch:** `validation/tempest`  
**GitHub Remote:** `https://github.com/Nopenope69/soc-lab.git` (All local branches pushed and up to date)  
**Python Environment:** `.venv/bin/python` (Python 3.14.6, pytest 9.1.1)  
**Test Suite Status:** 403 passed, 1 skipped, 1 warning (100% passing)

---

## 1. Permanent Repository Invariants & Frozen Hashes

The following files are strictly **FROZEN**. They must not be modified or tuned without creating a distinct, versioned artifact (e.g., E7v4):

| File Path | SHA-256 Digest | Role |
| :--- | :--- | :--- |
| `src/soc/estimators/e7v3.py` | `057f4d8547b00c80306d1ddd55fbac42dc304448f306d4bbd2fdbbb77ab9154e` | Core E7v3 EKF research candidate |
| `src/soc/estimators/base.py` | `33817e762e359c214cd9824c7684202b0ff129c9ef86b6994cdaf5fd8d8e04da` | Base estimator interface |
| `deliverable/bms_soc_ref.py` | `1e49223a5aed13554d2787d29e5a289b6541c7cabd7207480e195254001fb431` | Standalone zero-dependency BMS reference implementation |
| `deliverable/calibrations/ge105_v1.json` | `b5bb35137e08e1b6da985cbe03fb9d611748ad886d016783af530187cdb9111c` | Pre-registered GE105 calibration |
| `deliverable/calibrations/uconn_soh_pulse_v2_frozen_v27.json` | `efd71dc3f4d34698169250df6e62331add594087a37109f499a352df2795c095` | Pre-registered UConn SOH pulse model |
| `data/manifests/calce_a123.sha256` | Exactly 52 non-comment hash lines | CALCE A123 test dataset manifest |

---

## 2. Five-Point Governance Rule

Under the governing validation standard (`docs/SOH_STATUS.md`), an algorithm or model determination is classified as **`LAB_VALIDATED`** only if **ALL FIVE** criteria are met:
- **(a)** Real test files with verified SHA-256 manifest hashes.
- **(b)** Every evaluation script tracked in the repository and reproducible from a clean shell.
- **(c)** A frozen specification committed **BEFORE** unsealing the test cells.
- **(d)** A held-out evaluation result that beats a fair, pre-registered baseline on a reference independent of the estimator's own integral.
- **(e)** Enough data to support the claim, stated in numbers (e.g. multi-cell sample size, statistical significance).

**Any determination failing any single criterion is strictly classified as `DEVELOPMENT`.**

---

## 3. Branch Lineage & Task History

```
main (da8ee88)
  └── handover/hardening (f053eb3)
        └── handover/hardening2 (2b1d351)
              └── validation/ge105 (a14b37b) [Task V1: Gustave Eiffel 105 Ah LFP]
                    └── validation/uconn (3d461e4) [Task V2: UConn REIL SOH Dataset 5]
                          └── validation/tempest (86d2385) [Task V3: TEMPEST 280 Ah LFP BOL]
```

### Task V1: Gustave Eiffel 105 Ah LFP Validation (`validation/ge105`)
- **Dataset:** Gustave Eiffel 105 Ah LFP prismatic cells (Cell 05 and Cell 08).
- **Core Findings:**
  - Evaluated on real dataset (DOI `10.57745/G02IYE`, parameters `10.57745/SBNO8W`).
  - Pre-registered calibration `ge105_v1.json` evaluated against real test cell profiles.
  - E7v3 achieved $\le 1.5$ pp RMSE under dynamic profiles.
  - Status classified strictly as **`DEVELOPMENT`** because it fails Criterion (e): only 2 physical cells in dataset.
- **Key Reports:**
  - `reports/validation/ge105_report.md`
  - `reports/validation/ge105_reproduction.md`

### Task V2: UConn REIL Dataset 5 SOH Validation (`validation/uconn`)
- **Dataset:** 64 physical LithiumWerks 18650 APR18650M1B 1.2 Ah cylindrical LFP cells (2,855 RPT cycles across 11 cycling stress groups).
- **Split:** Strict cell-holdout (43 dev cells, 21 sealed test cells) and condition holdout (Groups 3 and 6).
- **Core Findings:**
  - **$SOH_C$:** Frozen `soh_pulse_v2` achieved 0.0211 MAE on sealed cells. It was **not shown to outperform** Ridge regression (0.0196 MAE) or a simple quadratic cycle counter (0.0221 MAE, overlapping bootstrap intervals [0.0181, 0.0260] vs [0.0199, 0.0281]).
  - **$SOH_R$:** **No evidence of estimation skill**. Ground-truth label is $r_{10\text{s}}$ from Step 20 and features are derived from the same pulse; a trivial reference ratio matches or beats the model (0.0095 vs 0.0094 MAE).
  - **Condition Holdout:** Labeled contaminated and supplementary due to mutual split overlap (17 of 21 sealed cells were training cells in condition holdout; 8 dev cells were test cells). Exactly 196 samples across 8 DEV cells were evaluated in `uconn_eval_sealed.py` (292 total samples across 12 cells in Groups 3 & 6 in the dataset).
  - **C Export (`deliverable/edge_pkg/soh_pulse_elasticnet_v2.h`):** Derived from a post-hoc 11-feature model modified after unsealing; strictly **`UNQUALIFIED`**.
  - **Overall Determination:** Reclassified from `LAB_VALIDATED` to **`DEVELOPMENT`** on 1.2 Ah cylindrical cells. Strictly **`UNQUALIFIED`** for 100 Ah cells.
- **Key Reports:**
  - `reports/validation/uconn_report.md`
  - `reports/validation/uconn_reproduction.md`
  - `reports/validation/uconn_sealed_results.json`

### Task V3: TEMPEST 280 Ah LFP Cell Characterisation (`validation/tempest`)
- **Dataset:** University of Bath / Zenodo record `19632939` (project TEMPEST, "LIC" cell).
- **Core Findings:**
  - Single-cell beginning-of-life (BOL) characterisation data only. Exactly **one physical cell**; zero degradation/SOH data; zero dynamic drive cycles.
  - **Leave-One-Temperature-Out (LOTO) 2RC ECM Generalization:**
    - 2 of 5 folds PASS (25 °C RMSE 0.35 mV; 30 °C RMSE 0.44 mV).
    - 3 of 5 folds FAIL acceptance gates (15 °C RMSE 13.05 mV [bias 9.52 mV]; 20 °C RMSE 2.76 mV [bias 2.01 mV > 2.0 mV gate]; 35 °C RMSE 4.95 mV [bias 3.84 mV > 2.0 mV gate]).
  - **Alternate-SOC Generalization:** Both folds FAIL (Odd SOC RMSE 17.31 mV; Even SOC RMSE 8.99 mV).
  - **Linear parameter interpolation beats per-fold constant baselines** on all folds.
  - Capacity monotonically increases from 299.03 Ah (15 °C) to 303.73 Ah (35 °C) at C/10. Reconciles with author CSV to $< 10^{-7}$ Ah; ~7% above nominal 280 Ah description.
  - Status classified strictly as **`DEVELOPMENT`** (fails Criterion (e); 1 physical cell; zero aging/SOH data).
- **Key Reports:**
  - `reports/validation/tempest_report.md`
  - `reports/validation/tempest_reproduction.md`
  - `reports/validation/tempest_spec_frozen.md`
  - `reports/validation/tempest_ecm_results.json`
  - `reports/validation/tempest_capacity_results.json`
  - `reports/validation/tempest_loto_baseline.json`
  - `reports/validation/tempest_cross_cell_comparison.json`

---

## 4. Key Cross-Cell Comparison (4 Physical Cells Audited)

| Metric / Parameter | CALCE A123 (1.06 Ah) | GE105 (105 Ah) | FlexiPod (100 Ah) | TEMPEST (280 Ah) |
| :--- | :--- | :--- | :--- | :--- |
| **Cell Format / Geometry** | Cylindrical (UNVERIFIED) | Prismatic (product knowledge) | Prismatic (product knowledge) | Prismatic (per README line 2) |
| **Nominal Capacity** | 1.1 Ah (UNVERIFIED, measured 1.0636 Ah) | 105 Ah (measured 105.04 Ah) | 100 Ah (measured 101.4 Ah) | 280 Ah (measured 301.7 Ah @ 25 °C) |
| **$R_0$ at ~50% SOC (25 °C)** | $\sim 50\text{--}60\ \text{m}\Omega$ (HPPC/drive cycle) | $0.46\ \text{m}\Omega$ (1C pulse) | $0.93\ \text{m}\Omega$ (100 A pulse) | $0.188\ \text{m}\Omega$ (0.5C pulse) |
| **Total Polarization $R_{\text{total}}$** | $\sim 80\text{--}90\ \text{m}\Omega$ | $0.78\ \text{m}\Omega$ | $1.72\ \text{m}\Omega$ | $0.279\ \text{m}\Omega$ |
| **Core Plateau Slope ($d\text{OCV}/d\text{SOC}$)** | $< 1.0\ \text{mV}/\%$ (0.12–0.25 mV/pp local) | $< 1.0\ \text{mV}/\%$ (0.38–0.88 mV/pp local) | $< 1.0\ \text{mV}/\%$ (local) | $1.38\ \text{mV/pp}$ (20–80% secant) |
| **Hysteresis Metric** | Model $M \approx 12\ \text{mV}$ | Measured loop gap $\sim 33\ \text{mV}$ | Model $M \approx 20\ \text{mV}$ | Continuous loop not tested |

*Note: Resistances were measured under distinct pulse rates and temperatures and are not directly comparable. No size-scaling inferences are warranted across four cells.*

---

## 5. Architectural Invariant: SOC vs SOH Boundary

- **`BmsSocEstimatorRef` / `E7v3` estimates SOC ONLY.**
- It does **not** track capacity degradation or battery SOH.
- Fast dynamic adaptation of $R_0$ via RLS is an operational filtering technique, **not** degradation tracking.
- SOH capacity fade $Q(T)$ must be injected from an external SOH supervisor.
- For non-CALCE calibrations, `deliverable/bms_soc_ref.py` uses the calibration file's capacity directly, while research `e7v3.py` linearly scales CALCE's $Q(T)$ curve. Divergence on GE105 is up to 3.61 pp in-envelope and 9.82 pp out-of-envelope (documented in Open Decision `DEC-06`).

---

## 6. How to Resume Work in a New Chat

1. **Working Directory:** `/Users/tecbusiness/Desktop/random/SOC`
2. **Data Directory:** `/Users/tecbusiness/soc_data` (`$SOC_DATA_DIR`)
3. **Active Branch:** `validation/tempest` (or switch to branch matching the task).
4. **Environment:** Activate `.venv` (`source .venv/bin/activate`).
5. **Verify Frozen Digests:** Always run SHA-256 check on the 5 frozen files + CALCE manifest at the start of any new session.
6. **Governance Rules:** Zero invention; facts only from files on disk; strict commit format `"validation: <task>.<step> <title>"`; never push without explicit user request.
