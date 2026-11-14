"""Training script for E8 Physics-Guided Residual GRU.

Trains ResidualGRU on CALCE A123 LFP cells to learn the structured residual error:
    Delta z_k = z_truth,k - z_physics,k

Training data:
- Profiles: DST and FUDS at 20 C, 25 C, 30 C.
- Includes matched starts and initial perturbation episodes (offsets +-5, +-10, +-15, +-20 pp).

Validation data (Held-out):
- Cross-profile: US06 at 20 C, 25 C, 30 C.
- Cross-temperature: DST at 40 C and 50 C.
"""

from dataclasses import replace
import os
from pathlib import Path
import random
import sys
from typing import List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.models.neural.gru_residual import ResidualGRU
from soc.models.plant import Measurement
from scripts.gauntlet_scenarios import prepare_scenario_data, ScenarioDataSet


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def run_e7v3_trajectory(
    data: ScenarioDataSet,
    params: ParamSet,
    start_soc: float,
    soc_std: float = 0.01,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run E7v3 filter on trajectory and extract input feature matrix and residual targets."""
    est = E7V3CompositeFilter(params)
    est.reset(start_soc, soc_std=soc_std)

    n = len(data.truth_soc)
    features = np.zeros((n, 13), dtype=np.float32)
    phys_soc = np.zeros(n, dtype=np.float32)

    for i in range(n):
        v = float(data.voltage_v[i])
        curr = float(data.current_a[i])
        t_c = float(data.temp_measured_c[i])
        dt = float(data.dt_arr[i])

        meas = Measurement(v=v, i=curr, temp_c=t_c, dt=dt, dropout=False)
        out = est.step(meas)

        phys_soc[i] = out.soc
        d_ocv = float(abs(est.ocv_table.derivative_soc(est.x[0], t_c)))

        features[i, 0] = curr
        features[i, 1] = v
        features[i, 2] = t_c
        features[i, 3] = out.soc
        features[i, 4] = out.soc_std
        features[i, 5] = out.voltage_residual if out.voltage_residual is not None else 0.0
        features[i, 6] = out.innovation_variance if out.innovation_variance is not None else 0.0
        features[i, 7] = out.kalman_gain_soc if out.kalman_gain_soc is not None else 0.0
        features[i, 8] = float(est.x[1])
        features[i, 9] = float(est.x[2])
        features[i, 10] = float(est.x[3])
        features[i, 11] = float(est.theta)
        features[i, 12] = d_ocv

    target_delta_z = (data.truth_soc - phys_soc).astype(np.float32)
    return features, phys_soc, target_delta_z


def create_windowed_tensors(
    features_list: List[np.ndarray],
    targets_list: List[np.ndarray],
    seq_len: int = 100,
    stride: int = 50,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Slice raw sequences into stacked window tensors efficiently."""
    x_slices = []
    y_slices = []

    for feat, targ in zip(features_list, targets_list):
        n = len(feat)
        if n <= seq_len:
            pad_len = seq_len - n
            feat_pad = np.pad(feat, ((0, pad_len), (0, 0)), mode="edge")
            targ_pad = np.pad(targ, (0, pad_len), mode="edge")
            x_slices.append(feat_pad)
            y_slices.append(targ_pad)
        else:
            for s in range(0, n - seq_len + 1, stride):
                e = s + seq_len
                x_slices.append(feat[s:e])
                y_slices.append(targ[s:e])

    x_tensor = torch.from_numpy(np.stack(x_slices, axis=0)).float()
    y_tensor = torch.from_numpy(np.stack(y_slices, axis=0)).unsqueeze(-1).float()
    return x_tensor, y_tensor


def generate_all_episodes(
    params: ParamSet,
    temps: list,
    profiles: list,
    include_perturbations: bool = True,
):
    all_features = []
    all_targets = []

    for t in temps:
        for prof in profiles:
            print(f"  Generating trajectory: {prof} at {t}C...")
            data = prepare_scenario_data(t, profile=prof)

            # 1. Matched start (S-A)
            feat_sa, _, targ_sa = run_e7v3_trajectory(data, params, data.start_soc, soc_std=0.005)
            all_features.append(feat_sa)
            all_targets.append(targ_sa)

            if include_perturbations:
                # 2. Perturbed starts from initial rest (+-5, +-10, +-15, +-20 pp)
                for offset in [-0.20, -0.10, -0.05, 0.05, 0.10, 0.20]:
                    s0 = min(max(data.start_soc + offset, 0.05), 0.98)
                    feat_p, _, targ_p = run_e7v3_trajectory(data, params, s0, soc_std=0.08)
                    all_features.append(feat_p)
                    all_targets.append(targ_p)

                # 3. Mid-plateau offsets (simulating S-B scenarios at 80, 60, 40% SOC)
                for z_target in [0.80, 0.60, 0.40]:
                    cross = np.where(data.truth_soc <= z_target)[0]
                    if len(cross) > 0:
                        idx_start = cross[0]
                        sub_data = ScenarioDataSet(
                            temp_c=data.temp_c,
                            cell_id=data.cell_id,
                            profile=data.profile,
                            time_s=data.time_s[idx_start:] - data.time_s[idx_start],
                            dt_arr=data.dt_arr[idx_start:],
                            current_a=data.current_a[idx_start:],
                            voltage_v=data.voltage_v[idx_start:],
                            temp_measured_c=data.temp_measured_c[idx_start:],
                            truth_soc=data.truth_soc[idx_start:],
                            cap_c20=data.cap_c20,
                            start_soc=data.truth_soc[idx_start],
                            i1_truth=data.i1_truth[idx_start:],
                            i2_truth=data.i2_truth[idx_start:],
                            h_truth=data.h_truth[idx_start:],
                            v_model_truth=data.v_model_truth[idx_start:],
                            ocv_mono=data.ocv_mono,
                        )
                        for offset in [-0.10, -0.05, 0.05, 0.10]:
                            s0 = min(max(data.truth_soc[idx_start] + offset, 0.05), 0.95)
                            feat_m, _, targ_m = run_e7v3_trajectory(sub_data, params, s0, soc_std=0.08)
                            all_features.append(feat_m)
                            all_targets.append(targ_m)

    return all_features, all_targets


def train_model():
    set_seed(42)
    device = torch.device("cpu")
    print(f"Using compute device: {device}")

    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    params = ParamSet.from_assumptions(assumptions, matched=True)

    cache_dir = repo_root / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "e8_episodes.npz"

    if cache_file.exists():
        print(f"Loading cached episodes from {cache_file}...")
        loaded = np.load(cache_file, allow_pickle=True)
        train_features = list(loaded["train_features"])
        train_targets = list(loaded["train_targets"])
        val_features = list(loaded["val_features"])
        val_targets = list(loaded["val_targets"])
    else:
        print("\n=== 1. Generating Training Data (DST & FUDS @ 20C, 25C, 30C on Cell A1-007) ===")
        all_train_features, all_train_targets = generate_all_episodes(
            params=params,
            temps=[20, 25, 30],
            profiles=["DST", "FUDS"],
            include_perturbations=True,
        )

        print("\n=== 2. Creating Inner Validation Split of TRAINING Data Only ===")
        # L3+: Strict split holds out 50C and A1-008 entirely.
        # Early stopping must use an inner split of the TRAINING data only (not US06 or DST 40C).
        n_episodes = len(all_train_features)
        rng = np.random.RandomState(42)
        perm = rng.permutation(n_episodes)
        split_point = int(0.80 * n_episodes)
        train_idx = perm[:split_point]
        val_idx = perm[split_point:]

        train_features = [all_train_features[i] for i in train_idx]
        train_targets = [all_train_targets[i] for i in train_idx]
        val_features = [all_train_features[i] for i in val_idx]
        val_targets = [all_train_targets[i] for i in val_idx]

        print(f"Split {n_episodes} training episodes into {len(train_features)} train and {len(val_features)} inner validation.")

        np.savez_compressed(
            cache_file,
            train_features=np.array(train_features, dtype=object),
            train_targets=np.array(train_targets, dtype=object),
            val_features=np.array(val_features, dtype=object),
            val_targets=np.array(val_targets, dtype=object),
        )
        print(f"Cached generated episodes to {cache_file}.")

    # Compute normalization
    concat_train = np.concatenate(train_features, axis=0)
    feat_mean = torch.from_numpy(np.mean(concat_train, axis=0).astype(np.float32))
    feat_std = torch.from_numpy(np.std(concat_train, axis=0).astype(np.float32))
    print(f"Computed normalization for {concat_train.shape[0]} training steps.")

    print("Building stacked tensor windows...")
    x_train, y_train = create_windowed_tensors(train_features, train_targets, seq_len=100, stride=50)
    x_val, y_val = create_windowed_tensors(val_features, val_targets, seq_len=100, stride=50)
    print(f"Tensors ready: x_train shape {x_train.shape}, x_val shape {x_val.shape}")

    train_ds = TensorDataset(x_train, y_train)
    val_ds = TensorDataset(x_val, y_val)

    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)

    model = ResidualGRU(
        in_features=13,
        hidden_size=32,
        num_layers=2,
        dropout=0.1,
        max_residual=0.25,
    ).to(device)
    model.set_normalization(feat_mean.to(device), feat_std.to(device))

    # Huber Loss (SmoothL1 with beta=0.01 = 1 pp)
    criterion = nn.SmoothL1Loss(beta=0.01)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=20, eta_min=1e-5)

    print("\n=== 3. Training Residual GRU (20 Epochs) ===")
    best_val_loss = float("inf")
    save_path = repo_root / "deliverable" / "e8_residual_gru.pt"
    save_path.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, 21):
        model.train()
        train_loss = 0.0
        for x_b, y_b in train_loader:
            x_b = x_b.to(device)
            y_b = y_b.to(device)

            optimizer.zero_grad()
            pred, _ = model(x_b, normalize=True)
            loss = criterion(pred, y_b)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss += loss.item() * len(x_b)

        scheduler.step()
        train_loss /= len(train_ds)

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for x_v, y_v in val_loader:
                x_v = x_v.to(device)
                y_v = y_v.to(device)
                pred_v, _ = model(x_v, normalize=True)
                v_loss = criterion(pred_v, y_v)
                val_loss += v_loss.item() * len(x_v)
        val_loss /= len(val_ds)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save({
                "model_state_dict": model.state_dict(),
                "in_features": model.in_features,
                "hidden_size": model.hidden_size,
                "num_layers": model.num_layers,
                "max_residual": model.max_residual,
                "feature_mean": model.feature_mean.cpu(),
                "feature_scale": model.feature_scale.cpu(),
                "epoch": epoch,
                "val_loss": val_loss,
            }, save_path)
            marker = " [Saved Best]"
        else:
            marker = ""

        print(f"Epoch {epoch:2d}/20 | Train Loss: {train_loss:.6f} | Val Loss: {val_loss:.6f}{marker}")

    print(f"\nTraining Complete. Best checkpoint saved to {save_path} (Val Loss: {best_val_loss:.6f})")


if __name__ == "__main__":
    train_model()
