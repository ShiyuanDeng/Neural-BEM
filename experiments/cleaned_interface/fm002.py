"""Corrected relaxed-gradient qualification and fixed damping/relaxation arms."""
import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import subprocess
import sys
import tarfile
from time import perf_counter
import numpy as np

from . import benchmark as b
from .fm001 import OUTPUT as INPUT, full_problem, scored
from .full_matrix import RelaxedStage, RelaxedObjective
from .io import read, write, digest, curve_from
from .physics import Execution, NodalKress
from .policy import CumulativePolicy
from .geometry import ProjectedUpdate
from .runner import fit
from experiments.shape_continuation.lm_backend import Ledger

OUTPUT = b.ROOT/'results/validation/cleaned_interfaces/FM-002'
PLAN = b.ROOT/'docs/iterations/cleaned_interfaces/iteration_19/03_plan.md'
CASES = ('modal__c13.3__development_c', 'modal__c13.3__shifted_star', 'modal__c4__development_c')
ARMS = {'D0': (True, False), 'R0': (False, False), 'D1': (True, True), 'R1': (False, True)}


@dataclass(frozen=True)
class FactorialPrefix(CumulativePolicy):
    name: str = 'fm002_factorial_prefix'
    version: str = '1.0.0'
    damped_prefix: bool = True
    relaxation: bool = False

    def operations(self, problem, physics):
        operations = list(super().operations(problem, physics))
        real = {o.frequency_hz:o for o in problem.real}
        taus = iter((3., 3., 10., 30., 100.))
        for index, op in enumerate(operations):
            if op.kind != 'fit' or not op.label.endswith('_damped'):
                continue
            tau = next(taus)
            obs = op.stage.observations if self.damped_prefix else tuple(real[o.frequency_hz] for o in op.stage.observations)
            config, weights, expected = self._config(problem, obs)
            label = op.label.removesuffix('_damped')+('_damped' if self.damped_prefix else '_real')
            if self.relaxation:
                label += '_relaxed'
            stage = replace(op.stage, observations=obs, weights=weights, label=label)
            if self.relaxation:
                stage = RelaxedStage.from_stage(stage, tau)
            details = dict(op.details, relaxed_tau=tau if self.relaxation else None,
                prefix_damped=self.damped_prefix, expected_noise_loss=expected,
                noise_threshold=config.loss_tolerance if expected else None,
                gradient='complete reduced gradient; frozen-weight curvature' if self.relaxation else 'ordinary',
                localization='same damped paired localization in all arms')
            operations[index] = replace(op, label=label, stage=stage, optimizer=config, details=details)
        return tuple(operations)


def seal(output):
    manifest = output/'manifest.json'
    if manifest.exists():
        return verify(output)
    sources = sorted(set(b.ROOT.glob('solvers/**/*.py')) |
                     set(b.ROOT.glob('experiments/cleaned_interface/*.py')) |
                     set(b.ROOT.glob('experiments/shape_continuation/*.py')) |
                     set(b.ROOT.glob('pytest/bem_inverse/*.py')) | {PLAN})
    inputs = set()
    for case in CASES:
        row = next(r for r in b.descriptors() if r['id']==case)
        inputs.update(b.ROOT/row[k] for k in ('truth','data','initial','clean','damped','reference_receipt') if k in row)
        inputs.update((INPUT/'catalogs'/case/name) for name in ('data.npz','qualification.json'))
        for stage in ('warmup_025_real_relaxed','stage_4_real_relaxed'):
            path = INPUT/'FRr'/'runs'/case/(stage+'.json')
            if path.exists():
                inputs.add(path)
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output/'sources.tar.gz', 'w:gz') as archive:
        for path in sources:
            archive.add(path, arcname=b.path_ref(path), recursive=False)
    record = dict(experiment='FM-002', cases=CASES, arms=ARMS,
        sources={b.path_ref(p):digest(p) for p in sources},
        inputs={b.path_ref(p):digest(p) for p in sorted(inputs)},
        source_archive_sha256=digest(output/'sources.tar.gz'), environment=b.environment(),
        commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
        branch=subprocess.check_output(['git','branch','--show-current'], text=True).strip(),
        execution=Execution().__dict__)
    write(manifest, record)
    return record


