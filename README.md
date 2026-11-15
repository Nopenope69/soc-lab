# SOC Estimation Lab: Research Handover

A rigorous benchmark harness and reference implementation repository for battery **State of Charge (SOC)** estimation on **Lithium Iron Phosphate (LFP / $\text{LiFePO}_4$)** chemistry.

---

## 1. Project Status & Research Scope

This repository constitutes a **RESEARCH HANDOVER** for closed-loop battery state estimation. 

### Current Primary Candidate: E7v3
The primary research candidate is **E7v3** (`E7V3CompositeFilter` in research, and `deliverable/bms_soc_ref.py` for deployment reference). E7v3 is a confidence-aware composite Extended Kalman Filter featuring:
- **Observability-Gated Voltage Feedback**: Suppresses divergence in the flat LFP plateau ($0.12\text{ to }0.25\text{ mV/pp}$) via dynamic slope thresholding and adaptive innovation step capping.
- **Joseph-Form Stabilized Covariance**: Maintains positive semi-definiteness under single-precision float32 execution.
- **Online $R_0$ Tracking via RLS**: Recursive Least Squares parameter tracking with hysteresis-aware decoupling.
- **Confidence-Aware Re-Initialization**: Recovers rapidly from uncalibrated / wrong initial SOC states without resting periods.

---

## 2. Validation Status: What Is Validated vs What Is NOT

> [!IMPORTANT]
> **VALIDATED (Certified Development Scope):**
> - **Specimens**: CALCE A123 Systems ANR26650M1-A (26650 cylindrical form-factor, $1.11\text{ Ah}$ calibrated baseline) cells (`A1-007` primary development, `A1-008` transfer check).
> - **Certified Thermal Envelope**: **20 °C to 50 °C** (evaluated at 20, 25, 30, 40, and 50 °C).
> - **Drive Cycles**: Dynamic driving profiles (DST, US06, FUDS) on laboratory cycler data.
> - **Fault Recovery**: Tested against sensor gain errors ($\pm 2\%$), persistent voltage sensor bias ($+50\text{ mV}$), and wrong starts ($-50\text{ pp}$, $-20\text{ pp}$, $+10\text{ pp}$).
> - **Numerical Equivalence**: The standalone standard library deliverable (`deliverable/bms_soc_ref.py`) matches the research filter to within $\le 10^{-12}$ on valid inputs across 25,000+ steps.

> [!CAUTION]
> **NOT VALIDATED (Explicit Out-of-Scope & Non-Deployment Warnings):**
> 1. **FlexiPod Deployment Gate: FAIL / NO-GO**  
>    Transfer to FlexiPod 100 Ah commercial cells was evaluated (`reports/flexipod1/`). The open-loop 2RC model gate failed across all held-out dynamic curves (voltage RMSE up to $87.4\text{ mV}$, implied SOC error up to $233\text{ pp}$). Transfer is blocked pending electrochemical impedance re-characterization and electro-thermal coupling. **Deployment on FlexiPod is NOT approved.**
> 2. **Field / On-Vehicle Operation**  
>    All validations were performed on laboratory Arbin cycler data. The algorithms have not been field-validated in operational vehicles, marine packs, or grid storage racks.
> 3. **Sub-20 °C Operation**  
>    Evaluated at 10 °C, 0 °C, and -10 °C. While numerical stability holds (zero state explosion), convergence rates degrade gracefully due to a 4.5x impedance surge and severe hysteresis widening. Sub-20 °C deployment requires cold-temperature calibration tables.
> 4. **State of Health (SOH)**  
>    This codebase estimates State of Charge ($z_k$). It does NOT estimate online capacity degradation or battery aging.

---

## 3. Installation & Optional Extras

The repository uses modern `pyproject.toml` packaging with modular extras to avoid forcing heavy machine-learning dependencies:

| Extra | Included Dependencies | Intended Use | Installation Command |
|:---|:---|:---|:---|
| **Core** | `numpy`, `scipy`, `pydantic`, `pyyaml` | Production BMS reference & core estimators | `pip install -e .` |
| **`dev`** | Core + `pytest` | Standard development & test suite | `pip install -e ".[dev]"` |
| **`research`** | Core + `matplotlib`, `pandas`, `openpyxl` | Generating plots, reports, and ingesting Excel data | `pip install -e ".[research]"` |
| **`neural`** | Core + `torch`, `lightgbm` | Experimental hybrid models (E8, E9, E10) | `pip install -e ".[neural]"` |
| **`all`** | All extras combined | Complete research and evaluation environment | `pip install -e ".[all]"` |

### Quick Virtual Environment Setup
```bash
make venv       # Creates .venv and installs with [dev] extra
source .venv/bin/activate
```

---

## 4. Dataset Setup & Configuration

Raw dataset files are not committed to git per repository hygiene rules.

1. **Set Dataset Directory**:
   Set `SOC_DATA_DIR` in your environment (defaults to `data/raw`):
   ```bash
   export SOC_DATA_DIR=/path/to/raw/datasets
   ```
2. **Directory Layout**:
   ```text
   $SOC_DATA_DIR/
   ├── calce_a123/          # 36 CALCE Excel workbooks (DST, US06, FUDS, OCV)
   └── flexipod/            # FlexiPod OCV and temperature discharge curves
   ```
