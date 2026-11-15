/**
 * @file test_soh_edge.c
 * @brief Standalone Embedded Verification Suite for Edge SOH Inference Package.
 * Tests:
 * 1. Pulse ECM ElasticNet inference.
 * 2. Empirical Power-Law inference.
 * 3. Dual-state Kalman tracker with independent qualification gating.
 * 4. 5,000 cycle long-duration numerical stability test.
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <assert.h>
#include "soh_edge_pipeline.h"

int main(void) {
    printf("=== SOH EDGE C INFERENCE VERIFICATION ===\n");

    SohEdgeContext_t ctx;
    SohState_t state;
    soh_edge_init(&ctx, 1.0f, 1.0f, &state);

    assert(state.soh_c_bol == 1.0f);
    assert(state.soh_r_bol == 1.0f);
    assert(!state.is_c_qualified);
    assert(!state.is_r_qualified);
    printf("  [PASS] Initialization: SOH_C=1.0, SOH_R=1.0, Qual=UNVALIDATED\n");

    /* 1. Empirical Step Test */
    soh_edge_step_empirical(&ctx, 10.0f, 2.0f, 25.0f, &state);
    assert(state.is_c_qualified == true);
    assert(state.is_r_qualified == false); /* Must remain unvalidated! */
    printf("  [PASS] Empirical Step: SOH_C=%.4f (Qualified: %d), SOH_R=%.4f (Qualified: %d)\n",
           state.soh_c_bol, state.is_c_qualified, state.soh_r_bol, state.is_r_qualified);

    /* 2. Pulse ECM Step Test */
    float mock_pulse[SOH_PULSE_NUM_FEATURES] = {
        0.0155f, 0.0052f, 980.0f, 0.0062f, 3950.0f, 0.0269f, 5.1f, 24.5f, -2.0f, 25.0f, 3.32f
    };
    soh_edge_step_pulse(&ctx, mock_pulse, 0.5f, &state);
    assert(state.is_c_qualified == true);
    assert(state.is_r_qualified == true); /* Now both qualified */
    printf("  [PASS] Pulse Step: SOH_C=%.4f (Qualified: %d), SOH_R=%.4f (Qualified: %d)\n",
           state.soh_c_bol, state.is_c_qualified, state.soh_r_bol, state.is_r_qualified);

    /* 3. 5,000 Cycle Long-Duration Numerical Stability Test */
    printf("  Running 5,000 continuous updates for numerical stability...\n");
    for (int i = 0; i < 5000; ++i) {
        if (i % 20 == 0) {
            soh_edge_step_pulse(&ctx, mock_pulse, 0.5f, &state);
        } else {
            soh_edge_step_empirical(&ctx, (float)(i * 2), 2.0f, 25.0f, &state);
        }
        /* Numerical integrity assertion */
        assert(!isnan(state.soh_c_bol));
        assert(!isnan(state.soh_r_bol));
        assert(!isnan(state.var_c));
        assert(!isnan(state.var_r));
        assert(state.var_c >= ctx.tracker_cfg.min_eigenval);
        assert(state.var_r >= ctx.tracker_cfg.min_eigenval);
        assert(state.soh_c_bol >= 0.20f && state.soh_c_bol <= 1.20f);
    }
    printf("  [PASS] 5,000 cycle stability: Final SOH_C=%.4f, SOH_R=%.4f, var_C=%.2e, var_R=%.2e\n",
           state.soh_c_bol, state.soh_r_bol, state.var_c, state.var_r);

    printf("=== ALL SOH EDGE C TESTS PASSED ===\n");
    return 0;
}
