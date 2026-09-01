"""gprMax FDTD reference: an independent-method cross-check for the BEM solvers.

Only ``cache_io`` is exported here. It has no dependency on gprMax itself and
is safe to import from the main test environment. ``run_case.py`` and
``build_scene.py`` do the actual simulation and must be run with the
``gprMax`` conda environment's interpreter -- see
``docs/gprmax_reference_study.md``.
"""

from . import cache_io

__all__ = ["cache_io"]
