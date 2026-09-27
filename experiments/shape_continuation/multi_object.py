"""Opt-in coupled Cartesian curves and object-resolved normal updates.

All objects remain in the forward problem, including frozen objects. The
injected single-object update owns the complete finite trial and its derivative.
This adapter does not introduce a polar chart or another inverse optimizer.
"""
from dataclasses import dataclass, replace

import numpy as np
from scipy.linalg import block_diag

from ordered_boundary import OrderedBoundary2D
from gpr_bem_kress.multicomponent import validate_multicomponent_admissibility

from .geometry import FourierCurve, grid_size
from .updates import UpdateRefused


@dataclass(frozen=True)
class MultiCurve:
    components: tuple
    ids: tuple

    def __post_init__(self):
        parts, ids = tuple(self.components), tuple(self.ids)
        if (not parts or len(parts) != len(ids) or len(set(ids)) != len(ids)
                or any(not isinstance(x, FourierCurve) for x in parts)
                or any(not isinstance(x, str) or not x for x in ids)):
            raise ValueError("Nonempty Fourier curves require distinct nonempty component IDs.")
        if len({x.band for x in parts}) != 1:
            raise ValueError("This first adapter uses a shared storage band.")
        object.__setattr__(self, "components", parts)
        object.__setattr__(self, "ids", ids)

    @property
    def band(self):
        return self.components[0].band

    @property
    def coefficients(self):
        # Shared K and fixed count within a stage make the existing LM cache
        # and history representation unambiguous; serialize IDs alongside it.
        return np.concatenate([c.coefficients for c in self.components])

    def values(self, count):
        return np.concatenate([c.values(count) for c in self.components])

    def nodes(self, count):
        return OrderedBoundary2D(tuple(replace(c.nodes(count), component_id=name)
                                       for c, name in zip(self.components, self.ids)))

    def validate(self):
        for c in self.components:
            c.validate()
        boundary = self.nodes(grid_size(self.band))
        validate_multicomponent_admissibility(boundary)
        return boundary


@dataclass(frozen=True)
class MultiSpace:
    curve: MultiCurve
    local_spaces: tuple
    active: tuple
    slices: tuple
    orders: np.ndarray
    labels: tuple


class MultiUpdate:
    """Compose existing object updates, using a sum of per-object RMS metrics."""
    name = "coupled_independent_normal_updates"

    def __init__(self, base, *, active=None, modes=None):
        self.base, self.active, self.modes = base, active, modes
        self.length_unit_m = base.length_unit_m

    def prepare(self, curve, update_modes, curve_modes):
        active = tuple(range(len(curve.components))) if self.active is None else tuple(self.active)
        if (not active or len(set(active)) != len(active)
                or any(j < 0 or j >= len(curve.components) for j in active)):
            raise ValueError("Active object indices must be nonempty, distinct and in range.")
        modes = (update_modes,) * len(curve.components) if self.modes is None else tuple(self.modes)
        if len(modes) != len(curve.components):
            raise ValueError("One update bandwidth required per object.")
        local = tuple(self.base.prepare(curve.components[j], modes[j], curve_modes) for j in active)
        counts = np.cumsum([0] + [len(x.orders) for x in local])
        slices = tuple(slice(int(a), int(b)) for a, b in zip(counts[:-1], counts[1:]))
        return MultiSpace(curve, local, active, slices,
                          np.concatenate([x.orders for x in local]),
                          tuple(f"{curve.ids[j]}:{label}" for j, x in zip(active, local) for label in x.labels))

    def velocities(self, space, nodes):
        if tuple(c.component_id for c in nodes.components) != space.curve.ids:
            raise ValueError("Physics boundary must have the same ordered component IDs.")
        value = np.zeros((nodes.num_nodes, len(space.orders)))
        for j, local, columns in zip(space.active, space.local_spaces, space.slices):
            value[nodes.component_slices[j], columns] = self.base.velocities(local, nodes.components[j])
        return value

    def metric(self, space, kind, smoothing_m=None):
        return block_diag(*(self.base.metric(x, kind, smoothing_m) for x in space.local_spaces))

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError("Invalid coupled update coefficients.")
        return a

    def measure(self, space, coefficients):
        a = self._checked(space, coefficients)
        parts = [self.base.measure(x, a[s]) for x, s in zip(space.local_spaces, space.slices)]
        return dict(maximum_normal_m=max(x["maximum_normal_m"] for x in parts),
                    rms_normal_m=float(np.sqrt(sum(x["rms_normal_m"]**2 for x in parts))))

    def trial(self, space, coefficients):
        a = self._checked(space, coefficients)
        parts, records = list(space.curve.components), []
        for j, local, columns in zip(space.active, space.local_spaces, space.slices):
            parts[j], row = self.base.trial(local, a[columns])
            records.append(dict(component_id=space.curve.ids[j], **row))
        candidate = MultiCurve(tuple(parts), space.curve.ids)
        try:
            candidate.validate()
        except ValueError as exc:
            raise UpdateRefused("coupled_geometry", str(exc)) from exc
        return candidate, dict(self.measure(space, a), component_trials=records,
                               projection_relative=max(r["projection_relative"] for r in records),
                               speed_ratio=max(r["speed_ratio"] for r in records))


