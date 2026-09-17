"""Preparation only: stdlib reads of saved evidence; no repository imports/solves.

Run: python -B /tmp/geometry-integration-prep-20260917/audit_saved_evidence.py
All output stays beside this script, outside the measured checkout.
"""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path('/home/drdeng/Neural_SDF_BEM_AD')
OUT = Path(__file__).resolve().parent
LIVE = ROOT / 'results/validation/topology/TOP-025-compiled-20260917-115641'
HISTORY = ROOT / 'results/validation/topology/TOP-025-20260915-210356-all-scenes-current'
FULL = ROOT / 'results/validation/speedup/SPD-006-20260916-full-inverse'
QUAL = ROOT / 'results/validation/speedup/SPD-006-20260916-qualification-01'
assert ROOT not in OUT.parents and OUT != ROOT
consumed = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    raw = path.read_bytes()
    consumed[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def lines(path):
    raw = path.read_bytes()
    consumed[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def verify(base, expected):
    missing, changed = [], []
    for name, sha in expected.items():
        path = base / name
        if not path.is_file():
            missing.append(name)
        elif digest(path) != sha:
            changed.append(name)
    return dict(listed_files=len(expected), missing=missing, changed=changed,
                passed=not missing and not changed)


def state_signature(state):
    """Archive coefficient fingerprint, NOT a production geometry cache key."""
    return tuple((c['chart'], c['component_id'], c['maximum_mode'],
                  struct.pack('<' + 'd' * len(c['parameters']), *c['parameters']))
                 for c in state)


manifest = read(LIVE / 'manifest.json')
live_before = verify(ROOT, manifest['source_sha256'])
qualification = read(QUAL / 'qualification.json')
qualified_inputs = verify(ROOT, qualification['input_sha256'])
fixtures = []


def fixture(name, path, state, selector, role):
    state_signature(state)  # schema and float64 packing check, not geometry validation
    assert len({c['component_id'] for c in state}) == len(state)
    assert all(c['chart'] == 'cartesian' and
               len(c['parameters']) == 4 * c['maximum_mode'] + 2 for c in state)
    fixtures.append(dict(name=name, source=str(path.relative_to(ROOT)),
                         source_sha256=consumed[str(path.relative_to(ROOT))],
                         selector=selector, role=role, state=state,
                         geometry_revalidated=False))


for scene in ('death', 'split', 'merge'):
    path = HISTORY / 'runs' / scene / 'topology/trajectory.jsonl'
    for i, row in enumerate(lines(path), 1):
        label = row['label']
        if label.startswith('before ') or label.endswith(' accepted'):
            fixture(scene + '_' + label.replace(' ', '_'), path, row['state'],
                    f'jsonl line {i}, state', 'existing SPD-006 event fixture')
for scene in ('central-ellipse-star', 'far-two-stars', 'death', 'split', 'merge'):
    path = HISTORY / 'runs' / scene / 'handoff.json'
    fixture(scene + ('_handoff' if scene in ('central-ellipse-star', 'far-two-stars')
                     else '_capacity_handoff'), path, read(path)['state'],
            'state', 'existing SPD-006 capacity/hard-case fixture')
qualified_names = sorted({row['fixture'] for row in qualification['rows']})
assert qualified_names == sorted(f['name'] for f in fixtures)
path = ROOT / 'results/validation/topology/TOP-006-20260911-scenes-v1/runs/A/far-ellipse-star/checkpoint.json'
fixture('top006_resolution_sensitive_abort', path, read(path)['state'], 'state',
        'test_refined_feasibility_guard expects 64-node accept, 128/256-node refusal; not rerun')
path = FULL / 'remaining_cost_profile/stage/initial_state.json'
fixture('spd006_profile_initial', path, read(path), 'root', 'profile replay input')
for scene in ('merge', 'central-ellipse-star', 'far-two-stars'):
    path = FULL / 'compiled_0/runs' / scene / 'F/stage_1/trajectory.jsonl'
    records = lines(path)
    for index in (0, len(records)-1):
        fixture(f'compiled_0_{scene}_stage1_row{index+1}', path,
                records[index]['state'], f'jsonl line {index+1}, state',
                'saved compiled trajectory endpoint; no new trajectory')

workers = []
for arm in ('compiled_0', 'compiled_1', 'reciprocal_0', 'reciprocal_1'):
    for scene in ('death', 'merge', 'central-ellipse-star', 'far-two-stars'):
        folder = FULL / arm / 'runs' / scene / 'F'
        jacobians, refusals = [], []
        for path in sorted(folder.glob('stage_*/jacobians.jsonl')):
            jacobians.extend(lines(path))
        for path in sorted(folder.glob('stage_*/feasibility.jsonl')):
            refusals.extend(lines(path))
        workers.append(dict(arm=arm, scene=scene, jacobian_records=len(jacobians),
                            one_sided_columns=sum(x['one_sided_columns'] for x in jacobians),
                            unresolved_columns=sum(x['unresolved_columns'] for x in jacobians),
                            logged_refusals=dict(Counter(x.get('reason', '<missing>') for x in refusals)),
                            refusal_records=len(refusals)))

test_files = [
    'pytest/gpr_bem_kress/test_isolation_and_api.py',
    'pytest/gpr_bem_kress/test_multicomponent.py',
    'pytest/ordered_boundary/test_ordered_periodic_curve.py',
    'pytest/ordered_boundary/test_ordered_boundary.py',
    'pytest/sdf_inverse/test_refined_feasibility_guard.py',
    'pytest/sdf_inverse/test_feasible_finite_differences.py',
    'pytest/sdf_inverse/test_spd001.py',
    'pytest/sdf_inverse/test_spd006.py',
    'pytest/sdf_inverse/test_cartesian_fourier_chart.py',
]
tests = []
for name in test_files:
    raw = (ROOT/name).read_bytes()
    consumed[name] = hashlib.sha256(raw).hexdigest()
    tree = ast.parse(raw, filename=name)
    tests.append(dict(path=name, sha256=consumed[name],
                      functions=[dict(name=node.name, line=node.lineno)
                                 for node in ast.walk(tree)
                                 if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]))

# Verify only the sealed historical artifacts actually read, not the live outputs.
seal_record = read(FULL / 'artifact_manifest.json')
seal = seal_record['files']
assert seal_record['file_count'] == len(seal)
selected = {str((ROOT/name).relative_to(FULL)): sha
            for name, sha in consumed.items()
            if FULL in (ROOT/name).parents and name != str((FULL/'artifact_manifest.json').relative_to(ROOT))}
seal_absent = [name for name in selected if name not in seal]
seal_mismatch = [name for name, sha in selected.items() if name in seal and seal[name] != sha]
live_after = verify(ROOT, manifest['source_sha256'])
result = dict(
    scope='saved-evidence and source-contract preparation only; no imported repository code, geometry evaluation, tests or inverse solves',
    prepared_utc=datetime.now(timezone.utc).isoformat(),
    active_campaign_sources_before=live_before,
    active_campaign_sources_after=live_after,
    active_campaign_listed_test_hashes=verify(ROOT, read(LIVE/'pre_dispatch_validation.json')['test_sha256']),
    qualification_inputs=qualified_inputs,
    selected_spd006_seal=dict(checked=len(selected), absent=seal_absent, mismatch=seal_mismatch,
                             passed=not seal_absent and not seal_mismatch),
    fixture_count=len(fixtures), existing_qualification_fixtures=len(qualified_names),
    fixture_schema_pass=True, geometry_revalidation_performed=False,
    workers=workers,
    totals=dict(jacobian_records=sum(w['jacobian_records'] for w in workers),
                one_sided_columns=sum(w['one_sided_columns'] for w in workers),
                unresolved_columns=sum(w['unresolved_columns'] for w in workers),
                logged_refusals=sum(w['refusal_records'] for w in workers)),
    test_inventory=tests, tests_executed=0, numerical_solves=0,
    limits=['Existing test definitions are inventoried, not executed.',
            'Saved hashes and schemas do not establish geometry admissibility.',
            'Zero one-sided columns does not mean no infeasible line-search candidates.',
            'No cache hit-rate or performance measurement was made.',
            'Live-source verification covers manifest-listed files, not reconstruction of the runners file inventory.'],
    consumed_sha256=consumed)
result['status'] = 'PASS' if all(result[name]['passed'] for name in ('active_campaign_sources_before',
            'active_campaign_sources_after', 'active_campaign_listed_test_hashes',
            'qualification_inputs', 'selected_spd006_seal')) else 'FAIL'
for name, value in [('audit.json', result), ('fixtures.json', fixtures)]:
    (OUT/name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
print(json.dumps({key:result[key] for key in ('active_campaign_sources_after',
    'active_campaign_listed_test_hashes', 'qualification_inputs', 'selected_spd006_seal',
    'fixture_count', 'existing_qualification_fixtures', 'totals', 'tests_executed', 'numerical_solves')}, indent=2))
raise SystemExit(0 if result['status'] == 'PASS' else 1)
