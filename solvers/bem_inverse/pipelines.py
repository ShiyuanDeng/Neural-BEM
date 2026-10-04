"""Named inverse pipelines: one recipe per physics, with the fixes that apply to it.

``runner.fit`` has interchangeable slots: physics, geometry update and the
response to an unresolved trial. A pipeline fills those slots by name and adds
no numerics. Policy, start and localization stay with the caller, so every
pipeline sees the same stages and data.

| Name | Physics | Geometry update | Unresolved trial |
|---|---|---|---|
| ``nodal_baseline`` | nodal Kress | spline (CI-001) | hard stop (CI-001) |
| ``nodal_fixed`` | nodal Kress | certified spectral (NU-003/005/006/007a) | promote once to N1024/2048 (RB-001) |
| ``modal_fixed`` | modal Müller (scaled Graf, finer profile) | certified spectral | hard stop |

The resolution response is qualified for nodal Kress only. Modal Müller sets
its trace cutoff from the storage band, and no modal response exists yet, so
combining them is refused. Omitting a pipeline keeps ``fit``'s legacy default.
"""
from dataclasses import asdict, dataclass, replace

from .continuation.lm_backend import ResolutionResponse
from .geometry_selection import GEOMETRY_UPDATES
from .physics import Execution, make_backend
from .runner import fit as _fit


@dataclass(frozen=True)
class Pipeline:
    name: str
    solver: str
    geometry_update: str
    resolution_response: tuple = None  # (production, refined) nodes after one promotion
    description: str = ''

    def __post_init__(self):
        if self.solver not in ('nodal_kress', 'modal_muller'):
            raise ValueError(f'Unknown solver {self.solver!r}')
        if self.geometry_update not in GEOMETRY_UPDATES:
            raise ValueError(f'Unknown geometry update {self.geometry_update!r}; choose from {GEOMETRY_UPDATES}')
        if self.resolution_response is not None:
            if self.solver != 'nodal_kress':
                raise ValueError('The resolution response is qualified for nodal_kress only; '
                                 'modal_muller has no resolution response yet')
            production, refined = self.resolution_response
            ResolutionResponse(production, refined)  # validates strict refinement

    def settings(self):
        return asdict(self)


PIPELINES = {p.name: p for p in (
    Pipeline('nodal_baseline', 'nodal_kress', 'spline', None,
             'CI-001 baseline: nodal Kress, spline projected update, hard stop on an unresolved trial'),
    Pipeline('nodal_fixed', 'nodal_kress', 'certified_spectral', (1024, 2048),
             'Nodal Kress with every applicable fix: certified spectral update, RB-001 resolution response'),
    Pipeline('modal_fixed', 'modal_muller', 'certified_spectral', None,
             'Node-free: modal Müller physics, certified spectral update; no modal resolution response exists'),
)}


def get(name):
    if isinstance(name, Pipeline):
        return name
    if name not in PIPELINES:
        raise ValueError(f'Unknown pipeline {name!r}; choose from {sorted(PIPELINES)}')
    return PIPELINES[name]


def physics(pipeline, execution=None):
    pipeline = get(pipeline)
    if pipeline.solver == 'modal_muller':
        from .modal_muller import register
        register()
    return make_backend(pipeline.solver, execution or Execution())


def resolution_response(pipeline, execution=None):
    """The response with its finer physics service, or None. RB-001/FM-005 use the same construction."""
    pipeline = get(pipeline)
    if pipeline.resolution_response is None:
        return None
    production, refined = pipeline.resolution_response
    finer = replace(execution or Execution(), resolution=production)
    return ResolutionResponse(production, refined, make_backend(pipeline.solver, finer))


def promoted(result, pipeline):
    """Whether any stage ended at the promoted resolution (fit records this itself only on resume)."""
    pipeline = get(pipeline)
    if pipeline.resolution_response is None:
        return False
    return any(row.get('nodes') == pipeline.resolution_response[0] for row in result.get('stages', ()))


def fit(problem, pipeline, *, execution=None, **options):
    """``runner.fit`` with the pipeline's slots filled; other options pass through unchanged.

    The pipeline owns ``solver``, ``physics``, ``geometry_update`` and ``resolution_response``.
    """
    pipeline = get(pipeline)
    owned = {'solver', 'physics', 'geometry_update', 'resolution_response', 'geometry_adapter'} & set(options)
    if owned:
        raise ValueError(f'The pipeline sets {sorted(owned)}; do not pass them')
    execution = execution or Execution()
    result = _fit(problem, solver=pipeline.solver, execution=execution, physics=physics(pipeline, execution),
                  geometry_update=pipeline.geometry_update,
                  resolution_response=resolution_response(pipeline, execution), **options)
    result.update(pipeline=pipeline.settings(), resolution_promoted=promoted(result, pipeline))
    return result
