"""Post-hoc age-only baseline evaluation for UConn REIL Dataset 5 (Task V2.11).

Evaluates State of Health (SOH_C and SOH_R) predicted strictly from aging duration
(RPT index / cumulative cycle count), comparing linear and non-linear (quadratic/sqrt)
functional forms fitted exclusively on DEV training cells against Ridge,
constant-mean, and frozen soh_pulse_v2.
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import yaml


def run_age_baseline_evaluation() -> Dict[str, Any]:
    root = Path(__file__).resolve().parent.parent.parent
    splits_path = root / "configs" / "validation" / "uconn_splits.yaml"
    calib_path = root / "deliverable" / "calibrations" / "uconn_soh_pulse_v2_frozen_v27.json"
    dev_feat_path = root / "reports" / "validation" / "uconn_dev_features.csv"
    sealed_feat_path = root / "reports" / "validation" / "uconn_sealed_features.csv"

    with open(splits_path, "r", encoding="utf-8") as f:
        splits = yaml.safe_load(f)
    with open(calib_path, "r", encoding="utf-8") as f:
        calib = json.load(f)

    train_cells = [str(c).zfill(2) for c in splits["cell_holdout"]["dev_cells"]["train_cells"]]
    val_cells = [str(c).zfill(2) for c in splits["cell_holdout"]["dev_cells"]["val_cells"]]
    sealed_cells = [str(c).zfill(2) for c in splits["cell_holdout"]["sealed_test_cells"]]
    held_out_groups = splits["condition_holdout"]["sealed_test_conditions"]
    dev_conditions = splits["condition_holdout"]["dev_conditions"]

    df_dev = pd.read_csv(dev_feat_path)
    df_sealed = pd.read_csv(sealed_feat_path)
    df_dev["cell_id_str"] = df_dev["cell_id"].astype(str).str.zfill(2)
    df_sealed["cell_id_str"] = df_sealed["cell_id"].astype(str).str.zfill(2)

    df_all = pd.concat([df_dev, df_sealed], ignore_index=True)

    df_train = df_dev[df_dev["cell_id_str"].isin(train_cells)]
    df_val = df_dev[df_dev["cell_id_str"].isin(val_cells)]

    feature_cols = calib["features"]
    scaler_mean = np.array(calib["scaler"]["mean"])
    scaler_scale = np.array(calib["scaler"]["scale"])

    w_c = np.array(calib["soh_c"]["coefficients"])
    b_c = calib["soh_c"]["intercept"]
    w_r = np.array(calib["soh_r"]["coefficients"])
    b_r = calib["soh_r"]["intercept"]

    # Fit Ridge baseline on train partition
    scaler_tr = StandardScaler()
    X_tr = scaler_tr.fit_transform(df_train[feature_cols].values)
    ridge_c = Ridge(alpha=0.005, random_state=42).fit(X_tr, df_train["soh_c"].values)
    ridge_r = Ridge(alpha=0.005, random_state=42).fit(X_tr, df_train["soh_r"].values)

    # Fit Age-only models on train partition
    # 1. Linear: SOH = a * rpt_num + b
    p_lin_c = np.polyfit(df_train["rpt_num"].values, df_train["soh_c"].values, 1)
    p_lin_r = np.polyfit(df_train["rpt_num"].values, df_train["soh_r"].values, 1)

    # 2. Non-linear: Quadratic SOH = a * rpt_num^2 + b * rpt_num + c
    p_quad_c = np.polyfit(df_train["rpt_num"].values, df_train["soh_c"].values, 2)
    p_quad_r = np.polyfit(df_train["rpt_num"].values, df_train["soh_r"].values, 2)

    # Constant-training-mean
    mean_c = float(df_train["soh_c"].mean())
    mean_r = float(df_train["soh_r"].mean())

    # Helper function to predict
    def predict_models(df: pd.DataFrame) -> Dict[str, Dict[str, np.ndarray]]:
        # Pulse v2 (14 features)
        X_norm = (df[feature_cols].values - scaler_mean) / scaler_scale
        pred_v2_c = np.clip(b_c + X_norm @ w_c, 0.2, 1.2)
        pred_v2_r = np.clip(b_r + X_norm @ w_r, 0.2, 2.5)

        # Ridge
        X_ridge = scaler_tr.transform(df[feature_cols].values)
        pred_ridge_c = np.clip(ridge_c.predict(X_ridge), 0.2, 1.2)
        pred_ridge_r = np.clip(ridge_r.predict(X_ridge), 0.2, 2.5)

        # Constant mean
        pred_const_c = np.full(len(df), mean_c)
        pred_const_r = np.full(len(df), mean_r)

        # Age linear
        pred_lin_c = np.clip(np.polyval(p_lin_c, df["rpt_num"].values), 0.2, 1.2)
        pred_lin_r = np.clip(np.polyval(p_lin_r, df["rpt_num"].values), 0.2, 2.5)

        # Age quadratic
        pred_quad_c = np.clip(np.polyval(p_quad_c, df["rpt_num"].values), 0.2, 1.2)
        pred_quad_r = np.clip(np.polyval(p_quad_r, df["rpt_num"].values), 0.2, 2.5)

        return {
            "soh_c": {
                "constant_mean": pred_const_c,
                "ridge": pred_ridge_c,
                "soh_pulse_v2": pred_v2_c,
                "age_linear": pred_lin_c,
                "age_quadratic": pred_quad_c,
            },
            "soh_r": {
                "constant_mean": pred_const_r,
                "ridge": pred_ridge_r,
                "soh_pulse_v2": pred_v2_r,
                "age_linear": pred_lin_r,
                "age_quadratic": pred_quad_r,
            },
        }

    preds_val = predict_models(df_val)
    preds_sealed = predict_models(df_sealed)

    # 1. DEV Validation results (11 cells, 468 samples)
    results: Dict[str, Any] = {
        "dev_validation": {"soh_c": {}, "soh_r": {}},
        "sealed_cells": {"soh_c": {}, "soh_r": {}},
        "sealed_bootstrap_cell_mae": {"soh_c": {}, "soh_r": {}},
        "condition_holdout": {},
    }

    models = ["constant_mean", "ridge", "soh_pulse_v2", "age_linear", "age_quadratic"]

    for target in ["soh_c", "soh_r"]:
        y_val = df_val[target].values
        for m in models:
            mae = float(np.mean(np.abs(y_val - preds_val[target][m])))
            rmse = float(np.sqrt(np.mean((y_val - preds_val[target][m]) ** 2)))
            results["dev_validation"][target][m] = {"mae": mae, "rmse": rmse}

    # 2. Sealed cell overall results (21 cells, 956 samples)
    for target in ["soh_c", "soh_r"]:
        y_sealed = df_sealed[target].values
        for m in models:
            mae = float(np.mean(np.abs(y_sealed - preds_sealed[target][m])))
            rmse = float(np.sqrt(np.mean((y_sealed - preds_sealed[target][m]) ** 2)))
            results["sealed_cells"][target][m] = {"mae": mae, "rmse": rmse}

    # 3. Bootstrap over 21 sealed cells
    np.random.seed(42)
    B = 10000

    for target in ["soh_c", "soh_r"]:
        cell_maes = {m: [] for m in models}
        for cid in sealed_cells:
            sub = df_sealed[df_sealed["cell_id_str"] == cid]
            y_sub = sub[target].values
            sub_preds = predict_models(sub)
            for m in models:
                cell_maes[m].append(float(np.mean(np.abs(y_sub - sub_preds[target][m]))))

        for m in models:
            arr = np.array(cell_maes[m])
            mean_cell_mae = float(np.mean(arr))
            boot = [float(np.mean(np.random.choice(arr, size=len(arr), replace=True))) for _ in range(B)]
            ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])
            results["sealed_bootstrap_cell_mae"][target][m] = {
                "mean_cell_mae": mean_cell_mae,
                "ci_95_lo": float(ci_lo),
                "ci_95_hi": float(ci_hi),
            }

    # 4. Condition holdout (Groups 3 and 6: 12 cells, 497 samples)
    df_cond_tr = df_all[df_all["group_id"].isin(dev_conditions)]
    df_cond_te = df_all[df_all["group_id"].isin(held_out_groups)]

    p_cond_lin_c = np.polyfit(df_cond_tr["rpt_num"].values, df_cond_tr["soh_c"].values, 1)
    p_cond_quad_c = np.polyfit(df_cond_tr["rpt_num"].values, df_cond_tr["soh_c"].values, 2)
    mean_cond_c = float(df_cond_tr["soh_c"].mean())

    y_cond_te = df_cond_te["soh_c"].values
    pred_cond_const = np.full(len(df_cond_te), mean_cond_c)
    X_cond_norm = (df_cond_te[feature_cols].values - scaler_mean) / scaler_scale
    pred_cond_v2 = np.clip(b_c + X_cond_norm @ w_c, 0.2, 1.2)
    pred_cond_lin = np.clip(np.polyval(p_cond_lin_c, df_cond_te["rpt_num"].values), 0.2, 1.2)
    pred_cond_quad = np.clip(np.polyval(p_cond_quad_c, df_cond_te["rpt_num"].values), 0.2, 1.2)

    results["condition_holdout"] = {
        "constant_mean_mae": float(np.mean(np.abs(y_cond_te - pred_cond_const))),
        "soh_pulse_v2_mae": float(np.mean(np.abs(y_cond_te - pred_cond_v2))),
        "age_linear_mae": float(np.mean(np.abs(y_cond_te - pred_cond_lin))),
        "age_quadratic_mae": float(np.mean(np.abs(y_cond_te - pred_cond_quad))),
    }

    return results


def main():
    res = run_age_baseline_evaluation()
    print("=== DEV VALIDATION (11 cells, 468 samples) ===")
    for t in ["soh_c", "soh_r"]:
        print(f"--- {t.upper()} ---")
        for m, vals in res["dev_validation"][t].items():
            print(f"  {m:16s}: MAE = {vals['mae']:.4f}, RMSE = {vals['rmse']:.4f}")

    print("\n=== SEALED CELLS OVERALL (21 cells, 956 samples) [POST-HOC] ===")
    for t in ["soh_c", "soh_r"]:
        print(f"--- {t.upper()} ---")
        for m, vals in res["sealed_cells"][t].items():
            boot = res["sealed_bootstrap_cell_mae"][t][m]
            print(
                f"  {m:16s}: Sample MAE = {vals['mae']:.4f} | "
                f"Cell Mean MAE = {boot['mean_cell_mae']:.4f} [95% CI: {boot['ci_95_lo']:.4f}, {boot['ci_95_hi']:.4f}]"
            )

    print("\n=== CONDITION HOLDOUT (Groups 3 & 6: 12 cells, 497 samples) [POST-HOC] ===")
    for k, v in res["condition_holdout"].items():
        print(f"  {k:22s}: MAE = {v:.4f}")


if __name__ == "__main__":
    main()
