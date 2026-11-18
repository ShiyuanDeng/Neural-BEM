"""B1 preparation, guarded checks, and single GPU fits. Fits require coordinator go."""
from b1_runtime import (ROOT, BASE, GIB, pin_torch, provenance, write, digest, now,
                        available, bem_jobs, bulk, guarded)
import argparse
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback

pin_torch()
import numpy as np
import torch
from bem_inverse import Execution, Problem
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings, forward_solve
from bem_inverse.real_only_policy import RealOnlyPolicy
from bem_inverse.io import curve_from, curve_record
import b1_data as D

DOC = ROOT/'docs/iterations/adapt_bem_to_baseline_data/06_fit_brg_tg002_cases'


@dataclass(frozen=True)
class B1Policy(RealOnlyPolicy):
    """Inherit every stage/tail rule; only use frequency blocks for ragged data."""
    fit_seconds: float = float('inf')

    def _fit(self, *args, **kwargs):
        operation = super()._fit(*args, **kwargs)
        return replace(operation, stage=replace(operation.stage, ragged_data=True))


def context():
    return ModalMuller(Execution(device='cuda', frequency_threads=1), ModalSettings(table_mode=True))


def make_problem(case, contrast):
    from experiments.benchmark.scenes import start_fixture
    hashes = D.verify_files(case)
    assert hashes['passes'], f'{case}: missing/unverified data; report to coordinator.'
    real, sources = [], []
    for f, source in zip(D.catalog()[::2], hashes['files'][::2]):
        obs, row = D.observation(case, f, source)
        real.append(obs)
        sources.append(row)
    return Problem(start_fixture(), tuple(real), None, contrast, allow_variable_acquisition=True), sources


def prepare():
    started = time.monotonic()
    request = json.loads(D.REQUEST.read_text())
    contract = {k: request[k] for k in ('units', 'background', 'frequencies')}
    contract['request_sha256'] = digest(D.REQUEST)
    contract_path = BASE/'acquisition.json'
    if contract_path.exists():
        assert json.loads(contract_path.read_text())==contract, 'Frozen acquisition changed.'
    else:
        write(contract_path, contract)
    rows = []
    for case in D.CASES:
        row = D.verify_files(case)
        row.update(layouts=[], error=None)
        try:
            if row['passes']:
                for f, source in zip(D.catalog(), row['files']):
                    _, converted = D.observation(case, f, source)
                    row['layouts'].append(converted)
                _, row['truth'] = D.truth_checked(case)
        except Exception:
            row.update(passes=False, error=traceback.format_exc())
        rows.append(row)
        print(case, 'PASS' if row['passes'] else 'BLOCKED', sum(r['passes'] for r in row['files']), '/37', row['error'] or '', flush=True)
    # Compare inherited operation records, including adaptive tail, without a solve.
    example = next((r['case'] for r in rows if r['passes']), None)
    schedule = None
    if example:
        p, _ = make_problem(example, 4.)
        physics = context()
        baseline, adapted = RealOnlyPolicy(), B1Policy()
        for original, changed in ((baseline.operations(p, physics), adapted.operations(p, physics)),
                                  (baseline.tail(p, physics, 95), adapted.tail(p, physics, 95))):
            assert len(original)==len(changed)
            for a, b in zip(original, changed):
                normalized = replace(b, stage=replace(b.stage, ragged_data=False)) if b.stage else b
                assert a.record()==normalized.record(), 'Schedule changed beyond frequency blocks.'
        from experiments.cleaned_interface.benchmark import FREQUENCIES
        assert [o.frequency_hz for o in p.real]==list(FREQUENCIES)
        schedule = adapted.plan(p, physics)
        schedule.update(default_schedule_and_tail_equal_except_ragged=True, elapsed_limit='disabled; infinity in ledger',
                        torch_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads())
    receipt = dict(utc=now(), provenance=provenance(), request_sha256=digest(D.REQUEST), cases=rows,
                   passes=all(r['passes'] for r in rows), policy=schedule, seconds=time.monotonic()-started,
                   available_bytes=available(), other_bem_jobs=bem_jobs(),
                   queue=[dict(row=row, case=case) for row in ('known', 'recovered') for case in D.ORDER])
    name = 'prepare_'+time.strftime('%H%M%S', time.gmtime())+'.json'
    write(BASE/name, receipt)
    return receipt


