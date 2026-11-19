# SOC-LAB Real-Data Validation Protocol & Governance Specification

> [!NOTE] Revision (V1.12)  
> Updated `LAB_VALIDATED` definition to the 5-point governance rule (real files, tracked/reproduced scripts, pre-committed spec, independent reference beating fair baseline, and stated data volume).

**Status:** ACTIVE SPECIFICATION  
**Scope:** Real-Data Ingestion, Manifest Hash Verification, Cell-Held-Out Split Governance, and Evaluation Integrity for State of Charge (SOC) and State of Health (SOH) Estimation.

---

## 1. Core Governing Rules

Every benchmark, evaluation script, and dataset loader in `soc-lab` must strictly adhere to the six immutable validation rules:

### Rule R1: External Data Storage and Cryptographic Manifests
* **External Storage:** Raw experimental battery datasets reside strictly **OUTSIDE** the git repository at `$SOC_DATA_DIR` (defaulting to `~/soc_data`). Raw laboratory test files must never be committed to git.
* **Cryptographic Manifest:** Every registered dataset must possess an immutable checksum manifest file located at `data/manifests/<dataset>.sha256`.
* **Manifest Provenance Header:** Every manifest file must record source metadata in header comments:
  - Source URL
  - DOI
  - Licence
  - Version
  - Download Date
* **File Hashes:** The body of each manifest records the SHA-256 fingerprint for every raw data file (`<sha256_hash>  <relative_filepath>`).

### Rule R2: Real File Verification, Zero Synthetic Generation, Zero Defaulting
* **Strict Real File Ingestion:** Loaders must read physical files from disk and verify SHA-256 checksums against the corresponding manifest before parsing.
* **No Synthetic Generation or Mocking in Validation:** No loader may generate, simulate, interpolate, or synthesize any measurement values.
* **No Defaulting of Missing Labels:** If a ground-truth measurement is absent (e.g. unmeasured resistance or capacity in an operational cycle), the sample must be **excluded** from that metric's evaluation. Defaulting ground truth (e.g. setting unmeasured $SOH_R = 1.0$) is strictly prohibited.
* **Graceful Missing Data Handling:** If dataset files are not present on disk, loaders must skip with an explicit, actionable message directing the operator to download the dataset to `$SOC_DATA_DIR`.

### Rule R3: Strict Cell-Level Splits and Sealed Test Partition
* **Partitioning Unit:** Data splits are strictly partitioned by **CELL** (never by cycle, time-step, or window). Time-series or cycle records from the same physical battery cell must never be divided across training/tuning and testing partitions.
* **Split Declarations:** Splits must be declared in `configs/validation/<dataset>_splits.yaml` prior to evaluation.
* **Sealed Test Set:** A designated partition of cells (`sealed_test_cells`) is sealed and protected by the repository's sealed-split mechanism (`data/splits.lock`, `tests/test_sealed_split.py`).
* **One-Shot Evaluation:** The test partition may be evaluated **exactly once** per released estimator version. Model tuning, hyperparameter search, and feature selection must utilize development cells (`dev_cells`) only.

### Rule R4: Frozen Reference Artefacts and Versioned Evolution
* **Immutability of Frozen Artefacts:** The existing baseline estimators are permanently frozen:
  - Reference SOC estimator: `src/soc/estimators/e7v3.py`
  - Reference edge BMS C implementation: `deliverable/bms_soc_ref.py`
* **New Estimators as Distinct Versions:** Any algorithmic enhancement, tuning adjustment, or new architecture must be introduced as an entirely new version (`E7v4`, `soh_pulse_v2`, etc.) with its own standalone design specification, frozen prior to unsealing the test set.
* **Comparative Reporting:** Every benchmark must report the new candidate against:
  - For SOC: **New Candidate vs Frozen Baseline (`E7v3` / `bms_soc_ref.py`) vs `E0` (Fair Anchored Coulomb Counting)**.
  - For SOH: **New Candidate vs Frozen Dual Tracker vs Constant-Training-Mean Baseline**.

### Rule R5: Strict Result Qualification Labels and Non-Pooling
* **`LAB_VALIDATED` Status:** LAB_VALIDATED requires ALL of: (a) real files with verified manifest hashes; (b) every evaluation script tracked in the repo and reproduced from a clean shell; (c) a spec committed BEFORE the sealed set is evaluated; (d) a held-out result that beats a fair baseline on a reference that is independent of the estimator's own integral; (e) enough data to support the claim, stated in numbers. Everything else is DEVELOPMENT.
* **`DEVELOPMENT` Status:** Any result on synthetic cohorts, simulation models, training/validation development cells, or unverified files must be explicitly labeled `DEVELOPMENT`.
* **Strict Non-Pooling:** Results must be reported **separately per dataset**. Performance metrics from different battery chemistries, form factors, manufacturers, or test regimes must never be averaged or pooled into a single composite metric.

### Rule R6: Beginning-of-Life (BOL) Ground-Truth Calibration
* **Measured Capacity Baseline:** Capacity state of health ($SOH_C$) must be baselined against the **measured beginning-of-life (BOL) capacity** of that specific physical cell, never the manufacturer's nameplate rating.
* **Matched Resistance Baseline:** Resistance state of health ($SOH_R$) must be baselined against measured direct-current internal resistance (DCIR) under matched state-of-charge, temperature, and current pulse specifications.

---

## 2. Per-Dataset Split Declarations

Splits are configured in `configs/validation/<dataset>_splits.yaml`. In accordance with Rule R3, all partitions are segregated by physical cell identifier:

| Dataset ID | Chemistry & Form Factor | Development Cells (`train_cells` / `val_cells`) | Sealed Test Cells (`sealed_test_cells`) | Environmental & Profile Conditions |
| :--- | :--- | :--- | :--- | :--- |
| **`calce_a123`** | A123 LFP (Format UNVERIFIED; measured ~1.06 Ah A1-007, ~1.09 Ah A1-008 at 25°C) | `A1-007` (Train/Val) | **`A1-008`** (Sealed Test) | Temperatures: $-10^\circ\text{C}$ to $50^\circ\text{C}$; Profiles: DST, US06, FUDS |
| **`gustave_eiffel_g02iye`** | EVE Energy LFP 105 Ah (Characterisation tests) | `cell_01`, `cell_02`, `cell_03` | **`cell_04`** (Sealed Test) | Characterisation tests at 0°C, 10°C, 25°C, 40°C |
| **`gustave_eiffel_sbno8w`** | EVE Energy LFP 105 Ah (Electrical parameters) | `cell_c01`, `cell_c02` | **`cell_c03`** (Sealed Test) | C/20 quasi-static OCV, HPPC pulses, parameter identification (0°C to 40°C) |
| **`uconn_reil_dataset1`** | LFP/Graphite (NOT DOWNLOADED, catalogued only) | `cell_01`, `cell_02`, `cell_03` | **`cell_04`** (Sealed Test) | Fast charging CC profiles, standard cycling, intermittent 100s RPT pulses |
| **`uconn_reil_dataset5`** | LFP/Graphite (1.1 Ah nominal) | `cell_condition1`, `cell_condition2`, `cell_condition3` | **`cell_condition4`** (Sealed Test) | 11 unique aging conditions cycled to 80% remaining capacity |
| **`wheeler_2025`** | LFP 1.1 Ah (NOT DOWNLOADED, catalogued only) | `Cell_01` through `Cell_14` (14 cells) | **`Cell_15` through `Cell_20`** (6 cells) | First-life EV WLTP cycles & second-life storage down to 40% capacity loss |
| **`tempest_zenodo`** | Prismatic LFP (280 Ah) | `cell_tempest_01` | **`cell_tempest_02`** (Sealed Test) | Characterisation (HPPC 15–35°C, entropy sweeps) |

---

## 3. Standardized Evaluation Matrix

### 3.1 State of Charge (SOC) Evaluation Matrix

For each dataset and test condition, the following metrics must be computed on the sealed test partition:

| Metric | Target Specification | Reference Baseline | Interpretation |
| :--- | :---: | :--- | :--- |
| **RMSE (%)** | $< 1.50\%$ | `E0` (Anchored Coulomb Counting) & `E7v3` | Global state estimation accuracy over dynamic drive cycles |
| **Max Absolute Error (%)** | $< 3.50\%$ | `E7v3` | Peak transient estimation deviation under aggressive current steps |
| **95th Percentile Error (%)** | $< 2.00\%$ | `E7v3` | Robustness excluding localized voltage recovery transients |
| **Drift Rate (%/hr)** | $< 0.10\%/\text{hr}$ | `E0` | Error accumulation rate under prolonged open-circuit rest or sensor bias |
| **Convergence Time ($t_{conv}$)** | $< 120\text{ s}$ | `E7v3` | Time to recover true state from an intentional $\pm 20\%$ initial SOC error |

### 3.2 State of Health (SOH) Evaluation Matrix

Evaluated separately for Capacity SOH ($SOH_C$) and Resistance SOH ($SOH_R$):

| Metric | Target Specification | Reference Baseline | Interpretation |
| :--- | :---: | :--- | :--- |
| **$SOH_C$ RMSE (%)** | $< 1.00\%$ | Constant-Training-Mean | Accuracy of remaining usable capacity relative to physical BOL |
| **$SOH_C$ MAE (%)** | $< 0.80\%$ | Constant-Training-Mean | Mean absolute error of capacity degradation tracking |
| **$SOH_R$ RMSE (%)** | $< 2.50\%$ | Constant-Training-Mean | Accuracy of internal resistance growth relative to matched BOL DCIR |
| **95% PICP (Coverage)** | $\ge 90.0\%$ | 95.0% Nominal Target | Empirical coverage probability of prediction uncertainty intervals |
| **MPIW (Interval Width)** | $< 5.00\%$ | Static Uncertainty Bounds | Mean prediction interval width; measures sharpness of uncertainty |

---

## 4. Operational Validation Workflow

1. **Verify Raw Data Environment:**
   ```bash
   export SOC_DATA_DIR=~/soc_data
   python scripts/verify_datasets.py
   ```
2. **Execute Development & Tuning on Dev Cells:**
   - Optimize estimators exclusively on `train_cells` and `val_cells`.
   - Any attempt to access `sealed_test_cells` during tuning raises `PermissionError` (Rule R3).
3. **Freeze Candidate Estimator:**
   - Document model specification and freeze code before unsealing test cells (Rule R4).
4. **Execute Sealed Test Evaluation:**
   - Evaluate candidate on sealed test cells with `final=True`.
   - LAB_VALIDATED requires ALL of: (a) real files with verified manifest hashes; (b) every evaluation script tracked in the repo and reproduced from a clean shell; (c) a spec committed BEFORE the sealed set is evaluated; (d) a held-out result that beats a fair baseline on a reference that is independent of the estimator's own integral; (e) enough data to support the claim, stated in numbers. Everything else is DEVELOPMENT.
   - Output individual results per dataset without pooling (Rule R5).
