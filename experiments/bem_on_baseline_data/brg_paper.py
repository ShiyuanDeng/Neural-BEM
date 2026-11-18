"""Owned BRG paper-data checks and BEM runs; baseline/solver paths are read-only."""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'solvers'), str(ROOT)]
BASE = ROOT / 'results/bem/baseline_data/brg_paper/2026-11-18'
CASES = ('glider_033', 'glider_10', 'star_full', 'star_limited', 'cavity_09', 'cavity_2')
LADDER = (1., 1.25, 1.5, 1.75, 2., 2.5, 3., 3.5, 4., 5., 6., 7., 8., 10., 12., 15.)
GIB = 1024**3
SERIES_LOSS = 1e-6


def write(path, value):
    from bem_inverse.io import write as save
    save(path, value)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def solver_state():
    status = subprocess.check_output(['git', 'status', '--porcelain', '--', 'solvers/bem_inverse'], cwd=ROOT, text=True)
    return dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                solver_dirty=bool(status.strip()), solver_status=status,
                source_hashes={str(p.relative_to(ROOT)): digest(p)
                               for p in sorted((ROOT / 'solvers/bem_inverse').rglob('*.py'))})


def available_memory():
    return 1024 * int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                           if line.startswith('MemAvailable:')))


def bulk_manifest(out):
    return [dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=digest(p))
            for p in sorted([*(out / 'local').rglob('*'), *out.glob('*.npz')]) if p.is_file()]


def guarded(command, out, seconds, expected_peak=GIB, launch_reserve=16*GIB, gpu_monitor=False):
    """Only the child group is stopped; keep shared desktop memory available."""
    available = available_memory()
    if available - expected_peak < launch_reserve:
        raise RuntimeError(f'Memory blocks launch: available={available/GIB:.2f} GiB, expected peak={expected_peak/GIB:.2f} GiB; keep {launch_reserve/GIB:g} GiB.')
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    reason = None
    peak = 0
    minimum_available = available
    gpu_peak = 0
    gpu_observed = False
    last_gpu_sample = -10.
    with out.open('w') as stream:
        child = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        while child.poll() is None:
            memory = available_memory()
            minimum_available = min(minimum_available, memory)
            status = Path(f'/proc/{child.pid}/status')
            try:
                for line in status.read_text().splitlines():
                    if line.startswith(('VmRSS:', 'VmHWM:')):
                        peak = max(peak, int(line.split()[1]) * 1024)
            except FileNotFoundError:
                pass
            if gpu_monitor and time.monotonic()-last_gpu_sample >= 2:
                last_gpu_sample = time.monotonic()
                try:
                    sample = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_gpu_memory',
                              '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=2)
                    for line in sample.stdout.splitlines():
                        pid, used = [v.strip() for v in line.split(',')]
                        if int(pid) == child.pid:
                            gpu_peak = max(gpu_peak, int(used)*1024**2)
                            gpu_observed = True
                    with (out.parent/'gpu_resources.csv').open('a') as resources:
                        resources.write(f'{time.monotonic()-started:.6f},{memory},{peak},{gpu_peak}\n')
                except (ValueError, subprocess.TimeoutExpired):
                    pass
            if memory < 14 * GIB:
                reason = 'memory reserve below 14 GiB'
            elif time.monotonic() - started >= seconds:
                reason = f'wall limit {seconds:g} seconds'
            if reason:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    break
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                break
            time.sleep(.1)
        returncode = child.wait()
    return dict(command=command, pid=child.pid, returncode=returncode, stop_reason=reason,
                wall_seconds=time.monotonic()-started, peak_rss_bytes=peak,
                peak_gpu_bytes=gpu_peak if gpu_observed else None,
                expected_peak_bytes=expected_peak, launch_reserve_bytes=launch_reserve,
                minimum_available_bytes=minimum_available)


def context_for(device, trace_minimum=None):
    from bem_inverse import Execution
    from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings
    settings = dict(table_mode=True, series_loss=SERIES_LOSS)
    if trace_minimum is not None:
        settings['trace_minimum'] = trace_minimum
    return ModalMuller(Execution(device=device, frequency_threads=1), ModalSettings(**settings))


