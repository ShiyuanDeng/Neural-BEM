"""Latest-versus-hybrid videos with the native exact geometry runtime.

Run with the archived renderer's CLI flags, including --output and --prepare-only.
The historical renderer and its saved evidence remain byte-for-byte unchanged.
"""
from functools import lru_cache
import importlib.util
from pathlib import Path
import sys

from .geometry_runtime import geometry_validated

RENDERER = (Path(__file__).resolve().parents[2] /
            'results/validation/shape_continuation/videos/latest_vs_hybrid/render.py')


@lru_cache(maxsize=1)
def load_renderer():
    spec = importlib.util.spec_from_file_location('shape_continuation_latest_renderer', RENDERER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.diagnostic = geometry_validated(module.diagnostic)
    module.original_prepare_case = module.prepare_case
    module.prepare_case = prepare_case
    return module


def prepare_case(job):
    """Importable worker entry point for both fork and spawn process pools."""
    return load_renderer().original_prepare_case(job)


def main():
    load_renderer().main()


if __name__ == '__main__':
    main()
