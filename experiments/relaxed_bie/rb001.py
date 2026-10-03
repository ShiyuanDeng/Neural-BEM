"""RB-001 archived hard-stop replay and bounded numerical-resolution probes."""
import argparse
from dataclasses import asdict, replace
import difflib
import hashlib
from pathlib import Path
import subprocess
import sys
import tarfile
from threading import Lock
from time import perf_counter
import types

import numpy as np

from bem_inverse.continuation import lm_backend as lm
from bem_inverse.continuation.geometry_runtime import geometry_runtime
from bem_inverse.geometry import ProjectedUpdate
from bem_inverse.io import curve_from, curve_record, digest, portable, read, write
from bem_inverse.physics import Execution, NodalKress
from experiments.cleaned_interface import benchmark as b
from experiments.cleaned_interface.fm001 import OUTPUT as CATALOGS, full_problem

ROOT = b.ROOT
ARCHIVE = ROOT/'results/validation/cleaned_interfaces/FM-002'
OUTPUT = ROOT/'results/validation/relaxed_bie/RB-001'
PLAN = ROOT/'docs/iterations/relaxed_bie/iteration_01/03_plan.md'
CASES = (('modal__c13.3__development_c', 'R0', 'fixed_M49'),
         ('modal__c13.3__development_c', 'R1', 'release_M11'),
         ('modal__c13.3__shifted_star', 'R0', 'fixed_M49'),
         ('modal__c13.3__shifted_star', 'R1', 'fixed_M49'))


def verify_archive():
    manifest = read(ARCHIVE/'manifest.json')
    receipt = read(ARCHIVE/'final_verification.json')
    checks = []
    def check(path, expected):
        actual = digest(path)
        if actual != expected:
            raise ValueError('Changed archived artifact: '+str(path))
        checks.append(dict(path=str(path.relative_to(ROOT)), sha256=actual))
    check(ARCHIVE/'manifest.json', receipt['manifest_sha256'])
    check(ARCHIVE/'sources.tar.gz', manifest['source_archive_sha256'])
    with tarfile.open(ARCHIVE/'sources.tar.gz') as archive:
        for name, expected in manifest['sources'].items():
            actual = hashlib.sha256(archive.extractfile(name).read()).hexdigest()
            if actual != expected:
                raise ValueError('Archive member differs from manifest: '+name)
    for name, expected in manifest['inputs'].items():
        check(ROOT/name, expected)
    for name, expected in receipt['artifacts'].items():
        check(ARCHIVE/name, expected)
    for name, key in [('qualification.json', 'qualification_sha256'),
                      ('summary.json', 'summary_sha256'), ('README.md', 'report_sha256')]:
        check(ARCHIVE/name, receipt[key])
    for name, expected in read(ARCHIVE/'reporting_verification.json')['files'].items():
        check(ROOT/name, expected)
    return dict(passed=True, source_members=len(manifest['sources']), artifacts=checks)


def archived_optimizer():
    """Execute exact archived optimizer bytes with hash-identical numerical dependencies."""
    name = 'bem_inverse.continuation._rb001_archived_lm'
    module = types.ModuleType(name)
    module.__package__ = 'bem_inverse.continuation'
    sys.modules[name] = module
    with tarfile.open(ARCHIVE/'sources.tar.gz') as archive:
        source = archive.extractfile('solvers/bem_inverse/continuation/lm_backend.py').read()
    exec(compile(source, 'FM-002/sources.tar.gz:lm_backend.py', 'exec'), module.__dict__)
    return module


class Budget:
    """Count actual dispatch, including concurrent failures, before running physics."""
    def __init__(self, units=4000, seconds=1800):
        self.cap, self.seconds, self.started = units, seconds, perf_counter()
        self.units, self.counts, self.failed = 0, {}, {}
        self.lock = Lock()

    def charge(self, kind):
        with self.lock:
            if perf_counter()-self.started >= self.seconds:
                raise lm.TrialWallLimit('RB-001 Stage-A wall ceiling')
            if self.units >= self.cap:
                raise lm.TrialSolveCap('RB-001 Stage-A dispatch ceiling')
            self.units += 1
            self.counts[kind] = self.counts.get(kind, 0)+1

    def snapshot(self):
        return dict(units=self.units, cap=self.cap, seconds=perf_counter()-self.started,
                    wall_cap=self.seconds, counts=dict(self.counts), failures=dict(self.failed))


