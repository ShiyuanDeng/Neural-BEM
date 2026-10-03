"""FM-001 reproducible catalogs, fixed arms and external truth scoring.

Run with the archive's EMNerf Python, PYTHONPATH=.:solvers and single-threaded
BLAS. This benchmark owns truth; full_matrix.py and runner.py never read it.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
from pathlib import Path
import subprocess
import tarfile
from time import perf_counter
import traceback
import numpy as np

from . import benchmark as b
from .io import read, write, digest, curve_from
from .physics import Execution, NodalKress
from .policy import CumulativePolicy
from .full_matrix import RealRelaxedPrefix
from .runner import fit
from .qualification import compare
from experiments.shape_continuation.geometry_runtime import geometry_runtime

OUTPUT = b.ROOT/'results/validation/cleaned_interfaces/FM-001'
PLAN = b.ROOT/'docs/iterations/cleaned_interfaces/iteration_18/03_plan.md'
CONTROLS = ('modal__c13.3__development_c', 'modal__c4__development_c')
C_STARTS = ('modal__c13.3__development_c', 'modal__c13.3__opposite_c')


def rows_for(arm):
    rows = b.descriptors()
    high = [next(r for r in rows if r['id']==case) for case in C_STARTS]
    high += [r for r in rows if r['contrast']==13.3 and r['id'] not in C_STARTS]
    modal = [r for r in rows if r['panel']=='modal' and r['contrast']!=13.3]
    return high+modal+([r for r in rows if r['panel']!='modal'] if arm=='F' else [])


def seal(output):
    path = output/'implementation.json'
    if path.exists():
        verify(output)
        return read(path)
    sources = sorted(set(b.ROOT.glob('experiments/cleaned_interface/*.py')) |
        set(b.ROOT.glob('experiments/shape_continuation/*.py')) | set(b.ROOT.glob('solvers/**/*.py')) |
        {b.ROOT/'experiments/modal_atlas/mie_localize.py'})
    inputs = {PLAN}
    for row in b.descriptors():
        inputs.update(b.ROOT/row[k] for k in ('truth','data','initial','clean','damped') if k in row)
        if 'damped' not in row:
            inputs.add(b.DEFAULT_OUTPUT/'augmented'/row['id']/'observations.json')
        for name in ('result.json','accepted.json','checkpoint.json'):
            p = b.DEFAULT_OUTPUT/'runs'/row['id']/name
            if p.exists():
                inputs.add(p)
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output/'implementation.tar.gz', 'w:gz') as tar:
        for p in sources:
            tar.add(p, arcname=b.path_ref(p), recursive=False)
    record = dict(experiment='FM-001', commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        sources={b.path_ref(p):digest(p) for p in sources}, inputs={b.path_ref(p):digest(p) for p in sorted(inputs)},
        archive_sha256=digest(output/'implementation.tar.gz'), plan_sha256=digest(PLAN),
        environment=b.environment(), execution=asdict(Execution()),
        F_order=[r['id'] for r in rows_for('F')], FRr_order=[r['id'] for r in rows_for('FRr')],
        tau=[3,3,10,30,100], recovery=b.COMPARISON['recovery'])
    write(path, record)
    return record


def verify(output):
    receipt = read(output/'implementation.json')
    for group in ('sources','inputs'):
        for path, expected in receipt[group].items():
            if digest(b.ROOT/path) != expected:
                raise ValueError('Sealed '+group+' changed: '+path)
    if digest(output/'implementation.tar.gz') != receipt['archive_sha256']:
        raise ValueError('Implementation archive changed')
    return receipt


def scored(row, result, limits):
    metrics = b.score(row, curve_from(result['final_curve']))
    residual = result.get('relative_residual')
    residual_pass = bool(residual is not None and np.all(np.asarray(residual)<=limits))
    paired_residual = result.get('paired_relative_residual', residual)
    reference = read(b.ROOT/row['reference_receipt'])
    retention = {}
    for metric in ('rms_mm','hausdorff_upper_mm'):
        value = reference['metrics'][metric]
        retention[metric] = bool(metrics[metric]<=value+max(.02,.05*value))
    baseline = np.asarray(reference['relative_residual'])
    retention['per_frequency_residual'] = bool(paired_residual is not None and
        np.all(np.asarray(paired_residual)<=baseline+np.maximum(1e-6,.05*baseline)))
    paired_recovered = bool(result['final_audit_passed'] and metrics['rms_mm']<=1 and
        metrics['hausdorff_upper_mm']<=2 and paired_residual is not None and
        np.all(np.asarray(paired_residual)<=b.residual_limits(row)))
    retention['recovery'] = not reference['recovered'] or paired_recovered
    retention['numerical_audit'] = bool(result['final_audit_passed'])
    return dict(result, case=row['id'], metrics=metrics, residual_limits=limits,
        paired_recovered=paired_recovered, paired_historical_retention=retention,
        paired_historical_pass=all(retention.values()),
        recovery_residual_pass=residual_pass,
        recovered=bool(result['final_audit_passed'] and metrics['rms_mm']<=1 and
                       metrics['hausdorff_upper_mm']<=2 and residual_pass),
        maximum_residual=None if residual is None else float(max(residual)))


def controls(output):
    checks = []
    for case in CONTROLS:
        row = next(r for r in b.descriptors() if r['id']==case)
        folder = output/'phase1'/'controls'/case
        if folder.exists():
            raise FileExistsError('Preserve prior control: '+str(folder))
        result = fit(b.fitting_problem(row, b.DEFAULT_OUTPUT), execution=Execution(), output=folder,
            on_event=lambda e:print(case, e['operation']['label'], e['reason'], flush=True))
        write(folder/'result.json', scored(row, result, b.residual_limits(row)))
        check = compare(folder, b.DEFAULT_OUTPUT/'runs'/case)
        checks.append(dict(case=case, comparison=check))
        write(output/'phase1'/'controls.json', dict(passed=all(x['comparison']['quality_pass'] for x in checks), controls=checks))
        print('CONTROL', case, check, flush=True)
    return checks


def archived_clean(row, catalog, original):
    if catalog=='real':
        record = read(b.ROOT/row['data'])
        if 'clean_real' not in record and 'clean' in row:
            record = read(b.ROOT/row['clean'])
    else:
        record = read(b.ROOT/row['damped']) if 'damped' in row else read(
            b.DEFAULT_OUTPUT/'augmented'/row['id']/'observations.json')
    if 'clean_real' in record:
        return np.asarray(record['clean_real'])+1j*np.asarray(record['clean_imag'])
    if any(o.sigma_real_imag for o in original) and not (catalog=='real' and 'clean' in row):
        raise ValueError('No archived clean signal for noisy diagonal: '+row['id'])
    return np.asarray(record['observed_real'])+1j*np.asarray(record['observed_imag'])


def catalogs(output):
    verify(output)
    backend = NodalKress(Execution())
    reports = []
    for row in rows_for('F'):
        folder = output/'catalogs'/row['id']
        path = folder/'qualification.json'
        if path.exists():
            report = read(path)
            if not report['passed'] or digest(folder/'data.npz') != report['data_sha256']:
                raise ValueError('Preserve failed/changed catalog: '+row['id'])
            reports.append(report)
            continue
        started = perf_counter()
        problem = b.fitting_problem(row, b.DEFAULT_OUTPUT)
        truth = curve_from(read(b.ROOT/row['truth']))
        arrays, qualifications = {}, {}
        for catalog in ('real','damped'):
            original = getattr(problem, catalog)
            scan = replace(original[0].acquisition, paired=False)
            templates = tuple(replace(o, acquisition=scan, scattered=np.ones(scan.data_shape, complex)) for o in original)
            def generate(obs):
                low = backend.evaluate(truth, obs, row['contrast'], 1024).prediction
                high = backend.evaluate(truth, obs, row['contrast'], 2048).prediction
                return low, high
            with geometry_runtime('both'), backend.ordered_calls(generate, templates) as calls:
                generated = [call() for call in calls]
            low, high = [np.stack([pair[j] for pair in generated]) for j in (0,1)]
            refinement = np.linalg.norm((low-high).reshape(len(low),-1),axis=1)/np.linalg.norm(high.reshape(len(high),-1),axis=1)
            clean_diagonal = archived_clean(row, catalog, original).T
            diagonal_relative = np.linalg.norm(np.diagonal(low,axis1=1,axis2=2)-clean_diagonal,axis=1)/np.linalg.norm(clean_diagonal,axis=1)
            seed = int(hashlib.sha256(('FM-001 '+row['id']+' '+catalog).encode()).hexdigest()[:8],16)
            rng = np.random.default_rng(seed)
            noisy = all(o.sigma_real_imag>0 for o in original)
            sigma_full = (.01 if noisy else 0)*np.linalg.norm(low.reshape(len(low),-1),axis=1)/np.sqrt(2*24*24)
            observed = low+sigma_full[:,None,None]*(rng.normal(size=low.shape)+1j*rng.normal(size=low.shape))
            diagonal = np.stack([o.scattered for o in original])
            observed[:,np.arange(24),np.arange(24)] = diagonal
            # Archived diagonal errors have their original declared variance.
            sigma_paired = np.array([o.sigma_real_imag for o in original])
            sigma_effective = np.sqrt((24*sigma_paired**2+(24*24-24)*sigma_full**2)/(24*24))
            # Use the archived clean diagonal for exact observed-noise scoring.
            clean = low.copy()
            clean[:,np.arange(24),np.arange(24)] = clean_diagonal
            noise = np.linalg.norm((observed-clean).reshape(len(low),-1),axis=1)/np.linalg.norm(clean.reshape(len(low),-1),axis=1)
            arrays.update({catalog+'_observed':observed, catalog+'_clean':clean,
                           catalog+'_sigma':sigma_effective, catalog+'_noise_relative':noise})
            qualifications[catalog] = dict(refinement_relative=refinement, clean_diagonal_relative=diagonal_relative,
                observed_diagonal_identical=bool(np.array_equal(np.diagonal(observed,axis1=1,axis2=2), diagonal)),
                passed=bool(max(refinement)<=1e-8 and max(diagonal_relative)<=1e-8),
                seed=seed, independent_offdiagonal_sigma=sigma_full, effective_sigma=sigma_effective,
                realized_noise_relative=noise, noisy=noisy,
                noise_contract='Archived observed diagonal; independent off-diagonal Gaussian draw scaled to 1% full-matrix RMS. Effective scalar sigma preserves total expected noise energy.')
        folder.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(folder/'data.npz', **arrays)
        report = dict(case=row['id'], passed=all(r['passed'] for r in qualifications.values()),
            nodes=[1024,2048], seconds=perf_counter()-started, catalogs=qualifications,
            data_sha256=digest(folder/'data.npz'), implementation_sha256=digest(output/'implementation.json'))
        write(path, report)
        reports.append(report)
        print('CATALOG', row['id'], report['passed'], report['seconds'], flush=True)
        if not report['passed']:
            raise ValueError('Catalog qualification failed: '+row['id'])
    receipt = dict(passed=len(reports)==36 and all(r['passed'] for r in reports), cases=reports,
        files={str(p.relative_to(output)):digest(p) for p in sorted((output/'catalogs').rglob('*')) if p.is_file()})
    write(output/'catalogs.json', receipt)
    return receipt


def full_problem(row, output):
    # Reads observations and the prescribed start, never truth or old endpoints.
    problem = b.fitting_problem(row, b.DEFAULT_OUTPUT)
    folder = output/'catalogs'/row['id']
    receipt = read(folder/'qualification.json')
    if not receipt['passed'] or digest(folder/'data.npz') != receipt['data_sha256']:
        raise ValueError('Unqualified full-matrix data')
    scan = replace(problem.real[0].acquisition, paired=False)
    with np.load(folder/'data.npz') as data:
        catalogs = {name:tuple(replace(o, acquisition=scan, scattered=data[name+'_observed'][i],
                           sigma_real_imag=float(data[name+'_sigma'][i])) for i,o in enumerate(getattr(problem,name)))
                    for name in ('real','damped')}
        limits = np.maximum(.003, 3*data['real_noise_relative'])
    return replace(problem, **catalogs), limits


def run_arm(output, arm):
    verify(output)
    if not read(output/'catalogs.json')['passed'] or not read(output/'phase1'/'controls.json')['passed']:
        raise ValueError('Catalog and paired-compatibility gates must pass')
    phase1 = read(output/'phase1'/'gates.json')
    if not phase1['full_matrix_passed'] or (arm=='FRr' and not phase1['relaxation_passed']):
        raise ValueError('Phase 1 numerical gates not passed for '+arm)
    status = output/arm/'status.json'
    if status.exists() and read(status).get('stopped'):
        return read(status)
    results, lost = [], []
    for row in rows_for(arm):
        folder = output/arm/'runs'/row['id']
        if (folder/'result.json').exists():
            result = read(folder/'result.json')
            if result['implementation_sha256'] != digest(output/'implementation.json'):
                raise ValueError('Different implementation in existing run')
        else:
            if folder.exists():
                raise FileExistsError('Incomplete run preserved: '+str(folder))
            problem, limits = full_problem(row, output)
            try:
                result = fit(problem, execution=Execution(), policy=CumulativePolicy() if arm=='F' else RealRelaxedPrefix(),
                    output=folder, on_event=lambda e:print(arm,row['id'],e['operation']['label'],e['reason'],flush=True))
                result = scored(row, result, limits)
            except Exception:
                result = dict(case=row['id'], outcome='WORKER_EXCEPTION', recovered=False, traceback=traceback.format_exc())
            result.update(implementation_sha256=digest(output/'implementation.json'), arm=arm,
                          catalog_sha256=digest(output/'catalogs'/row['id']/'data.npz'))
            write(folder/'result.json', result)
        results.append(result)
        reference = read(b.DEFAULT_OUTPUT/'runs'/row['id']/'result.json')
        if reference['recovered'] and not result['recovered']:
            lost.append(row['id'])
        receipt = dict(arm=arm, completed=len(results), scheduled=len(rows_for(arm)),
            recovered=sum(r['recovered'] for r in results), lost=lost, stopped=len(lost)>=2,
            reason='second previously recovered case lost' if len(lost)>=2 else 'complete' if len(results)==len(rows_for(arm)) else 'running')
        write(status, receipt)
        print('ARM_RESULT', arm, row['id'], result['outcome'], result['recovered'], result.get('metrics'), flush=True)
        if receipt['stopped']:
            break
    verify(output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('seal','verify','controls','catalogs','arm','paths','report'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--arm', choices=('F','FRr'), default='F')
    parser.add_argument('--fallback', action='store_true')
    args = parser.parse_args()
    if args.command=='arm':
        value = run_arm(args.output, args.arm)
    elif args.command in ('paths','report'):
        from . import fm001_diagnostics
        value = getattr(fm001_diagnostics, args.command)(args.output, **({'fallback':args.fallback} if args.command=='paths' else {}))
    else:
        value = globals()[args.command](args.output)
    print(args.command, 'complete', flush=True)


if __name__=='__main__':
    main()
