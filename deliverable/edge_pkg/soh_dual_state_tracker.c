/**
 * @file soh_dual_state_tracker.c
 * @brief Implementation of Embedded Dual-State Kalman Tracker.
 * 
 * Joseph-form covariance updates maintain positive semi-definiteness.
 * Independent qualification flags prevent unvalidated resistance measurements
 * from updating qualified production state.
 */

#include "soh_dual_state_tracker.h"
#include <math.h>

void soh_tracker_init(
    const SohTrackerConfig_t* config,
    float initial_soh_c,
    float initial_soh_r,
    SohState_t* out_state
) {
    if (!out_state) return;
    (void)config;

    out_state->soh_c_bol = initial_soh_c;
    out_state->soh_c_rated = initial_soh_c;
    out_state->soh_r_bol = initial_soh_r;
    out_state->var_c = 4.0e-4f; /* Initial 2% 1-sigma uncertainty */
    out_state->var_r = 4.0e-4f; /* Initial 2% 1-sigma uncertainty */
    out_state->cov_cr = 0.0f;
    out_state->cycle_index = 0;
    out_state->timestamp_s = 0.0f;
    out_state->is_c_qualified = false;
    out_state->is_r_qualified = false;
    out_state->qual_c = SOH_QUAL_UNVALIDATED;
    out_state->qual_r = SOH_QUAL_UNVALIDATED;
}

void soh_tracker_predict(
    const SohTrackerConfig_t* config,
    float delta_ah,
    SohState_t* inout_state
) {
    if (!config || !inout_state) return;

    if (delta_ah < 0.0f) delta_ah = 0.0f;

    /* Irreversible monotonic physical degradation step */
    inout_state->soh_c_bol -= config->deg_rate_c_per_ah * delta_ah;
    inout_state->soh_c_rated -= config->deg_rate_c_per_ah * delta_ah;
    inout_state->soh_r_bol -= config->deg_rate_r_per_ah * delta_ah;

    /* Covariance propagation: P^- = P + Q */
    inout_state->var_c += config->q_proc_c;
    inout_state->var_r += config->q_proc_r;

    /* Enforce PSD eigenvalue floor */
    if (inout_state->var_c < config->min_eigenval) inout_state->var_c = config->min_eigenval;
    if (inout_state->var_r < config->min_eigenval) inout_state->var_r = config->min_eigenval;
}

bool soh_tracker_update(
    const SohTrackerConfig_t* config,
    const SohEstimate_t* estimate,
    SohState_t* inout_state
) {
    if (!config || !estimate || !inout_state) return false;
    if (estimate->status != SOH_STATUS_VALID) return false;

    /* 1. SOH_C Update (if qualified or valid) */
    if (estimate->qual_c == SOH_QUAL_QUALIFIED && estimate->variance_c > 0.0f) {
        float r_c = estimate->variance_c;
        float p_c = inout_state->var_c;
        float innov_c = estimate->soh_c - inout_state->soh_c_bol;
        float s_c = p_c + r_c;

        /* Mahalanobis gating check */
        float maha_sq_c = (innov_c * innov_c) / s_c;
        if (maha_sq_c <= config->mahalanobis_thresh) {
            float k_c = p_c / s_c;
            inout_state->soh_c_bol += k_c * innov_c;
            inout_state->soh_c_rated += k_c * innov_c;
            /* Joseph update: P^+ = (1 - K) * P * (1 - K) + K * R * K */
            float one_minus_k = 1.0f - k_c;
            inout_state->var_c = (one_minus_k * p_c * one_minus_k) + (k_c * r_c * k_c);

            inout_state->is_c_qualified = true;
            inout_state->qual_c = SOH_QUAL_QUALIFIED;
        }
    }

    /* 2. SOH_R Update: STRICTLY ONLY IF QUALIFIED */
    if (estimate->qual_r == SOH_QUAL_QUALIFIED && estimate->variance_r > 0.0f) {
        float r_r = estimate->variance_r;
        float p_r = inout_state->var_r;
        float innov_r = estimate->soh_r - inout_state->soh_r_bol;
        float s_r = p_r + r_r;

        float maha_sq_r = (innov_r * innov_r) / s_r;
        if (maha_sq_r <= config->mahalanobis_thresh) {
            float k_r = p_r / s_r;
            inout_state->soh_r_bol += k_r * innov_r;
            float one_minus_k = 1.0f - k_r;
            inout_state->var_r = (one_minus_k * p_r * one_minus_k) + (k_r * r_r * k_r);

            inout_state->is_r_qualified = true;
            inout_state->qual_r = SOH_QUAL_QUALIFIED;
        }
    }

    /* State bounding */
    if (inout_state->soh_c_bol < 0.20f) inout_state->soh_c_bol = 0.20f;
    if (inout_state->soh_c_bol > 1.20f) inout_state->soh_c_bol = 1.20f;
    if (inout_state->soh_r_bol < 0.20f) inout_state->soh_r_bol = 0.20f;
    if (inout_state->soh_r_bol > 1.50f) inout_state->soh_r_bol = 1.50f;

    return true;
}
