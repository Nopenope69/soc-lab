/**
 * @file soh_edge_pipeline.h
 * @brief Top-Level Embedded SOH Inference Pipeline for Battery Management Systems.
 */

#ifndef SOH_EDGE_PIPELINE_H
#define SOH_EDGE_PIPELINE_H

#include "soh_edge_types.h"
#include "soh_pulse_elasticnet.h"
#include "soh_empirical_powerlaw.h"
#include "soh_dual_state_tracker.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    SohTrackerConfig_t tracker_cfg;
    SohEmpiricalConfig_t empirical_cfg;
} SohEdgeContext_t;

void soh_edge_init(
    SohEdgeContext_t* ctx,
    float initial_soh_c,
    float initial_soh_r,
    SohState_t* out_state
);

void soh_edge_step_pulse(
    SohEdgeContext_t* ctx,
    const float pulse_features[SOH_PULSE_NUM_FEATURES],
    float delta_ah,
    SohState_t* inout_state
);

void soh_edge_step_empirical(
    SohEdgeContext_t* ctx,
    float total_ah_throughput,
    float delta_ah,
    float temp_c,
    SohState_t* inout_state
);

#ifdef __cplusplus
}
#endif

#endif /* SOH_EDGE_PIPELINE_H */