def check_worker(case, out):
    start = time.monotonic()
    before = provenance()
    hashes = D.verify_files(case)
    assert hashes['passes']
    write(out/'inputs.json', hashes)
    curve, truth_record = D.truth_checked(case)
    physics = context()
    profile = physics.resolution_profile(curve.band)
    torch.cuda.reset_peak_memory_stats()
    rows = []
    for f, source in zip(D.catalog(), hashes['files']):
        began = time.monotonic()
        row = dict(index=f['index'], frequency_hz=f['frequency_hz'], passes=False)
        try:
            observation, conversion = D.observation(case, f, source)
            row['conversion'] = conversion
            eta = float(case.split('__c')[1])
            a = forward_solve(curve, observation, eta, profile['production'], context=physics)
            production = a.prediction.copy()
            row['production'] = a.diagnostics
            del a
            b = forward_solve(curve, observation, eta, profile['refined'], context=physics)
            refined = b.prediction.copy()
            row['refined'] = b.diagnostics
            del b
            delta = production-observation.scattered
            difference = float(np.linalg.norm(delta)/np.linalg.norm(observation.scattered))
            refinement = float(np.linalg.norm(production-refined)/np.linalg.norm(refined))
            row.update(relative_brg_difference=difference, relative_refinement_difference=refinement,
                       max_absolute_difference=float(abs(delta).max()),
                       receiver_relative_errors=np.linalg.norm(delta, axis=0)/np.linalg.norm(observation.scattered, axis=0),
                       direction_relative_errors=np.linalg.norm(delta, axis=1)/np.linalg.norm(observation.scattered, axis=1),
                       passes=difference <= .01 and refinement <= 1e-6)
            copy = out/'local'/f'fields_{f["index"]:03d}.npz'
            np.savez_compressed(copy, production=production, refined=refined,
                                k_bem=observation.wavenumber, frequency_hz=observation.frequency_hz,
                                receivers=np.asarray(f['receivers_xy'])*D.SCALE,
                                directions=f['directions_xy'])
            row['own_copy'] = dict(path=str(copy.relative_to(ROOT)), sha256=digest(copy),
                                   axes=['direction', 'receiver'], length_unit_m=D.LENGTH, amplitude_scale=1.)
        except Exception:
            row['exception'] = traceback.format_exc()
        row['seconds'] = time.monotonic()-began
        rows.append(row)
        write(out/f'frequency_{f["index"]:03d}.json', row)
        print(case, f['index'], row['passes'], row.get('relative_brg_difference'),
              row.get('relative_refinement_difference'), row.get('exception', ''), flush=True)
        # A refusal on the truth stops this case, never changes its frequency list.
        if 'exception' in row:
            break
    after = provenance()
    result = dict(case=case, passes=len(rows)==37 and all(r['passes'] for r in rows),
                   checked=len(rows), planned=37, profile=profile, truth=truth_record,
                   thresholds=dict(brg=.01, refinement=1e-6, series_loss=1e-9),
                   failed_frequencies=[r['index'] for r in rows if not r['passes']],
                   maximum_brg_difference=max((r['relative_brg_difference'] for r in rows if 'relative_brg_difference' in r), default=None),
                   maximum_refinement_difference=max((r['relative_refinement_difference'] for r in rows if 'relative_refinement_difference' in r), default=None),
                   seconds=time.monotonic()-start, start=before, end=after,
                   solver_unchanged=before['solver_hashes']==after['solver_hashes'],
                   host_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                   gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                   gpu_peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                   torch_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads())
    result['passes'] &= result['solver_unchanged'] and not before['solver_dirty'] and not after['solver_dirty']
    write(out/'qualification.json', result)


