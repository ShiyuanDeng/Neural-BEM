"""TG-002 inputs (prepare/generate/verify) and the generic benchmark fit runner.

Inputs live in ``results/validation/cleaned_interfaces/TG-002`` and are sealed
by hash. Fits go to a separate run directory per experiment arm. Fitting
receives a ``Problem`` only; truth is read by scoring after the fit and its
independent audit return. Scoring and recovery gates are CI-001's, reused
unchanged: RMS <= 1 mm, Hausdorff upper bound <= 2 mm, per-frequency residual
<= max(0.003, 3 x noise), and a passed final numerical audit.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import multiprocessing
from pathlib import Path
import subprocess
import tarfile
from time import perf_counter
import traceback

import numpy as np

from bem_inverse.continuation.geometry_runtime import geometry_runtime
from bem_inverse.io import read, write, digest, curve_record, curve_from, portable
from bem_inverse.physics import Execution, make_backend
from bem_inverse.runner import fit
from bem_inverse import pipelines as P
from bem_inverse import policies as R
from experiments.cleaned_interface import benchmark as ci
from . import scenes as S

ROOT = ci.ROOT
INPUTS = ROOT/'results/validation/cleaned_interfaces/TG-002'
QUALIFICATION_NODES, QUALIFICATION_TOLERANCE = (1024, 2048), 1e-8
LOCALIZATION = ('none', 'grid')
MAX_WORKERS = 3  # each fit can peak near 8 GB; 6 workers once OOM-killed this desktop


def sources():
    return sorted({*Path(__file__).resolve().parent.glob('*.py'), S.LOGO,
                   ROOT/'experiments/cleaned_interface/benchmark.py', *ROOT.glob('solvers/bem_inverse/**/*.py')})


def prepare(output=INPUTS):
    output = Path(output)
    if (output/'manifest.json').exists():
        raise FileExistsError('Preserve the existing TG-002 inputs; use another output directory')
    output.mkdir(parents=True, exist_ok=True)
    paths = sources()
    with tarfile.open(output/'sources.tar.gz', 'w:gz') as archive:
        for p in paths:
            archive.add(p, arcname=ci.path_ref(p), recursive=False)
    start = start_path(output)
    start.parent.mkdir(parents=True, exist_ok=False)
    write(start, curve_record(S.start_fixture()))
    for scene in S.SCENES:
        folder = output/'inputs'/scene
        folder.mkdir(parents=True, exist_ok=False)
        write(folder/'truth.json', curve_record(S.truth_fixture(scene)))
    write(output/'manifest.json', dict(
        experiment='TG-002', purpose='the ten-scene benchmark; inputs only',
        scenes={s: dict(shape={k: v for k, v in S.SHAPES[s].items() if k != 'outline'}, placement=S.PLACEMENTS[s])
                for s in S.SCENES},
        start=dict(center_m=[S.START_CENTER_M.real, S.START_CENTER_M.imag], radius_m=S.START_RADIUS_M),
        contrasts=S.CONTRASTS, logo=S.LOGO_PROVENANCE, frequencies_hz=ci.FREQUENCIES, damping_ratio=.25,
        acquisition='CI-001 frozen 24-pair ring', noise='none; observed equals the N2048 prediction',
        qualification=dict(nodes=QUALIFICATION_NODES, max_relative_difference=QUALIFICATION_TOLERANCE),
        sources={ci.path_ref(p): digest(p) for p in paths}, archive_sha256=digest(output/'sources.tar.gz'),
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        initial_status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
        environment=ci.environment(), inputs_sealed=False))
    return dict(prepared=list(S.SCENES), output=str(output))


def start_path(output=INPUTS):
    return Path(output)/'inputs'/'start.json'


def _template(scene, damped):
    # Placeholder values: generation uses only each template's wavenumber and acquisition.
    one = np.ones((24, len(ci.FREQUENCIES)))
    return ci.observations(dict(observed_real=one, observed_imag=0*one), dict(case=scene), damped=damped)


def generate(output=INPUTS, execution=None):
    """Noiseless real and damped catalogs, each qualified by node doubling, CPU reference path."""
    output = Path(output)
    manifest = verify(output)
    execution = execution or Execution(device='cpu', acceleration='reference', frequency_threads=4)
    physics = make_backend('nodal_kress', execution)
    failures = []
    for scene in S.SCENES:
        truth = curve_from(read(output/'inputs'/scene/'truth.json'))
        for contrast in S.CONTRASTS:
            folder = output/'inputs'/scene/S.tag(contrast)
            for damped, name, stem in ((False, 'observations', 'qualification'),
                                       (True, 'damped', 'damped_qualification')):
                if (folder/f'{stem}.json').exists():
                    continue
                folder.mkdir(parents=True, exist_ok=True)
                template = _template(scene, damped)
                started = perf_counter()
                columns = []
                with geometry_runtime(execution.geometry):
                    for n in QUALIFICATION_NODES:
                        with physics.ordered_calls(lambda o: physics.evaluate(truth, o, contrast, n).prediction,
                                                   template) as calls:
                            columns.append(np.column_stack([call() for call in calls]))
                coarse, clean = columns
                relative = np.linalg.norm(coarse-clean, axis=0)/np.linalg.norm(clean, axis=0)
                passed = bool(np.isfinite(relative).all() and max(relative) <= QUALIFICATION_TOLERANCE)
                record = dict(observed_real=clean.real, observed_imag=clean.imag, clean_real=clean.real,
                              clean_imag=clean.imag, frequencies_hz=ci.FREQUENCIES,
                              realized_noise_relative=np.zeros(len(ci.FREQUENCIES)))
                if damped:
                    record.update(wavenumbers_real=[complex(o.wavenumber).real for o in template],
                                  wavenumbers_imag=[complex(o.wavenumber).imag for o in template], gamma=.25,
                                  sigma_real_imag=np.zeros(len(ci.FREQUENCIES)), relative_complex_rms=0.)
                check = dict(passed=passed, contrast=contrast, damped=damped, refinement_relative=relative,
                             nodes=QUALIFICATION_NODES, tolerance=QUALIFICATION_TOLERANCE,
                             seconds=perf_counter()-started, execution=asdict(execution), physics=physics.receipt())
                if passed:
                    write(folder/f'{name}.json', record)
                    check['observations_sha256'] = digest(folder/f'{name}.json')
                    write(folder/f'{stem}.json', check)
                else:
                    write(folder/f'failed_{stem}.json', check)
                    failures.append(dict(scene=scene, contrast=contrast, damped=damped, worst=float(max(relative))))
                print('INPUT', scene, S.tag(contrast), name, passed, f'{max(relative):.2e}',
                      f'{check["seconds"]:.1f}s', flush=True)
    manifest.update(inputs_sealed=not failures, qualification_failures=failures,
                    inputs={str(p.relative_to(output)): digest(p) for p in sorted((output/'inputs').rglob('*.json'))
                            if not p.name.startswith('failed_')})
    write(output/'manifest.json', manifest)
    return dict(sealed=not failures, failures=failures, cases=len(descriptors(output)))


def verify(output=INPUTS, *, require_inputs=False):
    """Enforce the frozen inputs. Source digests are generation provenance, not a lock."""
    output = Path(output)
    manifest = read(output/'manifest.json')
    if not manifest.get('inputs_sealed'):
        for path, expected in manifest['sources'].items():
            if digest(ROOT/path) != expected:
                raise RuntimeError('TG-002 source changed before inputs were sealed: '+path)
    if digest(output/'sources.tar.gz') != manifest['archive_sha256']:
        raise RuntimeError('TG-002 source snapshot changed')
    for path, expected in manifest.get('inputs', {}).items():
        if digest(output/path) != expected:
            raise RuntimeError('TG-002 input changed: '+path)
    if require_inputs and not manifest.get('inputs_sealed'):
        raise ValueError('TG-002 inputs are not generated and sealed')
    return manifest


def descriptors(output=INPUTS):
    """CI-001-shaped rows for every qualified case, in benchmark order."""
    output = Path(output)
    rows = []
    for scene in S.SCENES:
        for contrast in S.CONTRASTS:
            folder = output/'inputs'/scene/S.tag(contrast)
            if not ((folder/'qualification.json').exists() and (folder/'damped_qualification.json').exists()):
                continue
            rows.append(dict(id=S.case_id(contrast, scene), panel='benchmark', case=scene, contrast=contrast,
                data=ci.path_ref(folder/'observations.json'), damped=ci.path_ref(folder/'damped.json'),
                qualification=ci.path_ref(folder/'qualification.json'),
                damped_qualification=ci.path_ref(folder/'damped_qualification.json'),
                initial=ci.path_ref(start_path(output)), truth=ci.path_ref(output/'inputs'/scene/'truth.json')))
    return rows


def row(case, output=INPUTS):
    found = next((r for r in descriptors(output) if r['id'] == case), None)
    if found is None:
        raise ValueError(f'Unknown or unqualified case {case!r}; known: {list(S.CASES)}')
    return found


def keep_start(problem, physics, rule, ledger, progress):
    """Localization replacement: no grid search; the 0.25 GHz warm-up moves the start circle."""
    ledger.reserve(0)
    record = dict(reason='grid localization disabled; prescribed start kept', additional_localization_solves=0,
                  grid_search=False, start=curve_record(problem.initial))
    progress([record])
    return problem.initial, record


def problem(case, output=INPUTS):
    return ci.fitting_problem(row(case, output), output)


def _physics(solver, execution):
    if solver == 'modal_muller':
        from bem_inverse.modal_muller import register
        register()
    return make_backend(solver, execution)


def _fit(problem, settings, execution, folder, adapter, on_event):
    if 'policy' in settings:
        spec = settings['policy']
        return R.fit(problem, spec['recipe']['name'], execution=execution, contract=spec['contract'], output=folder,
                     localization_adapter=adapter, on_event=on_event)
    if 'pipeline' in settings:
        return P.fit(problem, settings['pipeline']['name'], execution=execution, output=folder,
                     localization_adapter=adapter, on_event=on_event)
    return fit(problem, solver=settings['solver'], execution=execution,
               physics=_physics(settings['solver'], execution), output=folder,
               geometry_update=settings['geometry_update'], localization_adapter=adapter, on_event=on_event)


def run_case(job):
    run_dir, case_row, settings = job
    run_dir = Path(run_dir)
    folder = run_dir/'runs'/case_row['id']
    if (folder/'result.json').exists():
        return read(folder/'result.json')
    if folder.exists():
        raise FileExistsError(f'Incomplete run preserved at {folder}; use a fresh run directory')
    folder.mkdir(parents=True)
    execution = Execution(**settings['execution'])
    started = perf_counter()
    try:
        result = _fit(ci.fitting_problem(case_row, run_dir), settings, execution, folder,
            keep_start if settings['localization'] == 'none' else None,
            lambda e: print(case_row['id'], e['operation']['label'], e['reason'], flush=True))
        # ON-001 boundary: case entry to the returned, audited numerical output; scoring excluded.
        result['audited_output_seconds'] = perf_counter()-started
        # The inverse and its independent audit have returned before target access.
        metrics = ci.score(case_row, curve_from(result['final_curve']))
        limits = ci.residual_limits(case_row)
        residual = result.get('relative_residual')
        result.update(case=case_row, settings=settings, metrics=metrics, residual_limits=limits,
            recovered=bool(result['final_audit_passed'] and metrics['rms_mm'] <= 1. and
                           metrics['hausdorff_upper_mm'] <= 2. and residual is not None and np.all(residual <= limits)),
            maximum_residual=None if residual is None else float(max(residual)))
    except Exception:
        result = dict(case=case_row, settings=settings, outcome='WORKER_EXCEPTION', recovered=False,
                      traceback=traceback.format_exc())
    write(folder/'result.json', result)
    print('RESULT', case_row['id'], result['outcome'], result['recovered'], result.get('metrics'), flush=True)
    return result


def settings_for(*, localization, execution, solver=None, geometry_update=None, pipeline=None, policy=None,
                 contract=None):
    """The single setting of one run directory: a policy, a pipeline, or solver plus update."""
    chosen = sum(x is not None for x in (pipeline, policy)) + (solver is not None or geometry_update is not None)
    if chosen > 1:
        raise ValueError('Choose one of a policy, a pipeline, or solver/geometry_update')
    if policy is None and pipeline is None and (solver is None or geometry_update is None):
        raise ValueError('Without a policy or pipeline, pass both solver and geometry_update')
    if localization not in LOCALIZATION:
        raise ValueError(f'localization must be one of {LOCALIZATION}')
    if policy is not None:
        contract = dict(R.BENCHMARK_CONTRACT if contract is None else contract)
        return portable(dict(policy=R.settings(policy, contract), localization=localization,
                             execution=asdict(R.execution_for(policy, execution))))
    if contract is not None:
        raise ValueError('A contract applies to named policies only')
    method = (dict(pipeline=P.get(pipeline).settings()) if pipeline is not None else
              dict(solver=solver, geometry_update=geometry_update))
    return portable(dict(method, localization=localization, execution=asdict(execution)))


def physics_for(settings):
    if 'policy' in settings:
        return P.physics(settings['policy']['recipe']['pipeline'], Execution(**settings['execution']))
    if 'pipeline' in settings:
        return P.physics(settings['pipeline']['name'], Execution(**settings['execution']))
    return _physics(settings['solver'], Execution(**settings['execution']))


def open_run(run_dir, cases, settings, *, output=INPUTS, experiment=None):
    """Create or check ``run_dir``'s manifest; mixed settings or inputs are refused."""
    run_dir = Path(run_dir)
    manifest = run_dir/'manifest.json'
    if not manifest.exists():
        run_dir.mkdir(parents=True, exist_ok=True)
        write(manifest, dict(experiment=experiment, inputs=ci.path_ref(Path(output)/'manifest.json'),
            inputs_sha256=digest(Path(output)/'manifest.json'), settings=settings, cases=list(cases),
            environment=ci.environment(),
            commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)))
    saved = read(manifest)
    if saved['settings'] != settings or saved['inputs_sha256'] != digest(Path(output)/'manifest.json'):
        raise ValueError('Do not mix settings or inputs in one run directory; use a fresh one')
    return saved


