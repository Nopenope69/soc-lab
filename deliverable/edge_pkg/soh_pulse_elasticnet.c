/**
 * @file soh_pulse_elasticnet.c
 * @brief Implementation of 2-RC ECM Pulse Response ElasticNet SOH Estimator.
 * 
 * Memory footprint: Constants stored in Flash (.rodata).
 * Zero dynamic memory. Stack usage < 128 bytes.
 */

#include "soh_pulse_elasticnet.h"

/* PLACEHOLDER COEFFICIENTS: Unvalidated on physical cells.
 * Single source of truth is exported from Python PulseElasticNetEstimator.export_c_header().
 * Qualification status is strictly SOH_QUAL_UNQUALIFIED.
 */
#define SOH_PULSE_COEFFICIENTS_PLACEHOLDER 1

/* Standard Scaler Means for 11 features:
   [r0_ohm, r1_ohm, c1_f, r2_ohm, c2_f, r_total_ohm, tau1_s, tau2_s, i_amplitude_a, temp_c, v_initial_v] */
static const float SCALER_MEAN[SOH_PULSE_NUM_FEATURES] = {
    0.0150f, 0.0050f, 1000.0f, 0.0060f, 4000.0f, 0.0260f, 5.0f, 25.0f, -2.0f, 25.0f, 3.30f
};

static const float SCALER_SCALE[SOH_PULSE_NUM_FEATURES] = {
    0.0030f, 0.0015f, 300.0f, 0.0020f, 1000.0f, 0.0050f, 1.5f, 5.0f, 1.0f, 10.0f, 0.20f
};

/* Linear Model Coefficients for SOH_C */
static const float COEFS_C[SOH_PULSE_NUM_FEATURES] = {
    -0.0125f, -0.0080f, 0.0010f, -0.0075f, 0.0005f, -0.0190f, -0.0020f, -0.0030f, 0.0f, 0.0015f, 0.0f
};
static const float INTERCEPT_C = 0.9850f;

/* Linear Model Coefficients for SOH_R */
static const float COEFS_R[SOH_PULSE_NUM_FEATURES] = {
    -0.0450f, -0.0250f, 0.0020f, -0.0300f, 0.0015f, -0.0850f, -0.0050f, -0.0080f, 0.0f, 0.0040f, 0.0f
};
static const float INTERCEPT_R = 0.9800f;

void soh_pulse_elasticnet_predict(
    const float raw_features[SOH_PULSE_NUM_FEATURES],
    SohEstimate_t* out_estimate
) {
    if (!out_estimate) return;

    float dot_c = INTERCEPT_C;
    float dot_r = INTERCEPT_R;

    for (int i = 0; i < SOH_PULSE_NUM_FEATURES; ++i) {
        float x_norm = (raw_features[i] - SCALER_MEAN[i]) / SCALER_SCALE[i];
        dot_c += COEFS_C[i] * x_norm;
        dot_r += COEFS_R[i] * x_norm;
    }

    /* Bounding to physical limits */
    if (dot_c < 0.20f) dot_c = 0.20f;
    if (dot_c > 1.20f) dot_c = 1.20f;
    if (dot_r < 0.20f) dot_r = 0.20f;
    if (dot_r > 1.50f) dot_r = 1.50f;

    out_estimate->soh_c = dot_c;
    out_estimate->soh_r = dot_r;
    out_estimate->variance_c = 1.6e-5f; /* ~0.4% std error */
    out_estimate->variance_r = 2.5e-5f; /* ~0.5% std error */
    out_estimate->status = SOH_STATUS_VALID;
    
    /* Default qualification status is UNQUALIFIED (UNVALIDATED) until validated on physical hardware */
    out_estimate->qual_c = SOH_QUAL_UNQUALIFIED;
    out_estimate->qual_r = SOH_QUAL_UNQUALIFIED;
}
