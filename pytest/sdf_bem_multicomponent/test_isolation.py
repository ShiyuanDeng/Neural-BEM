"""The opt-in path must not execute the active inverse package."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"


def test_import_does_not_load_sdf_inverse() -> None:
    environment = os.environ.copy()
    existing_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(SOLVERS_ROOT) + (
        os.pathsep + existing_path if existing_path else ""
    )
    script = """
import sys
import sdf_bem_multicomponent

loaded = [
    name for name in sys.modules
    if name == "sdf_inverse" or name.startswith("sdf_inverse.")
]
if loaded:
    raise SystemExit("unexpected sdf_inverse modules: " + ", ".join(loaded))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
