"""Cache regeneration script for SOC Lab dataset artifacts.

Regenerates data/cache/e8_episodes.npz (and other neural cache files) directly
from raw CALCE A123 data on clean checkout.

Enforces strict evaluation split (L3+):
- Training domain: DST & FUDS at 20 C, 25 C, 30 C on Cell A1-007.
- Inner split: 80% train / 20% validation strictly of the training data.
- Held-out: 50 C and Cell A1-008 are held out entirely.
- US06 and 40 C are excluded from training and validation (test sets only).
"""

import argparse
from pathlib import Path
import sys
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from scripts.train_e8_residual_gru import generate_all_episodes


def regenerate_e8_cache(force: bool = False) -> Path:
    cache_dir = repo_root / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "e8_episodes.npz"

    if cache_file.exists() and not force:
        print(f"Cache already exists at {cache_file}. Use --force to regenerate.")
        return cache_file

    print("\n[Regenerate Cache] Loading assumptions and parameter set...")
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    params = ParamSet.from_assumptions(assumptions, matched=True)

    print("[Regenerate Cache] Generating training episodes (DST & FUDS @ 20C, 25C, 30C on Cell A1-007)...")
    all_features, all_targets = generate_all_episodes(
        params=params,
        temps=[20, 25, 30],
        profiles=["DST", "FUDS"],
        include_perturbations=True,
    )

    n_episodes = len(all_features)
    print(f"[Regenerate Cache] Generated {n_episodes} raw physical episodes.")

    # L3+: Inner split of TRAINING data only (holding out 50C and A1-008 entirely)
    rng = np.random.RandomState(42)
    perm = rng.permutation(n_episodes)
    split_point = int(0.80 * n_episodes)
    train_idx = perm[:split_point]
    val_idx = perm[split_point:]

    train_features = [all_features[i] for i in train_idx]
    train_targets = [all_targets[i] for i in train_idx]
    val_features = [all_features[i] for i in val_idx]
    val_targets = [all_targets[i] for i in val_idx]

    print(f"[Regenerate Cache] Inner split: {len(train_features)} train, {len(val_features)} inner val.")

    np.savez_compressed(
        cache_file,
        train_features=np.array(train_features, dtype=object),
        train_targets=np.array(train_targets, dtype=object),
        val_features=np.array(val_features, dtype=object),
        val_targets=np.array(val_targets, dtype=object),
    )
    print(f"[Regenerate Cache] Successfully wrote {cache_file} ({cache_file.stat().st_size / (1024 * 1024):.2f} MB).")
    return cache_file


def main():
    parser = argparse.ArgumentParser(description="Regenerate cached data artifacts for SOC Lab.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of existing cache.")
    args = parser.parse_args()

    regenerate_e8_cache(force=args.force)


if __name__ == "__main__":
    main()
