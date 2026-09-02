"""Solver selection for ``pytest/gpr_bem_shared``.

Two solver packages live side by side under ``solvers/``:

    solvers/gpr_bem_ref/   the original, frozen
    solvers/gpr_bem_mod/   the convention-change copy

The tests in ``pytest/gpr_bem_shared/`` import the plain name ``gpr_bem``, so
they run unchanged against either one. Which package that name resolves to is
chosen by ``--solver`` (or the ``SOLVER`` environment variable):

    python -m pytest pytest/                  # ref, the default
    python -m pytest pytest/ --solver=mod     # mod
    SOLVER=mod python -m pytest pytest/       # same

The files in ``pytest/solver_comparisons/`` bypass this and import both
packages directly under their real names, which is why they are named apart in
the first place -- two packages called ``gpr_bem`` could not coexist in one
interpreter. Geometry-only tests in ``pytest/ordered_boundary/`` and
``pytest/sdf_to_ordered_boundary/`` are also solver-independent; their metrics
must not be interpreted as BIE/PDE solver errors. The alias is nevertheless
made available globally before collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "solvers"))

import solver_select

solver_select.ensure_on_path()


def pytest_addoption(parser):
    parser.addoption(
        "--solver",
        action="store",
        default=solver_select.resolve_from_argv([]),
        choices=sorted(solver_select.SOLVER_NAMES),
        help="Which solver package the bare name 'gpr_bem' resolves to.",
    )
    parser.addoption(
        "--perfect-sampling",
        action="store_true",
        default=False,
        help=(
            "Diagnostic toggle: replace a test's real (compressed, irregular) IBIM "
            "boundary samples with perfect_circle_boundary_samples() at the same N, "
            "to isolate how much error node irregularity is responsible for."
        ),
    )
    parser.addoption(
        "--include-qbx-archive",
        action="store_true",
        default=False,
        help=(
            "Run the archived, slow QBX comparison rows. These diagnostics may "
            "explicitly allow invalid expansion clearance and are not production gates."
        ),
    )


def pytest_configure(config):
    config._selected_solver = solver_select.alias_as_gpr_bem(config.getoption("--solver"))


def pytest_report_header(config):
    package = solver_select.SOLVER_NAMES[config.getoption("--solver")]
    return (
        "gpr_bem alias for pytest/gpr_bem_shared: "
        f"{package}  ({solver_select.SOLVERS_DIR / package})"
    )


@pytest.fixture(scope="session")
def include_qbx_archive(request) -> bool:
    """Whether explicitly archived QBX comparison rows should be reproduced."""

    return bool(request.config.getoption("--include-qbx-archive"))