def conditional_information(jacobians, metrics, *, rcond=1e-10):
    """Project each physical Jacobian against all other objects' column spaces.

    Per-object RMS is the metric convention. A common absolute SVD threshold
    (rcond times the largest singular value of the combined physical Jacobian)
    avoids promoting weak nuisance blocks through independent normalization.
    """
    if len(jacobians) != len(metrics) or not jacobians or not 0 < rcond < 1:
        raise ValueError("Matched nonempty Jacobian/metric blocks and 0<rcond<1 required.")
    physical = [np.linalg.solve(np.linalg.cholesky(g), np.asarray(j).T).T
                for j, g in zip(jacobians, metrics)]
    threshold = rcond * np.linalg.svd(np.column_stack(physical), compute_uv=False)[0]
    rows = []
    for i, a in enumerate(physical):
        others = [b for j, b in enumerate(physical) if j != i]
        if others:
            u, s, _ = np.linalg.svd(np.column_stack(others), full_matrices=False)
            u = u[:, s > threshold]
            remainder = a - u @ (u.T @ a)
        else:
            remainder = a.copy()
        total = float(np.linalg.norm(a)**2)
        rows.append(dict(singular_values=np.linalg.svd(a, compute_uv=False),
                         conditional_singular_values=np.linalg.svd(remainder, compute_uv=False),
                         conditional_gram=remainder.T @ remainder,
                         conditional_jacobian=remainder,
                         conditional_fraction=float(np.linalg.norm(remainder)**2 / total) if total else 0.,
                         absolute_rank_threshold=float(threshold)))
    return rows


def insertion_response(state, points, *, work=None):
    """Paired scattered-data response per unit inserted area in package units.

    Equal permeability, finite dielectric contrast, exterior separated points:
    q(x)=(ki²-k²) u_source(x) u_reciprocal(x), with BOTH total fields in the
    current configuration. No conjugation in reciprocity; real stacking and
    objective weighting belong to the caller. This nominates infinitesimal
    disks and is not a finite birth acceptance rule.
    """
    from scipy.special import hankel1
    from .forward import PointSourceAcquisition, _operators, _solve, timed

    scan = state.acquisition
    if not isinstance(scan, PointSourceAcquisition) or not scan.paired:
        raise ValueError("Insertion diagnostic currently requires paired point sources.")
    points = np.asarray(points, float)
    if work is not None:
        work.check()
        work.rhs_columns += len(scan.receivers)
    _, build_receiver, incident = _operators(state.curve)
    with timed(work, "topology_grid_operator"):
        operator = build_receiver(state.curve, points, state.wavenumber)
    with timed(work, "topology_reciprocal_solve"):
        d, n = incident(state.curve, scan.receivers, state.wavenumber)
        reciprocal, _ = _solve(state.matrix, state.factors, np.concatenate((d, n), axis=1).T)
    with timed(work, "topology_grid_fields"):
        def green(sources):
            distance = np.linalg.norm(points[:, None, :] - sources[None, :, :], axis=-1)
            if np.any(distance == 0):
                raise ValueError("Topology points must be separated from sources and receivers.")
            return .25j * hankel1(0, state.wavenumber * distance)
        primal = operator.apply_state(state.traces).T + scan.strength * green(scan.sources)
        dual = operator.apply_state(reciprocal).T + green(scan.receivers)
        result = ((state.interior_wavenumber**2 - state.wavenumber**2) * primal * dual).T
    if not np.isfinite(result).all():
        raise FloatingPointError("Nonfinite insertion response.")
    return result
