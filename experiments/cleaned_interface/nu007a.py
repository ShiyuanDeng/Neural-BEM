"""NU-007 completion under threshold-scaled gates, isolated from concurrent work.

The original NU-007 failure remains preserved. Freeze writes a source archive
with the proposed public selection applied only inside that archive. Execute
precheck/campaign from its extracted contents with NU007_WORKSPACE pointing to
the real repository. No frozen historical input or source seal is rewritten.
"""
import argparse
from contextlib import contextmanager
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

import numpy as np
import torch

from bem_inverse.batched import BatchedCertifiedUpdate
from bem_inverse.certified import regularity_floor, ROLES, TIERS
from bem_inverse.device_certified import DeviceCertifiedUpdate
from bem_inverse.continuation.updates import UpdateRefused
from bem_inverse.io import read, write, digest, portable, curve_from
from bem_inverse.physics import Execution
from bem_inverse.modal_muller import register
from bem_inverse import runner
from . import benchmark as b

SOURCE_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get('NU007_WORKSPACE', SOURCE_ROOT)).resolve()
b.ROOT = ROOT
b.BASE = ROOT/'results/validation/shape_continuation'
b.SOURCE_MANIFEST = b.BASE/'SC-051-frequency-only/manifest.json'
from .n_update_audit import ArmPolicy, CORE, case_drift
from .nu003 import CONSTRUCTION, decide, identity

BASE = ROOT/'results/validation/cleaned_interfaces'
DEFAULT_OUTPUT = BASE/'NU-007a-20261003'
BEFORE = "        return BatchedCertifiedUpdate(length_unit_m, device=None if execution.device == 'auto' else execution.device)"
AFTER = """        update = BatchedCertifiedUpdate(length_unit_m, device=None if execution.device == 'auto' else execution.device)
        if update.device == 'cuda':
            from .device_certified import DeviceCertifiedUpdate
            return DeviceCertifiedUpdate(length_unit_m, device=update.device)
        return update"""
CONTRACT = dict(
    experiment='NU-007a', source_states='NU-006: last accepted state in every stage',
    sizes_m=[1e-7, 1e-3, 6e-3, 1.8e-2], directions=3, seed=5,
    bound_tolerance=1e-9, bound_scale='max(1, abs(host bound))',
    same_threshold_side=True, same_regularity_side=True,
    same_decisions_reasons_candidates=True, same_role_tiers=True,
    campaign_cases=list(CORE), repeats=3, execution=Execution('cuda', 4).__dict__,
    adoption='NU-001 no-drift and >=5/6 matches, same NU-006 decisions, work and tier counts; '
             'bit-identical fresh CPU/GPU accepted curves; full-path timing reported separately',
    disclosure='Threshold-scaled gate chosen after original NU-007 diagnostic and 36-trial replay; '
               'not an independent unseen-data gate. Original failed evidence is preserved.',
)


def freeze(output):
    output.mkdir(parents=True, exist_ok=True)
    if (output/'manifest.json').exists():
        raise FileExistsError('Use existing sealed sources or a fresh output; do not overwrite the seal.')
    sources = sorted(set(ROOT.glob('solvers/**/*.py')) | set(ROOT.glob('experiments/**/*.py')))
    before, after = {}, {}
    with tarfile.open(output/'sources.tar.gz', 'w:gz') as archive:
        for path in sources:
            name = str(path.relative_to(ROOT))
            content = path.read_bytes()
            before[name] = hashlib.sha256(content).hexdigest()
            if name == 'solvers/bem_inverse/geometry_selection.py':
                text = content.decode()
                if text.count(BEFORE) != 1:
                    raise ValueError('Public selection changed; review integration before freezing.')
                content = text.replace(BEFORE, AFTER).encode()
            after[name] = hashlib.sha256(content).hexdigest()
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    old = read(BASE/'NU-006/manifest.json')
    inputs = dict(old['inputs'])
    for name, expected in read(BASE/'NU-006/augmentation.json')['files'].items():
        inputs[str(Path('results/validation/cleaned_interfaces/NU-006')/name)] = expected
    for campaign in ('NU-006', 'CI-001'):
        for case in CORE:
            for path in (BASE/campaign/'runs'/case).glob('*.json'):
                inputs[str(path.relative_to(ROOT))] = digest(path)
        path = BASE/campaign/'comparison.json'
        inputs[str(path.relative_to(ROOT))] = digest(path)
    for name, expected in inputs.items():
        if digest(ROOT/name) != expected:
            raise ValueError('Historical input changed: '+name)
    write(output/'contract.json', CONTRACT)
    write(output/'manifest.json', dict(sources=after, original_sources=before, inputs=inputs,
        cases=[r for r in old['cases'] if r['id'] in CORE], archive_sha256=digest(output/'sources.tar.gz'),
        contract_sha256=digest(output/'contract.json'), plan_sha256=digest(output/'PLAN.md'),
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        shared_selection_untouched=True))
    print('FROZEN', output, flush=True)


