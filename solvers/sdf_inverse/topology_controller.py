"""Automatic material topology control around the direct explicit Kress inverse.

No truth geometry, object count or requested event type enters this API. Masks
are disposable proposals; accepted geometries and every optimizer iterate are
smooth explicit Fourier components with persistent IDs.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
from typing import Callable

import numpy as np
from scipy import ndimage
from skimage.measure import find_contours

from .curve_updates import (
    fit_cartesian_fourier_curve_state, fit_radial_fourier_curve_state,
    polar_angle_gauge_fixed_point, radial_fourier_parameterization,
)
from .explicit_fourier import CartesianFourierCurveState, circle_cartesian_fourier_state
from .geometry import OrderedSDFGeometryError
from .optimization import ParameterFDConfig, normalized_complex_residual
from .radial_topology import (
    MultiRadialFourierState, _inside_polygon, _minimum_polygon_distance,
    circle_radial_fourier_state, evaluate_current_domain_topological_derivative,
    evaluate_multiradial_objective, run_multiradial_fd_inverse, component_radius_floor,
)
from gpr_bem_kress.multicomponent import MultiComponentKressGeometryError

CONNECTIVITY = ndimage.generate_binary_structure(2, 1)
GEOMETRY_ERRORS = (ValueError, OrderedSDFGeometryError, MultiComponentKressGeometryError)


def component_parameterization(component):
    return (component.parameterization() if isinstance(component, CartesianFourierCurveState)
            else radial_fourier_parameterization(component))


def chart_contour_modes(config):
    """Bandwidth a fitted contour is given in the configured chart.

    A radial component of band ``K`` is *exactly* a polar-angle Cartesian
    component of band ``K + 1``: ``r(theta) e(theta)`` raises every radial mode
    by one, and the radial chart's gauge-fixed mode one keeps the Cartesian
    mean on the radial centre.  Asking for one more mode is therefore what
    makes the two charts carry the same shape content at the same setting,
    rather than handicapping the Cartesian fit by a mode.
    """
    return config.contour_modes + 1 if config.chart == 'cartesian' else config.contour_modes


def cartesian_component(component):
    """The exact polar-angle Cartesian form of one explicit component.

    A radial component of band ``K`` is a gauge-fixed Cartesian component of
    band ``K + 1`` to machine precision: ``r(theta) e(theta)`` raises every
    radial mode by one, and the radial chart's zeroed mode one keeps the
    Cartesian mean exactly on the radial centre, which is the point the gauge
    measures its angle about.  Nothing is lost or approximated here, so a
    Cartesian run may start from the same geometry a radial run starts from.
    """
    if isinstance(component, CartesianFourierCurveState):
        return component
    curve = radial_fourier_parameterization(component).discretize(4096)
    fitted = fit_cartesian_fourier_curve_state(
        curve.points, maximum_mode=component.maximum_mode + 1, center=component.center,
        component_id=component.component_id, source_identifier=component.source_identifier)
    return polar_angle_gauge_fixed_point(fitted)[0]


def state_in_chart(state, chart):
    """Re-express a whole state in ``chart``, or return it unchanged."""
    if state is None or chart != 'cartesian':
        return state
    return MultiRadialFourierState(tuple(cartesian_component(c) for c in state.components))


def circle_component(center, radius_m, component_id, chart):
    """A circular seed in the requested chart. Both are exact circles."""
    if chart == 'cartesian':
        return circle_cartesian_fourier_state(center, radius_m, component_id)
    return circle_radial_fourier_state(center, radius_m, component_id)


@dataclass(frozen=True)
class TopologyControllerConfig:
    inspection_center: tuple[float, float] = (0.5, 0.5)
    inspection_radius_m: float = 0.20
    raster_size: int = 101
    boundary_buffer_m: float = 0.006
    minimum_component_radius_m: float = 0.008
    maximum_birth_radius_m: float = 0.065
    birth_radius_grid_m: tuple[float, ...] | None = None
    split_seed_radius_factors: tuple[float, ...] = (1.,)
    maximum_events: int = 8
    maximum_cycles: int = 12
    fixed_iterations: int = 18
    candidate_refinement_iterations: int = 3
    relative_error_tolerance: float = 0.005
    acceptance_absolute_margin: float = 1.e-10
    acceptance_relative_margin: float = 1.e-5
    cross_resolution_factor: float = 5.0
    maximum_candidates_per_type: int = 48
    contour_modes: int = 8
    chart: str = 'radial'

    def __post_init__(self):
        if self.chart not in ('radial', 'cartesian'):
            raise ValueError("chart must be 'radial' or 'cartesian'.")
        for name in ('raster_size', 'maximum_events', 'maximum_cycles', 'fixed_iterations',
                     'maximum_candidates_per_type', 'contour_modes'):
            if isinstance(getattr(self, name), bool) or int(getattr(self, name)) != getattr(self, name) or getattr(self, name) < 1:
                raise ValueError(f'{name} must be a positive integer.')
        if self.raster_size < 17 or self.candidate_refinement_iterations < 0:
            raise ValueError('Insufficient raster or invalid candidate refinement budget.')
        for name in ('inspection_radius_m', 'boundary_buffer_m', 'minimum_component_radius_m',
                     'maximum_birth_radius_m', 'relative_error_tolerance', 'acceptance_absolute_margin',
                     'acceptance_relative_margin', 'cross_resolution_factor'):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f'{name} must be finite and nonnegative.')
        if self.inspection_radius_m <= 0 or self.minimum_component_radius_m <= 0:
            raise ValueError('Inspection and minimum component radii must be positive.')
        if self.maximum_birth_radius_m < self.minimum_component_radius_m:
            raise ValueError('Birth radius bounds are inconsistent.')
        if self.birth_radius_grid_m is not None:
            radii = tuple(float(r) for r in self.birth_radius_grid_m)
            if (not radii or not np.all(np.isfinite(radii)) or len(set(radii)) != len(radii)
                    or min(radii) < self.minimum_component_radius_m
                    or max(radii) > self.maximum_birth_radius_m):
                raise ValueError('birth_radius_grid_m must contain unique finite radii within the configured bounds.')
            object.__setattr__(self, 'birth_radius_grid_m', radii)
        factors = tuple(float(f) for f in self.split_seed_radius_factors)
        if (not factors or not np.all(np.isfinite(factors)) or len(set(factors)) != len(factors)
                or min(factors) <= 0 or max(factors) > 1):
            raise ValueError('split_seed_radius_factors must be unique finite values in (0, 1].')
        object.__setattr__(self, 'split_seed_radius_factors', factors)
        if np.shape(self.inspection_center) != (2,) or not np.all(np.isfinite(self.inspection_center)):
            raise ValueError('inspection_center must contain two finite coordinates.')


@dataclass(frozen=True)
class TopologyWorkspace:
    points: np.ndarray
    axis_x: np.ndarray
    axis_y: np.ndarray
    domain: np.ndarray
    material: np.ndarray
    component_masks: tuple[np.ndarray, ...]
    addition: np.ndarray
    removal: np.ndarray
    spacing_m: float


@dataclass(frozen=True)
class TopologyCandidate:
    kind: str
    state: MultiRadialFourierState | None
    parents: tuple[str, ...]
    children: tuple[str, ...]
    sensitivity_score: float
    construction: str


@dataclass(frozen=True)
class TopologyFrame:
    state: MultiRadialFourierState | None
    loss: float
    label: str
    cycle: int


@dataclass(frozen=True)
class TopologyInverseResult:
    final_state: MultiRadialFourierState | None
    stop_reason: str
    frames: tuple[TopologyFrame, ...]
    events: tuple[dict, ...]
    passes: tuple[dict, ...]


def topology_objective(state, data, geometry, solve_config):
    if state is None:
        residual, relative = normalized_complex_residual(
            np.zeros_like(data.observed_scattered_response),
            data.observed_scattered_response, data.frequency_weights)
        return .5 * float(residual @ residual), float(relative)
    evaluation = evaluate_multiradial_objective(state, data, geometry, solve_config=solve_config)
    return evaluation.loss, evaluation.relative_l2_error


def build_topology_workspace(state, data, geometry, solve_config, config):
    c = np.asarray(config.inspection_center)
    r = config.inspection_radius_m
    x = np.linspace(c[0] - r, c[0] + r, config.raster_size)
    y = np.linspace(c[1] - r, c[1] + r, config.raster_size)
    xx, yy = np.meshgrid(x, y)
    points = np.stack((xx, yy), axis=-1)
    flat = points.reshape(-1, 2)
    domain = np.linalg.norm(points - c, axis=-1) <= r
    masks = []
    clearance = np.full(len(flat), np.inf)
    if state is not None:
        for component in state.components:
            polygon = component_parameterization(component).discretize(512).points
            masks.append(_inside_polygon(flat, polygon).reshape(xx.shape))
            clearance = np.minimum(clearance, _minimum_polygon_distance(flat, polygon))
    material = np.logical_or.reduce(masks) if masks else np.zeros(xx.shape, bool)
    valid = domain & (clearance.reshape(xx.shape) > config.boundary_buffer_m)
    fields = []
    for region, change in ((valid & ~material, 'addition'), (valid & material, 'removal')):
        field = np.full(xx.shape, np.nan)
        if np.any(region):
            field[region] = evaluate_current_domain_topological_derivative(
                state, data, points[region], geometry_config=geometry,
                solve_config=solve_config, material_change=change).values
        fields.append(field)
    return TopologyWorkspace(points, x, y, domain, material, tuple(masks),
                             fields[0], fields[1], float(x[1] - x[0]))


def classify_material_change(old_masks, proposed):
    """Classify connectivity through old/new overlap, rejecting nested holes."""
    # Components wholly outside the inspection raster are unchanged by mask
    # surgery. Count only visible components on both sides of this comparison;
    # the controller preserves invisible explicit components in the candidate.
    # Counting an empty old mask would suppress a legitimate two-child split.
    old_masks = tuple(mask for mask in old_masks if np.any(mask))
    if np.any(ndimage.binary_fill_holes(proposed) & ~proposed):
        return 'unsupported_nested_hole'
    labels, count = ndimage.label(proposed, structure=CONNECTIVITY)
    old_count = len(old_masks)
    overlap = np.array([[np.any(old & (labels == k)) for k in range(1, count + 1)]
                        for old in old_masks], dtype=bool).reshape(old_count, count)
    if count > old_count:
        if np.any(overlap.sum(axis=0) == 0):
            return 'birth'
        if np.any(overlap.sum(axis=1) > 1):
            return 'split'
    if count < old_count:
        if np.any(overlap.sum(axis=0) > 1):
            return 'merge'
        if np.any(overlap.sum(axis=1) == 0):
            return 'death'
    return 'no_topology_change'


def fit_mask_component(mask, workspace, component_id, maximum_mode, geometry, chart='radial'):
    """Fit one outer contour in the requested chart.

    ``radial`` keeps the historical policy: a radial fit when it is admissible
    and faithful, otherwise promotion to an arc-length Cartesian contour that
    no radial component could hold.  ``cartesian`` fits the polar-angle chart
    directly and requires the result to be gauge-fixed, because that is the
    chart its optimizer holds every component in.  Arc length gets no fallback
    there: it is the parameter in which these targets are *not* band-limited,
    so a contour fitted in it carries a truncation error the optimizer cannot
    remove, and its scored loss would not be the loss the optimizer starts
    from.
    """
    if np.any(ndimage.binary_fill_holes(mask) & ~mask):
        raise ValueError('unsupported_nested_hole')
    if np.any(mask[[0, -1], :]) or np.any(mask[:, [0, -1]]):
        raise ValueError('Contour touches topology workspace boundary.')
    smooth = ndimage.gaussian_filter(mask.astype(float), 0.8)
    contours = find_contours(smooth, .5)
    if len(contours) != 1:
        raise ValueError('Expected one closed outer contour.')
    contour = contours[0]
    points = np.column_stack((workspace.axis_x[0] + contour[:, 1] * workspace.spacing_m,
                              workspace.axis_y[0] + contour[:, 0] * workspace.spacing_m))
    if not np.allclose(points[0], points[-1]):
        raise ValueError('Open topology contour.')
    area = .5 * np.sum(points[:-1, 0] * points[1:, 1] - points[:-1, 1] * points[1:, 0])
    if area < 0:
        points = points[::-1]
    distance = np.r_[0., np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    sample = np.linspace(0., distance[-1], 512, endpoint=False)
    uniform = np.column_stack([np.interp(sample, distance, points[:, j]) for j in range(2)])
    spectrum = np.fft.rfft(uniform, axis=0) / len(uniform)
    k = max(8, maximum_mode + 2)
    cosine, sine = 2 * spectrum[:k + 1].real, -2 * spectrum[:k + 1].imag
    cosine[0] *= .5
    sine[0] = 0
    cartesian = CartesianFourierCurveState(cosine, sine, component_id)
    curve = cartesian.parameterization().discretize(512)
    center = np.mean(workspace.points[mask], axis=0)
    if chart == 'cartesian':
        # Two centres are tried: the mask's own centroid, and the smoothed
        # contour's Fourier mean. A cut can leave a piece that is single-valued
        # in polar angle about one and not the other.
        tolerance = max(2.5 * workspace.spacing_m, .12 * cartesian.mean_radius_m)
        for origin in (center, cartesian.center):
            try:
                polar = fit_cartesian_fourier_curve_state(curve.points, maximum_mode=maximum_mode,
                                                          center=origin, component_id=component_id)
                # The fit's centre is the requested one; the gauge's centre is
                # the component's own Fourier mean, and the projection
                # reconciles them. Its residual is the component's distance
                # from the chart the optimizer holds it in, so a contour that
                # cannot reach that chart is not a candidate: accepting it
                # would hand the optimizer a state whose scored loss is not
                # the loss it starts from.
                polar, residual = polar_angle_gauge_fixed_point(polar)
                if max(polar.initial_projection_maximum_m, residual) > tolerance:
                    raise ValueError('Gauge-fixed polar-angle fit loses contour features.')
                polar.boundary_curve(geometry)
                return polar
            except GEOMETRY_ERRORS:
                continue
        raise ValueError('No gauge-fixed polar-angle contour represents this mask.')
    try:
        radial = fit_radial_fourier_curve_state(curve, maximum_mode=maximum_mode, center=center)
        # A poor projection must not silently erase a neck or a concavity.
        if radial.initial_projection_maximum_m > max(2.5 * workspace.spacing_m, .12 * radial.mean_radius_m):
            raise ValueError('Radial projection loses contour features.')
        MultiRadialFourierState((radial,)).boundary(geometry)
        return radial
    except GEOMETRY_ERRORS:
        cartesian.boundary_curve(geometry)
        return cartesian


def generate_topology_candidates(state, workspace, geometry, config, event_serial):
    """Construct all four event classes before finite-objective selection."""
    w = workspace
    components = () if state is None else state.components
    ids = tuple(c.component_id for c in components)
    candidates, rejected = [], []
    pixel_area = w.spacing_m**2
    min_pixels = max(8, int(np.pi * config.minimum_component_radius_m**2 / pixel_area))
    serial = f't{event_serial:03d}'

    def submit_mask(mask, parents, construction, score):
        kind = classify_material_change(w.component_masks, mask)
        if kind in ('no_topology_change', 'unsupported_nested_hole'):
            if kind == 'unsupported_nested_hole':
                rejected.append(dict(kind=kind, construction=construction, parents=parents))
            return
        labels, count = ndimage.label(mask, structure=CONNECTIVITY)
        # A bridge can incidentally connect more than its two seed components.
        # Connectivity owns the event lineage: retire every linked parent.
        affected_labels = set()
        for index, cid in enumerate(ids):
            if cid in parents:
                affected_labels.update(np.unique(labels[w.component_masks[index]]))
        affected_labels.discard(0)
        parents = tuple(cid for index, cid in enumerate(ids)
                        if cid in parents or any(np.any(w.component_masks[index] & (labels == label))
                                                for label in affected_labels))
        unaffected = tuple(c for c in components if c.component_id not in parents)
        unaffected_mask = np.zeros_like(mask)
        for index, cid in enumerate(ids):
            if cid not in parents:
                unaffected_mask |= w.component_masks[index]
        pieces = [labels == i for i in range(1, count + 1)
                  if not np.any((labels == i) & unaffected_mask)]
        if any(np.count_nonzero(p) < min_pixels for p in pieces):
            return
        children = tuple(f'{serial}.{kind}{i + 1}' for i in range(len(pieces)))
        seed_factors = config.split_seed_radius_factors if kind == 'split' else (1.,)
        variants = [(1, factor) for factor in seed_factors]
        contour_modes = chart_contour_modes(config)
        if contour_modes != 1:
            variants.append((contour_modes, 1.))
        for modes, seed_factor in variants:
            try:
                # A moment-matched circular seed is a deliberately coarse
                # candidate, independently scored beside the contour fit.
                # Do not confuse that approximation with chart promotion.
                fitted = tuple(
                    circle_component(np.mean(w.points[p], axis=0),
                        seed_factor * np.sqrt(np.count_nonzero(p) * pixel_area / np.pi), cid, config.chart)
                    if modes == 1 else fit_mask_component(p, w, cid, modes, geometry, config.chart)
                    for p, cid in zip(pieces, children))
                replacement = MultiRadialFourierState(unaffected + fitted) if unaffected + fitted else None
                candidates.append(TopologyCandidate(kind, replacement, parents, children,
                                  float(score), f'{construction}; modes={modes}; seed_scale={seed_factor:g}'))
            except GEOMETRY_ERRORS as exc:
                rejected.append(dict(kind=kind, construction=construction, reason=str(exc)))

    # All favourable connected exterior regions, not only the global minimum.
    finite_add = np.isfinite(w.addition)
    if np.any(finite_add) and np.nanmin(w.addition) < 0:
        minimum = np.nanmin(w.addition)
        seen = set()
        for fraction in (.65, .35):
            labels, count = ndimage.label(finite_add & (w.addition < fraction * minimum), CONNECTIVITY)
            for label in range(1, count + 1):
                region = labels == label
                if np.count_nonzero(region) < 4:
                    continue
                weight = -w.addition[region]
                center = np.average(w.points[region], axis=0, weights=weight)
                key = tuple(np.round(center / (2 * w.spacing_m)).astype(int))
                if key in seen:
                    continue
                seen.add(key)
                radius = min(config.maximum_birth_radius_m,
                             np.sqrt(np.count_nonzero(region) * pixel_area / np.pi))
                sizes = (tuple(radius * factor for factor in (1., .75, .5, .35))
                         if config.birth_radius_grid_m is None else config.birth_radius_grid_m)
                for size in sizes:
                    if size < config.minimum_component_radius_m:
                        continue
                    disk = np.linalg.norm(w.points - center, axis=-1) <= size
                    if classify_material_change(w.component_masks, w.material | disk) != 'birth':
                        continue
                    child = circle_component(center, size, f'{serial}.birth', config.chart)
                    new = MultiRadialFourierState(components + (child,))
                    candidates.append(TopologyCandidate('birth', new, (), (child.component_id,),
                        float(np.sum(w.addition[region]) * pixel_area), f'exterior_td_region; radius={size:.5g}'))

    # Atomic death: score every leave-one-out state, even if its TD is ambiguous.
    for index, component in enumerate(components):
        survivors = components[:index] + components[index + 1:]
        candidates.append(TopologyCandidate('death', MultiRadialFourierState(survivors) if survivors else None,
            (component.component_id,), (), float(np.nansum(w.removal[w.component_masks[index]]) * pixel_area),
            'leave_one_component_out'))

    # Removal thresholds may expose several children or an unsupported hole.
    for index, component in enumerate(components):
        own = w.component_masks[index]
        finite = own & np.isfinite(w.removal)
        if not np.any(finite) or np.min(w.removal[finite]) >= 0:
            continue
        for fraction in (.2, .5, .8):
            cut = own & (w.removal < fraction * np.min(w.removal[finite]))
            submit_mask(w.material & ~cut, (component.component_id,), 'interior_td_threshold',
                        np.nansum(w.removal[cut]) * pixel_area)
        # Extend favourable removal corridors to the boundary: a discrete cut,
        # never an intermediate pinched Kress boundary. Orientations are derived
        # from current geometry; every corridor must have negative removal score.
        points = w.points[own]
        center = np.mean(points, axis=0)
        _, axes = np.linalg.eigh(np.cov((points - center).T))
        major = axes[:, -1]
        angle = np.arctan2(major[1], major[0])
        corridors = []
        for rotation in (0., np.pi / 4, -np.pi / 4, np.pi / 2):
            normal = np.array([np.cos(angle + rotation), np.sin(angle + rotation)])
            projection = (w.points - center) @ normal
            extent = np.max(np.abs(projection[own]))
            for offset in (-.25, 0., .25):
                for width in (.012, .020, .032):
                    cut = own & (np.abs(projection - offset * extent) < width / 2)
                    known = cut & finite
                    score = float(np.sum(w.removal[known]) * pixel_area)
                    if np.count_nonzero(known) >= 3 and score < 0:
                        mask = w.material & ~cut
                        if classify_material_change(w.component_masks, mask) == 'split':
                            corridors.append((score, mask, width, rotation, offset))
        corridor_families = {}
        for corridor in sorted(corridors, key=lambda c: c[0] / max(1, np.count_nonzero(w.material & ~c[1]))):
            count = ndimage.label(corridor[1], CONNECTIVITY)[1]
            key = (count, corridor[3], corridor[4])
            corridor_families.setdefault(key, []).append(corridor)
        retained_corridors = [family[0] for family in corridor_families.values()]
        for score, mask, width, rotation, offset in retained_corridors:
            submit_mask(mask, (component.component_id,),
                        f'interior_td_corridor; width={width}; angle={rotation}; offset={offset}', score)

    # Exterior bridges connect entire old components; only the single outer
    # contour is sent to Kress, so no forward solve is performed at contact.
    for i, j in combinations(range(len(components)), 2):
        a, b = np.asarray(components[i].center), np.asarray(components[j].center)
        direction = b - a
        length2 = direction @ direction
        if length2 <= 0:
            continue
        t = np.clip((w.points - a) @ direction / length2, 0., 1.)
        distance = np.linalg.norm(w.points - (a + t[..., None] * direction), axis=-1)
        scale = min(components[i].mean_radius_m, components[j].mean_radius_m)
        for factor in (.45, .75, 1.05):
            bridge = (distance < factor * scale) & w.domain
            known = bridge & ~w.material & finite_add
            score = float(np.sum(w.addition[known]) * pixel_area)
            if np.count_nonzero(known) >= 3 and score < 0:
                submit_mask(w.material | bridge, (ids[i], ids[j]),
                            f'exterior_td_bridge; factor={factor}', score)
    selected = []
    for kind in ('birth', 'death', 'split', 'merge'):
        group = sorted((c for c in candidates if c.kind == kind), key=lambda c: c.sensitivity_score)
        # Death is cheap and exhaustive. Other classes have a finite search budget.
        if kind == 'death':
            selected.extend(group)
            continue
        # Keep competing connectivity changes and coarse/contour fits in the
        # finite budget. Strong threshold fragmentation must not crowd out all
        # two-child corridors before the real objective gets to compare them.
        families = {}
        for candidate in group:
            key = (len(candidate.children), candidate.construction.split(';')[0],
                   ';'.join(candidate.construction.split(';')[-2:]) if kind != 'birth' else '')
            families.setdefault(key, []).append(candidate)
        diverse = []
        while families and len(diverse) < config.maximum_candidates_per_type:
            for key in tuple(families):
                if len(diverse) == config.maximum_candidates_per_type:
                    break
                diverse.append(families[key].pop(0))
                if not families[key]:
                    del families[key]
        selected.extend(diverse)
    return tuple(selected), tuple(rejected)


def _optimizer_config(state, config, iterations=None):
    # The Cartesian names carry the same three roles under different spellings:
    # mode zero translates, mode one scales, and the rest are shape. The shape
    # bound is halved because a radial mode-m amplitude appears in this chart
    # as two coefficient pairs of *half* that amplitude, so half the bound is
    # what reproduces the radial trust region rather than doubling it.
    steps = [(.012 if name.endswith('radius_m') or '.cos_1_' in name or '.sin_1_' in name
              else .018 if '.center_' in name or '.cos_0_' in name
              else .003 if '.cos_' in name or '.sin_' in name else .006)
             for name in state.parameter_names]
    return ParameterFDConfig(max_iterations=config.fixed_iterations if iterations is None else iterations,
        finite_difference_steps=1.e-4, max_steps=np.asarray(steps), initial_damping=1.e-3,
        max_damping_trials=5, max_backtracks=7, gradient_tolerance=1.e-7,
        loss_tolerance=1.e-10, relative_step_tolerance=1.e-7,
        max_parameters=max(64, state.parameter_count), infeasible_trial_policy='reject')


def run_topology_aware_fourier_inverse(initial_state, data, production_geometry_config,
        refined_geometry_config, *, solve_config, config=None,
        progress_callback: Callable[[TopologyFrame], None] | None = None,
        workspace_callback: Callable[[int, TopologyWorkspace], None] | None = None):
    """Refine, compare finite events, accept the best, restart and repeat."""
    config = TopologyControllerConfig() if config is None else config
    state, frames, events, passes = initial_state, [], [], []
    stop = 'maximum_cycles'
    used_ids = set(() if initial_state is None else initial_state.component_ids)
    event_serial = 1

    def emit(current, loss, label, cycle):
        frame = TopologyFrame(current, float(loss), label, cycle)
        frames.append(frame)
        if progress_callback:
            progress_callback(frame)

    for cycle in range(config.maximum_cycles):
        if state is not None and all(component_radius_floor(c) >= config.minimum_component_radius_m for c in state.components):
            result = run_multiradial_fd_inverse(state, data, production_geometry_config,
                solve_config=solve_config, config=_optimizer_config(state, config),
                minimum_component_radius_m=config.minimum_component_radius_m,
                cartesian_gauge=config.chart == 'cartesian',
                progress_callback=lambda item: emit(item.state, item.loss, f'refine {item.iteration}', cycle))
            state = result.final_state
            trigger = result.stop_reason
        elif state is None:
            trigger = 'empty_domain'
            emit(None, topology_objective(None, data, production_geometry_config, solve_config)[0], trigger, cycle)
        else:
            trigger = 'component_radius_floor'
            emit(state, topology_objective(state, data, production_geometry_config, solve_config)[0], trigger, cycle)
        base_loss, relative = topology_objective(state, data, production_geometry_config, solve_config)
        if relative <= config.relative_error_tolerance:
            stop = 'recovered'
            break
        if len(events) >= config.maximum_events:
            stop = 'maximum_events'
            break
        workspace = build_topology_workspace(state, data, production_geometry_config, solve_config, config)
        if workspace_callback:
            workspace_callback(cycle, workspace)
        while any(cid.startswith(f't{event_serial:03d}.') for cid in used_ids):
            event_serial += 1
        candidates, rejections = generate_topology_candidates(
            state, workspace, production_geometry_config, config, event_serial)
        refined_base = topology_objective(state, data, refined_geometry_config, solve_config)[0]
        trials, feasible = [], []
        for candidate in candidates:
            row = dict(kind=candidate.kind, parents=candidate.parents, children=candidate.children,
                       construction=candidate.construction, sensitivity_score=candidate.sensitivity_score,
                       production_loss=None, refined_loss=None, accepted=False)
            if candidate.kind == 'birth':
                newborn = next(c for c in candidate.state.components if c.component_id in candidate.children)
                row['birth_radius_m'] = newborn.mean_radius_m
                row['birth_center_m'] = np.asarray(newborn.center).tolist()
            if candidate.kind == 'split':
                row['split_seed_radii_m'] = [c.mean_radius_m for c in candidate.state.components
                                             if c.component_id in candidate.children]
            trials.append(row)
            try:
                if candidate.state is not None and any(component_radius_floor(c) < config.minimum_component_radius_m
                                                        for c in candidate.state.components):
                    raise ValueError('Candidate violates topology feature-radius floor.')
                loss = topology_objective(candidate.state, data, production_geometry_config, solve_config)[0]
                row['raw_production_loss'] = loss
                row['production_loss'] = loss
                feasible.append((loss, candidate, row))
            except GEOMETRY_ERRORS as exc:
                row['reason'] = f'invalid_geometry: {exc}'
        # Apply the same short refinement budget to each competing event type
        # and resulting component count. A higher-dimensional fragmented cut
        # must not prevent a simple split from being refined and compared.
        refinement_groups = sorted(set((item[1].kind, 0 if item[1].state is None
                                        else len(item[1].state.components)) for item in feasible))
        for kind, component_count in refinement_groups:
            group = sorted((x for x in feasible if x[1].kind == kind and
                            (0 if x[1].state is None else len(x[1].state.components)) == component_count),
                           key=lambda x: x[0])
            if group and config.candidate_refinement_iterations:
                loss, candidate, row = group[0]
                if candidate.state is not None:
                    try:
                        result = run_multiradial_fd_inverse(candidate.state, data, production_geometry_config,
                            solve_config=solve_config,
                            config=_optimizer_config(candidate.state, config, config.candidate_refinement_iterations),
                            minimum_component_radius_m=config.minimum_component_radius_m,
                            cartesian_gauge=config.chart == 'cartesian')
                        candidate = replace(candidate, state=result.final_state)
                        row['production_loss'] = result.iterations[-1].loss
                        row['candidate_refinement_steps'] = len(result.iterations) - 1
                        feasible = [(row['production_loss'], candidate, row) if item[2] is row else item for item in feasible]
                    except GEOMETRY_ERRORS as exc:
                        row['polish_reason'] = str(exc)
        accepted = []
        margin = config.acceptance_absolute_margin + config.acceptance_relative_margin * base_loss
        for loss, candidate, row in feasible:
            delta = base_loss - loss
            if delta <= margin:
                row['reason'] = 'production_objective_not_decreased'
                continue
            try:
                refined = topology_objective(candidate.state, data, refined_geometry_config, solve_config)[0]
                row['refined_loss'] = refined
                refined_delta = refined_base - refined
                if min(delta, refined_delta) <= margin + config.cross_resolution_factor * abs(delta - refined_delta):
                    row['reason'] = 'cross_resolution_margin_failed'
                    continue
                row['eligible'] = True
                accepted.append((loss, candidate, row))
            except GEOMETRY_ERRORS as exc:
                row['reason'] = f'refined_invalid_geometry: {exc}'
        passes.append(dict(cycle=cycle, trigger=trigger, base_loss=base_loss,
                           refined_base_loss=refined_base, trials=trials, rejected_masks=rejections))
        if not accepted:
            stop = 'topology_stationary'
            break
        loss, best, row = min(accepted, key=lambda item: item[0])
        row['accepted'] = True
        event = dict(cycle=cycle, kind=best.kind, parents=best.parents, children=best.children,
            before_ids=() if state is None else state.component_ids,
            after_ids=() if best.state is None else best.state.component_ids,
            production_before=base_loss, production_after=loss,
            refined_before=refined_base, refined_after=row['refined_loss'],
            construction=best.construction)
        event['candidate_refinement_steps'] = row.get('candidate_refinement_steps', 0)
        if best.kind == 'birth':
            event['raw_birth_radius_m'] = row['birth_radius_m']
        events.append(event)
        used_ids.update(best.children)
        event_serial += 1
        emit(state, base_loss, f'before {best.kind}', cycle)
        state = best.state
        emit(state, loss, f'{best.kind.upper()} accepted', cycle)
    return TopologyInverseResult(state, stop, tuple(frames), tuple(events), tuple(passes))
