# Specification: Lithium-Ion Battery SOH Estimation Subsystem

**Document Version:** 1.0.0  
**Date:** 2026-11-15  
**Scope:** Lithium-ion Battery State of Health (SOH) Estimation for EV and BESS applications  
**Integration:** Coexists with `src/soc/` (SOC Estimation Lab) in directory `src/soh/` without breaking or altering SOC functionality.

---

## 1. Executive Summary & Goals

This specification defines the architecture, data contracts, mathematical formulations, quality layers, baseline models, and benchmarking harness for battery State of Health (SOH) estimation.

Real-world deployment demands that an SOH algorithm survive non-ideal operating conditions: partial charge segments, temperature variations, sensor noise, relaxation periods, and cell chemistry divergence. Rather than relying solely on deep neural networks on full laboratory charge-discharge cycles, this subsystem provides a modular, multi-pipeline architecture:
1. **Separation of SOH States**: Distinct $SOH_C$ (Capacity retention) and $SOH_R$ (Resistance health) state variables with rigorous Reference Measurement Protocols.
2. **Quality & Observability**: Strict feature quality validation (derivative SNR, ECM parameter conditioning, relaxation time) and window eligibility gates.
3. **Pluggable Estimators**: Standardized interface supporting offline training, online step prediction, and state updates across empirical, physical, and embedded models.
4. **Uncertainty-Aware Fusion**: Tracking engine handling intermittent updates, correlated errors via Covariance Intersection, and innovation gating.
5. **Phase 1 Focus**: Data contracts, reference protocols, dataset loaders, ground-truth generation, baseline regression, and test harnesses.

---

## 2. Directory Layout & Module Responsibilities

```
src/soh/
├── __init__.py
├── common/
│   ├── __init__.py
│   ├── contracts.py          # Data contracts: Measurement, CycleRecord, SOHState, Window
│   ├── protocols.py          # CellReferenceSpec & Reference Measurement Protocols (C_ref, R_ref)
│   ├── units.py              # Canonical units (V, A, s, °C, Ah, Ohm) and sign conventions
│   └── eligibility.py        # Window eligibility checks & INSUFFICIENT_INFORMATION outcome
├── data/
│   ├── __init__.py
│   ├── base_loader.py        # Abstract aging dataset loader
│   ├── calce_aging.py        # CALCE cycle aging dataset parser (CS2 / A123)
│   ├── synthetic_aging.py    # Physics-based electrochemical synthetic aging generator
│   └── window_extractor.py   # Partial-charge window segmentation & metadata extraction
├── degradation/
│   ├── __init__.py
│   ├── mechanisms.py         # Calibrated degradation kinetics (SEI solvent diffusion, LLI, LAM)
│   ├── reversible.py         # Reversible effects (temperature Arrhenius scaling, hysteresis, relaxation)
│   └── state.py              # True internal degradation state container
├── features/
│   ├── __init__.py
│   ├── quality.py            # Quality metrics: derivative SNR, temperature drift, current stability
│   ├── ica.py                # dQ/dV filtering, peak tracking, area extraction & eligibility
│   ├── dva.py                # dV/dQ differential voltage analysis
│   └── pulse_ecm.py          # Transient pulse extraction & 2-RC parameter identification
├── estimators/
│   ├── __init__.py
│   ├── base.py               # SohEstimator abstract base class & SupportsEmbeddedExport mixin
│   ├── baseline_ridge.py     # Conventional regularized Ridge baseline (Phase 1)
│   ├── pulse_elastic_net.py  # UConn 2-RC ECM + ElasticNet pulse estimator (Phase 2)
│   ├── ica_gpr_ekf.py        # Kadem & Kim ICA feature + GPR measurement + EKF (Phase 3)
│   └── pinn_degradation.py   # Physics-informed neural network with SEI kinetics (Phase 5)
├── fusion/
│   ├── __init__.py
│   ├── covariance.py         # Cross-covariance & Covariance Intersection (CI) for correlated errors
│   ├── gating.py             # Mahalanobis outlier rejection & innovation gating
│   └── tracker.py            # Dual-state [SOH_C, SOH_R] adaptive Kalman tracker
├── embedded/
│   ├── __init__.py
│   ├── exporter.py           # Fixed-point C-header / micro-table code generator
│   └── benchmark.py          # Microcontroller profiling harness (RAM, Flash, latency, FLOPs)
└── benchmarks/
    ├── __init__.py
    ├── metrics.py            # RMSE, MAE, MaxError, 95th-pct, PICP, MPIW, Winkler score
    ├── split_runner.py       # Grouped leave-one-battery-out cross-validation
    └── report.py             # Benchmark report generation (Markdown & CSV)
```

