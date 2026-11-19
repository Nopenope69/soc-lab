#!/usr/bin/env python3
"""SOH_R Tautology and Trivial Baseline Evaluation for UConn REIL Dataset 5 (Task V2.12).

Documents that SOH_R ground truth and feature extraction share the same measurement:
- Label: SOH_R = r_pulse_10s(RPT k) / r_pulse_10s(RPT 0) (uconn_loader.py:128-140)
- Feature: r_10s_ohm = |delta_v_10s| / |delta_i| from the identical Step 20 pulse.

Evaluates a trivial baseline fitted on DEV training cells only:
    SOH_R_hat = r_10s_ohm / mean(RPT-0 r_10s_ohm over DEV train cells)
against constant-mean, age-only, Ridge, frozen 14-feature soh_pulse_v2,
and the 11-feature post-hoc model.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import yaml


def bootstrap_cell_ci(
    df: pd.DataFrame,
    pred_col: str,
    target_col: str = "soh_r",
    n_boot: int = 2000,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """Compute cell-bootstrap 95% confidence interval for mean MAE across cells."""
    rng = np.random.default_rng(seed)
    cells = df["cell_id_str"].unique()
    n_cells = len(cells)

    # Precalculate per-cell MAE
    cell_maes = {}
    for c in cells:
        sub = df[df["cell_id_str"] == c]
        cell_maes[c] = float(np.mean(np.abs(sub[target_col].values - sub[pred_col].values)))

    cell_mae_list = np.array([cell_maes[c] for c in cells])
    point_mae = float(np.mean(cell_mae_list))

    # Bootstrap cell-level resamples
    boot_means = []
    for _ in range(n_boot):
        sample_cells = rng.choice(cells, size=n_cells, replace=True)
        boot_means.append(np.mean([cell_maes[c] for c in sample_cells]))

    ci_low = float(np.percentile(boot_means, 2.5))
    ci_high = float(np.percentile(boot_means, 97.5))
    return point_mae, ci_low, ci_high


def run_tautology_evaluation() -> Dict[str, Any]:
    root = Path(__file__).resolve().parent.parent.parent
    splits_path = root / "configs" / "validation" / "uconn_splits.yaml"
    calib14_path = root / "deliverable" / "calibrations" / "uconn_soh_pulse_v2_frozen_v27.json"
    calib11_path = root / "deliverable" / "calibrations" / "uconn_soh_pulse_v2.json"
    dev_feat_path = root / "reports" / "validation" / "uconn_dev_features.csv"
    sealed_feat_path = root / "reports" / "validation" / "uconn_sealed_features.csv"

    with open(splits_path, "r", encoding="utf-8") as f:
        splits = yaml.safe_load(f)
    with open(calib14_path, "r", encoding="utf-8") as f:
        c14 = json.load(f)
    with open(calib11_path, "r", encoding="utf-8") as f:
        c11 = json.load(f)

    train_cells = [str(c).zfill(2) for c in splits["cell_holdout"]["dev_cells"]["train_cells"]]
    val_cells = [str(c).zfill(2) for c in splits["cell_holdout"]["dev_cells"]["val_cells"]]
    sealed_cells = [str(c).zfill(2) for c in splits["cell_holdout"]["sealed_test_cells"]]
    held_out_groups = splits["condition_holdout"]["sealed_test_conditions"]

    df_dev = pd.read_csv(dev_feat_path)
    df_sealed = pd.read_csv(sealed_feat_path)
    df_dev["cell_id_str"] = df_dev["cell_id"].astype(str).str.zfill(2)
    df_sealed["cell_id_str"] = df_sealed["cell_id"].astype(str).str.zfill(2)

    df_all = pd.concat([df_dev, df_sealed], ignore_index=True)
    df_train = df_dev[df_dev["cell_id_str"].isin(train_cells)].copy()
    df_val = df_dev[df_dev["cell_id_str"].isin(val_cells)].copy()
    df_sealed_cells = df_sealed[df_sealed["cell_id_str"].isin(sealed_cells)].copy()
    df_cond = df_all[df_all["group_id"].isin(held_out_groups)].copy()

    # 1. Fit Trivial Baseline strictly on DEV train cells
    # mean of RPT-0 r_10s_ohm over DEV training cells
    df_train_rpt0 = df_train[df_train["rpt_num"] == 0]
    mean_r0_train = float(df_train_rpt0["r_10s_ohm"].mean())
    print("=" * 80)
    print("SOH_R TAUTOLOGY & TRIVIAL BASELINE EVALUATION")
    print("=" * 80)
    print(f"Mean RPT-0 r_10s_ohm over DEV train cells: {mean_r0_train:.6f} Ohm (across {len(df_train_rpt0)} cells)")

    # 2. Fit Constant-Mean Baseline on DEV train
    mean_soh_r_train = float(df_train["soh_r"].mean())

    # 3. Fit Age-Quadratic Baseline on DEV train
    p_quad_r = np.polyfit(df_train["rpt_num"].values, df_train["soh_r"].values, 2)

    # 4. Fit Ridge Model (14 features) on DEV train
    cols14 = c14["features"]
    scaler_tr14 = StandardScaler()
    X_tr14 = scaler_tr14.fit_transform(df_train[cols14].values)
    ridge_r = Ridge(alpha=0.005, random_state=42).fit(X_tr14, df_train["soh_r"].values)

    # 5. Extract 14-feature model weights
    mean14 = np.array(c14["scaler"]["mean"])
    scale14 = np.array(c14["scaler"]["scale"])
    w_r14 = np.array(c14["soh_r"]["coefficients"])
    b_r14 = c14["soh_r"]["intercept"]

    # 6. Extract 11-feature post-hoc model weights
    cols11 = c11["features"]
    mean11 = np.array(c11["scaler"]["mean"])
    scale11 = np.array(c11["scaler"]["scale"])
    w_r11 = np.array(c11["soh_r"]["coefficients"])
    b_r11 = c11["soh_r"]["intercept"]

    def compute_predictions(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        # Constant-mean
        out["pred_const"] = mean_soh_r_train
        # Age-quadratic
        out["pred_age_quad"] = np.clip(np.polyval(p_quad_r, df["rpt_num"].values), 0.2, 2.5)
        # Trivial baseline
        out["pred_trivial"] = np.clip(df["r_10s_ohm"].values / mean_r0_train, 0.2, 2.5)
        # Ridge (14 feat)
        X_r14 = scaler_tr14.transform(df[cols14].values)
        out["pred_ridge"] = np.clip(ridge_r.predict(X_r14), 0.2, 2.5)
        # soh_pulse_v2 (14 feat)
        X_norm14 = (df[cols14].values - mean14) / scale14
        out["pred_v2_14"] = np.clip(b_r14 + X_norm14 @ w_r14, 0.2, 2.5)
        # post-hoc 11 feat
        X_norm11 = (df[cols11].values - mean11) / scale11
        out["pred_v2_11"] = np.clip(b_r11 + X_norm11 @ w_r11, 0.2, 2.5)
        return out

    df_val_pred = compute_predictions(df_val)
    df_sealed_pred = compute_predictions(df_sealed_cells)
    df_cond_pred = compute_predictions(df_cond)

    models = [
        ("constant_mean", "pred_const"),
        ("age_quadratic", "pred_age_quad"),
        ("trivial_baseline", "pred_trivial"),
        ("ridge_14feat", "pred_ridge"),
        ("soh_pulse_v2_14feat", "pred_v2_14"),
        ("post_hoc_11feat", "pred_v2_11"),
    ]

    results = {}

    def report_partition(name: str, df: pd.DataFrame, is_post_hoc: bool = False):
        tag = " [POST-HOC, ADDED AFTER UNSEALING]" if is_post_hoc else ""
        print(f"\n=== {name} (N_cells={len(df['cell_id_str'].unique())}, N_samples={len(df)}){tag} ===")
        part_res = {}
        for m_name, pred_col in models:
            sample_mae = float(np.mean(np.abs(df["soh_r"].values - df[pred_col].values)))
            sample_rmse = float(np.sqrt(np.mean((df["soh_r"].values - df[pred_col].values) ** 2)))
            cell_mae, ci_low, ci_high = bootstrap_cell_ci(df, pred_col)
            part_res[m_name] = {
                "sample_mae": sample_mae,
                "sample_rmse": sample_rmse,
                "cell_mae": cell_mae,
                "ci_95": [ci_low, ci_high],
            }
            print(
                f"  {m_name:<20}: Sample MAE = {sample_mae:.4f} | "
                f"Cell Mean MAE = {cell_mae:.4f} [95% CI: {ci_low:.4f}, {ci_high:.4f}]"
            )
        results[name] = part_res

    # 1. DEV Validation (Pre-unsealing development partition)
    report_partition("DEV VALIDATION", df_val_pred, is_post_hoc=False)

    # 2. Sealed Test Cells (Post-hoc, added after unsealing)
    report_partition("SEALED TEST CELLS", df_sealed_pred, is_post_hoc=True)

    # 3. Condition Holdout (Post-hoc, added after unsealing)
    report_partition("CONDITION HOLDOUT", df_cond_pred, is_post_hoc=True)

    return results


if __name__ == "__main__":
    run_tautology_evaluation()
