# Experimental Neural Hybrid Models

**Status**: Research Exploration (Not for Direct BMS Deployment)  
**Location**: `models/experimental/`  
**Dependencies**: Requires the optional `neural` package extra (`pip install 'soc-lab[neural]'`).

---

## 1. Scope & Isolation

These trained model weights and booster files were relocated out of `deliverable/` during the handover hardening pass. 

The `deliverable/` directory is strictly reserved for:
- `bms_soc_ref.py`: The frozen E7v3 confidence-aware composite EKF reference implementation.
- `calibration.py` & `calibrations/`: The standardized cell calibration contract and JSON profiles.
- `golden/`: Golden input/output test vectors for third-party reimplementation verification.

The neural and boosted tree estimators (`E8`, `E8-LGBM`, `E9`, `E10`) are experimental research exploratory prototypes. They are NOT approved for direct micro-BMS integration due to memory footprint, floating-point library requirements, and out-of-distribution risks.

---

## 2. Model Inventory & Provenance

| Filename | Algorithm | Architecture | Training Dataset | Primary Metric |
|:---|:---|:---|:---|:---:|
| `e8_residual_gru.pt` | **E8 (GRU)** | 1-layer GRU (32 hidden units) with 13 temporal features (32-step window) | CALCE A123 20–40 °C (DST, US06, FUDS) | Whole RMSE $\approx 1.25\text{ pp}$ |
| `e8_residual_lgbm.txt` | **E8-LGBM** | LightGBM regression booster (Huber loss, 120 rounds) | CALCE A123 20–40 °C (DST, US06, FUDS) | Whole RMSE $\approx 0.98\text{ pp}$ |
| `e9_tcn.pt` | **E9 (TCN-UKF)** | 5-layer Dilated Causal TCN (32 channels) + UKF | CALCE A123 20–40 °C | Whole RMSE $\approx 1.12\text{ pp}$ |
| `e10_pinn.pt` | **E10 (PINN-AEKF)**| Physics-Informed MLP with 2RC electrochemical loss + Adaptive EKF | CALCE A123 20–40 °C | Voltage MAE $\approx 4.8\text{ mV}$ |

---

## 3. Retraining Scripts

To reproduce or retrain these weights from raw CALCE data:
- `scripts/train_e8_residual_gru.py` -> produces `models/experimental/e8_residual_gru.pt`
- `scripts/train_e8_residual_lgbm.py` -> produces `models/experimental/e8_residual_lgbm.txt`
- `scripts/train_e9_tcn.py` -> produces `models/experimental/e9_tcn.pt`
- `scripts/train_e10_pinn.py` -> produces `models/experimental/e10_pinn.pt`