---

## 3. Mathematical Formulations & Ground-Truth Reference Protocols

### 3.1 Canonical Units and Sign Conventions
* **Current $I$**: Matches the existing SOC lab:
  - $I > 0$: **Discharge** (cell gives power to load).
  - $I < 0$: **Charge** (charger delivers power to cell).
  - $I = 0$: **Rest**.
* **Voltage $V$**: Volts [V].
* **Time $t$**: Seconds [s].
* **Temperature $T$**: Degrees Celsius [°C] (internal thermodynamic equations convert to Kelvin [K] via $T_K = T + 273.15$).
* **Capacity $Q$**: Ampere-hours [Ah].
* **Resistance $R$**: Ohms [$\Omega$].

### 3.2 Cell Reference Protocols & Health Definitions
Health definitions cannot rely on unqualified nominal datasheet ratings. Instead, each cell type has a configurable `CellReferenceSpec`:

```python
class CellReferenceSpec(BaseModel):
    chemistry: str                     # e.g., "LFP", "NMC", "NCA"
    nominal_capacity_ah: float         # Nameplate rated capacity
    v_max: float                       # Upper cutoff voltage (e.g., 3.65 V for LFP, 4.20 V for NMC)
    v_min: float                       # Lower cutoff voltage (e.g., 2.00-2.50 V cell-specific)
    t_ref_c: float = 25.0              # Standard reference temperature (25 °C)
    c_rate_ref: float = 0.5            # Reference discharge C-rate (e.g. 0.5C or 1.0C)
    hppc_soc_ref: float = 0.5          # HPPC reference SOC (50% SOC)
    hppc_pulse_duration_s: float = 10.0# HPPC pulse duration (10s)
    hppc_pulse_c_rate: float = 1.0     # HPPC pulse rate (1C)
```

#### Dual Capacity SOH Metrics:
1. **Rated-Relative Capacity SOH ($SOH_{C,\text{rated}}$)**:
   $$SOH_{C,\text{rated}}(k) = \frac{C_{\text{actual}}(k, T_{\text{ref}}, I_{\text{ref}})}{C_{\text{rated}}(T_{\text{ref}})}$$
2. **Measured BOL-Relative Capacity Retention ($SOH_{C,\text{bol}}$)**:
   $$SOH_{C,\text{bol}}(k) = \frac{C_{\text{actual}}(k, T_{\text{ref}}, I_{\text{ref}})}{C_{\text{BOL}}(T_{\text{ref}}, I_{\text{ref}})}$$
   where $C_{\text{BOL}}$ is the measured usable capacity during cycle 0/1 reference discharge.

#### Dual Resistance SOH Metrics:
1. **Measured BOL-Relative Resistance SOH ($SOH_{R,\text{bol}}$)**:
   $$SOH_{R,\text{bol}}(k) = \frac{R_{\text{BOL}}(SOC_{\text{ref}}, T_{\text{ref}}, \Delta t_{\text{pulse}})}{R_{\text{actual}}(k, SOC_{\text{ref}}, T_{\text{ref}}, \Delta t_{\text{pulse}})}$$
2. **Rated-Relative Resistance SOH ($SOH_{R,\text{rated}}$)**:
   $$SOH_{R,\text{rated}}(k) = \frac{R_{\text{rated}}(SOC_{\text{ref}}, T_{\text{ref}}, \Delta t_{\text{pulse}})}{R_{\text{actual}}(k, SOC_{\text{ref}}, T_{\text{ref}}, \Delta t_{\text{pulse}})}$$
   where $R = \frac{V(t_0) - V(t_0 + \Delta t_{\text{pulse}})}{|I_{\text{pulse}}|}$.

---

## 4. Feature Quality & Window Eligibility Layers

