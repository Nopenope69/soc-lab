/**
 * @file soh_dual_state_tracker.h
 * @brief Embedded Dual-State Kalman Tracker with Independent SOH_C / SOH_R Qualification.
 */

#ifndef SOH_DUAL_STATE_TRACKER_H
#define SOH_DUAL_STATE_TRACKER_H

#include "soh_edge_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float deg_rate_c_per_ah;  /* Baseline throughput degradation rate for C */
    float deg_rate_r_per_ah;  /* Baseline throughput degradation rate for R */
    float q_proc_c;           /* Process noise covariance for C */
    float q_proc_r;           /* Process noise covariance for R */
    float min_eigenval;       /* PSD regularizer floor */
    float mahalanobis_thresh; /* Innovation gating threshold */
} SohTrackerConfig_t;

void soh_tracker_init(
    const SohTrackerConfig_t* config,
    float initial_soh_c,
    float initial_soh_r,
    SohState_t* out_state
);

void soh_tracker_predict(
    const SohTrackerConfig_t* config,
    float delta_ah,
    SohState_t* inout_state
);

bool soh_tracker_update(
    const SohTrackerConfig_t* config,
    const SohEstimate_t* estimate,
    SohState_t* inout_state
);

#ifdef __cplusplus
}
#endif

#endif /* SOH_DUAL_STATE_TRACKER_H */
