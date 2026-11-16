# SOH Evidence and Dataset Provenance Inventory

> **Auditor**: Antigravity SOH Validation Team  
> **Date**: 2026-11-16  
> **Scope**: Independent audit of all data sources, file trees, loaders, and benchmark results supporting state-of-health (SOH) estimation.  
> **Rule Compliance**: Download nothing; verify solely against files present on disk.

---

## 1. Summary of Datasets on Disk

| Dataset Identifier | Physical Disk Location | Manifest Status | Contents Description | Usability for Longitudinal SOH Aging |
| :--- | :--- | :--- | :--- | :--- |
| **CALCE A123 Dynamic Cycles** | `data/raw/calce_a123/` | 52 verified hashes in `data/manifests/calce_a123.sha256` | 38 Excel workbooks (`.xlsx`/`.xls`) across 2 cells (A1-007, A1-008) at temperatures from -10°C to +50°C. Contains DST, US06, FUDS drive cycles and low-rate OCV tests. | **UNUSABLE for SOH aging**. These are single-cycle dynamic test profiles used for SOC validation. They do not track capacity fade or cycle degradation over life. |
| **FlexiPod BOL** | `data/raw/flexipod/` | Local raw directory | BOL characterization logs: 0.1C OCV curve, 0.5C capacity check, and HPPC pulses at BOL. | **UNUSABLE for SOH aging**. BOL characterization only (cycle count = 1). |
| **Gustave Eiffel 105Ah** | `$SOC_DATA_DIR/gustave_eiffel_105ah` | Hash manifest in `data/manifests/` | Dynamic operating profiles on 105 Ah prismatic cells. | **UNUSABLE for SOH aging**. SOC validation cycles; no aging history. |
| **Tempest 280Ah** | `$SOC_DATA_DIR/tempest_280ah` | Hash manifest in `data/manifests/` | Dynamic operating profiles on 280 Ah utility cells. | **UNUSABLE for SOH aging**. SOC validation cycles; no aging history. |
| **UConn REIL** | `$SOC_DATA_DIR/uconn_reil` | Hash manifest in `data/manifests/` | Secondary use profile cycling logs. | **UNUSABLE for SOH aging**. Operating cycles without standardized periodic SOH capacity/DCIR checkups. |
| **Wheeler A123** | `$SOC_DATA_DIR/wheeler_a123` | Empty directory (0 files) | Empty directory. | **NOT LOADABLE** (0 files on disk). |
| **CALCE CS2 Aging Series** | Not present | No files | Longitudinal cycling to end-of-life on prismatic CS2 cells. | **NOT PRESENT** (0 files on disk). |
| **Oxford Battery Intelligence Lab** | Not present | No files | Kokam 740 mAh pouch cells cycled at 40°C. | **NOT PRESENT** (0 files on disk). |
| **MIT/Stanford Fast Charging (Severson 2019)** | Not present | No files | 124 APR18650M1A cells cycled to failure under varied fast-charging policies. | **NOT PRESENT** (0 files on disk). |

---

## 2. Inventory of Historical SOH Benchmark Results

Every SOH benchmark result reported across Phases 1 through 6.3 was generated using either **analytical synthetic generators** or **PyBaMM electrochemical simulation**, not physical aged cell data files:

### Phase 1: Baseline Degradation
- **Data Source**: `SyntheticAgingGenerator` (`src/soh/data/synthetic_aging.py`).
- **Mechanism**: Synthetic square-root power law ($\text{fade} \propto k^{0.5}$) with pseudo-random seed noise.
- **Classification**: **SIMULATION / SYNTHETIC**.

### Phase 2: Pulse ECM & ElasticNet
- **Data Source**: `SyntheticAgingGenerator` + exploratory parse of 6 CALCE dynamic files in `scripts/run_soh_phase2.py`.
- **Finding**: The CALCE dynamic files yielded only single-cycle instantaneous voltage drops, not longitudinal aging. Training and testing were conducted on `SyntheticAgingGenerator`.
- **Classification**: **SIMULATION / SYNTHETIC**.

### Phase 3: ICA + GPR-EKF
- **Data Source**: `SyntheticAgingGenerator`.
- **Mechanism**: Simulated constant-current charging sweeps with synthesized Gaussian differential capacity peaks.
- **Classification**: **SIMULATION / SYNTHETIC**.

### Phase 4: SOH Fusion Tracker
- **Data Source**: `SyntheticAgingGenerator` multi-feature streams.
- **Mechanism**: Joint Kalman filtering of synthetic ICA and synthetic pulse features.
- **Classification**: **SIMULATION / SYNTHETIC**.

### Phase 5, 5.1, 5.2: Physics-Informed Neural Network (PINN)
- **Data Source**: `PyBammAgingSimulator` (`src/soh/data/pybamm_simulator.py`).
- **Mechanism**: Single Particle Model with electrolyte (SPMe) and SEI growth kinetics parameterized by Chen 2020 (LG M50T 21700 NMC-811 / graphite).
- **Classification**: **SIMULATION (PyBaMM)**.

### Phase 6: Shadow Integration & Reference Validation
- **Data Source**: `RealCellDataLoader` (`src/soh/data/real_cell_adapters.py`).
- **Finding**: Despite method names `load_calce_a123`, `create_oxford_reference_cohort`, and `create_mit_stanford_reference_cohort`, these adapters did not read disk files; they synthesized data in-memory via mathematical formulas with `np.random.default_rng`.
- **Classification**: **SIMULATION / SYNTHETIC**.

### Phase 6.1: Benchmark Integrity Audit
- **Data Source**: `real_cell_adapters.py` (synthetic formulas) + PyBaMM simulations.
- **Classification**: **SIMULATION / SYNTHETIC**.

### Phase 6.2: Production Prototype Qualification
- **Data Source**: `real_cell_adapters.py` (MIT knee-point formula) + `StandardizedHppcCohortGenerator` (60 synthetic 1-RC ECM pulses).
- **Classification**: **SIMULATION / SYNTHETIC**.

### Phase 6.3: Hardware Qualification
- **Data Source**: Synthetic formulas + host CPU execution profiling.
- **Classification**: **SIMULATION / SYNTHETIC**.

---

## 3. Conclusions and Governance Actions

1. **No Physical Aged Data Exists in the Pipeline**: All current SOH models are calibrated and verified solely against synthetic mathematical formulas or physics simulations.
2. **Resistance SOH ($SOH_R$) is Completely Unvalidated**: No physical cell DCIR measurements have been ingested or evaluated.
3. **Qualification Demotion**: In accordance with rule R5 and Hardening 2 standards, all SOH estimators must carry status `SIM_VALIDATED`, `EXPERIMENTAL`, or `UNVALIDATED`. No estimator may claim `LAB_VALIDATED` until verified physical laboratory aging datasets with valid SHA-256 manifests are ingested.