### 4.1 Feature Quality Metrics
Features must not be accepted blindly. Every feature extractor emits a `FeatureQualityRecord`:
* **ICA / DVA Derivative Quality**:
  - Raw voltage quantization step test ($\Delta V_{\min} \ge 3 \times \text{ADC LSB}$).
  - Current stability: coefficient of variation $c_v = \frac{\sigma(I)}{|\mu(I)|} \le c_{v,\max}$ (default 0.03).
  - Temperature gradient: $|\frac{dT}{dt}| \le 0.02\,^\circ\text{C/s}$.
  - Differentiation conditioning: condition number of smoothing spline / Gaussian derivative filter.
* **Pulse / 2-RC Observability**:
  - Pulse magnitude: $|I_{\text{pulse}}| \ge 0.2 C$.
  - Normalized Jacobian condition number $\kappa(\mathbf{J}_{\text{norm}}^T \mathbf{J}_{\text{norm}}) \le \kappa_{\max}$ (default $10^4$).
  - Fit residual RMSE $\le 5\,\text{mV}$.
  - Parameter bounds check: $R_0, R_1, R_2 > 0$, $\tau_1, \tau_2 \in [\tau_{\min}, \tau_{\max}]$.
  - Post-pulse relaxation window duration $\ge 3 \times \tau_2$.

### 4.2 Window Eligibility & Observability
Partial-charge windows are verified against estimator-specific observability requirements:
* If a window fails the required criteria (e.g. charging window too short, current reversals during charging, excessive thermal drift), the pipeline returns an explicit outcome:
  `EstimationStatus.INSUFFICIENT_INFORMATION`.
* The BMS / supervisory loop does not produce a degraded or random estimate; it retains the prior state estimate with appropriate covariance propagation.

---

## 5. Degradation & Physics Modeling

The dedicated `src/soh/degradation/` module models physical mechanisms as calibrated domain assumptions, keeping irreversible degradation cleanly separated from reversible variations:

1. **Irreversible Degradation**:
   - SEI Solvent Diffusion Layer Growth:
     $$\frac{d\delta_{\text{SEI}}}{dt} = \frac{k_{\text{SEI}}}{2 \delta_{\text{SEI}}} \exp\left(-\frac{E_{a,\text{SEI}}}{R_g T}\right) \cdot \theta_{\text{anode}}$$
   - Loss of Lithium Inventory ($LLI$):
     $$\frac{d Q_{\text{LLI}}}{dt} = A_{\text{cell}} \cdot F \cdot \rho_{\text{Li}} \frac{d\delta_{\text{SEI}}}{dt}$$
   - Independent Resistance Growth ($R_0$ scaling with SEI film thickness and contact loss).
2. **Reversible Variations**:
   - Temperature dependence of resistance via Arrhenius relationship:
     $$R(T) = R_{\text{ref}} \exp\left(\frac{E_{a,R}}{R_g}\left(\frac{1}{T} - \frac{1}{T_{\text{ref}}}\right)\right)$$
   - Voltage relaxation kinetics and open-circuit voltage hysteresis.

---

## 6. Common Estimator Interface & Fusion Architecture

### 6.1 Unified Estimator Interface
```python
class SohEstimator(ABC):
    @abstractmethod
    def fit(self, dataset: "SohDataset") -> "SohEstimator":
        """Offline training / calibration on batch datasets."""
        ...

    @abstractmethod
    def predict_window(
        self,
        window: "PartialWindow",
        features: "SohFeatureRecord"
    ) -> "SohEstimate":
        """Compute point prediction, uncertainty, and status from a window."""
        ...

    @abstractmethod
    def update_state(
        self,
        current_state: "SOHState",
        estimate: "SohEstimate",
        dt: float
    ) -> "SOHState":
        """Discrete online state tracking update step."""
        ...
```
Optional C-header code export is exposed via the mixin `SupportsEmbeddedExport`:
```python
class SupportsEmbeddedExport(Protocol):
    def export_c_header(self, destination: Path) -> None:
        """Export fixed-point parameters and lookups to C header."""
        ...
```

### 6.2 Fusion Engine
* **Observation Mapping**: Separate observation matrices $\mathbf{H}_C = [1, 0]$ and $\mathbf{H}_R = [0, 1]$ allow processing scalar $SOH_C$, scalar $SOH_R$, or joint $[SOH_C, SOH_R]^T$ observations.
* **Correlated Error Handling**:
  - Independent estimates use standard Kalman update.
  - Correlated multi-estimator estimates mapped to the same state subspace are fused via **Covariance Intersection (CI)**:
    $$\mathbf{P}_{\text{CI}}^{-1} = \omega \mathbf{P}_1^{-1} + (1-\omega) \mathbf{P}_2^{-1}$$
