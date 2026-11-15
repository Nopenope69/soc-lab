"""Benchmark script comparing 2025-2026 Architectures: E7v3, E8, E8-LGBM, and E9.

Evaluates:
- E7v3: Adaptive Physics Composite Filter
- E8: Physics-Guided Residual GRU (arXiv:2606.12000)
- E8-LGBM: Physics-Guided Residual LightGBM
- E9: TCN + Unscented Kalman Filter (PLOS ONE June 2026)

Profiles: DST and US06 at 20°C and 30°C on CALCE A123 LFP cells.
"""

import os
from pathlib import Path
import sys
import numpy as np

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# Warm up LightGBM booster before Torch imports to prevent macOS libomp symbol clash
import lightgbm as lgb
_lgbm_model = repo_root / "models" / "experimental" / "e8_residual_lgbm.txt"
if not _lgbm_model.exists():
    _lgbm_model = repo_root / "deliverable" / "e8_residual_lgbm.txt"
_warmup = lgb.Booster(model_file=str(_lgbm_model))
import torch
torch.set_num_threads(1)

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.estimators.e8_residual_gru import E8ResidualGRUEstimator
from soc.estimators.e8_residual_lgbm import E8ResidualLGBMEstimator
from soc.estimators.e9_tcn_ukf import E9TCNUKFEstimator
from soc.models.plant import Measurement
from scripts.gauntlet_scenarios import prepare_scenario_data


def evaluate_all():
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    params = ParamSet.from_assumptions(assumptions, matched=True)

    print("=" * 80)
    print(f"{'Profile':<8} {'Temp':<6} | {'E7v3 (Phys)':<12} {'E8 (GRU)':<12} {'E8-LGBM':<12} {'E9 (TCN-UKF)':<12}")
    print("=" * 80)

    for prof in ["DST", "US06"]:
        for temp in [20, 30]:
            data = prepare_scenario_data(temp, profile=prof)
            n = len(data.truth_soc)

            e7 = E7V3CompositeFilter(params)
            e7.reset(data.start_soc, soc_std=0.005)

            e8 = E8ResidualGRUEstimator(params)
            e8.reset(data.start_soc, soc_std=0.005)

            elgb = E8ResidualLGBMEstimator(params)
            elgb.reset(data.start_soc, soc_std=0.005)

            e9 = E9TCNUKFEstimator(params)
            e9.reset(data.start_soc, soc_std=0.005)

            soc_e7, soc_e8, soc_lgb, soc_e9 = [], [], [], []

            for i in range(n):
                m = Measurement(
                    v=data.voltage_v[i],
                    i=data.current_a[i],
                    temp_c=data.temp_measured_c[i],
                    dt=data.dt_arr[i],
                    dropout=False,
                )
                soc_e7.append(e7.step(m).soc)
                soc_e8.append(e8.step(m).soc)
                soc_lgb.append(elgb.step(m).soc)
                soc_e9.append(e9.step(m).soc)

            rmse_e7 = np.sqrt(np.mean(((np.array(soc_e7) - data.truth_soc) * 100) ** 2))
            rmse_e8 = np.sqrt(np.mean(((np.array(soc_e8) - data.truth_soc) * 100) ** 2))
            rmse_lgb = np.sqrt(np.mean(((np.array(soc_lgb) - data.truth_soc) * 100) ** 2))
            rmse_e9 = np.sqrt(np.mean(((np.array(soc_e9) - data.truth_soc) * 100) ** 2))

            print(
                f"{prof:<8} {temp}C   | "
                f"{rmse_e7:6.3f}%     "
                f"{rmse_e8:6.3f}%     "
                f"{rmse_lgb:6.3f}%     "
                f"{rmse_e9:6.3f}%"
            )

    print("=" * 80)


if __name__ == "__main__":
    evaluate_all()
