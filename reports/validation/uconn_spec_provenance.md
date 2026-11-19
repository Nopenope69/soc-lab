# UConn REIL Dataset 5: Partition Split Provenance and Cell Overlap Audit (Task V2.11)

> [!NOTE] Revision (V2.11)  
> Audit of pre-freeze data scanning, split selection provenance, partition cell lists, and cross-split cell overlap.

**Document ID:** AUD-UCONN-SPLIT-001  
**Date:** 2026-11-19  
**Repository:** `/Users/tecbusiness/Desktop/random/SOC`  
**Branch:** `validation/uconn`  

---

## 1. Pre-Freeze Data Scanning & Label Visibility (V2.1 - V2.3)

Prior to committing the formal partition specification in Step V2.4 (`f4a8d87`):

1. **Inventory Scan (Step V2.1, Commit `5250bdd`):**
   - The scan script `scripts/validation/uconn_inventory_scan.py` scanned all 64 physical cells (`02` through `65`) across 207 CSV files.
   - Initial capacity $C_0$ was computed and tabulated for all 64 cells (mean 1.2134 Ah, range 1.2046–1.2228 Ah) in `reports/validation/uconn_cell_summary.csv`.
2. **Label Extraction (Step V2.3, Commit `d2d6987`):**
   - The label extraction script `scripts/validation/uconn_extract_labels.py` extracted ground-truth $SOH_C$ and $SOH_R$ across all 2,855 RPT records for all 64 cells into `reports/validation/uconn_labels.csv`.
   - Global dataset label statistics across all cells (including cells later assigned to the sealed test set) were computed and published in `reports/validation/uconn_labels.md`:
     - **$SOH_C$ (2,855 samples):** Min = 0.7234, 25% = 0.8893, Median = 0.9289, Mean = 0.9189, 75% = 0.9601, Max = 1.0000.
     - **$SOH_R$ 50% 10s (2,855 samples):** Min = 0.9282, 25% = 0.9701, Median = 0.9803, Mean = 0.9873, 75% = 1.0000, Max = 1.2061.
   - Therefore, complete label distributions and initial baseline capacities across all cells were extracted and inspected before the partition specification was frozen in Step V2.4.

---

## 2. Partition Selection Provenance

- **Split Definitions:** Defined in `configs/validation/uconn_splits.yaml` (Step V2.4).
- **Earlier Configuration:** An earlier file `configs/validation/uconn_reil_dataset5_splits.yaml` contained only placeholder string tokens (`cell_condition1`, etc.) without physical cell IDs.
- **Selection Rule & Seed Status:**
  - `configs/validation/uconn_splits.yaml` assigns cells by group counts (e.g., 3 train, 1 val, 2 test per group for Groups 1–10; 2 train, 1 val, 1 test for Group 11).
  - For condition holdout, it designates Groups 3 and 6 as test conditions with comments noting "High-rate rapid aging" and "Severe degradation regime".
  - **Audit Finding:** Neither configuration file states a random seed, mathematical PRNG algorithm, or formal deterministic selection rule for why specific cell IDs (e.g., `06, 07` vs `02, 03`) were chosen.
  - **Rule Determination:** **UNVERIFIED** (no seed or generation rule documented in repository files).

---

## 3. Cell Allocations per Partition

The 64 cells (`02` to `65`) are distributed as follows across the two splits:

### 3.1 Split 1: Cell-Held-Out Split (Within-Condition Generalization)
- **Train Partition (32 cells):**  
  `['02', '03', '04', '08', '09', '10', '14', '15', '16', '20', '21', '22', '26', '27', '28', '32', '33', '34', '38', '39', '40', '44', '45', '46', '50', '51', '52', '56', '57', '58', '62', '63']`
- **Validation Partition (11 cells):**  
  `['05', '11', '17', '23', '29', '35', '41', '47', '53', '59', '64']`
- **Sealed Test Partition (21 cells):**  
  `['06', '07', '12', '13', '18', '19', '24', '25', '30', '31', '36', '37', '42', '43', '48', '49', '54', '55', '60', '61', '65']`

### 3.2 Split 2: Condition-Held-Out Split (Cross-Condition Generalization)
- **Dev Condition Partition (52 cells across Groups 1, 2, 4, 5, 7, 8, 9, 10, 11):**  
  `['02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '38', '39', '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '50', '51', '52', '53', '54', '55', '56', '57', '58', '59', '60', '61', '62', '63', '64', '65']`
- **Sealed Test Condition Partition (12 cells across Groups 3 and 6):**  
  `['14', '15', '16', '17', '18', '19', '32', '33', '34', '35', '36', '37']`

---

## 4. Cross-Split Overlap and Lack of Independence

A rigorous cross-comparison reveals that **the two evaluation splits are NOT independent of each other**:

1. **Sealed Test Cells Used as Training Cells:**
   - Exactly **17 of the 21 "sealed test cells"** from Split 1 are assigned to the 9 dev conditions in Split 2:
     `['06', '07', '12', '13', '24', '25', '30', '31', '42', '43', '48', '49', '54', '55', '60', '61', '65']`
   - In the condition-holdout evaluation, these 17 sealed test cells are included in the training set (`df_cond_tr`) used to fit models.
2. **Development Cells Used as Test Cells:**
   - Exactly **8 of the 43 "development cells"** (6 Train cells: `14`, `15`, `16`, `32`, `33`, `34`; 2 Val cells: `17`, `35`) from Split 1 are located in Groups 3 and 6, and thus serve as the held-out test cohort in Split 2.
3. **Implication:**
   Because cells that are sealed in Split 1 are used as training data in Split 2, and cells that are dev/training in Split 1 serve as test targets in Split 2, the two evaluations are mutually contaminated and cannot be cited as independent experimental validations.