* **Innovation Gating**: Outliers with Mahalanobis distance $d_M^2 > \chi^2_{p, 0.99}$ are flagged and rejected.
* **Timestamp & Stale Rejection**: Updates with observation age $\Delta t > \tau_{\text{stale}}$ are discarded.

---

## 7. Benchmarking & Validation Rigor

### 7.1 Cross-Validation Strategy
* **Grouped Battery-Level Splits**: Whole cells are held out (e.g. Leave-One-Battery-Out). Cycles from the same physical cell are never split across train and test.
* **Leakage-Free Preprocessing**: Scalers, feature normalizers, and PCA/POD bases are fit solely on training cells and applied to test cells.
* **Cross-Chemistry Validation**: Verification on both LFP (A123 / CALCE) and NMC (CS2 / LG) cells.

### 7.2 Uncertainty Metrics
Alongside point-error metrics (RMSE, MAE, MaxError, 95th percentile), regression uncertainty is scored via:
* **Prediction Interval Coverage Probability (PICP)**:
  $$\text{PICP} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}\left(y_i \in [\hat{L}_i, \hat{U}_i]\right)$$
  (Target: $\ge 95\%$ for nominal $95\%$ interval).
* **Mean Prediction Interval Width (MPIW)**:
  $$\text{MPIW} = \frac{1}{N} \sum_{i=1}^N (\hat{U}_i - \hat{L}_i)$$
* **Winkler Interval Score**: Penalizes wide intervals as well as coverage misses:
  $$\text{Score}_i = (\hat{U}_i - \hat{L}_i) + \frac{2}{\alpha}(\hat{L}_i - y_i)\mathbf{1}(y_i < \hat{L}_i) + \frac{2}{\alpha}(y_i - \hat{U}_i)\mathbf{1}(y_i > \hat{U}_i)$$

---

## 8. Phase 1 Implementation Plan

1. **Dependencies**: Ensure `scikit-learn>=1.9.1` is documented in `pyproject.toml` / `requirements.txt`.
2. **Contracts & Protocols (`src/soh/common/`)**:
   - `units.py`: Polarity, canonical units, conversions.
   - `protocols.py`: `CellReferenceSpec`, protocol rules.
   - `contracts.py`: `Measurement`, `CycleRecord`, `SOHState`, `FeatureQualityRecord`, `SohEstimate`.
   - `eligibility.py`: Window eligibility rules and `INSUFFICIENT_INFORMATION` status.
3. **Degradation Framework (`src/soh/degradation/`)**:
   - `mechanisms.py`: Base degradation models (SEI kinetics, empirical power law).
   - `reversible.py`: Temperature corrections ($R(T)$ Arrhenius).
4. **Data Loaders (`src/soh/data/`)**:
   - `base_loader.py`: Standard aging cycle iterator.
   - `synthetic_aging.py`: Parametric synthetic aging generator for repeatable unit testing.
   - `calce_aging.py`: CALCE real-cell aging parser for A123/CS2 cells.
   - `window_extractor.py`: Charging window extractor with configurable $\Delta \text{SOC}$ and $\Delta V$ filters.
5. **Phase 1 Baseline Estimator (`src/soh/estimators/`)**:
   - `base.py`: `SohEstimator` ABC and `SupportsEmbeddedExport`.
   - `baseline_ridge.py`: Leakage-free regularized Ridge regression baseline predicting $SOH_{C,\text{bol}}$ and $SOH_{R,\text{bol}}$ with uncertainty intervals.
6. **Benchmarking & Validation (`src/soh/benchmarks/`)**:
   - `metrics.py`: RMSE, MAE, MaxError, 95th-pct, PICP, MPIW, Winkler score.
   - `split_runner.py`: Leave-One-Battery-Out cross-validation runner.
7. **Testing Suite (`tests/soh/`)**:
   - Unit tests for contracts, protocols, quality checks, synthetic data, CALCE loader, baseline training, and evaluation metrics.
   - Regression check confirming existing SOC tests remain 100% passing.
