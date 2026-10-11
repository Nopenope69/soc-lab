"""AST scanner verifying zero hardcoded constants and zero literal arithmetic.

Enforces:
1. Every numeric literal outside tests and the defaults loader (loader.py) must be in the
   allowlist: {0, 1, 2, -1, 3600, 1000, 60}.
2. No arithmetic expression made only of numeric literals (e.g. 1000 // (2 * 5)) is permitted.
"""

import ast
from pathlib import Path
from typing import List, Tuple
import pytest


ALLOWLIST = {0, 1, 2, -1, 3600, 1000, 60}


def is_pure_literal_expr(node: ast.AST) -> bool:
    """Recursively check whether an AST node is composed solely of numeric literals."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
        return is_pure_literal_expr(node.operand)
    if isinstance(node, ast.BinOp):
        return is_pure_literal_expr(node.left) and is_pure_literal_expr(node.right)
    return False


def scan_file_for_violations(filepath: Path) -> List[Tuple[int, str]]:
    """Scan a Python file for forbidden numeric literals and pure literal arithmetic."""
    violations = []
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(filepath))

    for node in ast.walk(tree):
        # Check numeric literals
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if node.value not in ALLOWLIST:
                violations.append(
                    (node.lineno, f"Forbidden constant '{node.value}' not in allowlist {ALLOWLIST}")
                )
        # Check literal arithmetic (BinOp on pure literal sub-expressions)
        if isinstance(node, ast.BinOp) and is_pure_literal_expr(node):
            violations.append(
                (node.lineno, f"Forbidden literal arithmetic expression '{ast.unparse(node)}'")
            )

    return violations


def test_no_hardcoded_constants_in_source_tree():
    """Verify that all files in src/ (except loader.py) have zero forbidden literals or literal arithmetic."""
    root_dir = Path(__file__).resolve().parent.parent
    src_dir = root_dir / "src" / "soc"

    all_violations = []
    for py_file in src_dir.rglob("*.py"):
        # The defaults loader is exempt per specification
        if py_file.name == "loader.py":
            continue

        violations = scan_file_for_violations(py_file)
        for lineno, msg in violations:
            all_violations.append(f"{py_file.relative_to(root_dir)}:{lineno}: {msg}")

    assert len(all_violations) == 0, (
        f"Found {len(all_violations)} AST violations:\n" + "\n".join(all_violations)
    )


def test_scanner_catches_synthetic_violations():
    """Verify that the scanner correctly catches forbidden constants and literal arithmetic."""
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
