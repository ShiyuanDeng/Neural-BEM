"""The 36-case regression boundary. Only this module reads targets/history.

Preparation freezes data and code; augmentation is explicit and separately
sealed. Fitting receives a Problem, never this descriptor or its truth path.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
import csv
import hashlib
import multiprocessing
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from time import perf_counter
import traceback
import numpy as np

from experiments.shape_continuation.forward import PointSourceAcquisition
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.geometry_runtime import geometry_runtime, geometry_validated
from experiments.shape_continuation.metrics import boundary_distance
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from .io import read, write, digest, curve_from, portable
from .problem import Observation, Problem
from .physics import Execution, make_backend
from .policy import CumulativePolicy
from .runner import fit

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'results/validation/shape_continuation'
SOURCE_MANIFEST = BASE/'SC-051-frequency-only/manifest.json'
DEFAULT_OUTPUT = ROOT/'results/validation/cleaned_interfaces/CI-001'
FREQUENCIES = tuple(float(f) for f in np.round(np.arange(.25e9, 2.5e9+1, .125e9)))

# Freeze before running, not after observing errors. These are engineering
# regression gates, not claims of numerical equivalence between algorithms.
COMPARISON = dict(
    geometry_absolute_mm=.02, geometry_relative=.05,
    residual_absolute=1e-6, residual_relative=.05,
    recovery=dict(rms_mm=1., hausdorff_upper_mm=2., residual=.003, noise_multiple=3.),
    same_backend=dict(prediction_relative=1e-10, jacobian_relative=1e-8,
        accepted_curve_absolute=1e-9, loss_relative=1e-7, loss_absolute=1e-14,
        decisions_equal=True, work_equal=True),
    spd016=dict(prediction_relative=1e-9, jacobian_relative=1e-7, minimum_pair_saving=.20),
    runtime=dict(max_ratio=1.20, repeats=3, statistic='median',
        required_match=['hardware', 'device', 'frequency_threads', 'BLAS threads', 'worker count',
                        'source/input hashes', 'full original-start path', 'comparable host load'],
        archived_runtime_comparable=False),
    status='Frozen proposed numerical gates; all-36 retention and matched runtime remain to be measured')


def environment():
    try:
        from threadpoolctl import threadpool_info
        threadpools=threadpool_info()
    except ImportError:
        threadpools=dict(runtime_introspection='threadpoolctl not installed; configured BLAS environment recorded')
    try:
        import torch
        gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        torch_version=torch.__version__
    except ImportError:
        gpu,torch_version=None,None
    return dict(python=sys.version, platform=platform.platform(), machine=platform.node(),
        gpu=gpu,torch=torch_version, numpy=np.__version__, threadpools=threadpools,
        blas_threads={k: os.getenv(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
        inherited_sc={k: os.getenv(k) for k in ('SC_FORWARD_BACKEND','SC_FREQUENCY_THREADS','SC_GEOMETRY_RUNTIME')},
        load_average=os.getloadavg())


def path_ref(path):
    return str(Path(path).resolve().relative_to(ROOT))


def descriptors():
    rows = [dict(r) for r in read(SOURCE_MANIFEST)['cases'] if r['panel'] in ('core','fresh','far','modal')]
    if len(rows) != 36 or len({r['id'] for r in rows}) != 36:
        raise ValueError('Expected exactly 36 distinct configurations')
    for row in rows:
        tag = 'c'+f'{row["contrast"]:g}'
        folder = ROOT/'results/validation/modal_atlas/MA-004/inputs'/tag/row['case']/'damped_0.25'
        if (folder/'observations.json').exists():
            row.update(damped=path_ref(folder/'observations.json'),
                       damped_qualification=path_ref(folder/'qualification.json'))
        receipt = BASE/'SC-051-frequency-only/references'/f'{row["id"]}__reference.json'
        row['reference_receipt'] = path_ref(receipt)
        row['predecessor_path'] = predecessor_path(row)
    return rows


def predecessor_path(row):
    """Explicit archived path, for evidence only; never chooses a fitting path."""
    paths = []
    if row['panel'] == 'core':
        trajectory = next(t for t in read(BASE/'SC-040-six-scene-pipeline/trajectories.json')['trajectories']
                          if t['case'] == row['case'])
        for step in trajectory['steps']:
            item = dict(source=step['source'], through_iteration=step['iteration'], stage=step['stage'])
            if paths and paths[-1]['source'] == item['source']:
                paths[-1] = item
            else:
                paths.append(item)
        if row['case'] in ('circle_to_star', 'kite'):
            band = 25 if row['case'] == 'circle_to_star' else 22
            paths.append(dict(source=path_ref(BASE/'SC-041-atlas-decisions/runs'/row['case']/f'M{band}/result.json'),
                              cost_scope='additional full segment'))
    elif row['panel'] == 'fresh':
        paths.append(dict(source=path_ref(Path(row['reference']).resolve().parent.parent/'prefix/result.json'),
                          cost_scope='full original-start prefix'))
    elif row['panel'] == 'modal':
        saved = read(ROOT/row['reference'])
        if saved.get('tail', {}).get('parent'):
            paths.append(dict(source=saved['tail']['parent'], cost_scope='D prefix included in DF total; do not add twice'))
    paths.append(dict(source=row['reference'], cost_scope=row['cost_scope']))
    for item in paths:
        p = ROOT/item['source']
        item['sha256'] = digest(p)
    return paths


def acquisition():
    """Frozen SC/MA 24-pair ring, copied bit for bit from the original input builder."""
    angles = np.linspace(0., 2*np.pi, 24, endpoint=False)
    offset = .06/.30
    source = np.column_stack((.5+.30*np.cos(angles), .5+.30*np.sin(angles)))
    receiver = np.column_stack((.5+.30*np.cos(angles+offset), .5+.30*np.sin(angles+offset)))
    return PointSourceAcquisition((source-np.array([.5,.5]))/.05,
                                  (receiver-np.array([.5,.5]))/.05, 1e-6+0j)


def noise_sigma(data, row):
    if 'sigma_real_imag' in data:
        return np.asarray(data['sigma_real_imag'])
    # SC-050 and MA-004 explicitly specify 1% noise for this fixture. This
    # extracts declared measurement metadata, not errors or policy choices.
    if row['case'] == 'noisy_asymmetric':
        clean = np.asarray(data['clean_real'])+1j*np.asarray(data['clean_imag'])
        return .01*np.linalg.norm(clean, axis=0)/np.sqrt(2*len(clean))
    return np.zeros(len(FREQUENCIES))


def observations(data, row, *, damped=False):
    values = np.asarray(data['observed_real'])+1j*np.asarray(data['observed_imag'])
    if values.shape != (24, len(FREQUENCIES)):
        raise ValueError('Unexpected frozen observation shape')
    if 'frequencies_hz' in data and tuple(data['frequencies_hz']) != FREQUENCIES:
        raise ValueError('Frozen frequency catalog changed')
    sigma, scan = noise_sigma(data, row), acquisition()
    waves = [2*np.pi*f*np.sqrt((4*np.pi*1e-7)*8.854187817e-12*6.)*.05 for f in FREQUENCIES]
    if damped:
        waves = [k*(1+.25j) for k in waves]
        if 'wavenumbers_real' in data and not np.allclose(data['wavenumbers_real'], np.real(waves), rtol=1e-13, atol=0):
            raise ValueError('Damped real wavenumbers changed')
        if 'wavenumbers_imag' in data and not np.allclose(data['wavenumbers_imag'], np.imag(waves), rtol=1e-13, atol=0):
            raise ValueError('Damped imaginary wavenumbers changed')
    return tuple(Observation(k, scan, values[:, i], f, float(sigma[i])) for i, (k,f) in enumerate(zip(waves,FREQUENCIES)))


def original_start(row):
    if 'initial' in row:
        return curve_from(read(ROOT/row['initial']))
    return FourierCurve.circle(.065/.05, (complex(.48,.52)-(.5+.5j))/.05)


def fitting_problem(row, output):
    # This function deliberately does not access row['truth'] or any endpoint.
    real = observations(read(ROOT/row['data']), row)
    if 'damped' in row:
        damped_data = read(ROOT/row['damped'])
    else:
        path = Path(output)/'augmented'/row['id']/'observations.json'
        if not path.exists():
            raise ValueError(f'{row["id"]}: missing damped observations; run explicit augment first')
        damped_data = read(path)
    return Problem(original_start(row), real, observations(damped_data, row, damped=True), row['contrast'])


def prepare(output):
    output = Path(output)
    if (output/'manifest.json').exists():
        raise FileExistsError('Campaign already prepared; use verify or a different output directory')
    rows = descriptors()
    original_manifest = read(SOURCE_MANIFEST)
    paths = {SOURCE_MANIFEST}
    for row in rows:
        for key in ('data','initial','truth','clean','qualification','reference','reference_receipt',
                    'damped','damped_qualification'):
            if key in row:
                paths.add(ROOT/row[key])
        paths.update(ROOT/item['source'] for item in row['predecessor_path'])
        for key in ('qualification','damped_qualification'):
            if key in row:
                q = read(ROOT/row[key])
                if not q.get('passed', q.get('qualified', False)):
                    raise ValueError(f'Input qualification failed: {row["id"]}, {key}')
        receipt = read(ROOT/row['reference_receipt'])
        if receipt['sha256'] != digest(ROOT/row['reference']):
            raise ValueError('Historical reference no longer matches its scoring receipt: '+row['id'])
    damped_manifest = read(ROOT/'results/validation/modal_atlas/MA-004/manifest.json')
    expected_inputs = dict(original_manifest['inputs'], **damped_manifest['inputs'])
    for path in paths:
        expected = expected_inputs.get(path_ref(path))
        if expected is not None and digest(path) != expected:
            raise ValueError('Archived input changed: '+str(path))
    # No dependence on result-folder code. Freeze all potential maintained
    # numerical dependencies, plus the exact extracted source snapshots.
    sources = sorted(set(ROOT.glob('experiments/cleaned_interface/*.py')) |
        set(ROOT.glob('experiments/shape_continuation/*.py')) | set(ROOT.glob('solvers/**/*.py')) |
        {ROOT/'experiments/modal_atlas/mie_localize.py'})
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output/'sources.tar.gz', 'w:gz') as archive:
        for p in sources:
            archive.add(p, arcname=path_ref(p), recursive=False)
    write(output/'manifest.json', dict(experiment='CI-001', cases=rows, comparison=COMPARISON,
        policy=asdict(CumulativePolicy()), sources={path_ref(p):digest(p) for p in sources},
        inputs={path_ref(p):digest(p) for p in sorted(paths)}, archive_sha256=digest(output/'sources.tar.gz'),
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        initial_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
        environment=environment(), missing_damped=[r['id'] for r in rows if 'damped' not in r],
        observation_contract='Original real samples/noise draws unchanged. Missing damped samples must be '
            'generated and independently qualified in a separate, explicitly augmented data contract.'))
    write(output/'comparison_contract.json', COMPARISON)
    return dict(cases=len(rows), missing_damped=sum('damped' not in r for r in rows), output=str(output))


def verify(output, *, require_damped=False):
    output = Path(output)
    manifest = read(output/'manifest.json')
    for group in ('sources','inputs'):
        for path, expected in manifest[group].items():
            if digest(ROOT/path) != expected:
                raise RuntimeError('Frozen '+group+' changed: '+path)
    if digest(output/'sources.tar.gz') != manifest['archive_sha256']:
        raise RuntimeError('Source snapshot changed')
    seal = output/'augmentation.json'
    if seal.exists():
        for path, expected in read(seal)['files'].items():
            if digest(output/path) != expected:
                raise RuntimeError('Augmented input changed: '+path)
    if require_damped and manifest['missing_damped']:
        if not seal.exists() or not read(seal)['complete']:
            raise ValueError('All missing damped inputs must be explicitly generated and sealed before fitting')
    return manifest


def augment(output, execution, *, allow_new_damped_data=False, reuse_from=None):
    if not allow_new_damped_data:
        raise ValueError('Augmentation changes the observation contract; pass --allow-new-damped-data explicitly')
    output = Path(output)
    manifest = verify(output)
    if (output/'augmentation.json').exists():
        return read(output/'augmentation.json')
    if reuse_from is not None:
        source=Path(reuse_from)
        other=verify(source,require_damped=True)
        if other['inputs']!=manifest['inputs'] or other['missing_damped']!=manifest['missing_damped']:
            raise ValueError('Augmentation reuse requires identical frozen original inputs')
        seal=read(source/'augmentation.json')
        for relative,expected in seal['files'].items():
            path=Path(relative)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Invalid augmentation path')
            target=output/path
            if target.exists() and digest(target)!=expected:
                raise FileExistsError('Preserve different partial augmentation: '+str(target))
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/path,target)
        result=dict(complete=True,files=seal['files'],cases=manifest['missing_damped'],
                    source_manifest=digest(output/'manifest.json'),copied_from=str(source),
                    copied_seal_sha256=digest(source/'augmentation.json'))
        write(output/'augmentation.json',result)
        return result
    physics = make_backend('nodal_kress', execution)
    for row in manifest['cases']:
        if 'damped' in row:
            continue
        folder = output/'augmented'/row['id']
        if (folder/'qualification.json').exists():
            saved = read(folder/'qualification.json')
            if not saved['passed'] or saved['observations_sha256'] != digest(folder/'observations.json'):
                raise ValueError('Partial augmentation invalid: '+row['id'])
            continue
        real = observations(read(ROOT/row['data']), row)
        template = tuple(replace(o, wavenumber=o.wavenumber*(1+.25j)) for o in real)
        truth = curve_from(read(ROOT/row['truth']))
        started = perf_counter()
        with geometry_runtime(execution.geometry):
            columns = []
            for n in (1024,2048):
                with physics.ordered_calls(lambda o: physics.evaluate(truth,o,row['contrast'],n).prediction, template) as calls:
                    columns.append(np.column_stack([call() for call in calls]))
        a, clean = columns
        relative = np.linalg.norm(a-clean,axis=0)/np.linalg.norm(clean,axis=0)
        passed = bool(np.isfinite(relative).all() and max(relative) <= 1e-8)
        if not passed:
            write(folder/'failed_qualification.json', dict(passed=False, refinement_relative=relative))
            raise ValueError('Damped input refinement failed: '+row['id'])
        original = read(ROOT/row['data'])
        relative_noise = float(original.get('relative_complex_rms', .01 if row['case']=='noisy_asymmetric' else 0.))
        sigma = relative_noise*np.linalg.norm(clean,axis=0)/np.sqrt(2*len(clean))
        seed = int(hashlib.sha256(('CI-001 damped '+row['id']).encode()).hexdigest()[:8],16)
        rng = np.random.default_rng(seed)
        observed = clean+sigma[None,:]*(rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape))
        write(folder/'observations.json', dict(observed_real=observed.real, observed_imag=observed.imag,
            clean_real=clean.real, clean_imag=clean.imag, frequencies_hz=FREQUENCIES,
            wavenumbers_real=[complex(o.wavenumber).real for o in template],
            wavenumbers_imag=[complex(o.wavenumber).imag for o in template],
            gamma=.25, sigma_real_imag=sigma, relative_complex_rms=relative_noise,
            realized_noise_relative=np.linalg.norm(observed-clean,axis=0)/np.linalg.norm(clean,axis=0),
            seed=seed, noise_model='independent complex Gaussian draw; not a transform of real-frequency noise'))
        write(folder/'qualification.json', dict(passed=passed, refinement_relative=relative, nodes=[1024,2048],
            work_units=38, seconds=perf_counter()-started, source_real=row['data'], truth=row['truth'],
            original_real_sha256=digest(ROOT/row['data']), observations_sha256=digest(folder/'observations.json'),
            contract='new synthetic damped observations; original real measurements unchanged', physics=physics.receipt()))
        print('AUGMENTED',row['id'],float(max(relative)),flush=True)
    verify(output)
    files = {str(p.relative_to(output)):digest(p) for p in sorted((output/'augmented').rglob('*.json'))}
    result = dict(complete=True, files=files, cases=manifest['missing_damped'], source_manifest=digest(output/'manifest.json'),
                  environment=environment(), execution=asdict(execution))
    write(output/'augmentation.json',result)
    return result


def score(row, curve):
    target = curve_from(read(ROOT/row['truth']))
    # Preserve the historical polygon-distance and arclength-weighted metric.
    rms = symmetric_rms_distance(curve, target.values(16384), .05)
    distance, bound = boundary_distance(target,curve)
    return dict(rms_mm=1000*rms, hausdorff_mm=50*distance, hausdorff_upper_mm=50*(distance+bound))


def residual_limits(row):
    data = read(ROOT/row['data'])
    if 'realized_noise_relative' in data:
        noise = np.asarray(data['realized_noise_relative'])
    elif 'clean' in row:
        clean = read(ROOT/row['clean'])
        a = np.asarray(data['observed_real'])+1j*np.asarray(data['observed_imag'])
        b = np.asarray(clean['observed_real'])+1j*np.asarray(clean['observed_imag'])
        noise = np.linalg.norm(a-b,axis=0)/np.linalg.norm(b,axis=0)
    else:
        noise = np.zeros(len(FREQUENCIES))
    return np.maximum(.003,3*noise)


def run_case(job):
    output, row, solver, execution, *selection = job
    geometry_update = selection[0] if selection else None
    output = Path(output)
    folder = output/'runs'/row['id']
    if (folder/'result.json').exists():
        result=read(folder/'result.json')
        if result.get('manifest_sha256') != digest(output/'manifest.json'):
            raise ValueError('Existing result belongs to a different campaign: '+row['id'])
        return result
    if folder.exists():
        raise FileExistsError(f'Incomplete run preserved at {folder}; use a fresh campaign for a rerun')
    folder.mkdir(parents=True)
    try:
        problem = fitting_problem(row, output)
        result = fit(problem, solver=solver, execution=execution, output=folder, geometry_update=geometry_update,
            on_event=lambda event: print(row['id'],event['operation']['label'],event['reason'],flush=True))
        # The inverse and its independent audit have returned before target access.
        metrics = score(row,curve_from(result['final_curve']))
        limits = residual_limits(row)
        residual = result.get('relative_residual')
        result.update(case=row, metrics=metrics, residual_limits=limits,
            recovered=bool(result['final_audit_passed'] and metrics['rms_mm']<=1. and
                metrics['hausdorff_upper_mm']<=2. and residual is not None and np.all(residual<=limits)),
            maximum_residual=None if residual is None else float(max(residual)),
            manifest_sha256=digest(output/'manifest.json'))
    except Exception:
        result = dict(case=row, outcome='WORKER_EXCEPTION', recovered=False, traceback=traceback.format_exc(),
                      manifest_sha256=digest(output/'manifest.json'))
    write(folder/'result.json',result)
    print('RESULT',row['id'],result['outcome'],result['recovered'],result.get('metrics'),flush=True)
    return result


def run(output, execution, *, solver='nodal_kress', workers=1, cases=None, geometry_update=None):
    output = Path(output)
    manifest = verify(output,require_damped=True)
    if workers < 1:
        raise ValueError('workers must be positive')
    ids = {r['id'] for r in manifest['cases']}
    if cases and not set(cases)<=ids:
        raise ValueError('Unknown cases: '+str(set(cases)-ids))
    rows = [r for r in manifest['cases'] if cases is None or r['id'] in cases]
    # Preflight every requested input and capability before launching any fit.
    backend = make_backend(solver,execution)
    if geometry_update is not None:
        from .geometry_selection import make_update
        make_update(geometry_update, 1., execution)  # reject unknown selections before any fit
    policy = CumulativePolicy()
    for row in rows:
        problem = fitting_problem(row,output)
        backend.validate(problem)
        policy.operations(problem,backend)
    settings = dict(solver=solver,execution=asdict(execution),workers=workers)
    if geometry_update is not None:
        settings['geometry_update'] = geometry_update
    path = output/'execution.json'
    if path.exists() and read(path)['settings'] != portable(settings):
        raise ValueError('Do not mix execution settings in one campaign; use a new output directory')
    if not path.exists():
        write(path,dict(settings=settings,environment=environment(),manifest_sha256=digest(output/'manifest.json')))
    jobs = [(output,row,solver,execution,geometry_update) for row in rows]
    if workers==1:
        for job in jobs:
            run_case(job)
    else:
        with ProcessPoolExecutor(workers,mp_context=multiprocessing.get_context('spawn')) as pool:
            for future in as_completed([pool.submit(run_case,job) for job in jobs]):
                future.result()
    verify(output,require_damped=True)
    return report(output)


def report(output):
    output=Path(output)
    manifest=verify(output)
    rows=[]
    for case in manifest['cases']:
        ref=read(ROOT/case['reference_receipt'])
        path=output/'runs'/case['id']/'result.json'
        row=dict(id=case['id'],panel=case['panel'],contrast=case['contrast'],
                 reference_recovered=ref['recovered'],reference=case['reference_receipt'],
                 predecessor_path=case['predecessor_path'],historical_cost_scope=case['cost_scope'],
                 historical_full_path_runtime_comparable=False, status='PENDING')
        row['historical_costs']=historical_costs(case)
        if path.exists():
            actual=read(path)
            gates={}
            metrics=actual.get('metrics',{})
            for metric in ('rms_mm','hausdorff_upper_mm'):
                baseline=ref['metrics'][metric]
                limit=baseline+max(COMPARISON['geometry_absolute_mm'],COMPARISON['geometry_relative']*baseline)
                row['reference_'+metric]=baseline
                row[metric]=metrics.get(metric)
                row[metric+'_limit']=limit
                gates[metric]=metrics.get(metric) is not None and metrics[metric]<=limit
            residual=actual.get('relative_residual')
            baseline=np.asarray(ref['relative_residual'])
            limit=baseline+np.maximum(COMPARISON['residual_absolute'],COMPARISON['residual_relative']*baseline)
            gates['per_frequency_residual']=bool(residual is not None and np.all(np.asarray(residual)<=limit))
            gates['recovery']=not ref['recovered'] or actual.get('recovered',False)
            gates['numerical_audit']=bool(actual.get('final_audit_passed',False))
            row.update(status='PASS' if all(gates.values()) else 'REGRESSION', gates=gates,
                recovered=actual.get('recovered',False), outcome=actual['outcome'],
                relative_residual=residual, reference_relative_residual=ref['relative_residual'],
                residual_retention_limits=limit, work_units=actual.get('total_units'),
                fit_units=actual.get('fit_and_localization_units'), total_seconds=actual.get('total_seconds'),
                fit_seconds=actual.get('fit_and_localization_seconds'),
                numerical_audit=actual.get('final_audit_passed',False))
        rows.append(row)
    passed=sum(r['status']=='PASS' for r in rows)
    pending=sum(r['status']=='PENDING' for r in rows)
    summary=dict(cases=36,completed=36-pending,passed=passed,pending=pending,
        regressions=[r['id'] for r in rows if r['status']=='REGRESSION'],
        all_36_numerical_retention=passed==36,
        runtime_retention='NOT_ESTABLISHED: requires repeated matched full-path accelerated baseline timings',
        requirement_1_satisfied=False, rows=rows)
    runtime_path=output/'runtime_comparison.json'
    if runtime_path.exists():
        runtime=read(runtime_path)
        if any(digest(Path(path))!=expected for path,expected in runtime['result_hashes'].items()):
            raise ValueError('Matched-runtime result evidence changed')
        summary['runtime_retention']=bool(runtime['passed'])
        summary['requirement_1_satisfied']=bool(passed==36 and runtime['passed'])
    write(output/'comparison.json',summary)
    fields=['id','panel','contrast','status','reference_recovered','recovered','rms_mm','reference_rms_mm',
            'hausdorff_upper_mm','reference_hausdorff_upper_mm','numerical_audit','outcome',
            'work_units','fit_units','total_seconds','fit_seconds','historical_cost_scope']
    with (output/'comparison.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fields,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    return {k:v for k,v in summary.items() if k!='rows'}


def historical_costs(case):
    """Expose full-path evidence without treating cumulative parents as extra work."""
    saved=read(ROOT/case['reference'])
    components=[]
    for item in case['predecessor_path']:
        data=read(ROOT/item['source'])
        work=data.get('fit_and_localization_units',data.get('work',{}).get('work_units',data.get('total_units')))
        seconds=data.get('fit_and_localization_seconds',data.get('seconds'))
        scope=item.get('cost_scope','through selected archived state')
        if 'through_iteration' in item and 'history' in data:
            states=[h for h in data['history'] if h['iteration']<=item['through_iteration']]
            h=states[-1] if states else {}
            work=h.get('work',{}).get('stage_units')
            seconds=None # ledger elapsed time may include earlier stages
            scope='stage work through selected history; rejected/endpoint work after it excluded'
        components.append(dict(source=item['source'],sha256=item['sha256'],recorded_units=work,
                               recorded_seconds=seconds,scope=scope))
    full_units,full_seconds=None,None
    if case['cost_scope']=='full_fit':
        full_units=saved.get('fit_and_localization_units')
        full_seconds=saved.get('fit_and_localization_seconds')
        tail=saved.get('tail',{})
        if tail.get('frontier_units') and not tail.get('applied'):
            # MA-005 omitted this measured diagnostic from no-tail totals.
            full_units=None if full_units is None else full_units+tail['frontier_units']
            full_seconds=None if full_seconds is None else full_seconds+tail.get('frontier_seconds',0.)
    elif case['panel']=='fresh':
        # Both SC-044 segments report fitting+audit units in total_units.
        full_units=sum(item['recorded_units'] for item in components) if all(
            item['recorded_units'] is not None for item in components) else None
    return dict(outcome=saved.get('outcome',saved.get('status')),components=components,
        full_path_recorded_units=full_units,full_path_recorded_seconds=full_seconds,
        unit_scope='fitting + independent audits' if case['panel']=='fresh' else 'fitting + localization + frontier',
        missing_full_path_cost=full_units is None,
        explanation='Core paths include selected historical states and partial-stage work; no fabricated full-path sum. '
                    'Use a matched original-start rerun for runtime comparisons. Archived durations are not speed gates.')