def run_checks():
    # A run may check available cases while baseline-side data are still pending.
    # It never fits and never replaces an existing check.
    pre = prepare()
    report = []
    for row in pre['cases']:
        case = row['case']
        out = BASE/case/'checks'
        if (out/'qualification.json').exists():
            report.append(json.loads((out/'qualification.json').read_text()))
            continue
        if not row['passes']:
            report.append(dict(case=case, passes=False, status='INPUTS_PENDING', checked=0))
            continue
        if out.exists():
            report.append(dict(case=case, passes=False, status='INCOMPLETE_CHECK_REQUIRES_REVIEW', checked=0))
            continue
        try:
            receipt = guarded([sys.executable, __file__, '_check', '--case', case, '--out', str(out)], out)
        except RuntimeError as error:
            print(str(error), flush=True)
            break
        q = out/'qualification.json'
        result = json.loads(q.read_text()) if q.exists() else dict(case=case, passes=False, status='WORKER_FAILURE', checked=0)
        result['supervisor'] = {k: receipt[k] for k in ('seconds', 'stop_reason', 'host_peak_bytes', 'gpu_sampled_peak_bytes')}
        report.append(result)
        print('CASE', case, 'PASS' if result['passes'] else 'BLOCKED', result.get('failed_frequencies'), flush=True)
        report_checks(dict(cases=report))
        commit_owned(f'B1: retain forward checks for {case}')
    recorded = {r['case'] for r in report}
    report.extend(dict(case=r['case'], passes=False, status='CAPACITY_PENDING' if r['passes'] else 'INPUTS_PENDING', checked=0)
                  for r in pre['cases'] if r['case'] not in recorded)
    record = dict(utc=now(), cases=report, planned_cases=20, passes=len(report)==20 and all(r['passes'] for r in report),
                  fits_started=0, review_stop='Report to coordinator; no automatic fit')
    write(BASE/'check_summary.json', record)
    report_checks(record)
    commit_owned('B1: report available data checks and coordinator stop')


def report_checks(record):
    lines = ['# B1 checks, 18 November 2026', '',
             'No BEM fit has started. The coordinator review stop remains active.',
             'CUDA checks use default production/refined profiles and series_loss=1e-9.',
             'Both fitting rows will read only the saved, hash-verified BRG observations.', '',
             '| Case | Checked / 37 | BRG relative maximum | Refinement maximum | Status |',
             '|---|---:|---:|---:|---|']
    for r in record['cases']:
        lines.append(f'| {r["case"]} | {r.get("checked",0)} | {r.get("maximum_brg_difference")} | {r.get("maximum_refinement_difference")} | {"PASS" if r["passes"] else r.get("status", "FAILED CHECK")} |')
    lines += ['', 'Limits: BRG relative difference 0.01 at every frequency; refinement 1e-6.',
              'A failed or missing check blocks the case. No resolution or tolerance changed.', '',
              '[Compact checks and resource receipts](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/check_summary.json).',
              'Each case keeps per-frequency diagnostics and SHA-256 for the local field copies.',
              'Preparation receipts retain all input hashes, unit/layout proofs and default-schedule equality.', '',
              'Pending: complete missing checks, report to coordinator, then await the first-fit go.',
              'No solver, baseline, shared scoring or coordination file was changed.', '']
    (DOC/'results.md').write_text('\n'.join(lines))


def weak_start(physics, initial, observation):
    start = time.monotonic()
    nodes = physics.resolution_profile(initial.band)['production']
    state = forward_solve(initial, observation, 1.001, nodes, context=physics)
    p, d = state.prediction.reshape(-1), observation.scattered.reshape(-1)
    susceptibility = .001*float(np.real(np.vdot(p, d))/np.real(np.vdot(p, p)))
    return max(1.+susceptibility, .05), dict(rule='weak', epsilon=.001, minimum=.05,
                estimated_susceptibility=susceptibility, clipped=1.+susceptibility < .05,
                seconds=time.monotonic()-start, frequency_hz=observation.frequency_hz, nodes=nodes)


