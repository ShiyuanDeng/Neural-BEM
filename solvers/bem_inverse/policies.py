"""Named continuation policies: every recorded variant as one callable recipe.

A policy names a complete recipe: the stage schedule, its optimizer and stopping
options, the pipeline (physics and geometry update) and the execution options it
needs. Each entry stores only its parent and its own change, so neighbouring
policies differ for one declared reason and any two can be diffed.

Budgets are not part of a policy: ``build`` applies the caller's contract (work
units, wall seconds, model logging) to every policy alike.

| Policy | Parent | Change | Status |
|---|---|---|---|
| ``baseline`` | — | ``CumulativePolicy`` defaults, ``modal_fixed`` | default |
| ``feedback`` | baseline | agreement damping, no terminal tangent, two-frequency audits (DP-001 F) | qualified |
| ``four_phase`` | feedback | similarity start, four compact all-frequency stages, full release (CS-001) | candidate |
| ``reach_clip`` | baseline | reach-scaled steps (ON-001 G) | rejected |
| ``validity_first`` | feedback | sampled validity before the full certificate (exact) | candidate |
| ``entry_reuse`` | feedback | carry each stage endpoint into the next stage (exact) | candidate |
| ``exact_fast`` | validity_first | plus stage-entry reuse (exact) | candidate |
| ``compact_release`` | exact_fast | full-catalog stages stored at K=2M+2 | candidate |

Exact policies preserve every accepted decision of their parent; only the work done
changes. PS-001 (``docs/iterations/CI-SPD/PS-001_plan.md``) screens the set on TG-002.
"""
from dataclasses import dataclass, fields, replace

from . import pipelines as P
from .continuation_policy import ShapeFrequencyPolicy
from .physics import Execution
from .policy import CumulativePolicy

SCHEDULES = {'cumulative': CumulativePolicy, 'four_phase': ShapeFrequencyPolicy}
STATUSES = ('default', 'qualified', 'candidate', 'experimental', 'rejected')
CONTRACT = ('fit_units', 'fit_seconds', 'log_model')
# The fit part of the TG-002 campaign contract used by ON-001, DP-001, RG-001 and CS-001.
# Its endpoint-audit allowance belongs to the campaign that runs the audit.
BENCHMARK_CONTRACT = dict(fit_units=13412, fit_seconds=120., log_model=True)


@dataclass(frozen=True)
class Policy:
    """One registry entry: a parent plus a single declared change."""
    name: str
    parent: object
    change: str
    status: str
    options: tuple = ()      # (field, value): schedule options this entry sets
    execution: tuple = ()    # (field, value): Execution options this entry sets
    schedule: object = None  # None inherits the parent's schedule
    pipeline: object = None  # None inherits the parent's pipeline
    exact: bool = False      # preserves every accepted decision of the parent
    targets: str = ''
    evidence: str = ''

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f'Unknown status {self.status!r}')
        if self.schedule is not None and self.schedule not in SCHEDULES:
            raise ValueError(f'Unknown schedule {self.schedule!r}; choose from {sorted(SCHEDULES)}')
        if self.pipeline is not None:
            P.get(self.pipeline)
        allowed = {f.name for f in fields(CumulativePolicy)}
        for key, _ in self.options:
            if key in CONTRACT or key not in allowed:
                raise ValueError(f'{self.name}: {key!r} is not a policy option')
        runtime = {f.name for f in fields(Execution)}
        for key, _ in self.execution:
            if key not in runtime or key in ('device', 'frequency_threads'):
                raise ValueError(f'{self.name}: {key!r} is not a policy execution option')
        if (self.parent is None) != (self.schedule is not None and self.pipeline is not None):
            raise ValueError('Only the root policy declares both schedule and pipeline')


@dataclass(frozen=True)
class Recipe:
    """A resolved policy: everything needed to run it except the contract and devices."""
    name: str
    schedule: str
    options: dict
    pipeline: str
    execution: dict
    lineage: tuple

    def settings(self):
        return dict(name=self.name, schedule=self.schedule, options=dict(self.options), pipeline=self.pipeline,
                    execution=dict(self.execution), lineage=list(self.lineage))


EVIDENCE = dict(
    ON001='docs/iterations/cleaned_interfaces/iteration_31/01_results.md',
    DP001='docs/iterations/CI-SPD/DP-001_results.md',
    CS001='docs/iterations/CI-SPD/CS-001_results.md',
    PS001='docs/iterations/CI-SPD/PS-001_plan.md')

