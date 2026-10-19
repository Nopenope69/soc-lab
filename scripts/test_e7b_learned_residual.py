"""Test Optional E7b learned residual on DST scenarios.

Trains a linear model on voltage-residual features from DST at 20 and 30 C.
Evaluates on held-out DST at 40 and 50 C.
Checks if held-out BCD RMSE improves by >= 20% relative over E7 (2.578 pp -> <= 2.062 pp),
and whether it passes GATE 2 clause (ii) (>= 80% individual case wins).
"""

import pickle
from pathlib import Path
import sys
import numpy as np
from dataclasses import replace

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, Measurement
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from scripts.gauntlet_scenarios import (
    prepare_scenario_data,
    init_estimator_state,
    invert_ocv_table,
    ScenarioDataSet,
)

# 1. Load assumptions and winning E2 parameters from checkpoint
with open(repo_root / "reports" / "gauntlet" / ".stage2_checkpoint.pkl", "rb") as f:
    cp = pickle.load(f)
p_e7 = cp["best_by_estimator"]["E2"]["params"]

print("Loaded E7 parameters from Stage 2 checkpoint:")
print(f"  q_soc: {p_e7.process_noise_q_soc}")
print(f"  q_rc: {p_e7.process_noise_q_rc}")
print(f"  q_hyst: {p_e7.process_noise_q_hysteresis}")
print(f"  r_v: {p_e7.measurement_noise_r_v}")

data_by_temp = {}
for t in [20, 30, 40, 50]:
    data_by_temp[t] = prepare_scenario_data(t, profile="DST")


def get_scenarios_for_temp(data: ScenarioDataSet):
    scenarios = []
    n = len(data.truth_soc)
    # S-B
    for z_target in [0.80, 0.60, 0.40, 0.20]:
        cross = np.where(data.truth_soc <= z_target)[0]
        if len(cross) == 0:
            continue
        k0 = int(cross[0])
        for off_pp in [-10.0, -5.0, 5.0, 10.0]:
            z_init = min(max(float(data.truth_soc[k0] + off_pp / 100.0), 0.0), 1.0)
            scenarios.append({
                "type": "SB",
                "k_s": k0,
                "k_e": n,
                "z_init": z_init,
                "i1": data.i1_truth[k0],
                "i2": data.i2_truth[k0],
                "h": data.h_truth[k0],
            })
    # S-C
    for z_s, z_e in [(0.80, 0.30), (0.90, 0.40)]:
        idx_s = np.where(data.truth_soc <= z_s)[0]
        idx_e = np.where(data.truth_soc <= z_e)[0]
        if len(idx_s) == 0 or len(idx_e) == 0:
            continue
        k_s = int(idx_s[0])
        k_e = int(idx_e[0])
        if k_e > k_s:
            scenarios.append({
                "type": "SC",
                "k_s": k_s,
                "k_e": k_e,
                "z_init": float(data.truth_soc[k_s]),
                "i1": data.i1_truth[k_s],
                "i2": data.i2_truth[k_s],
                "h": data.h_truth[k_s],
            })
    # S-D
    v_rest = float(data.voltage_v[0])
    z_inv = invert_ocv_table(v_rest, data.ocv_mono)
    scenarios.append({
        "type": "SD",
        "k_s": 0,
        "k_e": n,
        "z_init": z_inv,
        "i1": 0.0,
        "i2": 0.0,
        "h": 0.0,
    })
    return scenarios


def collect_features_and_targets(temp_list):
    X_list = []
    y_list = []
    for t in temp_list:
        data = data_by_temp[t]
        scenarios = get_scenarios_for_temp(data)
        for sc in scenarios:
            est = E2EKFHysteresis(p_e7)
            init_estimator_state(est, sc["z_init"], sc["i1"], sc["i2"], sc["h"])
            
            r_smooth = 0.0
            lambda_r = 0.99
            
            for k in range(sc["k_s"], sc["k_e"]):
                dt = float(data.dt_arr[k]) if k > 0 else 1.0
                v = float(data.voltage_v[k])
                i = float(data.current_a[k])
                m = Measurement(v=v, i=i, temp_c=float(t), dt=dt, dropout=False)
                
                est_out = est.step(m)
                soc_est = est_out.soc
                r = est_out.voltage_residual if est_out.voltage_residual is not None else 0.0
                r_smooth = lambda_r * r_smooth + (1.0 - lambda_r) * r
                
                truth_z = float(data.truth_soc[k])
                err_z = truth_z - soc_est
                
                feat = [
                    r,
                    r_smooth,
                    i,
                    soc_est,
                    float(t) / 50.0,
                    r * i,
                    r_smooth / (abs(i) + 0.1),
                    1.0,
                ]
                X_list.append(feat)
                y_list.append(err_z)
                
    return np.array(X_list), np.array(y_list)

