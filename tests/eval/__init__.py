"""Test package shim for `python -m unittest discover -s tests`.

When unittest starts discovery from `tests`, it imports this directory as the
top-level `eval` package. Extend the package search path so `eval.diff`,
`eval.runner`, and `eval.scorer` resolve to the project implementation under
the repository root.
"""

from pathlib import Path


PROJECT_EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
PROJECT_EVAL_PATH = str(PROJECT_EVAL_DIR)

if PROJECT_EVAL_PATH not in __path__:
    __path__.append(PROJECT_EVAL_PATH)