def verify(output):
    manifest = read(output/'manifest.json')
    for name, expected in manifest['sources'].items():
        if digest(SOURCE_ROOT/name) != expected:
            raise ValueError('Execute from the frozen source tree; changed source: '+name)
    for name, expected in manifest['inputs'].items():
        if digest(ROOT/name) != expected:
            raise ValueError('Changed historical input: '+name)
    for name, key in (('sources.tar.gz','archive_sha256'), ('contract.json','contract_sha256'), ('PLAN.md','plan_sha256')):
        if digest(output/name) != manifest[key]:
            raise ValueError('Changed qualification seal: '+name)
    return manifest


def compare_records(host, device, tolerance=1e-9):
    """Test actual branch predicates as well as a threshold-scaled bound error."""
    same_tiers = [(r['role'], r['tier']) for r in host] == [(r['role'], r['tier']) for r in device]
    bounds, same_keys = [], len(host) == len(device)
    for h, d in zip(host, device):
        for key in ('increment_bound', 'full_bound'):
            same_keys &= (key in h) == (key in d)
            if key not in h or key not in d:
                continue
            lower = key.replace('bound', 'lower')
            gap = abs(h[key]-d[key])/max(1., abs(h[key]))
            bounds.append(dict(role=h['role'], key=key, host=h[key], device=d[key], scaled_gap=gap,
                same_side=(h[key] < 1) == (d[key] < 1),
                threshold_margin=min(abs(1-h[key]), abs(1-d[key])),
                host_lower=h[lower], device_lower=d[lower], floor=h['regularity_floor'],
                same_regularity_side=(h[lower] >= h['regularity_floor']) == (d[lower] >= d['regularity_floor'])))
    return dict(same_tiers=same_tiers, same_bound_keys=bool(same_keys), bounds=bounds,
        bounds_agree=bool(same_keys and all(np.isfinite(r['scaled_gap']) and r['scaled_gap'] <= tolerance for r in bounds)),
        same_threshold_sides=all(r['same_side'] for r in bounds),
        same_regularity_sides=all(r['same_regularity_side'] for r in bounds))


class Observed:
    def certify(self, space, x):
        tier, row = super().certify(space, x)
        return tier, dict(row, regularity_floor=regularity_floor(x))


class HostUpdate(Observed, BatchedCertifiedUpdate):
    pass


class DeviceUpdate(Observed, DeviceCertifiedUpdate):
    pass


def precheck_state(curve, modes):
    updates = {'host': HostUpdate(.05, device='cuda'), 'device': DeviceUpdate(.05, device='cuda')}
    spaces = {name: update.prepare(curve, modes, curve.band) for name, update in updates.items()}
    rng = np.random.default_rng(CONTRACT['seed'])
    trials = []
    for size in CONTRACT['sizes_m']:
        for direction in range(CONTRACT['directions']):
            step = rng.normal(size=len(spaces['host'].orders))
            step *= size/updates['host'].measure(spaces['host'], step)['maximum_normal_m']
            outcomes = {}
            for name, update in updates.items():
                seconds = update.counts['certificate_seconds']
                try:
                    candidate, _ = update.trial(spaces[name], step)
                    outcome = dict(status='accepted', coefficients=candidate.coefficients)
                except (UpdateRefused, ValueError) as exc:
                    outcome = dict(status='refused', reason=getattr(exc, 'reason', str(exc)))
                outcomes[name] = dict(outcome, records=list(update.records),
                    certificate_seconds=update.counts['certificate_seconds']-seconds)
            h, d = outcomes['host'], outcomes['device']
            same = h['status'] == d['status'] and (h.get('reason') == d.get('reason') if h['status']=='refused'
                else np.array_equal(h['coefficients'], d['coefficients']))
            comparison = compare_records(h['records'], d['records'], CONTRACT['bound_tolerance'])
            for outcome in outcomes.values():
                coefficients = outcome.pop('coefficients', None)
                if coefficients is not None:
                    outcome['coefficients_sha256'] = hashlib.sha256(coefficients.tobytes()).hexdigest()
            trials.append(dict(size_m=size, direction=direction, same_decision=bool(same),
                               **comparison, outcomes=outcomes))
    return dict(K=curve.band, M=modes, trials=trials, counts={name: u.counts for name, u in updates.items()})


