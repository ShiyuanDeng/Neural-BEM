"""Small persistent work ledger and physically separated error measures."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import os
import resource
import time
import numpy as np

LIMITS = dict(assemblies=120, derivatives=36, factorizations=300, solves=600)


def jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=jsonable,
                                    allow_nan=False) + '\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


class BudgetStop(RuntimeError):
    pass


class Ledger:
    def __init__(self, output, source_hashes):
        self.output = Path(output)
        self.source_hashes = source_hashes
        self.started = time.perf_counter()
        self.counts = dict.fromkeys(LIMITS, 0)
        self.context = {}
        self.events = []
        self.check_source()

    def check_source(self):
        changed = [p for p, h in self.source_hashes.items() if digest(p) != h]
        if changed:
            raise BudgetStop('Imported numerical source changed: ' + ', '.join(changed))

    def elapsed(self):
        return time.perf_counter() - self.started

    def check(self, costs):
        if self.elapsed() >= 1800:
            raise BudgetStop('1800-second numerical cap reached')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 >= 8 * 1024**3:
            raise BudgetStop('8-GiB RSS cap reached')
        for key, amount in costs.items():
            if self.counts[key] + amount > LIMITS[key]:
                raise BudgetStop(f'{key} cap would be exceeded')

    def emit(self, operation, status, seconds, **extra):
        row = dict(timestamp=datetime.now(timezone.utc).isoformat(),
                   **self.context, operation=operation, status=status,
                   wall_seconds=seconds, cumulative_seconds=self.elapsed(),
                   peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                   cumulative_counts=dict(self.counts), **extra)
        with (self.output / 'work_ledger.jsonl').open('a') as stream:
            stream.write(json.dumps(row, default=jsonable, allow_nan=False) + '\n')
        self.events.append(row)

    def call(self, operation, fn, *, costs=None, **extra):
        costs = costs or {}
        self.check(costs)
        for key, amount in costs.items():
            self.counts[key] += amount
        self.emit(operation, 'attempted', None, reserved=costs, **extra)
        start = time.perf_counter()
        try:
            value = fn()
        except BaseException as exc:
            self.emit(operation, 'failed', time.perf_counter() - start,
                      reason=repr(exc), **extra)
            raise
        seconds = time.perf_counter() - start
        self.emit(operation, 'completed', seconds, **extra)
        self.check({})
        return value, seconds

    def reuse(self, operation, **extra):
        self.emit(operation, 'reused', 0.0, **extra)


def error_metrics(candidate, reference, floor):
    absolute = float(np.linalg.norm(candidate - reference))
    norm = float(np.linalg.norm(reference))
    return dict(absolute=absolute, relative=absolute / max(norm, floor),
                floor_dominated=norm < floor)


def trace_errors(candidate, reference, curves):
    weights = np.concatenate([c.arc_length_weights for c in curves])
    count = len(weights)
    result = {}
    for label, offset in [('dirichlet', 0), ('neumann', count)]:
        c = candidate[offset:offset + count] * np.sqrt(weights[:, None])
        r = reference[offset:offset + count] * np.sqrt(weights[:, None])
        result[label + '_trace_relative'] = float(np.linalg.norm(c - r) /
                                                  max(np.linalg.norm(r), 1e-300))
        result[label + '_trace_absolute'] = float(np.linalg.norm(c - r))
    return result
