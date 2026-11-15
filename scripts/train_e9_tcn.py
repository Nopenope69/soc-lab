"""Training script for BatteryTCN on CALCE A123 LFP cells.

Prepares sliding-window time-series data:
    Features: [current_a, voltage_v, temp_c, delta_v, delta_i]
    Target: truth_soc in [0, 1]

Trains BatteryTCN using Huber loss, AdamW, and CosineAnnealingLR.
Saves model checkpoint to deliverable/e9_tcn.pt.
"""

from pathlib import Path
import random
import sys
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.models.neural.tcn import BatteryTCN
from scripts.gauntlet_scenarios import prepare_scenario_data


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_tcn_sequences(window_size: int = 32, stride: int = 4):
    train_windows_x = []
    train_windows_y = []
    val_windows_x = []
    val_windows_y = []

    train_configs = [
        ("DST", 20), ("DST", 25), ("DST", 30),
        ("FUDS", 20), ("FUDS", 25), ("FUDS", 30),
    ]
    val_configs = [
        ("US06", 20), ("US06", 25), ("US06", 30),
    ]

    for prof, temp in train_configs:
        data = prepare_scenario_data(temp, profile=prof)
        v = data.voltage_v
        curr = data.current_a
        t_c = data.temp_measured_c
        n = len(v)

        dv = np.diff(v, prepend=v[0])
        di = np.diff(curr, prepend=curr[0])

        feats = np.stack([curr, v, t_c, dv, di], axis=1).astype(np.float32)
        target = data.truth_soc.astype(np.float32)

        for s in range(0, n - window_size + 1, stride):
            e = s + window_size
            train_windows_x.append(feats[s:e].T)  # [5, window_size]
            train_windows_y.append(target[e - 1])

    for prof, temp in val_configs:
        data = prepare_scenario_data(temp, profile=prof)
        v = data.voltage_v
        curr = data.current_a
        t_c = data.temp_measured_c
        n = len(v)

        dv = np.diff(v, prepend=v[0])
        di = np.diff(curr, prepend=curr[0])

        feats = np.stack([curr, v, t_c, dv, di], axis=1).astype(np.float32)
        target = data.truth_soc.astype(np.float32)

        for s in range(0, n - window_size + 1, stride * 2):
            e = s + window_size
            val_windows_x.append(feats[s:e].T)
            val_windows_y.append(target[e - 1])

    X_train = np.stack(train_windows_x, axis=0)  # [N, 5, 32]
    y_train = np.array(train_windows_y, dtype=np.float32)[:, None]  # [N, 1]
    X_val = np.stack(val_windows_x, axis=0)
    y_val = np.array(val_windows_y, dtype=np.float32)[:, None]

    return X_train, y_train, X_val, y_val


def train_tcn():
    set_seed(42)
    device = torch.device("cpu")

    cache_file = repo_root / "data" / "cache" / "tcn_data.npz"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    if cache_file.exists():
        print("Loading cached TCN sequences from", cache_file)
        loaded = np.load(cache_file)
        X_train = loaded["X_train"]
        y_train = loaded["y_train"]
        X_val = loaded["X_val"]
        y_val = loaded["y_val"]
    else:
        print("Building sliding-window TCN sequences...")
        X_train, y_train, X_val, y_val = build_tcn_sequences(window_size=32, stride=4)
        np.savez_compressed(cache_file, X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val)
        print("Cached TCN dataset to", cache_file)

    print(f"X_train: {X_train.shape}, y_train: {y_train.shape}")
    print(f"X_val:   {X_val.shape}, y_val:   {y_val.shape}")

    # Compute channel-wise mean and std across all time steps
    # X_train is [N, 5, 32]
    flat_feats = X_train.transpose(1, 0, 2).reshape(5, -1)
    mean_ch = torch.from_numpy(flat_feats.mean(axis=1)).float()
    scale_ch = torch.from_numpy(flat_feats.std(axis=1)).float()

    model = BatteryTCN(in_channels=5, dropout=0.05).to(device)
    model.set_normalization(mean_ch, scale_ch)

    train_ds = TensorDataset(torch.from_numpy(X_train).float(), torch.from_numpy(y_train).float())
    val_ds = TensorDataset(torch.from_numpy(X_val).float(), torch.from_numpy(y_val).float())

    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False)

    criterion = nn.HuberLoss(delta=0.02)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=12)

    best_val_rmse = float("inf")
    best_weights = None

    print("Beginning training...")
    for epoch in range(1, 13):
        model.train()
        train_loss = 0.0
        n_samples = 0

        for x_b, y_b in train_loader:
            x_b, y_b = x_b.to(device), y_b.to(device)
            optimizer.zero_grad()
            pred = model(x_b)
            loss = criterion(pred, y_b)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_loss += loss.item() * len(y_b)
            n_samples += len(y_b)

        scheduler.step()
        train_loss /= n_samples

        # Validation
        model.eval()
        val_sq_err = 0.0
        n_val = 0
        with torch.no_grad():
            for x_b, y_b in val_loader:
                x_b, y_b = x_b.to(device), y_b.to(device)
                pred = model(x_b)
                val_sq_err += torch.sum((pred - y_b) ** 2).item()
                n_val += len(y_b)

        val_rmse = np.sqrt(val_sq_err / n_val) * 100.0  # percentage
        print(f"Epoch {epoch:2d}/12 | Train Loss: {train_loss:.6f} | Val RMSE (US06): {val_rmse:.3f}%")

        if val_rmse < best_val_rmse:
            best_val_rmse = val_rmse
            best_weights = {
                "model_state_dict": model.state_dict(),
                "feat_mean": mean_ch,
                "feat_scale": scale_ch,
                "best_val_rmse": best_val_rmse,
                "window_size": 32,
            }

    out_dir = repo_root / "models" / "experimental"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "e9_tcn.pt"
    torch.save(best_weights, out_path)
    print(f"Saved best model checkpoint to {out_path} (Best Val RMSE: {best_val_rmse:.3f}%)")


if __name__ == "__main__":
    train_tcn()