def fit_worker(case, row, out):
    from bem_inverse.runner import fit
    from bem_inverse.material import MaterialUnknown
    before = provenance()
    # Recovered row has a neutral placeholder; eta from the case is never its initializer.
    problem, sources = make_problem(case, float(case.split('__c')[1]) if row=='known' else 1.)
    physics = context()
    torch.cuda.reset_peak_memory_stats()
    write(out/'manifest.json', dict(case=case, row=row, start=before, sources=sources,
                policy=B1Policy().plan(problem, physics), modal_settings=asdict(physics.settings),
                length_unit_m=problem.length_unit_m, origin_m=problem.origin_m,
                bounds_m=problem.bounds_m, start_curve=curve_record(problem.initial),
                torch_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads(),
                time_limit='disabled', geometry_update='slider', localization='none', noise_level=None))
    try:
        if row=='recovered':
            contrast, initialization = weak_start(physics, problem.initial, problem.real[0])
            problem = replace(problem, contrast=contrast)
            material = MaterialUnknown()
        else:
            initialization, material = dict(rule='supplied', seconds=0.), None
        write(out/'initialization.json', dict(**initialization, contrast=problem.contrast))
        result = fit(problem, physics=physics, forward_solve=lambda *a: forward_solve(*a, context=physics),
                     policy=B1Policy(), output=out/'local', geometry_update='slider', material=material,
                     on_event=lambda e: print(e['operation']['label'], e['reason'], flush=True))
        result['contrast'] = result.get('final_contrast', problem.contrast)
        write(out/'fit.json', result)
    except Exception:
        write(out/'failure.json', dict(traceback=traceback.format_exc()))
    finally:
        write(out/'worker_end.json', dict(end=provenance(),
                    host_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                    gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    gpu_peak_reserved_bytes=torch.cuda.max_memory_reserved()))


def score_endpoint(case, row, out):
    from types import SimpleNamespace
    from experiments.comparison.scoring import score, PROTOCOL
    from experiments.gaugal_comparison import tg002_data as Dgrid
    result = json.loads((out/'fit.json').read_text()) if (out/'fit.json').exists() else None
    final = result
    if final is None and (out/'local/unscored.json').exists():
        final = json.loads((out/'local/unscored.json').read_text())
    fit_record = dict(representation='curve', final_curve=final.get('final_curve') if final else None,
                      contrast=result.get('contrast') if result else None)
    arrays = {}
    if fit_record['final_curve'] and fit_record['contrast'] is not None:
        curve = curve_from(fit_record['final_curve'])
        arrays['image'] = ((fit_record['contrast']-1.)*Dgrid.fill_fraction(.05*curve.values(4096),
                          *Dgrid.pixel_grid(PROTOCOL['grid_cells']))).astype(np.float32)
    scores = score(SimpleNamespace(key='B1_'+row, noise=None), case, fit_record, arrays, ROOT)
    write(out/'raw_scores.json', scores)
    work = result.get('fit_work') or {} if result else {}
    seconds = result.get('fit_and_localization_seconds') if result else None
    units = work.get('work_units')
    receipt = json.loads((out/'supervisor.json').read_text())
    metric = dict(case=case, row=row, outcome=result.get('outcome') if result else 'WORKER_FAILURE',
                  detail=result.get('detail') if result else 'see failure/worker log',
                  last_stage=result.get('final_stage') if result else None, work_units=units,
                  fit_seconds=seconds, seconds_per_work_unit=seconds/units if seconds is not None and units else None,
                  forecast_40_fit_seconds=40*seconds if seconds is not None else None,
                  area_error=scores['area_error'], contrast=fit_record['contrast'],
                  host_peak_bytes=receipt['host_peak_bytes'], gpu_sampled_peak_bytes=receipt['gpu_sampled_peak_bytes'],
                  over_120_seconds=bool(seconds and seconds>120), over_1_hour=bool(seconds and seconds>3600),
                  reportable=receipt['reportable'], scoring_sha256=digest(ROOT/'experiments/comparison/scoring.py'))
    if (out/'worker_end.json').exists():
        peaks = json.loads((out/'worker_end.json').read_text())
        metric['host_peak_bytes'] = max(metric['host_peak_bytes'], peaks['host_peak_bytes'])
        metric.update({k: peaks[k] for k in ('gpu_peak_allocated_bytes', 'gpu_peak_reserved_bytes')})
    write(out/'metrics.json', metric)
    return metric


