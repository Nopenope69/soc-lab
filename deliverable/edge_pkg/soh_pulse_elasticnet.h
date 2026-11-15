/**
 * @file soh_pulse_elasticnet.h
 * @brief 2-RC ECM Pulse Response ElasticNet SOH Estimator for Microcontrollers.
 */

#ifndef SOH_PULSE_ELASTICNET_H
#define SOH_PULSE_ELASTICNET_H

#include "soh_edge_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SOH_PULSE_NUM_FEATURES 11

/* Public API */
void soh_pulse_elasticnet_predict(
    const float raw_features[SOH_PULSE_NUM_FEATURES],
    SohEstimate_t* out_estimate
);

#ifdef __cplusplus
}
#endif

#endif /* SOH_PULSE_ELASTICNET_H */