def run_fresh(job):
    """``run_case`` in a fresh spawned interpreter: no CUDA, cache or import state is shared."""
    with ProcessPoolExecutor(1, mp_context=multiprocessing.get_context('spawn')) as pool:
        return pool.submit(run_case, job).result()


def run(run_dir, cases, *, localization, execution, solver=None, geometry_update=None, pipeline=None,
        policy=None, contract=None, workers=1, output=INPUTS, experiment=None):
    """Fit ``cases`` into ``run_dir``. One run directory holds exactly one setting.

    Select a named ``policy`` (``bem_inverse.policies``, under the TG-002 contract unless
    ``contract`` is given), a named ``pipeline`` (``bem_inverse.pipelines``), or ``solver``
    plus ``geometry_update`` (the NL-001 form). Policy runs give every case a fresh
    interpreter so that per-case timings are comparable.
    """
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f'workers must be 1..{MAX_WORKERS}')
    settings = settings_for(localization=localization, execution=execution, solver=solver,
                            geometry_update=geometry_update, pipeline=pipeline, policy=policy, contract=contract)
    run_dir = Path(run_dir)
    verify(output, require_inputs=True)
    rows = [row(c, output) for c in cases]
    open_run(run_dir, cases, settings, output=output, experiment=experiment)
    # Preflight every input and capability before the first fit.
    physics = physics_for(settings)
    for r in rows:
        physics.validate(ci.fitting_problem(r, run_dir))
    jobs = [(run_dir, r, settings) for r in rows]
    if workers == 1:
        for job in jobs:
            (run_fresh if policy is not None else run_case)(job)
    else:
        with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('spawn')) as pool:
            for future in as_completed([pool.submit(run_case, job) for job in jobs]):
                future.result()
    return summarize(run_dir)


