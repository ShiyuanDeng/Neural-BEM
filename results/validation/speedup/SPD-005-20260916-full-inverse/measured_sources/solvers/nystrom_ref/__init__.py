"""Standalone Nystrom reference solver -- an oracle for the IBIM packages.

Deliberately a sibling of ``gpr_bem_ref`` / ``gpr_bem_mod`` rather than a module
inside either: an oracle that lives in the thing it judges shares its bugs, and
the shared ``pytest/`` suite resolves the bare name ``gpr_bem`` to one package
at a time, so a reference buried in ``gpr_bem_mod`` would vanish under
``--solver=ref``.
"""

from .nystrom_tmz import (
    Curve,
    NystromSolution,
    build_curve,
    circle_parameterization,
    ellipse_parameterization,
    solve_transmission,
    star_parameterization,
)

__all__ = [
    "Curve",
    "NystromSolution",
    "build_curve",
    "circle_parameterization",
    "ellipse_parameterization",
    "solve_transmission",
    "star_parameterization",
]
