/**
 * @file soh_edge_pipeline.c
 * @brief Implementation of Top-Level Embedded SOH Inference Pipeline.
 */

#include "soh_edge_pipeline.h"

void soh_edge_init(
    SohEdgeContext_t* ctx,
    float initial_soh_c,
    float initial_soh_r,
    SohState_t* out_state
) {
    if (!ctx || !out_state) return;

    /* Default conservative physical process rates */
    ctx->tracker_cfg.deg_rate_c_per_ah = 2.0e-5f;
    ctx->tracker_cfg.deg_rate_r_per_ah = 2.5e-5f;
    ctx->tracker_cfg.q_proc_c = 1.0e-7f;
    ctx->tracker_cfg.q_proc_r = 1.0e-7f;
    ctx->tracker_cfg.min_eigenval = 1.0e-8f;
    ctx->tracker_cfg.mahalanobis_thresh = 9.0f; /* 3-sigma gate */

    /* Default empirical parameters */
    ctx->empirical_cfg.alpha_deg = 2.5e-5f;
    ctx->empirical_cfg.z_exponent = 0.85f;
    ctx->empirical_cfg.ea_j_per_mol = 22400.0f;
    ctx->empirical_cfg.t_ref_k = 298.15f;

    soh_tracker_init(&ctx->tracker_cfg, initial_soh_c, initial_soh_r, out_state);
}

void soh_edge_step_pulse(
    SohEdgeContext_t* ctx,
    const float pulse_features[SOH_PULSE_NUM_FEATURES],
    float delta_ah,
    SohState_t* inout_state
) {
    if (!ctx || !pulse_features || !inout_state) return;

    /* 1. Predict step based on throughput */
    soh_tracker_predict(&ctx->tracker_cfg, delta_ah, inout_state);

    /* 2. Run ElasticNet inference */
    SohEstimate_t est;
    soh_pulse_elasticnet_predict(pulse_features, &est);

    /* 3. Filter update with independent SOH_C and SOH_R qualification */
    soh_tracker_update(&ctx->tracker_cfg, &est, inout_state);

    inout_state->cycle_index++;
}

void soh_edge_step_empirical(
    SohEdgeContext_t* ctx,
    float total_ah_throughput,
    float delta_ah,
    float temp_c,
    SohState_t* inout_state
) {
    if (!ctx || !inout_state) return;

    /* 1. Predict step based on throughput */
    soh_tracker_predict(&ctx->tracker_cfg, delta_ah, inout_state);

    /* 2. Run Empirical Power-Law inference */
    SohEstimate_t est;
    soh_empirical_predict(&ctx->empirical_cfg, total_ah_throughput, temp_c, &est);

    /* 3. Filter update (updates SOH_C only, leaves SOH_R untouched because qual_r == UNVALIDATED) */
    soh_tracker_update(&ctx->tracker_cfg, &est, inout_state);

    inout_state->cycle_index++;
}
