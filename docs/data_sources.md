# Laboratory Battery Datasets & Provenance Documentation

This document records the provenance, citations, digital object identifiers (DOIs), repository hosting, licensing terms, cell specifications, and on-disk verification status for all physical laboratory battery datasets evaluated in the `soc-lab` validation framework.

In compliance with **Rule R1**, raw measurement files reside outside this repository at `$SOC_DATA_DIR` (defaulting to `~/soc_data`), with the sole exception of `calce_a123` which is stored locally at `data/raw/calce_a123` (gitignored). In accordance with **Rule R2**, all datasets are audited against cryptographic SHA-256 manifests in `data/manifests/` built strictly from real files on disk without fabrication or synthetic defaulting.

---

## 1. Downloaded & Verified Datasets (`INTEGRITY_OK`)

The following datasets are physically present on disk and pass 100% cryptographic SHA-256 verification against their respective manifests via `scripts/verify_datasets.py`:

| Dataset ID | Dataset Title | DOI | Source URL | Licence | Version | Download Date | Cell Chemistry | Nominal / Measured Capacity | File Count | Byte Count |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **`calce_a123`** | CALCE A123 LFP Battery Dataset | `UNVERIFIED` | [calce.umd.edu/data](https://calce.umd.edu/data) | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | $\text{LiFePO}_4$ (LFP), format `UNVERIFIED` | Measured ~1.06 Ah (`A1-007`), ~1.09 Ah (`A1-008`) at 25°C | 52 | 506,702,062 B (~506.7 MB) |
| **`gustave_eiffel_g02iye`** | Characterisation tests of LFP 105Ah cells | `10.57745/G02IYE` | [doi.org/10.57745/G02IYE](https://doi.org/10.57745/G02IYE) | Etalab 2.0 | 2.0 | 2026-11-16 | $\text{LiFePO}_4$ (LFP) | 105.0 Ah (EVE Energy LFP 105 Ah, cells BUGE388..BUGE391) | 56 | 1,541,849,073 B (~1.54 GB) |
| **`gustave_eiffel_sbno8w`** | Electrical model parameters of LFP 105Ah cells | `10.57745/SBNO8W` | [doi.org/10.57745/SBNO8W](https://doi.org/10.57745/SBNO8W) | `UNVERIFIED` | `UNVERIFIED` | 2026-11-15 | $\text{LiFePO}_4$ (LFP) | 105.0 Ah (EVE Energy LFP 105 Ah) | 6 | 205,400 B (~205.4 KB) |
| **`uconn_reil_dataset5`** | UConn-ISU-ILCC LFP/Gr Battery Aging Dataset Extended (Dataset 5) | `UNVERIFIED` | [digitalcommons.lib.uconn.edu/reil_datasets/5](https://digitalcommons.lib.uconn.edu/reil_datasets/5) | CC BY 4.0 | `UNVERIFIED` | 2026-11-15 | LFP / Graphite (18650) | 1.2 Ah nominal (LithiumWerks APR18650M1B, per `README_Uconn.txt` on disk) | 2 | 2,406,392,335 B (~2.41 GB) |
| **`tempest_zenodo`** | record title not captured from the dataset files (UNVERIFIED); project name TEMPEST and 'LIC' cell as stated in the dataset files | `UNVERIFIED` | [zenodo.org/records/19632939](https://zenodo.org/records/19632939) | `UNVERIFIED` | `UNVERIFIED` | 2026-11-15 | $\text{LiFePO}_4$ (LFP, prismatic) | 280.0 Ah (TEMPEST LIC cell, per `LIC_characterisation_readme.txt` on disk) | 14 | 86,597,556 B (~86.6 MB) |

### On-Disk Source Citations
- **`calce_a123`:** Raw spreadsheet data located at `data/raw/calce_a123/`. Academic citation: W. He, N. Williard, C. Chen, M. Pecht, *State of charge estimation for LiFePO4 batteries including thermal effects*, Int. J. Electr. Power & Energy Syst. 62, 783–791 (2014); DOI UNVERIFIED. Web directories: `https://calce.umd.edu/data` and `https://web.calce.umd.edu/batteries/data/`.
- **`gustave_eiffel_g02iye`:** Recherche Data Gouv deposit: P. Von Hohendorff Seger and E. Redondo-Iglesias, *Characterisation tests of LFP 105Ah cells*, DOI: 10.57745/G02IYE. Files on disk at `$SOC_DATA_DIR/gustave_eiffel_105ah/` (extracted in `main_extracted/`).
- **`gustave_eiffel_sbno8w`:** Recherche Data Gouv deposit: P. Von Hohendorff Seger and E. Redondo-Iglesias, *Electrical model parameters of LFP 105Ah cells*, DOI: 10.57745/SBNO8W. Files on disk at `$SOC_DATA_DIR/gustave_eiffel_105ah/` (extracted in `params_extracted/`).
- **`uconn_reil_dataset5`:** UConn Digital Commons collection: Chao Hu et al., *UConn-ISU-ILCC LFP/Gr Battery Aging Dataset Extended (Dataset 5)*, `https://digitalcommons.lib.uconn.edu/reil_datasets/5`. Files on disk at `$SOC_DATA_DIR/uconn_reil/` (`README_Uconn.txt` [5,424 B] states 1.2 Ah nominal, APR18650M1B; and `rpt_data.zip` [2,406,386,911 B]).
- **`tempest_zenodo`:** University of Bath, Zenodo deposit record `19632939` (record title not captured from the dataset files (UNVERIFIED); project name TEMPEST and 'LIC' cell as stated in the dataset files). Files on disk at `$SOC_DATA_DIR/tempest_280ah/` (10 capacity and HPPC files across 15°C to 35°C, plus 4 analysis/readme files).

---

## 2. NOT DOWNLOADED Datasets (`catalogued only`)

The following datasets are recognized in `DATASET_METADATA` and have split configurations declared in `configs/validation/`, but their raw binary data has not been downloaded into `$SOC_DATA_DIR`. They are tracked via stub manifests with `status: NOT_DOWNLOADED` (0 expected hashes) and are skipped cleanly during testing:

| Dataset ID | Dataset Title | DOI | Source URL | Licence | Version | Status | Chemistry | Nominal Capacity | File Count |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- | :--- | :---: |
| **`uconn_reil_dataset1`** | UConn-ISU-ILCC LFP/Gr Battery Aging Dataset 1 | `UNVERIFIED` | [digitalcommons.lib.uconn.edu/reil_datasets/1/](https://digitalcommons.lib.uconn.edu/reil_datasets/1/) | CC BY 4.0 | `UNVERIFIED` | **`NOT_DOWNLOADED`** | LFP / Graphite (18650 from publication citation; UNVERIFIED on disk) | `UNVERIFIED` | 0 |
| **`wheeler_2025`** | Wheeler et al. 2025 Twenty-Cell LFP Aging Dataset | `UNVERIFIED` | [doi.org/10.1038/s41597-025-04712-7](https://doi.org/10.1038/s41597-025-04712-7) | `UNVERIFIED` | `UNVERIFIED` | **`NOT_DOWNLOADED`** | LFP 18650 (from the article title; UNVERIFIED on disk) | `UNVERIFIED` | 0 |

---

## 3. CALCE A123 Cell Identity & Capacity Conflict

A detailed investigative audit is recorded in [cell_identity_conflict.md](../../../../../../reports/handover/cell_identity_conflict.md). The key facts established from the raw files on disk are:

### 3.1 Empirical Measured Capacity vs Website Contradiction
1. **Measured Capacity on Disk:** The 52 raw spreadsheets in `data/raw/calce_a123` record quasi-static C/20 discharge tests spanning $-10^\circ\text{C}$ to $50^\circ\text{C}$. Measured C/20 capacities range from **$1.042\text{ Ah}$ to $1.105\text{ Ah}$**.
   - Reference Cell `A1-007` at 25°C: **$1.0636\text{ Ah}$** ($1063.6\text{ mAh}$).
   - Held-Out Cell `A1-008` at 25°C: **$1.0879\text{ Ah}$** ($1087.9\text{ mAh}$), which is $+2.28\%$ higher.
   - Cell-to-cell spread: Cell `A1-008` is systematically **$\sim 1.5\%$ to $2.5\%$ higher** in capacity than `A1-007` across all thermal chambers.
2. **Website Rating Contradiction:** The CALCE public website (`https://calce.umd.edu/data`) states **"2230 mAh"** (~2.2–2.3 Ah) for A123 samples. This is more than double the actual measured capacity in the raw time-series test files in that same repository.

### 3.2 Form Factor Ambiguity (18650 vs 26650)
- Commercial A123 Nanophosphate® cells include the **APR18650M1A/B** (rated nominal $1.1\text{ Ah}$, from general knowledge, not verified against a datasheet on disk, matching the empirical ~1.06 Ah capacity) and the **ANR26650M1A/B** (rated nominal $2.3 - 2.5\text{ Ah}$, from general knowledge, not verified against a datasheet on disk).
- The raw spreadsheet files contain only numeric time-series columns (timestamps, step numbers, current, voltage, capacity, temperature) with no photographs, mechanical dimensions, or cell model numbers.
- Because raw file evidence alone cannot prove whether Hypothesis A (the specimens are a 1.1 Ah-class cell, for example 18650 format, and the CALCE page's 2230 mAh listing does not describe them), Hypothesis B (degraded 26650 cells), or custom development prototypes holds, **we assert NEITHER 18650 nor 26650**.
- The form factor is formally catalogued as `cell_form_factor = "UNVERIFIED"`.

### 3.3 Algorithmic Baselines
All SOC and SOH evaluation pipelines must baseline capacity and Coulomb integration **strictly against the measured Beginning-of-Life (BOL) capacity per cell** ($1.0636\text{ Ah}$ for `A1-007` at 25°C, $1.0879\text{ Ah}$ for `A1-008` at 25°C), never against a generic catalog rating.

---

## 3.4 Dataset Limitations & Scope Clarifications

- **Remaining Useful Life (RUL):** Design specification only (`docs/rul_subsystem_design.md`). No runnable implementation exists in `src/soh`.
- **FlexiPod Dataset:** Contains beginning-of-life (BOL) characterization data only (`reports/flexipod1/`); no cycle degradation data or aged cell measurements.
- **HPPC Cohort:** Analytical simulation generated via `StandardizedHppcCohortGenerator` (`src/soh/data/pulse_hppc_cohort.py`), not physically measured test-bench hardware.

---

## 4. Directory Layout on Disk

When downloading external datasets to `$SOC_DATA_DIR` (default `/Users/tecbusiness/soc_data`), the directories must match the registered path patterns:

```text
$SOC_DATA_DIR/ (default ~/soc_data/)
├── gustave_eiffel_105ah/
│   ├── main_G02IYE_dataverse_files.zip
│   ├── main_extracted/
│   │   └── processed_data/2_processed_data/BUGE388..BUGE391
│   ├── params_SBNO8W_dataverse_files.zip
│   └── params_extracted/
│       ├── batt_data.mat
│       └── parameter_visualisation.m
├── uconn_reil/
│   ├── README_Uconn.txt
│   └── rpt_data.zip
└── tempest_280ah/
    ├── 15C_capacity.csv ... 35C_capacity.csv
    ├── 15C_hppc.csv ... 35C_hppc.csv
    └── LIC_capacity_analysis.csv ... LIC_entropy_analysis.csv

Repo-Local Path:
<REPO_ROOT>/data/raw/calce_a123/ (52 files: OCV and dynamic drive cycles DST, US06, FUDS)
```

To audit dataset integrity at any time, run:
```bash
python scripts/verify_datasets.py
```
