"""Tests for sealed data splits and AST protection against leakage."""

import ast
from pathlib import Path
import pytest

from soc.data.splits import load_test_split, load_train_split, load_val_split


def test_load_test_split_raises_permission_error_without_final_flag():
    """Verify that load_test_split strictly raises PermissionError when final=False."""
    with pytest.raises(PermissionError, match="Access denied"):
        load_test_split(final=False)

    # Calling with default (final omitted) must also raise
    with pytest.raises(PermissionError):
        load_test_split()


def test_load_test_split_returns_cycles_with_final_flag():
    """Verify that load_test_split succeeds when final=True."""
    cycles = load_test_split(final=True)
    assert isinstance(cycles, list)
    assert len(cycles) > 0
    assert "cycle_005" in cycles
    assert "cycle_006" in cycles


def test_train_and_val_splits_accessible_normally():
    """Verify train and validation splits can be accessed freely."""
    train = load_train_split()
    val = load_val_split()
    assert "cycle_001" in train
    assert "cycle_004" in val


def test_ast_prohibits_load_test_split_outside_final_path():
    """Verify AST of entire source tree has no calls to load_test_split outside authorized final path."""
    root_dir = Path(__file__).resolve().parent.parent
    src_dir = root_dir / "src" / "soc"

    # Authorized final evaluation paths
    authorized_modules = {"soc/eval/final.py", "soc/data/splits.py"}

    violations = []
    for py_file in src_dir.rglob("*.py"):
        rel_path = str(py_file.relative_to(root_dir / "src"))
        if rel_path in authorized_modules:
            continue

        with open(py_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == "load_test_split":
                    violations.append(
                        f"{py_file.relative_to(root_dir)}:{node.lineno}: unauthorized call to load_test_split"
                    )

    assert len(violations) == 0, (
        f"Found {len(violations)} leakage violations calling load_test_split:\n"
        + "\n".join(violations)
    )


def test_ast_scanner_catches_synthetic_leakage():
    """Verify that synthetic tuning or sweep code attempting to call load_test_split is caught."""
    code = "leak = load_test_split(final=True)"
    tree = ast.parse(code)
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", getattr(n.func, "attr", None)) == "load_test_split"
    ]
    assert len(calls) == 1
