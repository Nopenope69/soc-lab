"""Pytest configuration and global environment fixtures."""

import os
from pathlib import Path

# Prevent macOS OpenMP abort and multi-threading deadlock
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

try:
    import torch
    torch.set_num_threads(1)
except Exception:
    pass

try:
    import lightgbm as lgb
    model_txt = Path(__file__).resolve().parent.parent / "deliverable" / "e8_residual_lgbm.txt"
    if model_txt.exists():
        _warmup_booster = lgb.Booster(model_file=str(model_txt))
except Exception:
    pass


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_data: tests requiring raw datasets (skips with path if missing)"
    )
