/**
 * Auto-generated 2-RC ECM Pulse ElasticNet SOH Estimator Header
 * Microcontroller deployment: fixed feature inference without external libraries.
 */

#ifndef SOH_PULSE_ELASTICNET_H
#define SOH_PULSE_ELASTICNET_H

#define SOH_ECM_NUM_FEATURES 11

/* Feature means for StandardScaler */
static const float SOH_SCALER_MEAN[11] = { 7.43402341e-03f, 3.67118613e-03f, 1.01443053e+03f, 9.32631525e-03f, 3.83610852e+05f, 2.04315248e-02f, 3.74364025e+00f, 1.46094769e+02f, 2.00000000e+00f, 2.49994163e+01f, 3.30480674e+00f };

/* Feature scales (stds) for StandardScaler */
static const float SOH_SCALER_SCALE[11] = { 5.45052858e-04f, 1.27166325e-03f, 3.10114885e+02f, 1.03179187e-02f, 9.74248798e+05f, 1.06997892e-02f, 1.66657505e+00f, 1.37446697e+02f, 1.00000000e+00f, 8.55386011e-03f, 1.83952176e-03f };

/* Model weights for Capacity SOH (SOH_C) */
static const float SOH_C_COEFS[11] = { 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f };
static const float SOH_C_INTERCEPT = 9.99999635e-01f;

/* Model weights for Resistance SOH (SOH_R) */
static const float SOH_R_COEFS[11] = { 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f, 0.00000000e+00f };
static const float SOH_R_INTERCEPT = 9.99999864e-01f;

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