def _short(detail, limit=240):
    if not detail:
        return None
    lines = [line for line in str(detail).strip().splitlines() if line.strip()]
    return lines[-1][:limit] if lines else None


def summarize(run_dir):
    run_dir = Path(run_dir)
    rows = []
    for path in sorted((run_dir/'runs').glob('*/result.json')):
        r = read(path)
        m = r.get('metrics') or {}
        rows.append(dict(id=r['case']['id'], scene=r['case']['case'], contrast=r['case']['contrast'],
            outcome=r.get('outcome'), recovered=r['recovered'], rms_mm=m.get('rms_mm'),
            hausdorff_upper_mm=m.get('hausdorff_upper_mm'), maximum_residual=r.get('maximum_residual'),
            audit=r.get('final_audit_passed'), units=r.get('total_units'), seconds=r.get('total_seconds'),
            audited_output_seconds=r.get('audited_output_seconds'),
            resolution_promoted=r.get('resolution_promoted'),
            last_stage=(r.get('stages') or [{}])[-1].get('stage'), detail=_short(r.get('detail'))))
    summary = dict(completed=len(rows), recovered=sum(r['recovered'] for r in rows),
                   by_contrast={S.tag(c): sum(r['recovered'] for r in rows if r['contrast'] == c) for c in S.CONTRASTS},
                   rows=rows)
    write(run_dir/'summary.json', summary)
    return {k: v for k, v in summary.items() if k != 'rows'}


