# ERRATA: SOH Phase 6 Shadow Execution and Validation Report

> **Status Notice**: All references to "Real-Cell Reference Cohorts" (CALCE, Oxford, MIT/Stanford) in `reports/soh_phase6_shadow_validation_report.md` refer to **synthetically generated datasets** constructed from mathematical functions with seeded pseudo-random noise.

---

## 1. Provenance Audit Findings

In `reports/soh_phase6_shadow_validation_report.md` Section 3 ("Independent Validation on Real-Cell Reference Datasets"), the following datasets were evaluated:
- CALCE A123 (LFP/Graphite)
- Oxford Kokam 740mAh (NMC-LCO/Graphite)
- MIT/Stanford Fast Charging (LFP/Graphite)

Audit of `src/soh/data/real_cell_adapters.py` confirms that:
1. No raw experimental cycler files from CALCE, Oxford, or MIT were loaded.
2. The data was generated analytically using:
   - CALCE: $\text{fade}_c = 0.00045 \cdot k + 0.000008 \cdot k^{1.35}$
   - Oxford: $\text{fade} = 0.0012 \cdot k^{0.55} + 0.00015 \cdot k$
   - MIT: sigmoid knee fade centered at cycle 45
3. Resistance values were computed via deterministic algebraic functions of cycle index $k$.
4. Cell IDs and Batch IDs have been retroactively renamed with `SYN_` prefixes (`SYN_CALCE_CS2_35`, `SYN_OXFORD_CELL_01`, `SYN_MIT_CELL_...`, `SYN_BATCH_...`).

---

## 2. Status Reclassification

- **Shadow Framework Architecture**: The dual-track execution framework (Primary Estimator + Shadow Tracker + Telemetry Logging) is verified as valid software architecture.
- **Validation Status**: The quantitative results demonstrate model convergence and logging integrity under **simulation conditions (`SIM_VALIDATED`)**.
- **Hardware Qualification**: Physical cell aging validation and resistance tracking ($SOH_R$) remain **`UNVALIDATED`**.
