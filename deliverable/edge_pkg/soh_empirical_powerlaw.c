/**
 * @file soh_empirical_powerlaw.c
 * @brief Implementation of Fitted Empirical Power-Law SOH Estimator.
 */

#include "soh_empirical_powerlaw.h"
#include <math.h>

#define SOH_GAS_CONST_R 8.314462618f

void soh_empirical_predict(
    const SohEmpiricalConfig_t* config,
    float ah_throughput,
    float temp_c,
    SohEstimate_t* out_estimate
) {
    if (!out_estimate || !config) return;

    if (ah_throughput < 0.0f) ah_throughput = 0.0f;

    /* Temperature in Kelvin */
    float temp_k = temp_c + 273.15f;
    if (temp_k < 233.15f) temp_k = 233.15f; /* Clamp to -40°C */
    if (temp_k > 353.15f) temp_k = 353.15f; /* Clamp to +80°C */

    float t_ref_k = (config->t_ref_k > 200.0f) ? config->t_ref_k : 298.15f;

    /* Arrhenius thermal acceleration factor */
    float arrh_exp = (-config->ea_j_per_mol / SOH_GAS_CONST_R) * ((1.0f / temp_k) - (1.0f / t_ref_k));
    float arrh_factor = expf(arrh_exp);

    /* Throughput power-law loss: delta_C = alpha * (Ah)^z * arrh */
    float fade_c = config->alpha_deg * powf(ah_throughput, config->z_exponent) * arrh_factor;

    float pred_c = 1.0f - fade_c;
    if (pred_c < 0.20f) pred_c = 0.20f;
    if (pred_c > 1.20f) pred_c = 1.20f;

    out_estimate->soh_c = pred_c;
    /* Empirical power law does NOT model resistance growth physically */
    out_estimate->soh_r = 1.0f;
    out_estimate->variance_c = 1.0e-5f; /* ~0.3% std error */
    out_estimate->variance_r = 1.0e-2f; /* Unmodeled large variance */
    out_estimate->status = SOH_STATUS_VALID;
    
    /* QUALIFIED for Capacity (SOH_C), but strictly UNVALIDATED for Resistance (SOH_R) */
    out_estimate->qual_c = SOH_QUAL_QUALIFIED;
    out_estimate->qual_r = SOH_QUAL_UNVALIDATED;
}
