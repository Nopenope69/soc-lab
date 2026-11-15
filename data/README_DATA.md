# Raw Dataset Layout and Provenance

## 1. CALCE A123 LiFePO4 Dataset

- **Source**: Center for Advanced Life Cycle Engineering (CALCE), University of Maryland.
- **License / Access**: Public academic research data. Available from CALCE Battery Research Group repository.
- **Cell Chemistry & Geometry**: 1.11 Ah calibrated capacity $\text{LiFePO}_4$ / LFP (**A123 Systems ANR26650M1-A, 26650 cylindrical form-factor**). Note: Historically mislabeled in early documentation as 18650.
- **Tested Cells**: Primary development cell `A1-007`; held-out transfer validation cell `A1-008`.
- **Operating Temperatures**:
  - Gating decision temperatures: $20^\circ\text{C}, 25^\circ\text{C}, 30^\circ\text{C}, 40^\circ\text{C}, 50^\circ\text{C}$.
  - Informational sub-$20^\circ\text{C}$ temperatures: $-10^\circ\text{C}, 0^\circ\text{C}, 10^\circ\text{C}$.

### Expected Directory Structure
Set the environment variable `SOC_DATA_DIR` to the parent raw data folder (defaulting to `data/raw`). The loader expects the folder `calce_a123/` under `SOC_DATA_DIR` or pointing directly to `calce_a123/`:

```
data/raw/calce_a123/
├── A123_DST-US06-FUDS-0/
│   └── DST-US06-FUDS-0/
│       ├── A1-007-DST-US06-FUDS-0-20120813.xlsx
│       └── A1-008-DST-US06-FUDS-0-20120813.xlsx
├── A123_DST-US06-FUDS-20/
│   └── DST-US06-FUDS-20/
│       ├── A1-007-DST-US06-FUDS-20-20120817.xlsx
│       └── A1-008-DST-US06-FUDS-20-20120817.xlsx
├── A123_OCV20-20120614/
│   └── OCV20-20120614/
│       ├── A1-007-OCV20-20120614.xlsx
│       └── A1-008-OCV20-20120614.xlsx
...
```

### Glob Patterns Used by Loader
In `src/soc/data/calce_loader.py` and `scripts/evaluate_calce.py`:
- OCV folders: `*OCV{temp}-*` (or `*OCV-10*` for $-10^\circ\text{C}$, `*OCV25*` for $25^\circ\text{C}$).
- Dynamic cycle folders: `*DST-US06-FUDS-{temp}*` (or `*DST-US06-FUDS-N10*` for $-10^\circ\text{C}$).
- Excel files: `*{cell}*.xlsx` within resolved cycle directories.
- Canonical time-series sheet: starts with `Channel_1-`.

### Tests Requiring CALCE Raw Data
Tests needing raw data files are marked with `@pytest.mark.requires_data`. If raw data is absent or `SOC_DATA_DIR` is unset/invalid, these tests gracefully skip:
- `tests/test_bms_soc_ref.py::test_bms_soc_ref_agreement_with_repo_e7v3_on_dst`: Runs a full 25,000-step DST cycle to verify numerical parity between `deliverable/bms_soc_ref.py` and `src/soc/estimators/e7v3.py`.
- Benchmark evaluation scripts: `scripts/evaluate_calce.py`, `scripts/gauntlet_v3_scenarios.py`.

---

## 2. FlexiPod-1 Dataset (Evaluation Candidate)

- **Source**: FlexiPod 100 Ah commercial pouch cell characterization dataset.
- **Status**: Research evaluation completed; 2RC open-loop model gate failed (NO-GO for transfer).
- **Expected Directory**: `data/raw/flexipod/`
  - `OCV_and_HPPC_data_of_cells.xlsx`
  - `Temperature_based_V_curves.xlsx`
- **Integrity Manifest**: `data/raw/flexipod/manifest.sha256`.

---

## 3. Data Integrity & Checksums

The SHA-256 fingerprint of every uncompressed workbook and archive in `data/raw/calce_a123` is recorded in `data/MANIFEST_calce_a123.sha256`. To regenerate or verify:
```bash
python scripts/make_data_manifest.py
```