class MeteredPhysics(NodalKress):
    def __init__(self, execution, budget):
        super().__init__(execution)
        self.budget = budget
        self.solver_diagnostics = []

    def _dispatch(self, kind, function, *args):
        self.budget.charge(kind)
        try:
            return function(*args)
        except Exception:
            with self.budget.lock:
                self.budget.failed[kind] = self.budget.failed.get(kind, 0)+1
            raise

    def evaluate(self, *args):
        value = self._dispatch('evaluation', super().evaluate, *args)
        with self._lock:
            self.solver_diagnostics.append(dict(value.diagnostics,
                frequency_hz=args[1].frequency_hz,
                curve_sha256=hashlib.sha256(args[0].coefficients.tobytes()).hexdigest()))
        return value

    def derivative(self, *args):
        return self._dispatch('derivative', super().derivative, *args)

    def receipt(self):
        return dict(super().receipt(), solver_diagnostics=list(self.solver_diagnostics))


def inputs(case, arm, label):
    folder = ARCHIVE/'runs'/case/arm
    descriptor = next(row for row in b.descriptors() if row['id']==case)
    problem, limits = full_problem(descriptor, CATALOGS)
    entered = next(r for r in read(folder/'decisions.json')['decisions']
                   if r['operation']['label']==label and r['reason']=='resolved stage entered')
    op = entered['operation']
    fields = lm.FitStage.__dataclass_fields__
    stage = lm.FitStage(**{k:v for k,v in op['stage'].items() if k in fields},
                        observations=problem.real)
    config = lm.BackendConfig(**op['optimizer'])
    entry = next(r for r in read(folder/'accepted.json')['states']
                 if r['stage']==label and r['iteration']==0)
    return problem, stage, config, curve_from(entry['curve']), entered['work'], read(folder/(label+'.json'))


def restore_ledger(module, row):
    ledger = module.Ledger(cap=row['cap'], seconds=1800)
    ledger.units = row['work_units']
    ledger.stage, ledger.stage_quota = row['stage'], row['stage_quota']
    ledger.stage_start = ledger.units-row['stage_units']
    ledger.solves, ledger.reciprocal, ledger.failed = (dict(row[k]) for k in ('solves','reciprocal_batches','failed'))
    ledger.started -= row['seconds']
    return ledger


def evaluation_record(value):
    return dict(curve=curve_record(value.curve), loss=value.loss, relative_l2=value.relative_l2,
                residual=value.residual, prediction=value.prediction)


def replay(module, problem, stage, config, curve, entry_work, physics, folder):
    ledger = restore_ledger(module, entry_work)
    captured = dict(evaluations=[], jacobian=None, gradient=None, base=None, refined=[])
    class ObservedObjective(module.Objective):
        def _predict(self, shape, nodes, category, keep):
            result = super()._predict(shape, nodes, category, keep)
            if result is not None:
                captured['evaluations'].append(dict(evaluation_record(result), nodes=nodes,
                    category=category, system_residuals=[f.diagnostics['system_residual'] for f in result.forwards]))
            return result

        def jacobian(self, evaluation, update, space):
            matrix = super().jacobian(evaluation, update, space)
            captured.update(jacobian=matrix, gradient=matrix.T@evaluation.residual,
                            base=evaluation_record(evaluation))
            return matrix

        def refined(self, shape):
            result = super().refined(shape)
            captured['refined'] = [evaluation_record(v) for v in self.refined_cache.values() if v is not None]
            return result
    with geometry_runtime(physics.execution.geometry):
        result = module.fit_stage(curve, stage, problem.contrast, ProjectedUpdate(problem.length_unit_m),
            config, ledger, physics=physics, objective_factory=ObservedObjective)
    record = dict(stage=stage.label, outcome=result.outcome, stop=result.stop_reason, detail=result.detail,
        accepted_steps=result.accepted_steps, initial_loss=result.initial_loss, final_loss=result.final_loss,
        curve=curve_record(result.curve), history=result.history, trials=result.trials,
        acceptance_checks=result.acceptance_checks, work=result.work, seconds=result.seconds)
    write(folder/'stage.json', record)
    # Store fields and linearization separately, retaining all evaluated shapes in JSON.
    arrays = {f'prediction_{i}': e['prediction'] for i,e in enumerate(captured['evaluations'])}
    arrays.update(jacobian=captured['jacobian'], gradient=captured['gradient'],
                  base_prediction=captured['base']['prediction'], base_residual=captured['base']['residual'])
    np.savez_compressed(folder/'fields.npz', **arrays)
    write(folder/'evaluations.json', [{k:v for k,v in e.items() if k not in ('prediction','residual')}
                                    for e in captured['evaluations']])
    base = captured['base']
    last = record['history'][-1]
    write(folder/'resume_state.json', dict(stage=stage.label, iteration=last['iteration'],
        next_damping=last['next_damping'], work=last['work'], initial_loss=result.initial_loss,
        curve=base['curve'], loss=base['loss'], nodes=stage.nodes, refined_nodes=stage.refined_nodes,
        config=asdict(config), stage_definition=lm.stage_record(stage),
        relative_l2=base['relative_l2'], history=record['history'], trials=record['trials'],
        acceptance_checks=record['acceptance_checks'],
        scale=max(float(np.linalg.norm(curve.coefficients)*problem.length_unit_m), 1.),
        note='Linearization and base arrays in fields.npz; last accepted state before the failed proposal. '
             'Trial/check lists include the rejected proposal, to be retried separately.'))
    return record, captured


