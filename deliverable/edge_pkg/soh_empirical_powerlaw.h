/**
 * @file soh_empirical_powerlaw.h
 * @brief Empirical Power-Law SOH Estimator for Embedded Microcontrollers.
 */

#ifndef SOH_EMPIRICAL_POWERLAW_H
#define SOH_EMPIRICAL_POWERLAW_H

#include "soh_edge_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float alpha_deg;     /* Pre-exponential degradation coefficient */
    float z_exponent;    /* Throughput power exponent (~0.5 - 1.2) */
    float ea_j_per_mol;  /* Arrhenius activation energy (~22.4 kJ/mol) */
    float t_ref_k;       /* Reference temperature (298.15 K) */
} SohEmpiricalConfig_t;

/* Public API */
void soh_empirical_predict(
    const SohEmpiricalConfig_t* config,
    float ah_throughput,
    float temp_c,
    SohEstimate_t* out_estimate
);

#ifdef __cplusplus
}
#endif

#endif /* SOH_EMPIRICAL_POWERLAW_H */