3. **Data Integrity & Test Skipping**:
   - `data/MANIFEST_calce_a123.sha256`: SHA-256 checksums for every raw workbook file.
   - Tests requiring raw data are marked with `@pytest.mark.requires_data`. On a clean checkout without data, these tests skip cleanly with an explicit notice naming the missing path.

---

## 5. Estimator Identifier Map

Estimator implementations are registered in `soc.estimators.registry`:

| Identifier | Candidate Status | Description | Required Extra |
|:---|:---:|:---|:---:|
| **`e7v3`** | **Research Candidate** | Confidence-aware composite EKF with observability gating and RLS $R_0$ | Core |
| **`E0`** | Baseline | Coulomb counting with capacity scaling and rest/charge anchors | Core |
| **`E1`** | Baseline | Standard Thevenin 2RC Extended Kalman Filter | Core |
| **`E2`** | Baseline | Anchored Extended Kalman Filter with hysteresis state | Core |
| **`E3`** | Baseline | Unscented Kalman Filter (UKF) | Core |
| **`E4`**, **`e4v2`**| Prototype | EKF with online Recursive Least Squares (RLS) $R_0$ tracking | Core |
| **`E5`**, **`e5v4`**| Prototype | Observability-gated EKF variants | Core |
| **`E6`** | Prototype | RBC Dual EKF | Core |
| **`e7v2`** | Prototype | Intermediate composite filter | Core |
| **`E7`** | **Deprecated** | Deprecated unversioned alias; raises `NotImplementedError` directing to `e7v3` | Core |
| **`E8`**, **`e8`** | Experimental | Hybrid 2RC + Gated Recurrent Unit (GRU) residual model | `neural` |
| **`E8-LGBM`** | Experimental | Hybrid 2RC + LightGBM gradient-boosted tree residual model | `neural` |
| **`E9`** | Experimental | Temporal Convolutional Network (TCN) + UKF dual-observation | `neural` |
| **`E10`** | Experimental | Physics-Informed Neural Network (PINN) + Adaptive EKF | `neural` |

---

## 6. Makefile Targets

```bash
make venv      # Create .venv and install package with development extras
make install   # Install editable package into current active environment
make test      # Run full test suite without pytest cache provider
make smoke     # Run fast smoke evaluation scenario (<60s) for E0, E1, E2
make clean     # Remove build artifacts, pycache, and temporary test outputs
```

---

## 7. Deliverable Assets Layout

The `deliverable/` directory contains certified assets for standalone BMS integration:

```text
deliverable/
├── bms_soc_ref.py            # Zero-dependency, pure Python standard library E7v3 reference
├── calibration.py            # Certified CellCalibration contract with strict validation
├── calibrations/
│   ├── calce_a123_v4.json    # Validated CALCE A123 26650 20–50 °C calibration profile
│   └── flexipod_100ah_v1.json# FlexiPod profile (marked NOT_VALIDATED)
├── golden/
│   ├── golden_synthetic_dynamic.csv  # 25,000-step dynamic verification vector
│   ├── golden_synthetic_dropouts.csv # 25,000-step sensor dropout verification vector
│   └── README.md                     # Verification tolerances and replay instructions
└── READY_CRITERIA.md         # Production readiness and safety guardrail checklist
```

*(Experimental neural weights were relocated to `models/experimental/`).*

---

## 8. Command-Line Interface (CLI)

The `soc` CLI supports benchmark execution, parameter sensitivity sweeps, and report rendering:

```bash
# Run benchmark scenarios (flags: --csv / --output-csv, --report / --output-report)
soc run --scenario smoke --profile automotive --csv reports/smoke_results.csv --report reports/smoke_report.md

# Parameter sensitivity sweep example (evaluates E2 under varying voltage noise covariance R_v)
soc sweep --param filter.measurement_noise_r_v --values 1e-6,2.5e-5,1e-4 --estimator E2 --scenario smoke --output-csv reports/sweep_results.csv

# Render report from CSV (flags: --csv, --report / --output / --output-report)
soc report --csv reports/smoke_results.csv --report reports/smoke_report.md
```

---

## 9. Key Engineering Findings & Limitations

1. **The Plateau Observability Trap**:  
   In LFP cells, the central plateau (20% to 80% SOC) exhibits an ultra-flat slope ($0.12\text{ to }0.25\text{ mV/pp}$). In this region, a tiny $3\text{ mV}$ sensor error translates to $20\text{ pp}$ of implied SOC error. Un-gated Kalman filters diverge under bias; E7v3's observability gate caps innovation to prevent runaway error.
2. **Constant-Current vs Dynamic Excitation**:  
   On steady constant-current discharge without current fluctuations, Coulomb counting with known capacity is mathematically optimal. Kalman filters only outperform Coulomb counting when dynamic excitation (acceleration pulses, regenerative braking, or rest relaxation) makes open-circuit voltage observable.
3. **Recovery Time Horizon**:  
   When initialized with a completely wrong initial state (e.g. uncalibrated sleep wake-up at 50% true SOC with 0% estimate), E7v3 recovers to within 5 pp error in **~44 minutes median** and **~77 minutes p90** across dynamic cycles.
