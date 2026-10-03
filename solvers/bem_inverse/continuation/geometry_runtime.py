"""Scoped exact geometry acceleration for shape-continuation callers (SPD-015)."""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import wraps
import os

from ordered_boundary.validation_cache import (
    current_validation_cache, intersection_validation, validation_cache,
)

MODES = ('reference', 'cache', 'spatial', 'both')
_selection = ContextVar('shape_continuation_geometry_runtime', default=None)


def geometry_mode():
    """SC_GEOMETRY_RUNTIME defaults to both; reference retains pre-integration execution."""
    mode = _selection.get()
    if mode is None:
        mode = os.environ.get('SC_GEOMETRY_RUNTIME', 'both')
    if mode not in MODES:
        raise ValueError('SC_GEOMETRY_RUNTIME must be one of '+repr(MODES))
    return mode


@contextmanager
def geometry_runtime(mode):
    """Override the environment locally without keeping a cache across a run."""
    if mode not in MODES:
        raise ValueError('Geometry runtime must be one of '+repr(MODES))
    token = _selection.set(mode)
    try:
        with intersection_validation('spatial' if mode in ('spatial', 'both') else 'reference'):
            yield
    finally:
        _selection.reset(token)


@contextmanager
def geometry_batch():
    """Reuse an active cache, or create and clear a bounded cache for this batch.

    Explicit reference/certified cache contexts and intersection selections take
    precedence. Frequency workers inherit the selection and the thread-safe cache.
    No geometry state survives the outermost fit, objective or diagnostic call.
    """
    mode = geometry_mode()
    cache = mode in ('cache', 'both') and current_validation_cache() is None
    backend = 'spatial' if mode in ('spatial', 'both') else 'reference'
    with intersection_validation(backend, if_unset=True):
        with validation_cache('cache') if cache else nullcontext():
            yield


def geometry_validated(function):
    """Give a complete fit or diagnostic batch its own exact-validation scope."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        with geometry_batch():
            return function(*args, **kwargs)
    return wrapped
