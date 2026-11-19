/**
 * Auto-generated 2-RC ECM Pulse ElasticNet SOH Estimator Header
 * Microcontroller deployment: fixed feature inference without external libraries.
 */

#ifndef SOH_PULSE_ELASTICNET_H
#define SOH_PULSE_ELASTICNET_H

#define SOH_ECM_NUM_FEATURES 11

/* Feature means for StandardScaler */
static const float SOH_SCALER_MEAN[11] = { 1.73295336e-02f, 9.67768633e-03f, 5.65915344e+02f, 6.56095466e-02f, 1.42924201e+03f, 9.26167666e-02f, 5.48176660e+00f, 9.35165389e+01f, 4.51396796e-01f, 2.50000000e+01f, 3.30673529e+00f };

/* Feature scales (stds) for StandardScaler */
static const float SOH_SCALER_SCALE[11] = { 6.56272619e-04f, 5.57007712e-04f, 3.53817910e+01f, 5.49842715e-03f, 1.02157204e+02f, 5.84224166e-03f, 5.22591081e-01f, 7.66908425e+00f, 3.46839131e-03f, 1.00000000e+00f, 9.24602717e-04f };

/* Model weights for Capacity SOH (SOH_C) */
static const float SOH_C_COEFS[11] = { -1.93316014e-02f, -9.14477672e-03f, 7.27541384e-03f, -0.00000000e+00f, 2.94034457e-02f, -1.13498071e-02f, -0.00000000e+00f, 0.00000000e+00f, 1.84638192e-03f, 0.00000000e+00f, -3.02973047e-03f };
static const float SOH_C_INTERCEPT = 9.18993784e-01f;

/* Model weights for Resistance SOH (SOH_R) */
static const float SOH_R_COEFS[11] = { 9.86294204e-03f, 0.00000000e+00f, -4.06604857e-03f, 0.00000000e+00f, -1.07836980e-02f, 9.68890584e-03f, -0.00000000e+00f, -0.00000000e+00f, 7.08693148e-03f, 0.00000000e+00f, -3.95799698e-03f };
static const float SOH_R_INTERCEPT = 9.87213839e-01f;

/**
 * Lightweight embedded inference function.
 * Computes point estimates in O(N) operations.
 */
static inline void soh_predict_pulse(
    const float raw_features[SOH_ECM_NUM_FEATURES],
    float* out_soh_c,
    float* out_soh_r
) {
    float dot_c = SOH_C_INTERCEPT;
    float dot_r = SOH_R_INTERCEPT;
    for (int i = 0; i < SOH_ECM_NUM_FEATURES; ++i) {
        float x_norm = (raw_features[i] - SOH_SCALER_MEAN[i]) / SOH_SCALER_SCALE[i];
        dot_c += SOH_C_COEFS[i] * x_norm;
        dot_r += SOH_R_COEFS[i] * x_norm;
    }
    if (out_soh_c) *out_soh_c = dot_c;
    if (out_soh_r) *out_soh_r = dot_r;
}

#endif /* SOH_PULSE_ELASTICNET_H */
