"""AST scanner verifying zero hardcoded constants, zero literal arithmetic, and allowlisted string constants.

Enforces:
1. Every numeric literal outside tests and the defaults loader (loader.py) must be in the
   allowlist: {0, 1, 2, -1, 3600, 1000, 60}.
2. No arithmetic expression made only of numeric literals (e.g. 1000 // (2 * 5)) is permitted.
3. Every float("..") and int("..") string-literal constant must be explicitly registered and justified
   in tests/allowlisted_constants.json.
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import pytest


ALLOWLIST = {0, 1, 2, -1, 3600, 1000, 60}
ALLOWLIST_FILE = Path(__file__).resolve().parent / "allowlisted_constants.json"


def load_allowlist_registry() -> Dict[str, Set[str]]:
    """Load registry of allowed float('..') and int('..') calls per file."""
    if not ALLOWLIST_FILE.exists():
        return {}
    with open(ALLOWLIST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: set(v.get("allowed_calls", [])) for k, v in data.items()}


def is_pure_literal_expr(node: ast.AST) -> bool:
    """Recursively check whether an AST node is composed solely of numeric literals."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
        return is_pure_literal_expr(node.operand)
    if isinstance(node, ast.BinOp):
        return is_pure_literal_expr(node.left) and is_pure_literal_expr(node.right)
    return False


def scan_file_for_violations(
    filepath: Path,
    rel_path: Optional[str] = None,
    allowed_string_calls: Optional[Set[str]] = None,
) -> List[Tuple[int, str]]:
    """Scan a Python file for forbidden numeric literals, pure literal arithmetic, and unallowlisted string literals."""
    violations = []
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(filepath))

    allowed_calls = allowed_string_calls if allowed_string_calls is not None else set()

    for node in ast.walk(tree):
        # 1. Check numeric literals
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if node.value not in ALLOWLIST:
                violations.append(
                    (node.lineno, f"Forbidden constant '{node.value}' not in allowlist {ALLOWLIST}")
                )

        # 2. Check literal arithmetic (BinOp on pure literal sub-expressions)
        if isinstance(node, ast.BinOp) and is_pure_literal_expr(node):
            violations.append(
                (node.lineno, f"Forbidden literal arithmetic expression '{ast.unparse(node)}'")
            )

        # 3. Check float("..") and int("..") string-literal constants
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("float", "int"):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                call_repr = f'{node.func.id}("{node.args[0].value}")'
                if call_repr not in allowed_calls:
                    violations.append(
                        (
                            node.lineno,
                            f"Unallowlisted string-literal constant '{call_repr}' (must be registered in tests/allowlisted_constants.json)",
                        )
                    )

    return violations


def test_no_hardcoded_constants_in_source_tree():
    """Verify that all files in src/ (except loader.py) have zero forbidden literals, literal arithmetic, or unallowlisted string constants."""
    root_dir = Path(__file__).resolve().parent.parent
    src_dir = root_dir / "src" / "soc"
    registry = load_allowlist_registry()

    all_violations = []
    for py_file in src_dir.rglob("*.py"):
        # The defaults loader is exempt per specification
        if py_file.name == "loader.py":
            continue

        rel_path = str(py_file.relative_to(root_dir))
        allowed_for_file = registry.get(rel_path, set())
        violations = scan_file_for_violations(
            py_file, rel_path=rel_path, allowed_string_calls=allowed_for_file
        )
        for lineno, msg in violations:
            all_violations.append(f"{rel_path}:{lineno}: {msg}")

    assert len(all_violations) == 0, (
        f"Found {len(all_violations)} AST violations:\n" + "\n".join(all_violations)
    )


def test_scanner_catches_synthetic_violations():
    """Verify that the scanner correctly catches forbidden constants, literal arithmetic, and unallowlisted string constants."""
    code_with_forbidden_constant = "x = 42"
    tree1 = ast.parse(code_with_forbidden_constant)
    const_nodes = [
        n for n in ast.walk(tree1)
        if isinstance(n, ast.Constant) and n.value not in ALLOWLIST
    ]
    assert len(const_nodes) == 1

    code_with_literal_math = "y = 1000 // (2 * 5)"
    tree2 = ast.parse(code_with_literal_math)
    math_nodes = [
        n for n in ast.walk(tree2)
        if isinstance(n, ast.BinOp) and is_pure_literal_expr(n)
    ]
    assert len(math_nodes) >= 1

    code_with_string_constants = "z = float('3.14159')\nk = int('42')"
    tree3 = ast.parse(code_with_string_constants)
    calls = []
    for n in ast.walk(tree3):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("float", "int"):
            if n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                calls.append(f'{n.func.id}("{n.args[0].value}")')
    assert "float(\"3.14159\")" in calls
    assert "int(\"42\")" in calls
