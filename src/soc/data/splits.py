"""Sealed dataset splits loader with access protection."""

from pathlib import Path
from typing import List, Optional
import yaml


def get_default_splits_lock_path() -> Path:
    """Return default path to data/splits.lock."""
    this_dir = Path(__file__).resolve().parent
    root_dir = this_dir.parent.parent.parent
    return root_dir / "data" / "splits.lock"


def load_train_split(lock_path: Optional[Path] = None) -> List[str]:
    """Load training split cycles from sealed splits lock."""
    path = lock_path or get_default_splits_lock_path()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return list(data.get("train_cycles", []))


def load_val_split(lock_path: Optional[Path] = None) -> List[str]:
    """Load validation split cycles from sealed splits lock."""
    path = lock_path or get_default_splits_lock_path()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return list(data.get("val_cycles", []))


def load_test_split(final: bool = False, lock_path: Optional[Path] = None) -> List[str]:
    """Load test split cycles from sealed splits lock.

    Guarded by final=True requirement. Access is strictly forbidden during tuning or sweeps.
    """
    if not final:
        raise PermissionError(
            "Access denied: Test-split IDs can only be accessed with final=True on the final evaluation path."
        )

    path = lock_path or get_default_splits_lock_path()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return list(data.get("test_cycles", []))