def figure(output=INPUTS):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output = Path(output)
    ink, muted, spine, surface, accent, track = '#0b0b0b', '#52514e', '#c9c8c2', '#fcfcfb', '#eda100', '#2a78d6'
    fig, axes = plt.subplots(2, 5, figsize=(16, 7.4), facecolor=surface)
    s = S.START_CENTER_M+S.LENGTH*S.start_fixture().values(512)
    for ax, scene in zip(axes.ravel(), S.SCENES):
        z = S.CENTER+S.LENGTH*curve_from(read(output/'inputs'/scene/'truth.json')).values(2048)
        c = S.centre_m(scene)
        ax.set_facecolor(surface)
        ax.fill(100*z.real, 100*z.imag, color=track, alpha=.22, lw=0)
        ax.plot(100*np.r_[z, z[:1]].real, 100*np.r_[z, z[:1]].imag, color=track, lw=1.6)
        ax.plot(100*np.r_[s, s[:1]].real, 100*np.r_[s, s[:1]].imag, color=muted, lw=1.1, ls='--')
        ax.plot([50, 100*c.real], [50, 100*c.imag], color=accent, lw=1.2)
        ax.plot([50], [50], '+', color=muted, ms=7)
        ax.plot([100*c.real], [100*c.imag], 'o', color=accent, ms=3.5)
        ax.set_xlim(40, 60)
        ax.set_ylim(40, 60)
        ax.set_aspect('equal')
        ax.tick_params(colors=muted, labelsize=7)
        for side in ax.spines.values():
            side.set_color(spine)
        p = S.PLACEMENTS[scene]
        ax.set_title(scene.replace('_', ' '), color=ink, fontweight='bold', fontsize=11, loc='left', pad=16)
        ax.text(0, 1.01, f'offset {p["offset_mm"]} mm at {p["direction_deg"]}°, K={S.SHAPES[scene]["band"]}',
                transform=ax.transAxes, color=muted, fontsize=7.5, va='bottom')
    fig.text(.01, .01, 'TG-002 benchmark: truths (filled), the single 65 mm start circle at the scene centre (dashed), '
             'centroid offset (amber). Axes in cm. Truth files only; no new solves.', color=muted, fontsize=8)
    fig.tight_layout(rect=(0, .03, 1, 1))
    fig.savefig(output/'gallery.png', dpi=150, facecolor=surface)
    return str(output/'gallery.png')
