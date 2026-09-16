#!/usr/bin/env python3
"""Run the MLP-owned implicit inverse with Method B and Kress adjoint updates.

Defaults: Kress, adjoint, and a SIREN initialized to the wrong circle (or the
wrong star with ``--target star``). Each candidate updates network weights and
is evaluated on its re-extracted Method-B boundary. ``--optimizer
parameter_fd`` selects the numerical reference explicitly. Use
``run_explicit_radial_fourier_inverse.py`` for the separate curve-owned inverse.
"""

from __future__ import annotations

from typing import Sequence

from run_sdf_inverse_comparison import main as _comparison_main


def main(argv: Sequence[str] | None = None) -> int:
    return _comparison_main(argv, implicit_defaults=True)


if __name__ == "__main__":
    raise SystemExit(main())
