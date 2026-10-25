"""Named inverse pipelines: one recipe per physics, with the fixes that apply to it.

``runner.fit`` has interchangeable slots: physics and geometry update. A pipeline
fills those slots by name and adds no numerics. Policy, start and localization
stay with the caller, so every pipeline sees the same stages and data.

| Name | Physics | Geometry update |
|---|---|---|
| ``nodal_baseline`` | nodal Kress | spline (CI-001) |
| ``nodal_fixed`` | nodal Kress | sampled spectral (batched preparation) |
| ``modal_fixed`` | modal Müller (scaled Graf, finer profile) | sampled spectral |

Every pipeline accepts a trial curve when its loss decreases; none re-solves at a
finer resolution. Omitting a pipeline keeps ``fit``'s legacy default.
"""
from dataclasses import asdict, dataclass

from .geometry_selection import GEOMETRY_UPDATES
from .physics import Execution, make_backend
from .runner import fit as _fit


@dataclass(frozen=True)
class Pipeline:
    name: str
    solver: str
    geometry_update: str
    description: str = ''

    def __post_init__(self):
        if self.solver not in ('nodal_kress', 'modal_muller'):
            raise ValueError(f'Unknown solver {self.solver!r}')
        if self.geometry_update not in GEOMETRY_UPDATES:
            raise ValueError(f'Unknown geometry update {self.geometry_update!r}; choose from {GEOMETRY_UPDATES}')

    def settings(self):
        return asdict(self)


PIPELINES = {p.name: p for p in (
    Pipeline('nodal_baseline', 'nodal_kress', 'spline',
             'CI-001 baseline: nodal Kress, spline projected update'),
    Pipeline('nodal_fixed', 'nodal_kress', 'spectral',
             'Nodal Kress with sampled spectral update'),
    Pipeline('modal_fixed', 'modal_muller', 'spectral',
             'Node-free: modal Müller physics, sampled spectral update'),
)}


def get(name):
    if isinstance(name, Pipeline):
        return name
    if name not in PIPELINES:
        raise ValueError(f'Unknown pipeline {name!r}; choose from {sorted(PIPELINES)}')
    return PIPELINES[name]


def physics(pipeline, execution=None):
    """The pipeline's physics context and its forward solve, bound to that context."""
    pipeline = get(pipeline)
    if pipeline.solver == 'modal_muller':
        from .forward_solvers.modal_muller import register
        register()
    return make_backend(pipeline.solver, execution or Execution())


def fit(problem, pipeline, *, execution=None, **options):
    """``runner.fit`` with the pipeline's slots filled; other options pass through unchanged.

    The pipeline owns ``solver``, ``physics``, ``forward_solve`` and ``geometry_update``.
    """
    pipeline = get(pipeline)
    owned = {'solver', 'physics', 'forward_solve', 'geometry_update', 'geometry_adapter'} & set(options)
    if owned:
        raise ValueError(f'The pipeline sets {sorted(owned)}; do not pass them')
    execution = execution or Execution()
    context, forward_solve = physics(pipeline, execution)
    result = _fit(problem, solver=pipeline.solver, execution=execution, physics=context, forward_solve=forward_solve,
                  geometry_update=pipeline.geometry_update, **options)
    result.update(pipeline=pipeline.settings())
    return result