def verify(output):
    record = read(output/'manifest.json')
    for group in ('sources','inputs'):
        for name, checksum in record[group].items():
            if digest(b.ROOT/name) != checksum:
                raise ValueError('Changed sealed '+group+': '+name)
    if digest(output/'sources.tar.gz') != record['source_archive_sha256']:
        raise ValueError('Changed source archive')
    return record


def qualify(output):
    verify(output)
    target = output/'qualification.json'
    if target.exists():
        raise FileExistsError('Preserve previous qualification: '+str(target))
    command = [sys.executable,'-m','pytest','pytest/bem_inverse','experiments/cleaned_interface',
        'experiments/shape_continuation','pytest/gpr_bem_kress','pytest/ordered_boundary','-q']
    with (output/'qualification_tests.log').open('w') as log:
        process = subprocess.run(command, cwd=b.ROOT, stdout=log, stderr=subprocess.STDOUT)
    record = dict(test_returncode=process.returncode, test_command=command, probes=[], passed=False)
    write(target, record)
    if process.returncode:
        raise RuntimeError('Regression tests failed; see qualification_tests.log')
    backend = NodalKress(Execution())
    for case in CASES[:2]:
        row = next(r for r in b.descriptors() if r['id']==case)
        problem, _ = full_problem(row, INPUT)
        policy = FactorialPrefix(damped_prefix=False, relaxation=True)
        ops = {op.label:op for op in policy.operations(problem, backend) if op.kind=='fit'}
        for label in ('warmup_025_real_relaxed', 'stage_4_real_relaxed'):
            archived = read(INPUT/'FRr'/'runs'/case/(label+'.json'))
            curve = curve_from(archived['curve'])
            op = ops[label]
            update = ProjectedUpdate(problem.length_unit_m)
            space = update.prepare(curve, op.stage.update_modes, curve.band)
            objective = RelaxedObjective(op.stage, problem.contrast, op.optimizer, Ledger(), physics=backend)
            value = objective.production(curve, 'qualification')
            gradient = objective.gradient(value, update, space)
            old_gradient = objective.jacobian(value, update, space).T@value.residual
            direction = np.random.default_rng(56004).normal(size=len(gradient))
            direction /= np.linalg.norm(direction)
            checks = []
            for step in (1e-6, 1e-7):
                pair = [objective.production(update.trial(space, sign*step*direction)[0], 'qualification_fd').loss for sign in (1,-1)]
                fd = (pair[0]-pair[1])/(2*step)
                error = abs(float(gradient@direction)-fd)
                checks.append(dict(step_m=step, fd=fd, derivative=float(gradient@direction),
                    error=error, passed=bool(error<=2e-5*abs(fd)+1e-7)))
            fine = RelaxedObjective(replace(op.stage,nodes=1024,refined_nodes=2048),
                problem.contrast, op.optimizer, Ledger(), physics=backend)
            finer = fine.production(curve,'qualification_refined')
            refined_gradient = fine.gradient(finer, update, space)
            relative = float(np.linalg.norm(gradient-refined_gradient)/max(np.linalg.norm(refined_gradient),1e-14))
            probe = dict(case=case,stage=label,checks=checks, gradient_refinement_relative=relative,
                gradient_cosine_with_old=float(gradient@old_gradient/np.linalg.norm(gradient)/np.linalg.norm(old_gradient)),
                passed=bool(all(c['passed'] for c in checks) and relative<1e-3))
            record['probes'].append(probe)
            write(target,record)
            print('QUALIFICATION',case,label,probe,flush=True)
    record.update(passed=all(p['passed'] for p in record['probes']), backend=backend.receipt(),
        manifest_sha256=digest(output/'manifest.json'), tests_sha256=digest(output/'qualification_tests.log'))
    write(target, record)
    if not record['passed']:
        raise RuntimeError('Gradient qualification failed')
    verify(output)


