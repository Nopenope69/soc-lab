# Errata for Gauntlet V3 Freeze Specification (`FROZEN_SPEC.md`)

This errata document records three technical corrections and clarifications to `reports/gauntlet_v3/FROZEN_SPEC.md` identified during the research handover hardening pass.

---

### Erratum 1: Coulombic Efficiency ($\eta_c$)
- **Stated in legacy text / table**: Implied ideal $\eta_c = 1.000$.
- **Actual Frozen Value in Code**: $\eta_c = 0.998$ (calibrated from D8 anchor gap analysis on CALCE A123 26650 LFP cells).
- **Code Provenance**: Declared in `configs/assumptions/base.yaml` under `plant.coulombic_efficiency = 0.998` and consumed by `E7V3CompositeFilter` in `src/soc/estimators/e7v3.py` (via `ParamSet.coulombic_efficiency`) and `deliverable/bms_soc_ref.py`.
- **Impact**: Charge-integration steps apply $\eta_c = 0.998$ when $I < 0$ (charging). Discharge steps apply $\eta = 1.0$.

---

### Erratum 2: Initial RC and Hysteresis Uncertainty ($\sigma_{i,0}$, $\sigma_{h,0}$)
- **Stated in legacy text**: In section 1 item 2, implied initial standard deviations were $0.01$ or default filter values.
- **Actual Frozen Value in Code**:
  - `initial_rc_current_std_a = 0.10` ($100\text{ mA}$)
  - `initial_hysteresis_std = 0.10` ($10\%$)
- **Code Provenance**: `configs/assumptions/base.yaml` lines for `filter.initial_rc_current_std_a` and `filter.initial_hysteresis_std`. In `bms_soc_ref.py` and `e7v3.py`, `p_rc = 0.10^2 = 0.01` and `p_h = 0.10^2 = 0.01`.
- **Impact**: State covariances for polarization currents $i_1, i_2$ and hysteresis $h$ start at $0.01$, not $0.0001$.

---

### Erratum 3: Configuration Hash Hierarchy (Single Combined Hash)
- **Stated in legacy text**: Hash was reported only for the profile leaf file `calce_a123_v4.yaml` (`3a3391e4...`).
- **Actual Effective Configuration**: The true runtime configuration is the deep-merged combination of `configs/assumptions/base.yaml` + `configs/assumptions/profiles/calce_a123_v4.yaml`.
- **Combined Effective Config Hash**:
  `18902f2c61efc3b36f0d62e2e424e298c6b886c19398a433bf9f7861eced2a70`
- **Impact**: Tracking only the leaf profile hash hid default values inherited from `base.yaml`. Future releases should verify the combined resolved hash recorded in `RELEASE_MANIFEST.json`.
