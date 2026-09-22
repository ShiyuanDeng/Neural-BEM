"""Opt-in exact validation reuse, with a fresh bounded context for each fit.

Neither selection nor cache state is process-global. Solver callers outside an
explicit cache/fit context keep the reference path, including endpoint scoring.
No coefficient rounding or displayed geometry identifier is used as a key.
"""
from collections import Counter, OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import fields, is_dataclass
from functools import wraps
import operator
import sys
from time import perf_counter

import numpy as np

MODES = ('reference', 'cache', 'certified')
DEFAULT_MAX_BYTES = 16 * 1024 * 1024
_active = ContextVar('geometry_validation_cache', default=None)
_fit_selection = ContextVar('geometry_validation_fit_selection', default=None)


def array_key(values):
    """Complete ordered array contents; signed zero and dtype remain distinct."""
    values = np.asarray(values)
    if values.dtype.hasobject:
        raise TypeError('Geometry cache keys cannot contain object arrays.')
    return values.dtype.str, values.shape, values.tobytes(order='C')


def _retained_size(value):
    # Conservative per-entry accounting: shared objects may be counted twice.
    total = sys.getsizeof(value)
    if isinstance(value, (tuple, list)):
        total += sum(_retained_size(x) for x in value)
    elif is_dataclass(value) and not isinstance(value, type):
        total += sum(_retained_size(getattr(value, f.name)) for f in fields(value))
        total += sys.getsizeof(getattr(value, '__dict__', {}))
    return total


class ValidationCache:
    def __init__(self, mode, max_bytes=DEFAULT_MAX_BYTES):
        if mode not in MODES:
            raise ValueError('Geometry validation mode must be one of '+repr(MODES))
        if isinstance(max_bytes, bool) or operator.index(max_bytes) < 0:
            raise ValueError('max_bytes must be a nonnegative integer.')
        self.mode, self.max_bytes = mode, operator.index(max_bytes)
        self.counts, self.seconds, self.compute_seconds = Counter(), Counter(), Counter()
        self._entries = OrderedDict()
        self.retained_bytes = self.peak_bytes = 0

    def memoize(self, kind, key_factory, compute):
        started = perf_counter()
        self.counts[kind+'.requests'] += 1
        try:
            key = None if self.mode == 'reference' else (kind, key_factory())
            if key is not None and key in self._entries:
                self.counts[kind+'.hits'] += 1
                self._entries.move_to_end(key)
                return self._entries[key][0]
            self.counts[kind+'.misses'] += 1
            tick = perf_counter()
            try:
                value = compute()
            finally:
                self.compute_seconds[kind] += perf_counter()-tick
            # Cache returned invalid reports/counts, but never exception objects.
            if key is not None:
                size = _retained_size(key) + _retained_size(value) + 128
                if size <= self.max_bytes:
                    while self._entries and self.retained_bytes+size > self.max_bytes:
                        _, (_, released) = self._entries.popitem(last=False)
                        self.retained_bytes -= released
                        self.counts['evictions'] += 1
                    self._entries[key] = (value, size)
                    self.retained_bytes += size
                    self.peak_bytes = max(self.peak_bytes, self.retained_bytes)
                else:
                    self.counts['oversize_entries'] += 1
            return value
        finally:
            self.seconds[kind] += perf_counter()-started

    def snapshot(self):
        return dict(mode=self.mode, max_bytes=self.max_bytes, counts=dict(self.counts),
                    seconds=dict(self.seconds), compute_seconds=dict(self.compute_seconds),
                    retained_bytes=self.retained_bytes, peak_bytes=self.peak_bytes,
                    entries=len(self._entries), memory_accounting='conservative key/value and entry estimate')

    def clear(self):
        self._entries.clear()
        self.retained_bytes = 0


def current_validation_cache():
    return _active.get()


def memoized_validation(kind, key_factory, compute):
    cache = _active.get()
    return compute() if cache is None else cache.memoize(kind, key_factory, compute)


@contextmanager
def validation_cache(mode='cache', *, max_bytes=DEFAULT_MAX_BYTES):
    """Explicit low-level context, also useful for geometry-only qualification."""
    cache = ValidationCache(mode, max_bytes)
    token = _active.set(cache)
    try:
        yield cache
    finally:
        _active.reset(token)
        cache.clear()


@contextmanager
def geometry_validation(mode='reference', *, max_bytes=DEFAULT_MAX_BYTES, on_fit=None):
    """Select future fit-local contexts; independent solver calls stay uncached."""
    ValidationCache(mode, max_bytes)  # validate before modifying context state
    if on_fit is not None and not callable(on_fit):
        raise TypeError('on_fit must be callable or None.')
    token = _fit_selection.set((mode, max_bytes, on_fit))
    try:
        yield
    finally:
        _fit_selection.reset(token)


def fit_geometry_validation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        selection = _fit_selection.get()
        if selection is None:
            return function(*args, **kwargs)
        mode, max_bytes, on_fit = selection
        snapshot = None
        try:
            with validation_cache(mode, max_bytes=max_bytes) as cache:
                try:
                    return function(*args, **kwargs)
                finally:
                    snapshot = cache.snapshot()
                    geometry = args[2] if len(args) > 2 else kwargs.get('geometry_config')
                    snapshot['num_nodes'] = getattr(geometry, 'num_nodes', None)
        finally:
            if on_fit is not None and snapshot is not None:
                on_fit(snapshot)
    return wrapped


def validation_timed(kind):
    """Collect nested timings only when validation diagnostics were requested."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            cache = _active.get()
            if cache is None:
                return function(*args, **kwargs)
            started = perf_counter()
            cache.counts[kind+'.calls'] += 1
            try:
                return function(*args, **kwargs)
            finally:
                cache.seconds[kind] += perf_counter()-started
        return wrapped
    return decorate


def cached_self_intersections(function):
    @wraps(function)
    def wrapped(points, cross_tolerance, length_tolerance):
        return memoized_validation('self_intersection',
            lambda: (array_key(points), array_key([cross_tolerance, length_tolerance])),
            lambda: function(points, cross_tolerance, length_tolerance))
    return wrapped
