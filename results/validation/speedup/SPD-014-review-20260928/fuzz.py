"""Independent review fuzz of SPD-014's spatial self-intersection count.

Targets what the SPD-014 geometry screen did not reach on saved shapes:
non-zero counts (true crossings and tolerated touches) on the *pruned* path,
plus tolerance-boundary touches, pinched real shapes and heavy offsets.
Each case records the reference and spatial counts and whether pruning or the
dense fallback produced the spatial answer.

    python fuzz.py OUT.json
"""
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'solvers')]
from ordered_boundary.spatial_validation import _candidate_pairs  # noqa: E402
from ordered_boundary.validation import _self_intersection_count  # noqa: E402
from ordered_boundary.validation_cache import intersection_validation  # noqa: E402


def resolved(points, relative=1e-12):
    scale = max(float(np.linalg.norm(np.ptp(points, axis=0))), np.finfo(float).tiny)
    return relative * scale ** 2, relative * scale


def counts(points, cross, length):
    out = {}
    for backend in ('reference', 'spatial'):
        with intersection_validation(backend):
            out[backend] = int(_self_intersection_count(np.ascontiguousarray(points, float), cross, length))
    return out


def star(n, k, samples, radius=1.0, offset=0.0, jitter=0.0, rng=None):
    """Polygon through the {n/k} star vertices, each edge subdivided (many crossings)."""
    vertices = radius * np.exp(2j * np.pi * k * np.arange(n) / n)
    t = np.linspace(0, 1, samples, endpoint=False)
    points = np.concatenate([a + (b - a) * t for a, b in zip(vertices, np.roll(vertices, -1))])
    if jitter:
        points = points + jitter * (rng.normal(size=points.shape) + 1j * rng.normal(size=points.shape))
    return np.column_stack((points.real, points.imag)) + offset


def lemniscate(samples, offset=0.0):
    t = 2 * np.pi * np.arange(samples) / samples
    return np.column_stack((np.sin(t), np.sin(t) * np.cos(t))) + offset


def pinched(samples, gap):
    """A C-like closed curve whose two arms approach to `gap` (touching at gap<=tolerance)."""
    t = 2 * np.pi * np.arange(samples) / samples
    r = 1 + .6 * np.cos(t)
    z = r * np.exp(1j * t)
    z = np.where(np.abs(z.imag) < .15, z.real - .8 + 1j * z.imag * gap / .15, z)  # squeeze a waist
    return np.column_stack((z.real, z.imag))


def near_touch(samples, distance):
    """A square-ish loop plus an inward spike whose tip sits `distance` from the far side."""
    side = np.linspace(0, 1, samples // 4, endpoint=False)
    square = np.concatenate([np.column_stack((side, 0 * side)), np.column_stack((1 + 0 * side, side)),
                             np.column_stack((1 - side, 1 + 0 * side)), np.column_stack((0 * side, 1 - side))])
    tip = np.array([[.5, 1 - distance]])
    return np.concatenate([square[: samples // 4 * 2 + samples // 8], tip, square[samples // 4 * 2 + samples // 8:]])


def main(out):
    rng = np.random.default_rng(280928)
    cases = []
    for n, k in ((5, 2), (7, 2), (7, 3), (9, 4), (11, 5)):
        for samples in (8, 40):
            for offset in (0.0, 1e6, -3e8):
                cases.append((f'star{n}/{k} s{samples} off{offset:g}', star(n, k, samples, offset=offset)))
        cases.append((f'star{n}/{k} jittered', star(n, k, 24, jitter=1e-3, rng=rng)))
    for samples in (64, 512, 2048):
        cases.append((f'lemniscate {samples}', lemniscate(samples)))
        cases.append((f'lemniscate {samples} off1e7', lemniscate(samples, 1e7)))
    for samples in (256, 1024):
        for gap in (1e-1, 1e-6, 1e-12, 0.0):
            cases.append((f'pinched {samples} gap{gap:g}', pinched(samples, gap)))
    for samples in (256, 2048):
        for distance in (1e-3, 2e-12, 1e-12, 5e-13, 0.0, -1e-9):
            cases.append((f'near-touch {samples} d{distance:g}', near_touch(samples, distance)))
    for trial in range(200):
        n = int(rng.integers(8, 400))
        base = np.cumsum(rng.normal(size=(n, 2)) * rng.uniform(.01, 1), axis=0)
        cases.append((f'random walk {trial} n{n}', base * 10 ** rng.uniform(-6, 6) + rng.uniform(-1e8, 1e8)))
    rows, started = [], time.perf_counter()
    for label, points in cases:
        for relative in (0.0, 1e-12, 1e-6):
            cross, length = resolved(points, relative)
            result = counts(points, cross, length)
            pruned = _candidate_pairs(np.ascontiguousarray(points, float), length) is not None
            rows.append(dict(case=label, nodes=len(points), relative_tolerance=relative, pruned=pruned,
                             equal=result['reference'] == result['spatial'], **result))
    summary = dict(
        comparisons=len(rows), all_equal=all(r['equal'] for r in rows),
        mismatches=[r for r in rows if not r['equal']],
        nonzero_counts=sum(1 for r in rows if r['reference'] > 0),
        nonzero_on_pruned_path=sum(1 for r in rows if r['reference'] > 0 and r['pruned']),
        pruned_total=sum(1 for r in rows if r['pruned']), fallback_total=sum(1 for r in rows if not r['pruned']),
        seconds=time.perf_counter() - started, rows=rows)
    Path(out).write_text(json.dumps(summary, indent=1))
    print({k: v for k, v in summary.items() if k != 'rows'})


if __name__ == '__main__':
    main(sys.argv[1])
