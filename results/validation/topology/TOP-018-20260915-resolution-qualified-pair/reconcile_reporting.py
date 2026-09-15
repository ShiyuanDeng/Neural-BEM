"""Repair post-schedule annotations from immutable saved metrics; zero solves."""
from copy import deepcopy
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT))
from experiments.top018 import run as n


def main():
    campaign=n.read(HERE/'campaign.json')
    assert campaign['status']!='IN_PROGRESS'
    integrity=n.read(HERE/'source_integrity_before_reporting_repair.json')
    assert integrity['status']=='PASS'
    assert integrity['manifest_sha256']==n.p.digest(HERE/'manifest.json')
    observed,_=n.m.observations(HERE,n.SCENE)
    record=dict(status='REPORTING_RECONCILED',new_physical_solves=0,
        measured_source_revision=n.read(HERE/'manifest.json')['git_revision'],
        source_integrity_record_sha256=n.p.digest(HERE/'source_integrity_before_reporting_repair.json'),
        current_reporting_source_sha256={str(path.relative_to(ROOT)):n.p.digest(path)
            for path in (ROOT/'experiments/top018/run.py',ROOT/'experiments/top018/summarize.py')},
        root_cause='Python list/tuple equality rejected identical frequency values after the numerical schedule completed',
        worker_exits_preserved=campaign['workers'],arms={})
    def forbid(*args,**kwargs):raise AssertionError('reporting reconstruction must not dispatch a physical solve')
    n.p.physical.solve_multicomponent_kress_tmz_total_field_batch=forbid
    n.p.prediction=forbid
    n.m.rt.evaluate_multiradial_objective=forbid
    for arm in ('S','F'):
        folder=HERE/'runs'/f'{arm}-{n.SCENE}'
        original=folder/'metrics_before_reporting_repair.json'
        path=folder/'metrics.json'
        expected=integrity['original_metrics_sha256'][arm]
        if not original.exists():
            assert n.p.digest(path)==expected
            with original.open('xb') as stream:stream.write(path.read_bytes())
        assert n.p.digest(original)==expected
        raw=n.read(original);derived=deepcopy(raw)
        log=HERE/f'{arm}.log'
        assert n.p.digest(log)==integrity['worker_log_sha256'][arm]
        assert 'last measured gradient objective/resolution mismatch' in log.read_text()
        n.bind_objective_records(derived,observed,folder)
        derived.update(source_integrity=True,scene=n.SCENE,reporting_repair=dict(
            original_metrics_sha256=expected,original_metrics=original.name,
            physical_schedule_status_preserved=raw['status'],new_physical_solves=0))
        def scientific(value):
            added={'objective_identity','objective_sha256','source_integrity','scene','reporting_repair'}
            if isinstance(value,dict):return {k:scientific(v) for k,v in value.items() if k not in added}
            if isinstance(value,list):return [scientific(v) for v in value]
            return value
        assert scientific(raw)==scientific(derived),'reporting repair altered an original scientific field'
        n.write(path,derived)
        record['arms'][arm]=dict(original_metrics_sha256=expected,reconciled_metrics_sha256=n.p.digest(path),
            worker_log_sha256=n.p.digest(log),scientific_fields_unchanged=True)
    n.write(HERE/'reporting_repair.json',record)
    print('Post-schedule annotations reconciled; original records and failed-worker logs retained; zero physical solves.')


if __name__=='__main__':main()
