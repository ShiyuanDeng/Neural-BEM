"""MA-004 localization: the best exact-disk Mie grid point, refined by coordinate search."""
from time import perf_counter
from dataclasses import replace
import numpy as np

from gpr_bem_kress import cuda_assembly as CA
from .continuation.geometry import FourierCurve
from .continuation.geometry_runtime import geometry_validated


def disk_landscape(physics, observations, contrast, centers, radii, cutoff):
    """Exact homogeneous-disk Mie losses on a centre × radius grid, on the physics' device.

    The disk series does not depend on the boundary discretization, so every
    physics context shares it; only its execution settings and counters are used.
    """
    from .mie_localize import landscape
    execution = physics.execution
    started = perf_counter()
    reason, device = None, 'cpu-mie'
    if len(centers) == 1 or execution.acceleration == 'reference':
        value = landscape(observations, contrast, centers, radii, cutoff=cutoff)
    else:
        from .mie_grid import landscape_variant
        use_cuda = execution.device != 'cpu' and CA.available()
        if execution.device == 'cuda' and not use_cuda:
            raise RuntimeError('Explicit CUDA localization requested without a device')
        try:
            with CA._device_work:
                value = landscape_variant(observations, contrast, centers, radii, cutoff,
                                          device='cuda' if use_cuda else None)
            device = 'cuda-mie' if use_cuda else 'cpu-mie-recurrence'
        except Exception as exc:
            if execution.device != 'auto' or not CA.out_of_memory(exc):
                raise
            CA.record_fallback('Mie grid contraction')
            reason = 'Mie CUDA OOM'
            value = landscape_variant(observations, contrast, centers, radii, cutoff)
    physics.counters.record('disk_batches', perf_counter()-started, device, reason)
    return value


@geometry_validated
def localize(problem, physics, rule, ledger, on_progress=None):
    started = perf_counter()
    obs = problem.damped[:rule.frequencies]
    # FM-001 changes fitting acquisition, never the localization information.
    obs = tuple(o if o.acquisition.paired else replace(o,
        acquisition=replace(o.acquisition, paired=True), scattered=np.diag(o.scattered)) for o in obs)
    xs = np.arange(rule.center_min_m, rule.center_max_m + .0001, rule.center_step_m)
    radii_m = np.arange(rule.radius_min_m, rule.radius_max_m + .0001, rule.radius_step_m)
    x, y = np.meshgrid(xs, xs, indexing='ij')
    centers_m = (x+1j*y).ravel()
    centers = (centers_m-problem.origin_m)/problem.length_unit_m
    radii = radii_m/problem.length_unit_m
    (x0, y0), (x1, y1) = problem.bounds_m
    inside = ((x.ravel()[:, None]-radii_m >= x0) & (x.ravel()[:, None]+radii_m <= x1) &
              (y.ravel()[:, None]-radii_m >= y0) & (y.ravel()[:, None]+radii_m <= y1))
    cutoff = int(np.ceil(max(abs(o.wavenumber) for o in obs)*np.sqrt(max(problem.contrast, 1))*
                         radii.max()+rule.cutoff_padding))
    losses = []
    for i in range(0, len(centers), rule.batch_centers):
        ledger.reserve(0)
        losses.append(disk_landscape(physics, obs, problem.contrast, centers[i:i+rule.batch_centers], radii, cutoff))
    landscape = np.where(inside, np.concatenate(losses), np.inf)
    landscape[np.isnan(landscape)] = np.inf  # a failed grid point never wins
    grid_seconds = perf_counter()-started

    def loss(p):
        ledger.reserve(0)
        if not (rule.radius_min_m <= p[2] <= rule.radius_max_m and
                np.all(p[:2]-p[2] >= (x0, y0)) and np.all(p[:2]+p[2] <= (x1, y1))):
            return np.inf
        center = (complex(*p[:2])-problem.origin_m)/problem.length_unit_m
        return float(disk_landscape(physics, obs, problem.contrast, [center],
                                    [p[2]/problem.length_unit_m], cutoff)[0, 0])

    best = np.argmin(landscape)
    if not np.isfinite(landscape.flat[best]):
        raise RuntimeError('No damped Mie localization candidate inside the bounds')
    i, j = np.unravel_index(best, landscape.shape)
    start = np.array([centers_m[i].real, centers_m[i].imag, radii_m[j]])
    before = ledger.units
    p, value, steps = start.copy(), loss(start), np.array(rule.refinement_steps_m)
    for _ in range(rule.refinement_iterations):
        neighbors = [(loss(p+sign*steps[j]*np.eye(3)[j]), p+sign*steps[j]*np.eye(3)[j])
                     for j in range(3) for sign in (-1, 1)]
        candidate, q = min(neighbors, key=lambda row: row[0])
        if candidate < value:
            p, value = q, candidate
        else:
            steps /= 2
    curve = FourierCurve.circle(p[2]/problem.length_unit_m,
                                 (complex(*p[:2])-problem.origin_m)/problem.length_unit_m)
    record = dict(grid_start=start, parameters_m=p, mie_loss=value)
    if on_progress:
        on_progress([record])
    return curve, dict(record, units=ledger.units-before, seconds=perf_counter()-started,
                       grid_seconds=grid_seconds, cutoff=cutoff, selected_backend=physics.name)
