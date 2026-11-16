# CALCE A123 Cell Identity & Capacity Conflict Audit

## 1. Executive Summary

This audit investigates the cell identity, physical form factor, and nominal capacity contradictions for the **CALCE A123 LFP Battery Dataset** located at `data/raw/calce_a123`.

Historically, across different iterations of `soc-lab` and prior publications, this dataset was variously designated as:
- **Form Factor:** "26650 cylindrical (ANR26650M1-A)", "18650 cylindrical", or "Pouch".
- **Nominal Rating:** "1.1 Ah", "1.11 Ah", "1.2 Ah", "2.2 Ah", or "2230 mAh".

This audit establishes the empirical ground truth directly from the 52 raw spreadsheet files on disk and defines the engineering protocol going forward.

---

## 2. Empirical Ground Truth from Disk

### 2.1 File Evidence & Measured Capacities
The raw files at `data/raw/calce_a123` (52 files verified against `calce_a123.sha256`) comprise C/20 quasi-static open-circuit voltage tests (`OCV`) and dynamic pulse/drive cycles (`DST`, `US06`, `FUDS`) tested across eight chamber temperatures: $-10^\circ\text{C}$, $0^\circ\text{C}$, $10^\circ\text{C}$, $20^\circ\text{C}$, $25^\circ\text{C}$, $30^\circ\text{C}$, $40^\circ\text{C}$, and $50^\circ\text{C}$ on two test specimens (`A1-007` and `A1-008`).

Across all temperatures and test profiles, the raw measured C/20 discharge capacity ranges from **$\approx 1.042\text{ Ah}$ to $\approx 1.105\text{ Ah}$**:

| Temperature | Cell `A1-007` Measured C/20 Capacity | Cell `A1-008` Measured C/20 Capacity | Spread (`A1-008` vs `A1-007`) |
| :---: | :---: | :---: | :---: |
| **$-10^\circ\text{C}$** | $1.0600\text{ Ah}$ | $1.0791\text{ Ah}$ | $+1.80\%$ |
| **$0^\circ\text{C}$** | $1.0512\text{ Ah}$ | $1.0734\text{ Ah}$ | $+2.11\%$ |
| **$10^\circ\text{C}$** | $1.0485\text{ Ah}$ | $1.0692\text{ Ah}$ | $+1.97\%$ |
| **$20^\circ\text{C}$** | $1.0588\text{ Ah}$ | $1.0821\text{ Ah}$ | $+2.20\%$ |
| **$25^\circ\text{C}$ (Reference)** | **$1.0636\text{ Ah}$** ($1063.6\text{ mAh}$) | **$1.0879\text{ Ah}$** ($1087.9\text{ mAh}$) | **$+2.28\%$** |
| **$30^\circ\text{C}$** | $1.0682\text{ Ah}$ | $1.0931\text{ Ah}$ | $+2.33\%$ |
| **$40^\circ\text{C}$** | $1.0764\text{ Ah}$ | $1.1015\text{ Ah}$ | $+2.33\%$ |
| **$50^\circ\text{C}$** | $1.0811\text{ Ah}$ | $1.1052\text{ Ah}$ | $+2.23\%$ |

### 2.2 Specimen-to-Specimen Systematic Difference
- Specimen `A1-008` delivers systematically **$\approx 1.5\%$ to $2.5\%$ higher capacity** than specimen `A1-007` consistently across all thermal chambers.
- Neither cell delivers anything close to $2.0\text{ Ah}$ or $2.3\text{ Ah}$. Under dynamic loading at $-10^\circ\text{C}$, delivered discharge capacity drops to $0.7351\text{ Ah}$ (`A1-007`) and $0.4366\text{ Ah}$ (`A1-008`) due to terminal voltage cutoff at $2.0\text{ V}$.

---

## 3. The Contradiction with External CALCE Documentation

### 3.1 Website Claim: 2230 mAh
On the public CALCE battery data archive landing page (`https://calce.umd.edu/data` and `https://web.calce.umd.edu/batteries/data/`), the description for the A123 battery test dataset cites a nominal capacity of **"2230 mAh"** (or 2.2 Ah / 2.3 Ah).

This represents a **$2.1\times$ contradiction** with the actual time-series test files in that exact archive:
$$\frac{\text{CALCE Website Rating}}{\text{Actual Test File Measurements}} = \frac{2230\text{ mAh}}{1063.6\text{ mAh}} \approx 2.097$$

### 3.2 Literature Citation
The journal publication commonly associated with this dataset is:
> W. He, N. Williard, C. Chen, and M. Pecht, *"State of charge estimation for LiFePO4 batteries including thermal effects"* International Journal of Electrical Power & Energy Systems, vol. 62, pp. 783–791, 2014.

While this paper describes testing A123 LiFePO4 cells under similar thermal profiles, neither the paper nor the raw spreadsheet metadata contains a direct DOI link or verified physical specimen dimensions.

---

## 4. The Form Factor Ambiguity: 18650 vs 26650

A123 Systems historically produced two well-known commercial cylindrical cells with Nanophosphate® LiFePO4 chemistry:
1. **APR18650M1A / APR18650M1B:** 18650 cylindrical form-factor ($18\text{ mm} \times 65\text{ mm}$), nominal rated capacity **$1.1\text{ Ah}$ ($1100\text{ mAh}$)**.
2. **ANR26650M1A / ANR26650M1B:** 26650 cylindrical form-factor ($26\text{ mm} \times 65\text{ mm}$), nominal rated capacity **$2.3\text{ Ah} - 2.5\text{ Ah}$ ($2300 - 2500\text{ mAh}$)**.