def precheck(output):
    verify(output)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA qualification cannot silently fall back to CPU.')
    rows = []
    for case in CORE:
        last = {s['stage']: s for s in read(BASE/'NU-006/runs'/case/'accepted.json')['states']}
        for stage, state in last.items():
            path = output/'precheck_states'/case/(stage+'.json')
            if path.exists():
                row = read(path)
                if row['manifest_sha256'] != digest(output/'manifest.json'):
                    raise ValueError('Precheck state belongs to another seal.')
            else:
                row = dict(case=case, stage=stage, manifest_sha256=digest(output/'manifest.json'),
                           **precheck_state(curve_from(state['curve']), state['M']))
                write(path, row)
            rows.append(row)
            trials = row['trials']
            gates = ('same_decision','same_tiers','same_bound_keys','bounds_agree','same_threshold_sides','same_regularity_sides')
            print('PRECHECK', len(rows), '/72', case, stage, 'pass', all(t[g] for t in trials for g in gates), flush=True)
    trials = [t for r in rows for t in r['trials']]
    gates = {key: all(t[key] for t in trials) for key in gates}
    bounds = [v for t in trials for v in t['bounds']]
    result = dict(states=len(rows), trials=len(trials), gates=gates, passed=all(gates.values()),
        max_scaled_gap=max(v['scaled_gap'] for v in bounds), min_threshold_margin=min(v['threshold_margin'] for v in bounds),
        certificate_seconds={name: sum(t['outcomes'][name]['certificate_seconds'] for t in trials) for name in ('host','device')},
        device_fallbacks=sum(r['counts']['device']['device_certificate_fallbacks'] for r in rows),
        manifest_sha256=digest(output/'manifest.json'), environment=b.environment())
    verify(output)
    write(output/'precheck.json', result)
    print(portable(result), flush=True)
    if not result['passed']:
        raise RuntimeError('Precheck failed; campaign remains gated.')


def external_python():
    listing = subprocess.check_output(['ps','-C','python','-o','pid=,args='], text=True)
    return [line.strip() for line in listing.splitlines() if int(line.split()[0]) != os.getpid()
            and ('fm002' in line or 'pytest' in line or 'cleaned_interface' in line)]


def wait_for_other_run():
    while external_python():
        print('WAITING for other numerical work:', external_python(), flush=True)
        time.sleep(30)


@contextmanager
def reference_update():
    saved = runner.ProjectedUpdate
    runner.ProjectedUpdate = lambda unit: BatchedCertifiedUpdate(unit, device='cuda')
    try:
        yield
    finally:
        runner.ProjectedUpdate = saved


def status(row, result):
    ref = read(ROOT/row['reference_receipt'])
    gates = {key: result['metrics'][key] <= ref['metrics'][key]+max(.02, .05*ref['metrics'][key])
             for key in ('rms_mm','hausdorff_upper_mm')}
    gates['residual'] = bool(result['relative_residual'] is not None and np.all(
        np.asarray(result['relative_residual']) <= np.asarray(ref['relative_residual'])+
        np.maximum(1e-6, .05*np.asarray(ref['relative_residual']))))
    gates['recovery'] = not ref['recovered'] or result['recovered']
    gates['audit'] = result['final_audit_passed']
    return 'PASS' if all(gates.values()) else 'REGRESSION'


