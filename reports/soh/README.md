# SOH Phase 6 Audit Data & Shadow Telemetry Logs

This directory contains intermediate and audit JSON artifacts produced during Phase 6 SOH qualification and shadow testing:

1. **`soh_phase6_1_audit_data.json`**:
   - *Provenance:* Phase 6.1 production qualification audit metadata. Contains dataset provenance classifications and coverage metrics across LG M50T, CALCE A123, Oxford Kokam, and MIT/Stanford cohorts.
   - *Audit Status:* Reclassified in Phase 6.1/6.2/6.3 errata; real-cell cohorts without raw lab files on disk are classified as `SIMULATION`.
2. **`soh_phase6_2_audit_data.json`**:
   - *Provenance:* Phase 6.2 production prototype qualification metrics (empirical power law and GRU degradation evaluations).
3. **`soh_phase6_3_audit_data.json`**:
   - *Provenance:* Phase 6.3 experimental hardware qualification records.
4. **`soh_phase6_shadow_telemetry_log.json`**:
   - *Provenance:* Telemetry snapshots recorded during multi-model shadow execution across 4 parallel estimators (Pulse ECM, ICA/GPR-EKF, Empirical Power Law, GRU).
5. **`example_synchronized_telemetry.json`**:
   - *Provenance:* Sample multi-channel synchronized voltage, current, temperature, and cycle time-series verifying `SynchronizedTelemetryLogger` schema.

---

### Duplicate Header Reconciliation
The historical root-level header `deliverable/soh_pulse_elasticnet.h` was removed. The authoritative C header is:
- `deliverable/edge_pkg/soh_pulse_elasticnet.h`

**Difference Analysis:**
- The removed `deliverable/soh_pulse_elasticnet.h` was an auto-generated static inline header from an over-regularized synthetic fit with all feature coefficients equal to 0.0 (`SOH_C_COEFS[i] = 0.0f`), lacking bounds clamping, error return codes, and uncertainty estimates.
- `deliverable/edge_pkg/soh_pulse_elasticnet.h` is the formal C API declaration defining `soh_pulse_elasticnet_predict(const float raw_features[11], SohEstimate_t* out_estimate)` coupled with `soh_pulse_elasticnet.c`, implementing full runtime bounds enforcement, status flags (`SOH_QUAL_UNQUALIFIED`), and defensive clamping.