print("\nExtracting training features on DST at 20 and 30 C...")
X_train, y_train = collect_features_and_targets([20, 30])
print(f"X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")

# Train Ridge model with pure numpy
alpha = 1000.0
reg_eye = np.eye(X_train.shape[1])
reg_eye[-1, -1] = 0.0  # Do not regularize bias
w = np.linalg.solve(X_train.T @ X_train + alpha * reg_eye, X_train.T @ y_train)
print("Ridge Weights:", w[:-1], "Intercept:", w[-1])

# Evaluate on held-out DST at 40 and 50 C
print("\nEvaluating on held-out 40 and 50 C...")
e7_rmses = []
e7b_rmses = []
e0_rmses = []
beat_e0_count = 0
total_count = 0

p_e0 = replace(p_e7, anchor_enabled=False, rest_anchor_enabled=False)

for t in [40, 50]:
    data = data_by_temp[t]
    scenarios = get_scenarios_for_temp(data)
    for sc in scenarios:
        total_count += 1
        
        # E0 run
        e0 = E0CoulombCounting(p_e0)
        e0.reset(sc["z_init"])
        e0_soc = []
        for k in range(sc["k_s"], sc["k_e"]):
            dt = float(data.dt_arr[k]) if k > 0 else 1.0
            m = Measurement(v=float(data.voltage_v[k]), i=float(data.current_a[k]), temp_c=float(t), dt=dt, dropout=False)
            e0_soc.append(e0.step(m).soc)
        truth_slice = data.truth_soc[sc["k_s"]:sc["k_e"]]
        rmse_e0 = float(np.sqrt(np.mean(((np.array(e0_soc) - truth_slice)*100.0)**2)))
        e0_rmses.append(rmse_e0)
        
        # E7 & E7b run
        est = E2EKFHysteresis(p_e7)
        init_estimator_state(est, sc["z_init"], sc["i1"], sc["i2"], sc["h"])
        e7_soc = []
        e7b_soc = []
        r_smooth = 0.0
        lambda_r = 0.99
        
        for k in range(sc["k_s"], sc["k_e"]):
            dt = float(data.dt_arr[k]) if k > 0 else 1.0
            v = float(data.voltage_v[k])
            i = float(data.current_a[k])
            m = Measurement(v=v, i=i, temp_c=float(t), dt=dt, dropout=False)
            est_out = est.step(m)
            soc_est = est_out.soc
            e7_soc.append(soc_est)
            
            r = est_out.voltage_residual if est_out.voltage_residual is not None else 0.0
            r_smooth = lambda_r * r_smooth + (1.0 - lambda_r) * r
            
            feat = np.array([
                r,
                r_smooth,
                i,
                soc_est,
                float(t) / 50.0,
                r * i,
                r_smooth / (abs(i) + 0.1),
                1.0,
            ])
            corr = float(feat @ w)
            corr = np.clip(corr, -0.15, 0.15)
            e7b_soc.append(np.clip(soc_est + corr, 0.0, 1.0))
            
        rmse_e7 = float(np.sqrt(np.mean(((np.array(e7_soc) - truth_slice)*100.0)**2)))
        rmse_e7b = float(np.sqrt(np.mean(((np.array(e7b_soc) - truth_slice)*100.0)**2)))
        
        e7_rmses.append(rmse_e7)
        e7b_rmses.append(rmse_e7b)
        
        if rmse_e7b < rmse_e0:
            beat_e0_count += 1

mean_e7 = float(np.mean(e7_rmses))
mean_e7b = float(np.mean(e7b_rmses))
rel_improv = (mean_e7 - mean_e7b) / mean_e7 * 100.0
win_rate = (beat_e0_count / total_count) * 100.0

print(f"\n--- E7 vs E7b Comparison on Held-Out (40 & 50 C) ---")
print(f"E7 Held-out BCD Mean RMSE:  {mean_e7:.3f} pp")
print(f"E7b Held-out BCD Mean RMSE: {mean_e7b:.3f} pp")
print(f"Relative Improvement:      {rel_improv:+.2f}% (Requirement: >= +20.0%)")
print(f"Beat E0 Individual Wins:   {beat_e0_count}/{total_count} ({win_rate:.1f}%) (Requirement: >= 80.0%)")
