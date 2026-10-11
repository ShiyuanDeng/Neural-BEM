"""Named continuation policies: every recorded variant as one callable recipe.

A policy names a complete recipe: the stage schedule, its optimizer and stopping
options, the pipeline (physics, geometry update, unresolved-trial response) and the
execution options it needs. Each entry stores only its parent and its own change, so
neighbouring policies differ for one declared reason and any two can be diffed.

Budgets are not part of a policy: ``build`` applies the caller's contract (work
units, wall seconds, audit allowances, model logging) to every policy alike.

| Policy | Parent | Change | Status |
|---|---|---|---|
| ``baseline`` | — | ``CumulativePolicy`` defaults, ``modal_fixed`` | default |
| ``accuracy_exit`` | baseline | stop at full-catalog residual <= 0.003 with a passed audit (ON-001 E) | qualified |
| ``feedback`` | accuracy_exit | agreement damping, no terminal tangent, two-frequency audits (DP-001 F) | qualified |
| ``decision_gate`` | accuracy_exit | unresolved trials keep their gain decision (RG-001) | experimental |
| ``four_phase`` | feedback | similarity start, four compact all-frequency stages, full release (CS-001) | candidate |
| ``reach_clip`` | baseline | reach-scaled steps (ON-001 G) | rejected |
| ``working_frequencies`` | accuracy_exit | seven-frequency proposals (ON-001 EW) | rejected |
| ``validity_first`` | feedback | sampled validity before the full certificate (exact) | candidate |
| ``entry_reuse`` | feedback | carry each stage endpoint into the next stage (exact) | candidate |
| ``exact_fast`` | validity_first | plus stage-entry reuse (exact) | candidate |
| ``compact_release`` | exact_fast | full-catalog stages stored at K=2M+2 | candidate |
| ``resolution_response`` | exact_fast | ``modal_response``: promote an unresolved trial once | candidate |
| ``adaptive_resolution`` | compact_release | ``modal_response`` on the compact stages | candidate |

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
CONTRACT = ('fit_units', 'fit_seconds', 'audit_seconds', 'audit_aggregate_seconds', 'log_model')
# The TG-002 campaign contract used by ON-001, DP-001, RG-001 and CS-001.
BENCHMARK_CONTRACT = dict(fit_units=13412, fit_seconds=120., audit_seconds=30., audit_aggregate_seconds=30.,
                          log_model=True)


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
    RG001='docs/iterations/cleaned_interfaces/iteration_31/05_results.md',
    CS001='docs/iterations/CI-SPD/CS-001_results.md',
    PS001='docs/iterations/CI-SPD/PS-001_plan.md')

POLICIES = {p.name: p for p in (
    Policy('baseline', None, 'CumulativePolicy defaults with modal Müller and certified spectral geometry',
           'default', schedule='cumulative', pipeline='modal_fixed', evidence=EVIDENCE['ON001'],
           targets='reference recipe (ON-001 B, PC-001 M1)'),
    Policy('accuracy_exit', 'baseline', 'Stop at an accepted full-catalog state with maximum residual <= 0.003 '
           'once its endpoint audit passes', 'qualified', options=(('required_accuracy', .003),),
           evidence=EVIDENCE['ON001'], targets='work after the required accuracy is reached (ON-001 E)'),
    Policy('feedback', 'accuracy_exit', 'Agreement damping with a curvature floor and progress stop, no terminal '
           'tangent, two-frequency audit batches', 'qualified',
           options=(('damping_rule', 'agreement'), ('avoid_terminal_linearization', True)),
           execution=(('audit_frequency_batch', 2),), evidence=EVIDENCE['DP001'],
           targets='controller waste and repeated work (DP-001 F)'),
    Policy('decision_gate', 'accuracy_exit', 'An unresolved trial keeps its production/refined gain decision '
           'instead of stopping the fit', 'experimental', options=(('resolution_gate', 'decision'),),
           evidence=EVIDENCE['RG001'], targets='the fatal resolution gate that ends the four failures (RG-001)'),
    Policy('four_phase', 'feedback', 'Similarity initialization, unchanged frequency ladder, four compact '
           'all-frequency shape stages, full release', 'candidate', schedule='four_phase',
           evidence=EVIDENCE['CS001'], targets='the agreed four-phase schedule (CS-001 revised)'),
    Policy('reach_clip', 'baseline', 'Scale each step by a sampled reach estimate (factor 0.8)', 'rejected',
           options=(('reach_fraction', .8),), evidence=EVIDENCE['ON001'], targets='invalid proposals (ON-001 G)'),
    Policy('working_frequencies', 'accuracy_exit', 'Propose steps from five anchors plus two residual-selected '
           'frequencies; accept on the full catalog', 'rejected', options=(('working_anchors', 5),),
           evidence=EVIDENCE['ON001'], targets='per-step physics cost (ON-001 EW)'),
    Policy('validity_first', 'feedback', 'Run the sampled validity test before the full |W|^2 certificate; '
           'the certificate only overturns a sampled refusal', 'candidate',
           execution=(('validity_order', 'sampled_first'),), exact=True, evidence=EVIDENCE['PS001'],
           targets='inconclusive full certificates on complex curves (aphex: 30 of 49 fit seconds)'),
    Policy('entry_reuse', 'feedback', "Carry each stage's evaluated endpoint into the next stage when curve, "
           'catalog and resolution are unchanged', 'candidate', execution=(('stage_entry_reuse', True),),
           exact=True, evidence=EVIDENCE['PS001'],
           targets='repeated production and refined solves at every K192 stage entry'),
    Policy('exact_fast', 'validity_first', 'Add stage-entry reuse to sampled-first validity', 'candidate',
           execution=(('stage_entry_reuse', True),), exact=True, evidence=EVIDENCE['PS001'],
           targets='both exact repairs together'),
    Policy('compact_release', 'exact_fast', 'Store every full-catalog stage at K_geometry=2M+2 instead of 192',
           'candidate', options=(('release_storage', 'compact'),), evidence=EVIDENCE['PS001'],
           targets='trace cutoff 128/160 at every shape stage regardless of M (CS-001 phase-3 mechanism)'),
    Policy('resolution_response', 'exact_fast', 'Promote an unresolved trial once to the K_geometry=192 profile; '
           'reject unresolved trials there instead of stopping', 'candidate', pipeline='modal_response',
           evidence=EVIDENCE['PS001'], targets='the fatal resolution gate (RP-001 direction)'),
    Policy('adaptive_resolution', 'compact_release', 'Compact stages that promote once to the K_geometry=192 '
           'profile when a trial is unresolved', 'candidate', pipeline='modal_response',
           evidence=EVIDENCE['PS001'], targets='compact-stage speed without the CS-001 C-shape stop'),
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
    owned = {'policy', 'solver', 'physics', 'geometry_update', 'resolution_response', 'geometry_adapter'} & set(options)
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
