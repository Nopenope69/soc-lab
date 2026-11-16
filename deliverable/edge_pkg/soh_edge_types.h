/**
 * @file soh_edge_types.h
 * @brief Common types and contracts for embedded battery SOH estimation.
 * 
 * Target: ANSI C99 / MISRA-C compatible.
 * Zero dynamic heap allocation.
 */

#ifndef SOH_EDGE_TYPES_H
#define SOH_EDGE_TYPES_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    SOH_STATUS_VALID = 0,
    SOH_STATUS_INSUFFICIENT_INFORMATION = 1,
    SOH_STATUS_LOW_QUALITY_FEATURE = 2,
    SOH_STATUS_OUTLIER_REJECTED = 3,
    SOH_STATUS_CONVERGENCE_FAILURE = 4
} SohEstimationStatus_t;

typedef enum {
    SOH_QUAL_UNVALIDATED = 0,
    SOH_QUAL_UNQUALIFIED = 0,
    SOH_QUAL_QUALIFIED = 1,
    SOH_QUAL_EXPERIMENTAL = 2,
    SOH_QUAL_REJECTED = 3,
    SOH_QUAL_SIM_VALIDATED = 4,
    SOH_QUAL_LAB_VALIDATED = 5,
    SOH_QUAL_FIELD_VALIDATED = 6
} SohQualificationStatus_t;

typedef struct {
    float soh_c_bol;
    float soh_c_rated;
    float soh_r_bol;
    float var_c;
    float var_r;
    float cov_cr;
    uint32_t cycle_index;
    float timestamp_s;
    bool is_c_qualified;
    bool is_r_qualified;
    SohQualificationStatus_t qual_c;
    SohQualificationStatus_t qual_r;
} SohState_t;

typedef struct {
    float soh_c;
    float soh_r;
    float variance_c;
    float variance_r;
    SohEstimationStatus_t status;
    SohQualificationStatus_t qual_c;
    SohQualificationStatus_t qual_r;
} SohEstimate_t;

#ifdef __cplusplus
}
#endif

#endif /* SOH_EDGE_TYPES_H */