def shape_info(case):
    import numpy as np
    from scipy.special import i0e
    from experiments.baselines.brg.brg_data import true_curve
    from experiments.baselines.brg.run_paper import CASES as CASE_SETTINGS
    shape, eta, limited = CASE_SETTINGS[case]
    curve = true_curve(shape)
    coefficients = curve.coefficients.copy()
    coefficients[curve.band] = 0
    radius = float(np.abs(coefficients).sum())
    loss = float(np.finfo(float).eps * i0e(15*radius) * np.exp(15*radius))
    return dict(case=case, shape=shape, eta=eta, limited=limited, true_curve_band=curve.band,
                wave_radius=radius, k15_radius=15*radius, k15_series_estimate=loss,
                series_loss=SERIES_LOSS, k15_passes_series_limit=loss <= SERIES_LOSS,
                geometry_origin='analytic glider' if shape == 'glider' else 'recovered from the paper figure files')


def qualifies_resolution(row):
    if row.get('relative_refinement_difference', float('inf')) > 1e-6:
        return False
    coarse = row['relative_brg_difference']
    fine = row['relative_refined_brg_difference']
    # The thresholds remain recorded independently. A discrepancy unchanged
    # within the refinement tolerance is retained as a data/geometry mismatch.
    return coarse <= 1e-5 or (fine > 1e-5 and abs(coarse-fine) <= 1e-6)


def forward_worker(case, k, out, trace_minimum=None, _context=None):
    import numpy as np
    from bem_inverse.forward_solvers.modal_muller import forward_solve
    from experiments.baselines.brg.brg_data import observation, true_curve
    start = time.monotonic()
    state = solver_state()
    row = dict(case=case, k=k, trace_minimum=trace_minimum,
               passes=False, started=now(), solver_start=state)
    try:
        info = shape_info(case)
        curve = true_curve(info['shape'])
        obs, path, data_record = observation(case, k)
        context = _context if _context is not None else context_for('cpu', trace_minimum)
        profile = context.resolution_profile(curve.band)
        row.update(source=str(path.relative_to(ROOT)), source_sha256=digest(path),
                   data_record=data_record, data_shape=obs.scattered.shape, profile=profile,
                   wave_radius=info['wave_radius'])
        solve_start = time.monotonic()
        a = forward_solve(curve, obs, info['eta'], profile['production'], context=context)
        row['production_seconds'] = time.monotonic()-solve_start
        solve_start = time.monotonic()
        b = forward_solve(curve, obs, info['eta'], profile['refined'], context=context)
        row['refined_seconds'] = time.monotonic()-solve_start
        difference = a.prediction - obs.scattered
        relative = float(np.linalg.norm(difference)/np.linalg.norm(obs.scattered))
        refined = float(np.linalg.norm(a.prediction-b.prediction)/np.linalg.norm(b.prediction))
        row.update(relative_brg_difference=relative, relative_refinement_difference=refined,
                   relative_refined_brg_difference=float(np.linalg.norm(b.prediction-obs.scattered)/np.linalg.norm(obs.scattered)),
                   max_absolute_difference=float(abs(difference).max()), production=a.diagnostics,
                   refined=b.diagnostics,
                   illumination_relative_errors=np.linalg.norm(difference, axis=1)/np.linalg.norm(obs.scattered, axis=1),
                   receiver_relative_errors=np.linalg.norm(difference, axis=0)/np.linalg.norm(obs.scattered, axis=0),
                   passes=relative <= 1e-5 and refined <= 1e-6)
        np.savez_compressed(out/'local'/f'k_{k:g}.npz', production=a.prediction,
                            refined=b.prediction, observed=obs.scattered)
    except Exception as error:
        row.update(exception=repr(error), traceback=traceback.format_exc())
    row.update(wall_seconds=time.monotonic()-start, peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
               solver_end=solver_state())
    row['solver_changed_during_check'] = row['solver_start']['source_hashes'] != row['solver_end']['source_hashes']
    write(out/f'k_{k:g}.json', row)
    print(json.dumps(dict(case=case, k=k, passes=row['passes'], error=row.get('relative_brg_difference'),
                          exception=row.get('exception'))), flush=True)
    # Reuse true-shape geometry across a case's remaining frequencies. Failed
    # candidates still stop at their first witness; all numerical rows persist.
    if trace_minimum is not None and _context is None and qualifies_resolution(row):
        from scipy.special import i0e
        remaining = LADDER if k == LADDER[0] else reversed(LADDER)
        for other in remaining:
            target = out/f'k_{other:g}.json'
            if target.exists():
                continue
            x = other*info['wave_radius']
            if float(np.finfo(float).eps*i0e(x)*np.exp(x)) > SERIES_LOSS:
                continue
            forward_worker(case, other, out, trace_minimum, _context=context)
            if not qualifies_resolution(json.loads(target.read_text())):
                break
        # Final cavity checks retain the first actual series refusal while
        # reusing the geometry just checked at every admitted frequency.
        if 'final' in out.parts:
            for other in LADDER:
                x = other*info['wave_radius']
                if float(np.finfo(float).eps*i0e(x)*np.exp(x)) > SERIES_LOSS:
                    if not (out/f'k_{other:g}.json').exists():
                        forward_worker(case, other, out, trace_minimum, _context=context)
                    break