### Why Neither Can Be Asserted from Raw Files
1. The spreadsheet files (`.xlsx` and `.xls`) contain strictly electrical and environmental telemetry: timestamp, step index, cycle count, current, voltage, charge/discharge capacity, and thermocouple temperature.
2. No dimensional data, physical mass, photograph, barcode, or cell model string appears in the raw data files.
3. Two competing hypotheses explain the discrepancy:
   - **Hypothesis A (Mislabeled Form Factor):** The physical specimens were actually 18650 cells (`APR18650M1A`, nominal $1.1\text{ Ah}$, closely matching the measured $1.0636\text{ Ah}$ at 25°C), but were mislabeled as 26650 on the CALCE website.
   - **Hypothesis B (Degraded / Sub-Cycled 26650):** The physical specimens were heavily degraded 26650 cells, or sub-cells cycled over restricted windows.

Because raw file evidence alone cannot conclusively verify or refute either hypothesis without inventing external facts:
> **We assert NEITHER 18650 nor 26650.**
> The official form factor is catalogued as `UNVERIFIED`.

---

## 5. Engineering Protocol & Policy

To guarantee scientific rigor, benchmark integrity, and zero fabrication:
1. **Form Factor:** Explicitly marked as `cell_form_factor = "UNVERIFIED"`. Never hardcode `26650` or `18650` as an established fact for CALCE A123.
2. **Nominal Capacity Baseline:** Algorithms and evaluators must baseline SOH_C and SOC Coulomb counting **strictly against the measured BOL capacity of each physical cell** (e.g. $1.0636\text{ Ah}$ for `A1-007` at 25°C, $1.0879\text{ Ah}$ for `A1-008` at 25°C), never a generic catalog rating.
3. **Registry and Manifest Description:**
   `A123 LiFePO4, measured capacity about 1.06 Ah (A1-007) and about 1.09 Ah (A1-008) at 25 C, format UNVERIFIED`
4. **Frozen Files Preserved:** Frozen files (`calce_a123_v4.yaml`, estimator baselines) retain historical references without modification to guarantee absolute determinism and reproducible regression checks.

---

## 6. Errata Note: Historical Reports Coverage

> [!NOTE]
> **ERRATUM — Historical CALCE Cell Identity Designations**
>
> Historical test and evaluation reports in `reports/` and `reports/soh/`—including:
> - `reports/soh_phase3_ica_gpr_ekf_report.md`
> - `reports/soh_phase4_1_audit_report.md`
> - `reports/soh_phase5_1_pinn_audit_report.md`
> - `reports/soh_phase6_1_production_qualification_report.md`
> - `reports/soh_phase6_shadow_validation_report.md`
> - `reports/handover/float32_sensitivity.md`
> - `reports/gauntlet_v3/*`
>
> contain historical assertions referring to the CALCE A123 cells as "26650 cylindrical", "ANR26650M1-A", "18650 cylindrical", or "APR18650M1A". Per the frozen baseline preservation rules, these historical artifacts are kept unmodified. All future development, documentation, and production qualifications designate these cells strictly as:
>
> **"A123 LiFePO4, measured capacity about 1.06 Ah (A1-007) and about 1.09 Ah (A1-008) at 25 C, format unverified"**.

---

## 7. Inventory of Harmonized Repository Files (F1)

The following active files across configs, source code, scripts, and documentation were updated to replace unverified format assertions with the standardized description:

1. **Configurations & Profiles:**
   - `configs/assumptions/base.yaml`
   - `configs/assumptions/profiles/calce_a123.yaml`
   - `configs/assumptions/profiles/calce_a123_v2.yaml`
   - `configs/assumptions/profiles/calce_a123_v2_m0.yaml`
   - `configs/assumptions/profiles/calce_a123_v3.yaml`
   - `configs/assumptions/profiles/calce_a123_a1008.yaml`
   - `configs/assumptions/profiles/calce_a123_a1008_v2.yaml`
   - `configs/assumptions/profiles/calce_a123_a1008_v2_m0.yaml`
2. **Source Code & Deliverables:**
   - `src/soc/data/calce_loader.py`
   - `src/soh/data/calce_aging.py`
   - `src/soh/data/real_cell_adapters.py`
   - `deliverable/README.md`
   - `deliverable/calibration.py`
3. **Scripts & Pipeline Tools:**
   - `scripts/evaluate_calce.py`
   - `scripts/flexipod/ocv_hysteresis_fp.py`
   - `scripts/gauntlet_stage1.py`
   - `scripts/generate_final_documents.py`
   - `scripts/identify_calce_params.py`
   - `scripts/identify_calce_params_v2.py`
   - `scripts/make_release_manifest.py`
   - `scripts/run_soh_phase6_1_audit.py`
   - `scripts/run_soh_phase6_shadow_validation.py`
   - `scripts/stage_v1_model.py`
4. **Documentation:**
   - `README.md`
   - `data/README_DATA.md`
   - `docs/ALGORITHM_SPEC.md`
   - `PLAN_ADAPTER.md`

