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
        print("Cache not found. Generating training episodes on clean checkout...")
        assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
        params = ParamSet.from_assumptions(assumptions, matched=True)
        all_features, all_targets = generate_all_episodes(
            params=params,
            temps=[20, 25, 30],
            profiles=["DST", "FUDS"],
            include_perturbations=True,
        )
        # L3+: Inner split of TRAINING data only (50C and A1-008 held out entirely; no US06 or 40C)
        n_episodes = len(all_features)
        rng = np.random.RandomState(42)
        perm = rng.permutation(n_episodes)
        split_point = int(0.80 * n_episodes)
        train_idx = perm[:split_point]
        val_idx = perm[split_point:]

        train_features = [all_features[i] for i in train_idx]
        train_targets = [all_targets[i] for i in train_idx]
        val_features = [all_features[i] for i in val_idx]
        val_targets = [all_targets[i] for i in val_idx]

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            cache_file,
            train_features=np.array(train_features, dtype=object),
            train_targets=np.array(train_targets, dtype=object),
            val_features=np.array(val_features, dtype=object),
            val_targets=np.array(val_targets, dtype=object),
        )
        print(f"Cached {n_episodes} generated episodes to {cache_file}.")

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

    out_dir = repo_root / "models" / "experimental"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_txt_path = out_dir / "e8_residual_lgbm.txt"
    booster.save_model(str(model_txt_path))
    print(f"Successfully saved LightGBM model to {model_txt_path} ({model_txt_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    train_and_export_lgbm()