def forward_cases(cases):
    campaign_start = time.monotonic()
    BASE.mkdir(parents=True, exist_ok=True)
    radii = [shape_info(case) for case in cases]
    radii_path = BASE/'wave_radii.json'
    if not radii_path.exists():
        write(radii_path, dict(started=now(), solver=solver_state(), cases=radii))
    peak = GIB
    for case in cases:
        out = BASE/case/'forward'
        assert not (out/'qualification.json').exists(), 'Keep first qualification; no overwrite.'
        (out/'local').mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        record = dict(case=case, started=now(), solver_start=solver_state(),
                      ladder=LADDER, passing_prefix=[], attempted=[], thresholds=dict(brg=1e-5, refinement=1e-6),
                      series_loss=SERIES_LOSS, shape=shape_info(case), stop_reason=None, runs=[])
        for k in LADDER:
            remaining = 1800 - (time.monotonic()-started)
            if remaining <= 0:
                record['stop_reason'] = '30-minute forward budget'
                break
            command = [sys.executable, str(Path(__file__).resolve()), '_forward', '--case', case, '--one', str(k)]
            receipt = guarded(command, out/'local'/f'k_{k:g}.log', remaining, expected_peak=peak)
            record['runs'].append(receipt)
            record['attempted'].append(k)
            path = out/f'k_{k:g}.json'
            if not path.exists():
                record['stop_reason'] = receipt['stop_reason'] or f'worker exited {receipt["returncode"]}; see log'
                break
            row = json.loads(path.read_text())
            peak = max(peak, row['peak_rss_bytes'])
            if not row['passes']:
                record['stop_reason'] = row.get('exception', 'BRG/refinement threshold failed')
                break
            record['passing_prefix'].append(k)
            print(f'PASS {case} k={k:g} BRG={row["relative_brg_difference"]:.4g} refine={row["relative_refinement_difference"]:.4g} peak={row["peak_rss_bytes"]/GIB:.3f} GiB', flush=True)
        record.update(cap=max(record['passing_prefix']) if record['passing_prefix'] else None,
                      passes=record['passing_prefix'] == list(LADDER), wall_seconds=time.monotonic()-started,
                      solver_end=solver_state(), bulk_files=bulk_manifest(out))
        write(out/'qualification.json', record)
        print(f'CASE {case} cap={record["cap"]} passes={record["passes"]} reason={record["stop_reason"]}', flush=True)
        if not record['passes']:
            print('STOP: forward qualification failed; report to coordinator before any fit.', flush=True)
            break
    print(f'Forward batch wall seconds: {time.monotonic()-campaign_start:.3f}', flush=True)


def fixed_resolution():
    selection = json.loads((BASE/'resolution_selection/fixed_resolution.json').read_text())
    assert selection['passes'], 'Dataset-wide resolution must be fixed before fits.'
    return selection


def make_problem(case):
    from bem_inverse import FourierCurve, Problem
    from experiments.baselines.brg.brg_data import observation, REFERENCE_LENGTH_M
    observations, sources = [], []
    selection = fixed_resolution()
    for k in selection['cases'][case]['passing_prefix']:
        obs, path, _ = observation(case, k)
        observations.append(obs)
        sources.append(dict(k=k, path=str(path.relative_to(ROOT)), sha256=digest(path)))
    info = shape_info(case)
    problem = Problem(FourierCurve.circle(), tuple(observations), None, info['eta'],
                      length_unit_m=REFERENCE_LENGTH_M, origin_m=0j,
                      bounds_m=((-2., -2.), (2., 2.)), allow_variable_acquisition=True)
    return problem, sources


