#!/usr/bin/env python3
"""Show that the deployed contract and the copy review 6 tested last are the same code.

    python reviews/probes/check-of-the-last-fixes/same_code.py

Both files are parsed, every description (docstring) is blanked, and the two
syntax trees are compared. Only descriptions differ between the two files.
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def code(path: Path) -> str:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                first.value.value = ""
    return ast.dump(tree)


same = code(HERE / "contract_as_last_tested.py") == code(ROOT / "contracts" / "launch_claim_bounties.py")
print("same code, descriptions aside:", same)
sys.exit(0 if same else 1)