POLICIES = {p.name: p for p in (
    Policy('baseline', None, 'CumulativePolicy defaults with modal Müller and sampled spectral geometry',
           'default', schedule='cumulative', pipeline='modal_fixed', evidence=EVIDENCE['ON001'],
           targets='reference recipe (ON-001 B, PC-001 M1)'),
    Policy('feedback', 'baseline', 'Agreement damping with a curvature floor and progress stop, no terminal '
           'tangent, two-frequency audit batches', 'qualified',
           options=(('damping_rule', 'agreement'), ('avoid_terminal_linearization', True)),
           execution=(('audit_frequency_batch', 2),), evidence=EVIDENCE['DP001'],
           targets='controller waste and repeated work (DP-001 F)'),
    Policy('four_phase', 'feedback', 'Similarity initialization, unchanged frequency ladder, four compact '
           'all-frequency shape stages, full release', 'candidate', schedule='four_phase',
           evidence=EVIDENCE['CS001'], targets='the agreed four-phase schedule (CS-001 revised)'),
    Policy('reach_clip', 'baseline', 'Scale each step by a sampled reach estimate (factor 0.8)', 'rejected',
           options=(('reach_fraction', .8),), evidence=EVIDENCE['ON001'], targets='invalid proposals (ON-001 G)'),
    Policy('validity_first', 'feedback', 'Retain sampled-first order for optional certified geometry; '
           'ordinary spectral geometry already uses sampled checks', 'candidate',
           execution=(('validity_order', 'sampled_first'),), exact=True, evidence=EVIDENCE['PS001'],
           targets='inconclusive full certificates on complex curves (aphex: 30 of 49 fit seconds)'),
    Policy('entry_reuse', 'feedback', "Carry each stage's evaluated endpoint into the next stage when curve, "
           'catalog and resolution are unchanged', 'candidate', execution=(('stage_entry_reuse', True),),
           exact=True, evidence=EVIDENCE['PS001'],
           targets='repeated production and refined solves at every K192 stage entry'),
    Policy('exact_fast', 'validity_first', 'Add stage-entry reuse; retain the optional certificate-order setting', 'candidate',
           execution=(('stage_entry_reuse', True),), exact=True, evidence=EVIDENCE['PS001'],
           targets='both exact repairs together'),
    Policy('compact_release', 'exact_fast', 'Store every full-catalog stage at K_geometry=2M+2 instead of 192',
           'candidate', options=(('release_storage', 'compact'),), evidence=EVIDENCE['PS001'],
           targets='trace cutoff 128/160 at every shape stage regardless of M (CS-001 phase-3 mechanism)'),
)}


def get(name):
    if isinstance(name, Policy):
        return name
    if name not in POLICIES:
        raise ValueError(f'Unknown policy {name!r}; choose from {sorted(POLICIES)}')
    return POLICIES[name]


def lineage(name):
    """Root-first chain of policy names."""
    chain, seen = [], set()
    while name is not None:
        if name in seen:
            raise ValueError('Policy lineage has a cycle')
        seen.add(name)
        chain.append(name)
        name = get(name).parent
    return tuple(reversed(chain))


def recipe(name):
    """Resolve a policy's lineage into one recipe; later entries override earlier ones."""
    schedule = pipeline = None
    options, execution = {}, {}
    for entry in map(get, lineage(get(name).name)):
        schedule = entry.schedule or schedule
        pipeline = entry.pipeline or pipeline
        options.update(entry.options)
        execution.update(entry.execution)
    return Recipe(get(name).name, schedule, options, pipeline, execution, lineage(get(name).name))


def build(name, **contract):
    """The schedule object with the policy's options and the caller's contract."""
    unknown = set(contract)-set(CONTRACT)
    if unknown:
        raise ValueError(f'Contract fields are {CONTRACT}; got {sorted(unknown)}')
    resolved = recipe(name)
    return SCHEDULES[resolved.schedule](**resolved.options, **contract)


def execution_for(name, base=None):
    """``base`` (devices and threads) with the policy's execution options applied."""
    return replace(base or Execution(), **recipe(name).execution)


def difference(first, second):
    """Settings that differ between two resolved policies: {key: (first, second)}."""
    a, b = recipe(first), recipe(second)
    out = {}
    for group in ('schedule', 'pipeline'):
        if getattr(a, group) != getattr(b, group):
            out[group] = (getattr(a, group), getattr(b, group))
    for group in ('options', 'execution'):
        left, right = getattr(a, group), getattr(b, group)
        for key in sorted(set(left) | set(right)):
            if left.get(key) != right.get(key):
                out[f'{group}.{key}'] = (left.get(key), right.get(key))
    return out


def settings(name, contract=None):
    """Portable record of a policy: its declaration, resolved recipe and contract."""
    entry = get(name)
    return dict(entry=dict(name=entry.name, parent=entry.parent, change=entry.change, status=entry.status,
                           exact=entry.exact, targets=entry.targets, evidence=entry.evidence),
                recipe=recipe(name).settings(), pipeline=P.get(recipe(name).pipeline).settings(),
                contract=dict(contract or {}))


def fit(problem, name, *, execution=None, contract=None, **options):
    """Run ``problem`` under a named policy; other ``runner.fit`` options pass through.

    The policy owns the schedule object and the pipeline slots. ``execution`` gives
    devices and threads; the policy adds its execution options to it.
    """
    owned = {'policy', 'solver', 'physics', 'geometry_update', 'geometry_adapter'} & set(options)
    if owned:
        raise ValueError(f'The policy sets {sorted(owned)}; do not pass them')
    contract = dict(contract or {})
    result = P.fit(problem, recipe(name).pipeline, execution=execution_for(name, execution),
                   policy=build(name, **contract), **options)
    result['policy_spec'] = settings(name, contract)
    return result


def table():
    """Markdown table of the registry (parent, change, status, exactness)."""
    rows = ['| Policy | Parent | Change | Status | Exact |', '|---|---|---|---|---|']
    for entry in POLICIES.values():
        rows.append(f'| `{entry.name}` | {entry.parent or "—"} | {entry.change} | {entry.status} | '
                     f'{"yes" if entry.exact else "no"} |')
    return '\n'.join(rows)+'\n'