def run_case(output, row, arm):
    if (output/'result.json').exists():
        raise FileExistsError('Preserve completed run: '+str(output))
    if output.exists():
        raise FileExistsError('Preserve incomplete run: '+str(output))
    output.mkdir(parents=True)
    execution = Execution('cuda', 4)
    problem = b.fitting_problem(row, BASE/'NU-006')
    options = dict(solver='modal_muller', execution=execution, policy=ArmPolicy(geometry_update=CONSTRUCTION),
        output=output, on_event=lambda e: print('STAGE', arm, row['id'], e['operation']['label'], e['reason'], flush=True))
    before = b.environment()
    work_before = external_python()
    torch.cuda.synchronize()
    if arm == 'host':
        with reference_update():
            result = runner.fit(problem, **options)
    else:
        result = runner.fit(problem, geometry_update='certified_spectral', **options)
    torch.cuda.synchronize()
    # Scoring is outside the inverse and its measured wall time.
    result['metrics'] = b.score(row, curve_from(result['final_curve']))
    limits = b.residual_limits(row)
    residual = result.get('relative_residual')
    result.update(case=row, recovered=bool(result['final_audit_passed'] and result['metrics']['rms_mm']<=1.
        and result['metrics']['hausdorff_upper_mm']<=2. and residual is not None and np.all(residual<=limits)),
        maximum_residual=None if residual is None else float(max(residual)), residual_limits=limits)
    result['comparison_status'] = status(row, result)
    result['timing_environment'] = dict(before=before, after=b.environment(),
        external_work_before=work_before, external_work_after=external_python())
    write(output/'result.json', result)
    print('RESULT', arm, row['id'], result['outcome'], result['comparison_status'], result['total_seconds'], flush=True)
    return result


def pair_report(host, device):
    h, d = read(host/'result.json'), read(device/'result.json')
    accepted_h, accepted_d = read(host/'accepted.json')['states'], read(device/'accepted.json')['states']
    same_accepted = len(accepted_h)==len(accepted_d) and all(
        all(x[k]==y[k] for k in ('stage','iteration','M','units','curve')) for x,y in zip(accepted_h,accepted_d))
    tiers = [f'{role}_{tier}' for role in ROLES for tier in TIERS]
    same_tiers = all(h['geometry_work'][k]==d['geometry_work'][k] for k in tiers)
    decisions_h = [(x['operation']['label'], x['reason']) for x in h['decisions']]
    decisions_d = [(x['operation']['label'], x['reason']) for x in d['decisions']]
    return dict(same_accepted_states=same_accepted, same_final_curve=h['final_curve']==d['final_curve'],
        same_decisions=decisions_h==decisions_d, same_units=h['total_units']==d['total_units'],
        same_tiers=same_tiers, same_status=h['comparison_status']==d['comparison_status'],
        audits_passed=bool(h['initial_audit_passed'] and h['final_audit_passed'] and d['initial_audit_passed'] and d['final_audit_passed']),
        seconds={name:r['total_seconds'] for name,r in (('host',h),('device',d))},
        certificate_seconds={name:r['geometry_work']['certificate_seconds'] for name,r in (('host',h),('device',d))})


def campaign(output):
    manifest = verify(output)
    qualification = read(output/'precheck.json')
    if not qualification['passed'] or qualification['manifest_sha256'] != digest(output/'manifest.json'):
        raise ValueError('Campaign requires the successful sealed precheck.')
    register()
    rows = {r['id']:r for r in manifest['cases']}
    pairs = []
    for repeat in range(CONTRACT['repeats']):
        order = ('host','device') if repeat%2==0 else ('device','host')
        for case in CORE:
            for arm in order:
                folder = output/f'pair_{repeat+1}'/arm/'runs'/case
                if (folder/'result.json').exists():
                    continue
                wait_for_other_run()
                verify(output)
                run_case(folder, rows[case], arm)
            report = pair_report(output/f'pair_{repeat+1}/host/runs'/case, output/f'pair_{repeat+1}/device/runs'/case)
            pairs.append(dict(repeat=repeat+1, case=case, **report))
            write(output/'pairs.json', dict(pairs=pairs))
            keys = ('same_accepted_states','same_final_curve','same_decisions','same_units','same_tiers','same_status','audits_passed')
            if not all(report[k] for k in keys):
                raise RuntimeError('Fresh complete-path identity gate failed; see pairs.json.')
    verify(output)
    write(output/'campaign_complete.json', dict(passed=True, pairs=len(pairs), manifest_sha256=digest(output/'manifest.json')))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('command', choices=('freeze','verify','precheck','campaign'))
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    globals()[args.command](args.output.resolve())


if __name__ == '__main__':
    main()
