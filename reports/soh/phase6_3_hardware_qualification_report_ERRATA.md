# ERRATA: SOH Phase 6.3 Experimental Hardware Validation Report

> **Status Notice**: The "Hardware-in-the-Loop Edge Qualification" and "Real Cell Datasets" discussed in `reports/soh_phase6_3_hardware_qualification_report.md` reflect analytical simulation and host timing measurements, not physical laboratory cell or MCU testing.

---

## 1. Provenance and Qualification Clarifications

### Section 1: Estimator Qualification Status Reconciliations
- The discrepancies between the Phase 6.2 qualification matrix and benchmark evaluation tables are confirmed:
  1. Pulse ECM: 1.919% RMSE in synthetic HPPC cohort vs 0.35% theoretical figure in early mock tables.
  2. Empirical Power Law: 0.812%–0.885% batch holdout RMSE vs 0.21%–0.25% in idealized unperturbed fits.
  3. GRU Uncertainty: Interval coverage failed in mid-life (72.7%) and EOL (0.0%).

### Section 2: HPPC Data Provenance Audit
- `StandardizedHppcCohortGenerator` was audited and classified as **SIMULATION VALIDATION ONLY**. No physical HPPC pulses were acquired or evaluated.

### Section 3: Physical Cell Protocols
- The test matrices outlined for CALCE CS2, Oxford Kokam, and MIT Severson cells describe proposed or synthetic analytical approximations:
  - Oxford: Synthesized via $\text{fade} = 0.0012 \cdot k^{0.55} + 0.00015 \cdot k$.
  - MIT: Synthesized via sigmoid knee-rollover formula.
  - CALCE: Synthesized via power-law fade.
- Physical cell verification of DCIR and resistance aging ($SOH_R$) has **NOT** been performed. SOH_R remains **UNVALIDATED** on physical hardware.

### Section 4: Edge Timing and Resource Footprint
- The execution times (e.g. 0.035 µs, 0.42 ms, 2.85 ms) were measured on an x86/ARM host CPU (Apple Silicon / Darwin workstation), not an embedded microcontroller (ARM Cortex-M4/M33).
- These figures represent host analytical timings, not verified Worst-Case Execution Times (WCET) on embedded target hardware.

---

## 2. Updated Status
All candidate estimators are classified as **`SIM_VALIDATED`** only. Physical cell qualification status is **`UNVALIDATED`**.