def compare(reference, actual, fields_a=None, fields_b=None):
    """Frozen replay tolerances; time is intentionally not compared."""
    failures, errors = [], {}
    def equal(path, a, z):
        if a != z:
            failures.append(path)
    def numeric(path, a, z, coefficient=False):
        a,z=np.asarray(a),np.asarray(z)
        if a.shape != z.shape:
            failures.append(path+':shape')
            return
        error=float(np.max(np.abs(a-z), initial=0))
        errors[path]=error
        if not np.all(np.abs(a-z) <= (1e-9 if coefficient else 1e-10+1e-8*np.abs(a))):
            failures.append(path)
    for key in ('outcome','stop','detail','accepted_steps'):
        equal(key,reference[key],actual[key])
    for key in ('initial_loss','final_loss'):
        numeric(key,reference[key],actual[key])
    numeric('endpoint_coefficients',curve_from(reference['curve']).coefficients,
            curve_from(actual['curve']).coefficients, True)
    for section in ('history','trials','acceptance_checks'):
        equal(section+':count',len(reference[section]),len(actual[section]))
        for i,(a,z) in enumerate(zip(reference[section],actual[section])):
            for key,v in a.items():
                path=f'{section}.{i}.{key}'
                if key=='work':
                    for k in ('work_units','stage_units','solves','reciprocal_batches','failed'):
                        equal(path+'.'+k,v[k],z[key][k])
                elif key=='coefficients':
                    numeric(path,curve_from(v).coefficients,curve_from(z[key]).coefficients,True)
                elif isinstance(v,(int,float,list)) and not isinstance(v,bool):
                    numeric(path,v,z.get(key))
                else:
                    equal(path,v,z.get(key))
    if fields_a is not None:
        equal('field_evaluation_count',len(fields_a['evaluations']),len(fields_b['evaluations']))
        for i,(a,z) in enumerate(zip(fields_a['evaluations'],fields_b['evaluations'])):
            equal(f'field_{i}:nodes',a['nodes'],z['nodes'])
            equal(f'field_{i}:category',a['category'],z['category'])
            numeric(f'field_{i}',a['prediction'],z['prediction'])
    return dict(passed=not failures,failures=failures,maximum_absolute_errors=errors)


def value_from(row):
    return lm.Evaluation(curve_from(row['curve']),row['loss'],row['relative_l2'],row['residual'],row['prediction'])


def probe_pair(base, candidate, rb, rc, stage, config):
    bd=lm.relative_columns(base.prediction,rb.prediction)
    cd=lm.relative_columns(candidate.prediction,rc.prediction)
    limits=np.asarray(stage.discrepancy_tolerances)
    row=lm.acceptance(base.loss,candidate.loss,rb.loss,rc.loss,config)
    row.update(base_discrepancy=bd,candidate_discrepancy=cd,limits=limits,
               base_threshold_distance=limits-bd,candidate_threshold_distance=limits-cd,
               base_qualified=bool(np.all(np.isfinite(bd)) and np.all(bd<=limits)),
               candidate_qualified=bool(np.all(np.isfinite(cd)) and np.all(cd<=limits)),
               production_base_loss=base.loss,production_candidate_loss=candidate.loss,
               refined_base_loss=rb.loss,refined_candidate_loss=rc.loss,
               nodes=stage.nodes,refined_nodes=stage.refined_nodes)
    row['passed']=bool(row['accepted'] and row['base_qualified'] and row['candidate_qualified'])
    return row