def make_policy(device):
    import numpy as np
    from dataclasses import dataclass, replace
    from bem_inverse.policy import CumulativePolicy, Operation

    @dataclass(frozen=True)
    class BrgPolicy(CumulativePolicy):
        name: str = 'brg_observed_k_prefix'
        fit_seconds: float = 120. if device == 'cpu' else 3600.

        def operations(self, problem, physics):
            if not problem.real_only or not problem.allow_variable_acquisition:
                raise ValueError('BRG requires variable-acquisition real-only data.')
            operations = []
            for count in range(1, len(problem.real)+1):
                observations = problem.real[:count]
                band = max(1, int(np.floor(3*observations[-1].wavenumber)))
                quota = self.prefix_quotas[count-1] if count <= 4 else 1500
                op = self._fit(problem, physics, f'k_{observations[-1].wavenumber:g}', observations,
                               band, 2*band+2, quota, iterations=22,
                               purpose='Saved BRG frequency prefix; equal frequency weights; compact storage')
                operations.append(replace(op, stage=replace(op.stage, ragged_data=True)))
            operations.append(Operation('frontier', 'observable_frontier',
                'Record normal-mode frontier at highest frequency; no extra fit stages',
                'all ladder stages returned normally', 'save diagnostic and return',
                details=dict(top=self.frontier_top, threshold=self.frontier_threshold)))
            return tuple(operations)

        def tail(self, problem, physics, frontier):
            return ()
    return BrgPolicy()


def score_endpoint(case, out):
    import numpy as np
    from bem_inverse.io import curve_from
    from experiments.baselines.brg.brg_data import true_curve
    from experiments.comparison.scoring import region, region_scores
    result_path = out/'fit.json'
    result = json.loads(result_path.read_text()) if result_path.exists() else None
    if result is None and (out/'local/unscored.json').exists():
        result = json.loads((out/'local/unscored.json').read_text())
    accepted_path = out/'local/accepted.json'
    accepted = json.loads(accepted_path.read_text())['states'] if accepted_path.exists() else []
    if result:
        curve = curve_from(result['final_curve'])
    elif accepted:
        # Read runner's accepted checkpoint; never substitute truth for missing fit output.
        curve = curve_from(accepted[-1]['curve'])
    else:
        write(out/'metrics.json', dict(case=case, outcome='NO_SCORED_ENDPOINT',
              failure='No returned fit or accepted curve; see supervisor and worker log.'))
        return
    truth = true_curve(shape_info(case)['shape'])
    found, _ = region([curve.values(16384)])
    actual, _ = region([truth.values(16384)])
    raw = region_scores(found, actual)
    write(out/'raw_region_scores.json', raw)
    last = accepted[-1] if accepted else {}
    selection = fixed_resolution()
    supervisor_path = out/'supervisor.json'
    supervisor = json.loads(supervisor_path.read_text()) if supervisor_path.exists() else {}
    write(out/'metrics.json', dict(case=case, outcome=result['outcome'] if result else 'SUPERVISOR_STOP',
          detail=result.get('detail') if result else None, known_contrast=True, eta=shape_info(case)['eta'],
          area_error=raw['area_error'], missing_area=raw['missing_area'], excess_area=raw['excess_area'],
          final_active_k=LADDER[last['active_frequency_count']-1] if last else None,
          maximum_active_residual=last.get('maximum_stage_residual'),
          fit_seconds=result.get('fit_and_localization_seconds') if result else None,
          work=result.get('fit_work') if result else None,
          accepted_work_units=last.get('units'),
          supervisor_stop=supervisor.get('stop_reason'), trace_minimum=selection['fixed_K'],
          qualified_cap=selection['cases'][case]['cap'],
          first_forward_refused_k=selection['cases'][case]['first_refused_k'],
          scoring_source_sha256=digest(ROOT/'experiments/comparison/scoring.py')))
    np.savez_compressed(out/'curves.npz', coefficients=curve.coefficients, true_coefficients=truth.coefficients)


