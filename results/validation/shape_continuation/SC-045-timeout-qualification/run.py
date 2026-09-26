"""One independent requalification of five immutable timeout endpoints."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


c=module('sc045_common',HERE.parent/'SC-042-state-strategies/run.py')
n=module('sc045_noise',HERE.parent/'SC-044-noisy-fresh-cases/run.py')
TARGETS=(
    'SC-042-state-strategies/runs/kite/boundary',
    'SC-042-state-strategies/runs/kite/cap',
    'SC-042-state-strategies/runs/circle_to_c/boundary',
    'SC-044-noisy-fresh-cases/runs/asymmetric_lobes/clean/cap',
    'SC-044-noisy-fresh-cases/runs/asymmetric_lobes/noise_seed_0/boundary')


def sources():
    return dict(n.sources(),**{str(p.relative_to(c.sc.ROOT)):c.sc.digest(p) for p in (Path(__file__),HERE/'plan.md')})


def prepare():
    if (HERE/'manifest.json').exists():
        verify()
        return
    c.verify()
    n.verify()
    inputs=dict(c.sc.read(c.HERE/'manifest.json')['inputs'],**c.sc.read(n.HERE/'manifest.json')['inputs'])
    for target in TARGETS:
        folder=HERE.parent/target
        original=c.sc.read(folder/'audit.json')
        assert not original['passed'] and 'TrialWallLimit' in original['traceback']
        for name in ('result.json','audit.json','configuration.json'):
            p=folder/name
            inputs[str(p.relative_to(c.sc.ROOT))]=c.sc.digest(p)
    c.write(HERE/'manifest.json',dict(study='SC-045',targets=TARGETS,sources=sources(),inputs=inputs,
        workers=1,ceiling_per_audit=130,seconds_per_audit=900,prepared=time.strftime('%Y-%m-%dT%H:%M:%S%z')))
    c.write(HERE/'host_pressure.json',dict(captured=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        pressure={kind:Path('/proc/pressure',kind).read_text() for kind in ('cpu','memory','io')},
        note='Captured after the event, while pressure averages were decaying. The plan records the first observed 300-second memory averages.'))


def verify():
    manifest=c.sc.read(HERE/'manifest.json')
    assert manifest['sources']==sources()
    assert all(c.sc.digest(c.sc.ROOT/p)==value for p,value in manifest['inputs'].items())


def terminal(folder):
    return (folder/'result.json').exists() or (folder/'failure.json').exists()


def main():
    if len(sys.argv)>1 and sys.argv[1]=='prepare':
        prepare()
        return
    verify()
    if len(sys.argv)>2 and sys.argv[1]=='audit':
        index=int(sys.argv[2])
        target=TARGETS[index]
        output=HERE/'audits'/f'{index+1}.json'
        assert not output.exists(), 'Each follow-up is attempted once'
        verify()
        source=HERE.parent/target
        original=c.sc.read(source/'result.json')
        last=original['stages'][-1]['stage']
        if target.startswith('SC-042'):
            _,stages,config,_,_=c.stages_for(original['case'],original['arm'])
            stage=next(s for s in stages if s.label==last)
        else:
            stages,configs=n.make_stages(original['case'],original['profile'],original['arm'])
            stage,config=next((s,k) for s,k in zip(stages,configs) if s.label==last)
        print('AUDIT',target,flush=True)
        result=c.audit(c.ast.curve_from(original['curve']),stage,config)
        verify()
        c.write(output,dict(source=target,original_audit_passed=False,**result))
        print('DONE',target,result['passed'],result['work']['work_units'],flush=True)
        return
    print('Waiting for SC-042; independent audits will run serially in fresh processes.',flush=True)
    while not all(terminal(c.HERE/'runs'/case/arm) for case in c.CASES for arm in c.ARMS):
        time.sleep(5)
    for index in range(len(TARGETS)):
        if (HERE/'audits'/f'{index+1}.json').exists():continue
        subprocess.run([sys.executable,'-u',str(Path(__file__).resolve()),'audit',str(index)],check=True)
    rows=[c.sc.read(HERE/'audits'/f'{i+1}.json') for i in range(len(TARGETS))]
    c.write(HERE/'summary.json',dict(rows=rows,complete=True,passed=all(s['passed'] for s in rows),
        additional_units=sum(s['work']['work_units'] for s in rows),original_flags_unchanged=True))


if __name__=='__main__':main()
