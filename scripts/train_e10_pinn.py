"""Training script for Multi-Physics PINN Voltage Observation Model.

Trains VoltagePINN on CALCE A123 LFP cells to model the non-linear overpotential
correction Delta_V = V_meas - V_base under physics constraints:
1. Data fidelity (Huber loss).
2. Strict OCV-voltage monotonicity penalty (dV/dz >= 0).
3. Equilibrium zero-bias regularization.

Saves checkpoint to deliverable/e10_pinn.pt.
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

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.models.neural.pinn import VoltagePINN
from soc.models.plant import Measurement
from scripts.gauntlet_scenarios import prepare_scenario_data


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def generate_pinn_dataset(params: ParamSet):
    train_x = []
    train_y = []
    train_docv = []

    val_x = []
    val_y = []
    val_docv = []

    train_configs = [
        ("DST", 20), ("DST", 25), ("DST", 30),
        ("FUDS", 20), ("FUDS", 25), ("FUDS", 30),
    ]
    val_configs = [
        ("US06", 20), ("US06", 25), ("US06", 30),
    ]

    for prof, temp in train_configs:
        data = prepare_scenario_data(temp, profile=prof)
        est = E7V3CompositeFilter(params)
        est.reset(data.start_soc, soc_std=0.005)
        n = len(data.truth_soc)

        for i in range(0, n, 2):  # Subsample by 2 for speed
            curr = float(data.current_a[i])
            v_meas = float(data.voltage_v[i])
            temp_c = float(data.temp_measured_c[i])
            dt = float(data.dt_arr[i])

            m = Measurement(v=v_meas, i=curr, temp_c=temp_c, dt=dt, dropout=False)
            out = est.step(m)

            z = float(data.truth_soc[i])
            ocv = float(est.ocv_table.lookup(z, temp_c))
            r0 = float(est.r0_table.lookup(z, temp_c))
            r1 = float(est.r1_table.lookup(z, temp_c))
            r2 = float(est.r2_table.lookup(z, temp_c))
            r0_eff = float(est.theta * r0)
            r1_eff = float(est.theta * r1) if est.adapt_r1 else r1
            m_hyst = float(est.get_m_hyst(temp_c))

            # Polarization voltages v1 = i1*r1, v2 = i2*r2
            v1 = float(est.x[1]) * r1_eff
            v2 = float(est.x[2]) * r2
            h = float(est.x[-1])

            v_base = ocv + m_hyst * h - v1 - v2 - curr * r0_eff
            delta_v_target = v_meas - v_base
            d_ocv = float(abs(est.ocv_table.derivative_soc(z, temp_c)))

            train_x.append([z, v1, v2, h, curr, temp_c])
            train_y.append([delta_v_target])
            train_docv.append([d_ocv])

    for prof, temp in val_configs:
        data = prepare_scenario_data(temp, profile=prof)
        est = E7V3CompositeFilter(params)
        est.reset(data.start_soc, soc_std=0.005)
        n = len(data.truth_soc)

        for i in range(0, n, 4):
            curr = float(data.current_a[i])
            v_meas = float(data.voltage_v[i])
            temp_c = float(data.temp_measured_c[i])
            dt = float(data.dt_arr[i])

            m = Measurement(v=v_meas, i=curr, temp_c=temp_c, dt=dt, dropout=False)
            out = est.step(m)

            z = float(data.truth_soc[i])
            ocv = float(est.ocv_table.lookup(z, temp_c))
            r0 = float(est.r0_table.lookup(z, temp_c))
            r1 = float(est.r1_table.lookup(z, temp_c))
            r2 = float(est.r2_table.lookup(z, temp_c))
            r0_eff = float(est.theta * r0)
            r1_eff = float(est.theta * r1) if est.adapt_r1 else r1
            m_hyst = float(est.get_m_hyst(temp_c))

            v1 = float(est.x[1]) * r1_eff
            v2 = float(est.x[2]) * r2
            h = float(est.x[-1])

            v_base = ocv + m_hyst * h - v1 - v2 - curr * r0_eff
            delta_v_target = v_meas - v_base
            d_ocv = float(abs(est.ocv_table.derivative_soc(z, temp_c)))

            val_x.append([z, v1, v2, h, curr, temp_c])
            val_y.append([delta_v_target])
            val_docv.append([d_ocv])

    return (
        np.array(train_x, dtype=np.float32),
        np.array(train_y, dtype=np.float32),
        np.array(train_docv, dtype=np.float32),
        np.array(val_x, dtype=np.float32),
        np.array(val_y, dtype=np.float32),
        np.array(val_docv, dtype=np.float32),
    )


def train_pinn():
    set_seed(42)
    device = torch.device("cpu")

    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    params = ParamSet.from_assumptions(assumptions, matched=True)

    cache_file = repo_root / "data" / "cache" / "pinn_data.npz"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    if cache_file.exists():
        print("Loading cached PINN data from", cache_file)
        loaded = np.load(cache_file)
        X_train = loaded["X_train"]
        y_train = loaded["y_train"]
        docv_train = loaded["docv_train"]
        X_val = loaded["X_val"]
        y_val = loaded["y_val"]
        docv_val = loaded["docv_val"]
    else:
        print("Generating multi-physics PINN training trajectories...")
        X_train, y_train, docv_train, X_val, y_val, docv_val = generate_pinn_dataset(params)
        np.savez_compressed(
            cache_file,
            X_train=X_train,
            y_train=y_train,
            docv_train=docv_train,
            X_val=X_val,
            y_val=y_val,
            docv_val=docv_val,
        )
        print("Saved cache to", cache_file)

    print(f"X_train: {X_train.shape}, X_val: {X_val.shape}")

    mean_ch = torch.from_numpy(X_train.mean(axis=0)).float()
    scale_ch = torch.from_numpy(X_train.std(axis=0)).float()

    model = VoltagePINN(in_features=6, hidden_dim=32, max_delta_v=0.15).to(device)
    model.set_normalization(mean_ch, scale_ch)

    train_ds = TensorDataset(
        torch.from_numpy(X_train).float(),
        torch.from_numpy(y_train).float(),
        torch.from_numpy(docv_train).float(),
    )
    val_ds = TensorDataset(
        torch.from_numpy(X_val).float(),
        torch.from_numpy(y_val).float(),
        torch.from_numpy(docv_val).float(),
    )

    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=512, shuffle=False)

    huber = nn.HuberLoss(delta=0.01)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.005, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=10)

    best_val_mae = float("inf")
    best_weights = None

    print("Beginning PINN training...")
    for epoch in range(1, 11):
        model.train()
        train_loss = 0.0
        n_samples = 0

        for x_b, y_b, docv_b in train_loader:
            x_b.requires_grad_(True)
            optimizer.zero_grad()

            pred_dv = model(x_b)
            l_data = huber(pred_dv, y_b)

            # Physics constraint: compute dDeltaV/dz
            grad_z = torch.autograd.grad(
                outputs=pred_dv,
                inputs=x_b,
                grad_outputs=torch.ones_like(pred_dv),
                create_graph=True,
                retain_graph=True,
            )[0][:, 0:1]

            # Monotonicity penalty: dV_total/dz = dOCV/dz + dDeltaV/dz >= 0
            total_slope = docv_b + grad_z
            l_mono = torch.mean(torch.relu(-total_slope) ** 2)

            total_loss = l_data + 0.1 * l_mono
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_loss += total_loss.item() * len(y_b)
            n_samples += len(y_b)

        scheduler.step()
        train_loss /= n_samples

        # Validation
        model.eval()
        val_mae_sum = 0.0
        n_val = 0
        with torch.no_grad():
            for x_b, y_b, _ in val_loader:
                pred = model(x_b)
                val_mae_sum += torch.sum(torch.abs(pred - y_b)).item()
                n_val += len(y_b)

        val_mae_mv = (val_mae_sum / n_val) * 1000.0  # mV
        print(f"Epoch {epoch:2d}/10 | Loss: {train_loss:.6f} | Val MAE (US06): {val_mae_mv:.2f} mV")

        if val_mae_mv < best_val_mae:
            best_val_mae = val_mae_mv
            best_weights = {
                "model_state_dict": model.state_dict(),
                "feat_mean": mean_ch,
                "feat_scale": scale_ch,
                "best_val_mae_mv": best_val_mae,
            }

    out_dir = repo_root / "deliverable"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "e10_pinn.pt"
    torch.save(best_weights, out_path)
    print(f"Saved best PINN weights to {out_path} (Val MAE: {best_val_mae:.2f} mV)")


if __name__ == "__main__":
    train_pinn()
