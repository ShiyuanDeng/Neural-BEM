#!/usr/bin/env python3
"""Run the explicit radial-Fourier inverse with an MLP representation audit.

The accepted optimization state is the radial curve. The neural fit copies
that curve and checks its representation. This is the preferred explicit name
for the compatible ``run_mlp_sdf_inverse_comparison.py`` entry point. Use
``run_implicit_mlp_inverse.py`` for network-owned Kress adjoint updates instead.
"""

from __future__ import annotations

from typing import Sequence

from run_mlp_sdf_inverse_comparison import main as _radial_main


def main(argv: Sequence[str] | None = None) -> int:
    return _radial_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