def diagnose(problem, stage, config, captured, record, budget, folder):
    base=value_from(captured['base'])
    candidate=value_from(next(e for e in reversed(captured['evaluations']) if e['category']=='candidate'))
    fine_values={curve_from(e['curve']).coefficients.tobytes():value_from(e) for e in captured['refined']}
    rb,rc=(fine_values[x.curve.coefficients.tobytes()] for x in (base,candidate))
    ledger=lm.Ledger(cap=4000,seconds=1800,endpoint_reserve=0)
    low=MeteredPhysics(Execution(),budget)
    fine=MeteredPhysics(Execution(frequency_threads=1,resolution=1024),budget)
    higher=replace(stage,nodes=1024,refined_nodes=2048,quota=None)
    objective=lm.Objective(higher,problem.contrast,config,ledger,physics=fine)
    # Retained 1024 fields are exactly the new production fields. No new factors
    # are needed for this fixed-candidate diagnostic.
    rrb=objective.refined(base.curve)
    rrc=objective.refined(candidate.curve)
    if rrb is None or rrc is None:
        raise lm.NumericalFailure('Fine-pair diagnostic solve failed')
    coarse=probe_pair(base,candidate,rb,rc,stage,config)
    refinement=probe_pair(rb,rc,rrb,rrc,higher,config)
    write(folder/'refinement.json',dict(original=coarse,finer=refinement,
        reuse='Original N1024 base and candidate fields reused exactly', physics=fine.receipt()))
    np.savez_compressed(folder/'refinement_fields.npz',base_512=base.prediction,candidate_512=candidate.prediction,
        base_1024=rb.prediction,candidate_1024=rc.prediction,base_2048=rrb.prediction,candidate_2048=rrc.prediction)
    objective=lm.Objective(stage,problem.contrast,config,ledger,physics=low)
    objective.refined_cache[base.curve.coefficients.tobytes()]=rb
    update=ProjectedUpdate(problem.length_unit_m)
    space=update.prepare(base.curve,stage.update_modes,stage.curve_modes)
    matrix,gradient=captured['jacobian'],captured['gradient']
    trial=record['trials'][-1]
    normal=matrix.T@matrix
    if config.metric!='marquardt' or config.damping_rule!='schedule':
        raise ValueError('RB-001 requires the frozen Marquardt schedule')
    proposed=np.linalg.solve(normal+trial['damping']*np.diag(np.maximum(np.diag(normal),config.scaling_floor)),-gradient)
    proposed=lm.control_step(proposed,space,update,config)
    reconstructed=update.trial(space,0.5**trial['backtrack']*proposed)[0]
    reconstruction_error=float(np.max(np.abs(reconstructed.coefficients-candidate.curve.coefficients)))
    if reconstruction_error>1e-9:
        raise ValueError('Failed proposal reconstruction differs from the observed replay')
    write(folder/'candidate.json',dict(curve=curve_record(candidate.curve),base=curve_record(base.curve),
        proposal_m=proposed,trial=trial,reconstruction_maximum_coefficient_error=reconstruction_error))
    attempts=[]
    scale=max(float(np.linalg.norm(curve_from(record['history'][0]['coefficients']).coefficients)*problem.length_unit_m),1.)
    for backtrack in range(trial['backtrack']+1,config.max_backtracks+1):
        step=0.5**backtrack*proposed
        attempt=dict(backtrack=backtrack,step_norm_m=float(np.linalg.norm(step)))
        if np.linalg.norm(step)/scale<=config.relative_step_tolerance:
            attempt.update(passed=False,reason='relative_step_tolerance')
        else:
            try:
                shape,geometry=update.trial(space,step)
                attempt.update(curve=curve_record(shape),geometry=geometry)
                if not lm.inside_box(shape,config.domain_box):
                    attempt.update(passed=False,reason='outside_domain')
                else:
                    pc=objective.production(shape,'half_step')
                    fc=objective.refined(shape)
                    if pc is None or fc is None:
                        raise lm.NumericalFailure('Half-step diagnostic solve failed')
                    attempt.update(probe_pair(base,pc,rb,fc,stage,config))
            except lm.UpdateRefused as exc:
                attempt.update(passed=False,reason=exc.reason,detail=exc.detail)
        attempts.append(attempt)
        write(folder/'half_steps.json',dict(attempts=attempts,physics=low.receipt()))
        if attempt['passed']:
            break
    half=any(a['passed'] for a in attempts)
    return dict(refinement_passed=refinement['passed'],half_step_passed=half,
        continuation_gate=bool(refinement['passed'] or half),
        classification='both' if refinement['passed'] and half else 'refinement_only' if refinement['passed'] else
                       'smaller_step_only' if half else 'neither',work=ledger.snapshot(),
        reconstruction_maximum_coefficient_error=reconstruction_error)