def commit_owned(message):
    paths = [str(p.relative_to(ROOT)) for p in sorted((ROOT/'experiments/bem_on_baseline_data').glob('b1_*.py'))]
    paths += [str(DOC.relative_to(ROOT)), str(BASE.relative_to(ROOT))]
    subprocess.run(['git', 'add', '--', *paths], cwd=ROOT, check=True)
    size = sum((ROOT/p).stat().st_size for p in subprocess.check_output(
        ['git', 'diff', '--cached', '--name-only', '--', *paths], cwd=ROOT, text=True).splitlines() if (ROOT/p).is_file())
    if size > 5*1024**2:
        raise RuntimeError(f'Owned compact commit exceeds 5 MiB: {size} bytes')
    subprocess.run(['git', 'commit', '-m', message, '--', *paths], cwd=ROOT, check=True)
    subprocess.run(['git', 'push'], cwd=ROOT, check=True)
    subprocess.run(['git', 'status', '--short'], cwd=ROOT, check=True)


def fit_case(case, row):
    summary = json.loads((BASE/'check_summary.json').read_text())
    assert len(summary['cases'])==20 and all(r.get('checked')==37 for r in summary['cases']), 'All 20 checks must be reported first.'
    qualification = json.loads((BASE/case/'checks/qualification.json').read_text())
    assert qualification['passes'], 'Failed case is blocked; report to coordinator.'
    assert not bem_jobs(), 'Another BEM command is running; preserve capacity.'
    if row=='recovered':
        assert all(list((BASE/c/'known').glob('attempt_*/metrics.json')) for c in D.CASES), 'Known-contrast row must finish first.'
    base = BASE/case/row
    earlier = sorted(base.glob('attempt_*'))
    for old in earlier:
        receipt = json.loads((old/'supervisor.json').read_text())
        assert receipt['stop_reason']=='MEMORY_REQUEUE', 'No tuning rerun; prior fit stays final.'
    out = base/f'attempt_{len(earlier)+1:02d}'
    expected = max([3*GIB]+[json.loads(p.read_text())['host_peak_bytes'] for p in BASE.glob('*/*/attempt_*/supervisor.json')])
    receipt = guarded([sys.executable, __file__, '_fit', '--case', case, '--row', row, '--out', str(out)], out, expected)
    if receipt['stop_reason']=='MEMORY_REQUEUE':
        write(out/'requeue.json', dict(case=case, row=row, reason='Memory stop is not a result; retry when capacity allows.'))
    else:
        try:
            metrics = score_endpoint(case, row, out)
            print(json.dumps(metrics), flush=True)
            with (DOC/'results.md').open('a') as report:
                report.write(f'\n## {now()}: {row}, {case}\n\n')
                report.write(f'Outcome {metrics["outcome"]}; work {metrics["work_units"]}; fit {metrics["fit_seconds"]} s; area error {metrics["area_error"]}.\n')
                report.write(f'Raw metrics: `{out.relative_to(ROOT)}/metrics.json`.\n')
        except Exception:
            write(out/'scoring_failure.json', dict(traceback=traceback.format_exc()))
    write(out/'bulk_manifest.json', dict(files=bulk(out)))
    commit_owned(f'B1: retain {row} fit {case} and resource records')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('prepare', 'checks', '_check', 'fit', '_fit'))
    parser.add_argument('--case', choices=D.CASES)
    parser.add_argument('--row', choices=('known', 'recovered'))
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.action=='prepare':
        prepare()
    elif args.action=='checks':
        run_checks()
    elif args.action=='_check':
        check_worker(args.case, args.out)
    elif args.action=='_fit':
        fit_worker(args.case, args.row, args.out)
    else:
        assert args.case and args.row
        fit_case(args.case, args.row)


if __name__=='__main__':
    main()
