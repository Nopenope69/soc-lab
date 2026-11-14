"""Training and export script for E8 Physics-Guided Residual LightGBM.

Trains a LightGBM regressor on structured E7v3 residuals across LFP (A123) driving cycles
using Huber loss and saves the trained booster model to deliverable/e8_residual_lgbm.txt.
"""

from pathlib import Path
import sys
import numpy as np
import lightgbm as lgb

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from scripts.train_e8_residual_gru import generate_all_episodes


def train_and_export_lgbm():
    cache_file = repo_root / "data" / "cache" / "e8_episodes.npz"
    if not cache_file.exists():
        print("Generating training episodes...")
        assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
        params = ParamSet.from_assumptions(assumptions, matched=True)
        generate_all_episodes(params, temps=[20, 25, 30], cache_path=cache_file)

    print("Loading cached episodes from", cache_file)
    loaded = np.load(cache_file, allow_pickle=True)
    X_train = np.concatenate(list(loaded["train_features"]), axis=0)
    y_train = np.concatenate(list(loaded["train_targets"]), axis=0)
    X_val = np.concatenate(list(loaded["val_features"]), axis=0)
    y_val = np.concatenate(list(loaded["val_targets"]), axis=0)

    print(f"X_train shape: {X_train.shape}, X_val shape: {X_val.shape}")

    dtrain = lgb.Dataset(X_train, label=y_train)
    dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

    hyperparameters = {
        "objective": "huber",
        "huber_alpha": 0.9,
        "metric": "rmse",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_child_samples": 50,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "verbosity": -1,
        "n_jobs": 4,
        "seed": 42,
    }

    print("Training LightGBM residual booster...")
    booster = lgb.train(
        hyperparameters,
        dtrain,
        num_boost_round=120,
        valid_sets=[dval],
        callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=True)],
    )

    out_dir = repo_root / "deliverable"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_txt_path = out_dir / "e8_residual_lgbm.txt"
    booster.save_model(str(model_txt_path))
    print(f"Successfully saved LightGBM model to {model_txt_path} ({model_txt_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    train_and_export_lgbm()
