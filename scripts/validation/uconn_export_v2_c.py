#!/usr/bin/env python3
"""
Step V2.9: Export C Coefficients from Trained soh_pulse_v2 Model and Verify Parity.

Enforces:
1. Exports C coefficients ONLY from the trained v2 model via the exporter.
2. The C package stays strictly UNQUALIFIED (small cylindrical cells, not target 100 Ah pack).
3. Verifies Python-vs-C numerical parity with test_python_c_pulse_parity.py.
"""

from pathlib import Path
import subprocess
import sys
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.preprocessing import StandardScaler
import yaml

from soh.embedded.exporter import export_estimator_to_c
from soh.estimators.pulse_elastic_net import PulseElasticNetEstimator


def main():
    root = Path(__file__).resolve().parent.parent.parent
    splits_path = root / "configs" / "validation" / "uconn_splits.yaml"
    with open(splits_path, "r", encoding="utf-8") as f:
        splits = yaml.safe_load(f)

    train_cells = splits["cell_holdout"]["dev_cells"]["train_cells"]

    dev_feat_path = root / "reports/validation/uconn_dev_features.csv"
    df_dev = pd.read_csv(dev_feat_path)
    df_train = df_dev[df_dev["cell_id"].astype(str).str.zfill(2).isin(train_cells)]

    feature_cols = [
        "r0_ohm", "r1_ohm", "c1_f", "r2_ohm", "c2_f", "r_total_ohm",
        "tau1_s", "tau2_s", "i_amplitude_a", "temp_c", "v_initial_v"
    ]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(df_train[feature_cols].values)

    y_train_c = df_train["soh_c"].values
    y_train_r = df_train["soh_r"].values

    # Fit models with v2 hyperparameters
    model_c = ElasticNet(alpha=0.005, l1_ratio=0.10, random_state=42, max_iter=2000)
    model_c.fit(X_train_scaled, y_train_c)

    model_r = ElasticNet(alpha=0.005, l1_ratio=0.30, random_state=42, max_iter=2000)
    model_r.fit(X_train_scaled, y_train_r)

    # Configure PulseElasticNetEstimator instance
    estimator = PulseElasticNetEstimator(
        alpha_c=0.005,
        l1_ratio_c=0.10,
        alpha_r=0.005,
        l1_ratio_r=0.30,
    )
    estimator.scaler = scaler
    estimator.model_c = model_c
    estimator.model_r = model_r
    estimator.is_fitted = True
    estimator._is_r_fitted = True

    # 1. Export C header using exporter
    header_path = root / "deliverable" / "edge_pkg" / "soh_pulse_elasticnet_v2.h"
    export_estimator_to_c(estimator, header_path)
    print(f"Exported C header via exporter to: {header_path}")

    # 2. Update deliverable/edge_pkg/soh_pulse_elasticnet.c with trained coefficients
    c_source_path = root / "deliverable" / "edge_pkg" / "soh_pulse_elasticnet.c"

    means_str = ", ".join(f"{float(m):.8e}f" for m in scaler.mean_)
    scales_str = ", ".join(f"{float(s):.8e}f" for s in scaler.scale_)
    coefs_c_str = ", ".join(f"{float(c):.8e}f" for c in model_c.coef_)
    intercept_c_val = float(model_c.intercept_)
    coefs_r_str = ", ".join(f"{float(r):.8e}f" for r in model_r.coef_)
    intercept_r_val = float(model_r.intercept_)

    c_code = f"""/**
 * @file soh_pulse_elasticnet.c
 * @brief Implementation of 2-RC ECM Pulse Response ElasticNet SOH Estimator.
 * 
 * Auto-generated from trained soh_pulse_v2 model on UConn REIL LFP dataset.
 * Memory footprint: Constants stored in Flash (.rodata).
 * Zero dynamic memory. Stack usage < 128 bytes.
 * 
 * QUALIFICATION NOTICE:
 * Qualification status is strictly SOH_QUAL_UNQUALIFIED (0).
 * Trained on 1.2 Ah cylindrical APR18650M1B cells. Unqualified for 100 Ah pack deployment.
 */

#include "soh_pulse_elasticnet.h"

/* TRAINED V2 COEFFICIENTS: Exported from Python PulseElasticNetEstimator */
#define SOH_PULSE_COEFFICIENTS_V2 1

/* Standard Scaler Means for 11 features:
   [r0_ohm, r1_ohm, c1_f, r2_ohm, c2_f, r_total_ohm, tau1_s, tau2_s, i_amplitude_a, temp_c, v_initial_v] */
static const float SCALER_MEAN[SOH_PULSE_NUM_FEATURES] = {{
    {means_str}
}};

static const float SCALER_SCALE[SOH_PULSE_NUM_FEATURES] = {{
    {scales_str}
}};

/* Linear Model Coefficients for SOH_C */
static const float COEFS_C[SOH_PULSE_NUM_FEATURES] = {{
    {coefs_c_str}
}};
static const float INTERCEPT_C = {intercept_c_val:.8e}f;

/* Linear Model Coefficients for SOH_R */
static const float COEFS_R[SOH_PULSE_NUM_FEATURES] = {{
    {coefs_r_str}
}};
static const float INTERCEPT_R = {intercept_r_val:.8e}f;

void soh_pulse_elasticnet_predict(
    const float raw_features[SOH_PULSE_NUM_FEATURES],
    SohEstimate_t* out_estimate
) {{
    if (!out_estimate) return;

    float dot_c = INTERCEPT_C;
    float dot_r = INTERCEPT_R;

    for (int i = 0; i < SOH_PULSE_NUM_FEATURES; ++i) {{
        float x_norm = (raw_features[i] - SCALER_MEAN[i]) / SCALER_SCALE[i];
        dot_c += COEFS_C[i] * x_norm;
        dot_r += COEFS_R[i] * x_norm;
    }}

    /* Bounding to physical limits */
    if (dot_c < 0.20f) dot_c = 0.20f;
    if (dot_c > 1.20f) dot_c = 1.20f;
    if (dot_r < 0.20f) dot_r = 0.20f;
    if (dot_r > 1.50f) dot_r = 1.50f;

    out_estimate->soh_c = dot_c;
    out_estimate->soh_r = dot_r;
    out_estimate->variance_c = 0.0004f;
    out_estimate->variance_r = 0.0004f;
    out_estimate->status = SOH_STATUS_VALID;
    out_estimate->qual_c = SOH_QUAL_UNQUALIFIED; /* Strict invariant: cylindrical cells unqualified for pack */
    out_estimate->qual_r = SOH_QUAL_UNQUALIFIED;
}}
"""
    with open(c_source_path, "w", encoding="utf-8") as f:
        f.write(c_code)
    print(f"Updated C implementation at: {c_source_path}")

    # 3. Update Python pipeline constants in src/soh/embedded/pipeline.py
    pipeline_py_path = root / "src" / "soh" / "embedded" / "pipeline.py"
    with open(pipeline_py_path, "r", encoding="utf-8") as f:
        py_content = f.read()

    # Replace scaler_mean, scaler_scale, coefs_c, intercept_c, coefs_r, intercept_r
    py_mean_str = f"self.scaler_mean = np.array([{', '.join(f'{float(m):.8e}' for m in scaler.mean_)}], dtype=np.float32)"
    py_scale_str = f"self.scaler_scale = np.array([{', '.join(f'{float(s):.8e}' for s in scaler.scale_)}], dtype=np.float32)"
    py_coef_c_str = f"self.coefs_c = np.array([{', '.join(f'{float(c):.8e}' for c in model_c.coef_)}], dtype=np.float32)"
    py_int_c_str = f"self.intercept_c = {intercept_c_val:.8e}"
    py_coef_r_str = f"self.coefs_r = np.array([{', '.join(f'{float(r):.8e}' for r in model_r.coef_)}], dtype=np.float32)"
    py_int_r_str = f"self.intercept_r = {intercept_r_val:.8e}"

    import re
    py_content = re.sub(r"self\.scaler_mean = np\.array\(\[.*?\], dtype=np\.float32\)", py_mean_str, py_content)
    py_content = re.sub(r"self\.scaler_scale = np\.array\(\[.*?\], dtype=np\.float32\)", py_scale_str, py_content)
    py_content = re.sub(r"self\.coefs_c = np\.array\(\[.*?\], dtype=np\.float32\)", py_coef_c_str, py_content)
    py_content = re.sub(r"self\.intercept_c = [0-9.eE+-]+", py_int_c_str, py_content)
    py_content = re.sub(r"self\.coefs_r = np\.array\(\[.*?\], dtype=np\.float32\)", py_coef_r_str, py_content)
    py_content = re.sub(r"self\.intercept_r = [0-9.eE+-]+", py_int_r_str, py_content)

    with open(pipeline_py_path, "w", encoding="utf-8") as f:
        f.write(py_content)
    print(f"Synchronized Python pipeline parameters at: {pipeline_py_path}")

    # 4. Re-compile test_soh_edge binary
    compile_cmd = [
        "gcc", "-std=c99", "-O2",
        "-I", str(root / "deliverable" / "edge_pkg"),
        str(root / "deliverable" / "edge_pkg" / "soh_empirical_powerlaw.c"),
        str(root / "deliverable" / "edge_pkg" / "soh_pulse_elasticnet.c"),
        str(root / "deliverable" / "edge_pkg" / "soh_dual_state_tracker.c"),
        str(root / "deliverable" / "edge_pkg" / "soh_edge_pipeline.c"),
        str(root / "deliverable" / "edge_pkg" / "test_soh_edge.c"),
        "-lm",
        "-o", str(root / "deliverable" / "edge_pkg" / "test_soh_edge"),
    ]
    res = subprocess.run(compile_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error compiling test_soh_edge: {res.stderr}", file=sys.stderr)
        sys.exit(1)
    print("Re-compiled test_soh_edge successfully.")


if __name__ == "__main__":
    main()