def fit_worker(case, device, out):
    from bem_inverse.runner import fit
    from bem_inverse.forward_solvers.modal_muller import forward_solve
    problem, sources = make_problem(case)
    selection = fixed_resolution()
    context = context_for(device, selection['fixed_K'])
    policy = make_policy(device)
    write(out/'manifest.json', dict(case=case, device=device, started=now(), solver_start=solver_state(),
          sources=sources, policy=policy.plan(problem, context), eta=problem.contrast, material='known',
          series_loss=SERIES_LOSS, trace_minimum=selection['fixed_K'],
          qualified_cap=selection['cases'][case]['cap'],
          first_forward_refused_k=selection['cases'][case]['first_refused_k'],
          geometry_update='slider', localization='none', start='unit disk',
          command=sys.argv, other_processes=subprocess.run(['ps', '-eo', 'pid,pcpu,rss,comm'], capture_output=True, text=True).stdout))
    try:
        result = fit(problem, physics=context, forward_solve=lambda *a: forward_solve(*a, context=context),
                     policy=policy, output=out/'local', geometry_update='slider', material=None)
        write(out/'fit.json', result)
    except Exception as error:
        write(out/'failure.json', dict(exception=repr(error), traceback=traceback.format_exc()))
    finally:
        write(out/'worker_end.json', dict(solver_end=solver_state(), ended=now(),
              peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))


def fit_case(case, device, attempt=None):
    selection = fixed_resolution()
    assert selection['cases'][case]['passes'], 'All admitted frequencies must pass before a fit.'
    out = BASE/case/f'{device}_fit'
    if attempt is not None:
        out = out/f'attempt_{attempt:02d}'
    assert not out.exists(), 'Keep first fit, including failures; no tuning reruns.'
    (out/'local').mkdir(parents=True)
    start = solver_state()
    command = [sys.executable, str(Path(__file__).resolve()), '_fit', '--case', case, '--device', device]
    if attempt is not None:
        command.extend(['--out', str(out)])
    # Internal ledger has the scientific cap; supervisor also stops a blocked native call.
    try:
        receipt = guarded(command, out/'local/worker.log', 120. if device == 'cpu' else 3600.,
                          expected_peak=1.5*GIB if device == 'cuda' else selection['expected_fit_peak_bytes'],
                          launch_reserve=14.5*GIB if device == 'cuda' else 16*GIB,
                          gpu_monitor=device == 'cuda')
    except Exception as error:
        receipt = dict(command=command, returncode=None, stop_reason=repr(error), wall_seconds=0.)
    end = solver_state()
    write(out/'supervisor.json', dict(**receipt, started_solver=start, ended_solver=end,
          reportable=device == 'cuda' and not start['solver_dirty'] and not end['solver_dirty']
                     and receipt.get('stop_reason') != 'memory reserve below 14 GiB'
                     and receipt.get('returncode') is not None
                     and start['source_hashes'] == end['source_hashes']))
    try:
        score_endpoint(case, out)
    except Exception as error:
        write(out/'scoring_failure.json', dict(exception=repr(error), traceback=traceback.format_exc()))
    write(out/'bulk_manifest.json', dict(files=bulk_manifest(out)))
    print(json.dumps(dict(case=case, device=device, **receipt)), flush=True)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('forward', 'fit', '_forward', '_fit', 'plan'))
    parser.add_argument('--case', choices=(*CASES, 'all'), required=True)
    parser.add_argument('--one', type=float)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--trace-minimum', type=int)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.action == 'forward':
        return forward_cases(CASES if args.case == 'all' else (args.case,))
    assert args.case != 'all', 'Fits are individually launched after counting idle cores and memory.'
    out = BASE/args.case
    if args.action == '_forward':
        return forward_worker(args.case, args.one, args.out or out/'forward', args.trace_minimum)
    if args.action == '_fit':
        return fit_worker(args.case, args.device, args.out or out/f'{args.device}_fit')
    if args.action == 'fit':
        return fit_case(args.case, args.device)
    problem, _ = make_problem(args.case)
    print(json.dumps(make_policy(args.device).plan(problem, context_for(args.device, fixed_resolution()['fixed_K'])), default=str, indent=2))


if __name__ == '__main__':
    main()
