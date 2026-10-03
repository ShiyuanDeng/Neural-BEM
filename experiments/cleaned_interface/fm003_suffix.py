"""FM-003 suffix entry without repeating an original-start acceptance gate.

Use this entry point for Phase 2. The sealed fm003 module's generic fit wrapper
would audit the census endpoint as a new original start before stage 3, which
is not an operation in the registered suffix. The historical original-start
qualification is carried as provenance; the ordinary final audit is performed.
"""
from dataclasses import replace
from pathlib import Path
import sys
import tarfile
import traceback

from bem_inverse.io import curve_from, digest, read, write
from bem_inverse.runner import audit, deadline, fit
from . import fm003 as f


class SuffixAudit:
    def __init__(self, original_path):
        self.original_path = Path(original_path)
        self.calls = 0

    def __call__(self, *args):
        self.calls += 1
        if self.calls > 1:
            return audit(*args)
        historical = read(self.original_path)
        if not historical['passed']:
            raise ValueError('Historical CI-001 original-start audit did not pass')
        return dict(passed=True, performed=False,
            scope='Historical original-start qualification; suffix starts directly at stage_3_damped',
            source=f.b.path_ref(self.original_path), source_sha256=digest(self.original_path),
            seconds=0., work=dict(work_units=0, solves={}, reciprocal_batches={}, failed={}))


def continuation(output=f.OUTPUT):
    f.verify(output)
    census = read(output/'phase1/census.json')
    winner = census['winner_index']
    if winner is None:
        raise ValueError('No finite stage-2 endpoint to continue')
    source = output/'phase1/runs'/f'{winner:04d}'/'result.json'
    endpoint = read(source)
    folder = output/'phase2'
    if folder.exists():
        raise FileExistsError('Preserve prior continuation: '+str(folder))
    original_audit = f.b.DEFAULT_OUTPUT/'runs'/f.HIGH/'initial_audit.json'
    source_files = [Path(__file__).resolve(), Path(__file__).with_name('test_fm003_suffix.py').resolve(),
        f.PLAN.parent/'05_suffix_entry.md']
    receipt = dict(parent_implementation_sha256=digest(output/'implementation.json'),
        sources={f.b.path_ref(p):digest(p) for p in source_files},
        inputs={f.b.path_ref(p):digest(p) for p in (source,original_audit,output/'phase1/census.json')},
        correction='Reuse historical original-start qualification; no new gate before stage 3',
        winner_selected_by='lowest stage-2 loss, then lowest start index')
    write(output/'suffix_implementation.json',receipt)
    with tarfile.open(output/'suffix_implementation.tar.gz','w:gz') as archive:
        for path in source_files:
            archive.add(path,arcname=f.b.path_ref(path),recursive=False)
    row = f.descriptor(f.HIGH)
    problem = replace(f.b.fitting_problem(row,f.b.DEFAULT_OUTPUT),initial=curve_from(endpoint['curve']))
    policy = f.ContinuationPolicy(fit_units=13250,fit_seconds=1784.5)
    write(folder/'selection.json',dict(winner_index=winner,stage2_loss=endpoint['final_loss'],
        source_sha256=digest(source),selection='lowest stage-2 loss, then lowest start index',
        removed_prefix_units=162,removed_prefix_seconds=15.5,census_cost=census,
        suffix_implementation_sha256=digest(output/'suffix_implementation.json')))
    try:
        with deadline(900.):
            result = fit(problem,policy=policy,execution=f.EXECUTION,output=folder,
                audit_adapter=SuffixAudit(original_audit),
                on_event=lambda e:print('phase2',e['operation']['label'],e['reason'],flush=True))
        result = f.fm001.scored(row,result,f.b.residual_limits(row))
        result.update(winner_index=winner,census_work_units=census['work_units'],census_seconds=census['seconds'],
            initial_audit_reused_from_prefix=True,continued_endpoint_initial_audit_performed=False,
            total_with_census_and_prefix_units=result['total_units']+162+census['work_units'],
            total_with_census_and_prefix_seconds=result['total_seconds']+15.5+census['seconds'])
    except Exception:
        result = dict(outcome='CONTINUATION_EXCEPTION',recovered=False,winner_index=winner,
                      traceback=traceback.format_exc())
    write(folder/'result.json',result)
    return result


if __name__ == '__main__':
    print(continuation(Path(sys.argv[1]) if len(sys.argv)>1 else f.OUTPUT),flush=True)