def seal(output):
    if output.exists():
        raise FileExistsError('Preserve prior/incomplete RB-001 bundle: '+str(output))
    verification=verify_archive()
    output.mkdir(parents=True)
    write(output/'archive_verification.json',verification)
    sources=sorted(set(ROOT.glob('solvers/**/*.py'))|set(ROOT.glob('experiments/cleaned_interface/*.py'))|
        set(ROOT.glob('experiments/relaxed_bie/*.py'))|set(ROOT.glob('pytest/bem_inverse/*.py'))|{PLAN})
    with tarfile.open(output/'sources.tar.gz','w:gz') as archive:
        for path in sources:
            archive.add(path,arcname=str(path.relative_to(ROOT)),recursive=False)
    original=read(ARCHIVE/'manifest.json')
    differences=[]
    with tarfile.open(ARCHIVE/'sources.tar.gz') as archive:
        for path in sources:
            name=str(path.relative_to(ROOT))
            if name in original['sources'] and digest(path)!=original['sources'][name]:
                before=archive.extractfile(name).read().decode().splitlines(True)
                differences.extend(difflib.unified_diff(before,path.read_text().splitlines(True),
                    fromfile='FM-002/'+name,tofile='RB-001/'+name))
    (output/'source_changes.patch').write_text(''.join(differences))
    manifest=dict(experiment='RB-001',phase='Stage A',cases=CASES,
        sources={str(p.relative_to(ROOT)):digest(p) for p in sources},
        source_archive_sha256=digest(output/'sources.tar.gz'),archive_manifest_sha256=digest(ARCHIVE/'manifest.json'),
        plan_sha256=digest(PLAN),environment=b.environment(),
        branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        gpu=subprocess.check_output(['nvidia-smi'],text=True),
        execution=dict(original=asdict(Execution()),finer=asdict(Execution(frequency_threads=1,resolution=1024))),
        budget=dict(stage_a_units=4000,stage_a_seconds=1800,overall_seconds=10800))
    write(output/'manifest.json',manifest)


def stage_a(output):
    seal(output)
    budget=Budget()
    archived=archived_optimizer()
    results=[]
    for case,arm,label in CASES:
        print('STAGE_A',case,arm,label,flush=True)
        problem,stage,config,curve,entry_work,reference=inputs(case,arm,label)
        folder=output/'stage_a'/case/arm
        physics=MeteredPhysics(Execution(),budget)
        baseline,captured_a=replay(archived,problem,stage,config,curve,entry_work,physics,folder/'archived')
        historical_gate=compare(reference,baseline)
        write(folder/'historical_gate.json',historical_gate)
        actual,captured_b=replay(lm,problem,stage,config,curve,entry_work,physics,folder/'current')
        current_gate=compare(baseline,actual,captured_a,captured_b)
        write(folder/'current_gate.json',current_gate)
        row=dict(case=case,arm=arm,stage=label,replay_passed=historical_gate['passed'] and current_gate['passed'],
                 physics=physics.receipt())
        if row['replay_passed']:
            with geometry_runtime(physics.execution.geometry):
                row.update(diagnose(problem,stage,config,captured_b,actual,budget,folder))
        else:
            row.update(continuation_gate=False,reason='frozen replay gate failed')
        row['budget']=budget.snapshot()
        results.append(row)
        write(folder/'result.json',row)
        write(output/'stage_a.json',dict(completed=len(results),scheduled=4,rows=results,budget=budget.snapshot()))
        print('STAGE_A_RESULT',case,arm,row.get('classification'),row['continuation_gate'],budget.snapshot(),flush=True)
        del captured_a,captured_b
    verify_archive()
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('stage-a','verify-archive'))
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    if args.command=='stage-a':
        stage_a(args.output)
    else:
        print(portable(verify_archive()))


if __name__=='__main__':
    main()
