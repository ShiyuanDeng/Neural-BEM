"""Opt-in SPD-014 runtime; archived callers remain unchanged."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from ordered_boundary.validation_cache import (
    current_validation_cache, intersection_validation, validation_cache,
)

ARMS = ('reference', 'cache', 'spatial', 'both')
_cache_batches = ContextVar('spd014_cache_diagnostic_batches', default=False)


@contextmanager
def geometry_acceleration(arm='both'):
    """Select exact polygon pruning; decorated diagnostic batches also reuse checks.

    Existing inverse fit caches remain unchanged. Direct diagnostic callers
    should use ``cache_diagnostic`` or an explicit ``validation_cache`` scope;
    this selector deliberately does not keep a cache alive across a whole run.
    """
    if arm not in ARMS:
        raise ValueError('SPD-014 arm must be one of '+repr(ARMS))
    token = _cache_batches.set(arm in ('cache', 'both'))
    try:
        with intersection_validation('spatial' if arm in ('spatial', 'both') else 'reference'):
            yield
    finally:
        _cache_batches.reset(token)


def cache_diagnostic(function):
    """An independent exact cache per complete diagnostic, shared with its threads."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not _cache_batches.get() or current_validation_cache() is not None:
            return function(*args, **kwargs)
        with validation_cache('cache'):
            return function(*args, **kwargs)
    return wrapped
