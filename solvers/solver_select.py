"""Resolve the bare name ``gpr_bem`` to one of the selector-enabled packages.

Two IBIM packages participate in the existing driver/test alias:

    gpr_bem_ref/   the original, frozen
    gpr_bem_mod/   the convention-change copy

They are named apart so both can be imported into one interpreter -- two packages
called ``gpr_bem`` cannot. Existing shared tests and operational drivers write
``from gpr_bem import ...`` and let this module decide which IBIM implementation
that means.

``gpr_bem_kress`` is a third, direct-import sibling with a different geometry
contract (``PeriodicCurve2D``).  It is intentionally absent from ``SOLVER_NAMES``
until its forward and future adjoint pipelines satisfy their acceptance gates.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

SOLVERS_DIR = Path(__file__).resolve().parent
SOLVER_NAMES = {"ref": "gpr_bem_ref", "mod": "gpr_bem_mod"}
DEFAULT_SOLVER = "ref"


def ensure_on_path() -> None:
    if str(SOLVERS_DIR) not in sys.path:
        sys.path.insert(0, str(SOLVERS_DIR))


def resolve_from_argv(argv: list[str] | None = None) -> str:
    """Read ``--solver`` out of the command line before the real parser runs.

    Falls back to the ``SOLVER`` environment variable, then to ``ref``.
    """

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--solver",
        default=os.environ.get("SOLVER", DEFAULT_SOLVER),
        choices=sorted(SOLVER_NAMES),
    )
    known, _ = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    return known.solver


def alias_as_gpr_bem(selected: str) -> str:
    """Make ``import gpr_bem`` resolve to the selected package. Returns its real name.

    Submodules are re-registered rather than re-imported. The package ``__init__``
    pulls them all in eagerly, so they are already loaded; importing them a second
    time under a second name would create duplicate class objects and break the
    ``isinstance`` checks inside the solver.
    """

    ensure_on_path()
    package_name = SOLVER_NAMES[selected]
    package = importlib.import_module(package_name)
    sys.modules["gpr_bem"] = package
    prefix = package_name + "."
    for name, module in list(sys.modules.items()):
        if name.startswith(prefix):
            sys.modules["gpr_bem." + name[len(prefix):]] = module
    return package_name