def run(output):
    verify(output)
    qualification = read(output/'qualification.json')
    if not qualification['passed'] or qualification['manifest_sha256']!=digest(output/'manifest.json'):
        raise ValueError('Campaign requires qualification under the current seal')
    for case in CASES:
        row = next(r for r in b.descriptors() if r['id']==case)
        problem, limits = full_problem(row, INPUT)
        for arm, (damped, relaxed) in ARMS.items():
            verify(output)
            folder = output/'runs'/case/arm
            if (folder/'result.json').exists():
                if read(folder/'result.json')['manifest_sha256'] != digest(output/'manifest.json'):
                    raise ValueError('Completed run belongs to a different seal: '+str(folder))
                continue
            if folder.exists():
                raise FileExistsError('Preserve incomplete run: '+str(folder))
            policy = FactorialPrefix(damped_prefix=damped, relaxation=relaxed)
            started = perf_counter()
            result = fit(problem, execution=Execution(), policy=policy, output=folder,
                on_event=lambda e:print(case,arm,e['operation']['label'],e['reason'],flush=True))
            result = scored(row,result,limits)
            result.update(arm=arm,elapsed_seconds=perf_counter()-started,
                manifest_sha256=digest(output/'manifest.json'))
            write(folder/'result.json',result)
            report(output)
            print('ARM_RESULT',case,arm,result['outcome'],result['recovered'],result['metrics'],flush=True)
    verify(output)
    write(output/'final_verification.json', dict(passed=True,
        manifest_sha256=digest(output/'manifest.json'),
        qualification_sha256=digest(output/'qualification.json'),
        artifacts={str(p.relative_to(output)):digest(p) for p in sorted((output/'runs').rglob('*.json'))},
        summary_sha256=digest(output/'summary.json'), report_sha256=digest(output/'README.md')))


def report(output):
    rows = []
    for case in CASES:
        for arm in ARMS:
            path = output/'runs'/case/arm/'result.json'
            if not path.exists():
                continue
            d = read(path)
            rows.append(dict(case=case, arm=arm, outcome=d['outcome'],detail=d.get('detail'),
                recovered=d['recovered'],paired_recovered=d['paired_recovered'],metrics=d['metrics'],
                elapsed_seconds=d['elapsed_seconds'],maximum_residual=d['maximum_residual'],
                stages=[{k:s.get(k) for k in ('stage','stop','outcome','accepted_steps','initial_loss','final_loss','seconds','work')} for s in d['stages']]))
    summary = dict(completed=len(rows), scheduled=len(CASES)*len(ARMS), rows=rows,
        recovered={arm:sum(r['recovered'] for r in rows if r['arm']==arm) for arm in ARMS})
    write(output/'summary.json',summary)
    lines = ['# FM-002 corrected relaxed-gradient comparison','',
        'All arms use the same full-matrix catalogs and damped paired localization. D/R changes only early fitting damping; 0/1 changes only relaxation. Final scoring uses ordinary real data.', '',
        '| Case | Arm | Outcome | Full recovery | Paired recovery | RMS mm | Seconds |',
        '|---|---|---|---|---|---:|---:|']
    for r in rows:
        lines.append(f"| {r['case']} | {r['arm']} | {r['outcome']} | {r['recovered']} | {r['paired_recovered']} | {r['metrics']['rms_mm']:.6g} | {r['elapsed_seconds']:.1f} |")
    lines += ['',f"Completed {len(rows)}/{summary['scheduled']}. Numerical stops and budget stops are not evidence of convergence. These are single-run diagnostics, not matched runtime comparisons.",'']
    (output/'README.md').write_text('\n'.join(lines))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('seal','verify','qualify','run','report'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    globals()[args.command](args.output)


if __name__ == '__main__':
    main()
