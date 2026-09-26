"""One separately charged recovery of the audit lost to an output-path bug."""
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc046_parent',HERE.parent/'SC-045-timeout-qualification/run.py')
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
c=p.c
TARGET='SC-042-state-strategies/runs/kite/boundary'


def sources():
    return dict(p.sources(),**{str(f.relative_to(c.sc.ROOT)):c.sc.digest(f) for f in (Path(__file__),HERE/'plan.md')})


def verify():
    m=c.sc.read(HERE/'manifest.json')
    assert sources()==m['sources']
    assert all(c.sc.digest(c.sc.ROOT/f)==h for f,h in m['inputs'].items())


def prepare():
    if (HERE/'manifest.json').exists():
        verify()
        return
    p.verify()
    inputs=dict(c.sc.read(p.HERE/'manifest.json')['inputs'])
    failure=p.HERE/'audits/1.json'
    assert c.sc.read(failure)['outcome']=='OUTPUT_WRITE_FAILURE'
    inputs[str(failure.relative_to(c.sc.ROOT))]=c.sc.digest(failure)
    c.write(HERE/'manifest.json',dict(study='SC-046',sources=sources(),inputs=inputs,
        target=TARGET,cap=130,seconds=900,attempts=1))
    # Exercise the same atomic writer in the existing output directory.
    c.write(HERE/'preflight.json',dict(output_parent_exists=HERE.is_dir(),
        parent_verification_passed=True,only_one_recovery_allowed=True))


def main():
    if len(sys.argv)>1 and sys.argv[1]=='prepare':
        prepare()
        return
    verify()
    assert not (HERE/'result.json').exists(), 'Recovery already attempted'
    print('Waiting for the remaining SC-045 audits.',flush=True)
    while not (p.HERE/'summary.json').exists():time.sleep(5)
    verify()
    original=c.sc.read(HERE.parent/TARGET/'result.json')
    _,stages,config,_,_=c.stages_for('kite','boundary')
    stage=next(s for s in stages if s.label==original['stages'][-1]['stage'])
    result=c.audit(c.ast.curve_from(original['curve']),stage,config)
    row=dict(source=TARGET,original_audit_passed=False,previous_followup_outcome='OUTPUT_WRITE_FAILURE',**result)
    print('NUMERICAL_RESULT '+json.dumps(row,default=lambda value:value.tolist()),flush=True)
    c.write(HERE/'result.json',row)
    verify()
    c.write(HERE/'summary.json',dict(complete=True,passed=result['passed'],
        additional_units=result['work']['work_units'],original_flags_unchanged=True))


if __name__=='__main__':main()
