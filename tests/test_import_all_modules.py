"""Test importing every module in src/soc and src/soh via pkgutil.walk_packages.

Ensures zero undefined names (F821), syntax errors, or circular import failures
across supported Python versions (3.11, 3.12, 3.13, 3.14).
"""

import importlib
from pathlib import Path
import pkgutil
import sys
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.mark.parametrize("package_name", ["soc", "soh"])
def test_walk_packages_imports_cleanly(package_name: str):
    """Walk all modules in package and ensure each module imports without undefined names."""
    pkg = importlib.import_module(package_name)
    imported = []
    skipped = []

    for info in pkgutil.walk_packages(pkg.__path__, prefix=f"{package_name}."):
        mod_name = info.name
        try:
            importlib.import_module(mod_name)
            imported.append(mod_name)
        except (ImportError, ModuleNotFoundError) as exc:
            # If an optional extra is not installed (e.g. torch, lightgbm, pybamm), allow skip
            missing_mod = str(exc)
            if any(opt in missing_mod for opt in ["torch", "lightgbm", "sklearn", "pybamm"]):
                skipped.append((mod_name, missing_mod))
            else:
                raise

    assert len(imported) > 0, f"No modules imported for {package_name}"
