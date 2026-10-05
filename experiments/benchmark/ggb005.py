"""GGB-005: the GGB-004 initial circle stage fitted to 0.5 GHz only."""
import argparse
import json
from pathlib import Path

from . import ggb004 as prior

ROOT = prior.ROOT
OUTPUT = ROOT/'results/validation/cleaned_interfaces/GGB-005'
ID = 'GGB-005'
INDICES = (1,)


def sources():
    hashes = prior.sources()
    for path in (Path(__file__),ROOT/'experiments/benchmark/test_ggb005.py'):
        hashes[str(path.relative_to(ROOT))] = prior.common.previous.sha256(path)
    return hashes


def prepare(output):
    """Reuse passed derivative evidence only when its numerical sources match."""
    original = prior.OUTPUT/'qualification.json'
    old = json.loads(original.read_text())
    before = sources()
    data,seal = prior.common.inputs()
    if old['status']!='PASSED' or old['input']!=seal:
        raise ValueError('Prior qualification/input evidence is not qualified.')
    for path,sha in old['source_hashes'].items():
        if path.startswith('solvers/') or path.endswith('ggb002_adapter.py'):
            if before.get(path)!=sha:
                raise ValueError('Numerical source changed: '+path)
    rows = [r for r in old['rows'] if r['frequency_hz']==float(data['frequencies_hz'][1])]
    if len(rows)!=4 or {r['device'] for r in rows}!={'cpu','cuda'}:
        raise ValueError('Missing single-frequency CPU/CUDA derivative evidence.')
    output.mkdir(parents=True,exist_ok=True)
    if (output/'qualification.json').exists():
        raise ValueError('Preserve prior preparation before rerunning.')
    prior.common.write(output/'qualification.json',dict(experiment_id=ID,status='PASSED',
        source_hashes=before,input=seal,qualification_reused_from=str(original.relative_to(ROOT)),
        qualification_sha256=prior.common.previous.sha256(original),rows=rows,
        maximum_relative_column_error=max(e for r in rows for e in r['errors']),
        scope='Unchanged numerical implementation; active-frequency selection changed in the campaign driver.'))
    print('Unchanged numerical sources and single-frequency derivative qualification verified.')


def select_active(audited,indices,weights,config):
    rows = audited['audit']
    if not indices or len(set(indices))!=len(indices) or len(weights)!=len(indices):
        raise ValueError('Unique active indices and matching weights are required.')
    if any(i<0 or i>=len(rows) for i in indices):
        raise ValueError('Active audit index out of range.')
    active = [rows[i] for i in indices]
    for i,row in enumerate(rows):
        row['active_in_fit'] = i in indices
    joint = .5*sum(w*r['relative_residual']**2 for w,r in zip(weights,active))
    audited.update(refined_joint_loss=joint,noise_discrepancy_met=bool(joint<=config.loss_tolerance),
        all_frequency_noise_targets_met=all(r['noise_target_met'] for r in active),
        field_gates_passed=all(r['field_gate_passed'] for r in active))
    return audited


def audit(curve,data,service,weights,config):
    # All five fields are useful held-out evidence; only .5 GHz enters the fit/gates.
    audited,prediction,refined = prior.common.audit(curve,data,service,(.25,)*4,config)
    return select_active(audited,INDICES,weights,config),prediction,refined


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','run','verify'))
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args = parser.parse_args()
    if args.command=='prepare':
        prepare(args.output)
    elif args.command=='run':
        prior.run(args.output,experiment_id=ID,frequency_indices=INDICES,
                  source_manifest=sources,endpoint_audit=audit)
    else:
        prior.verify(args.output,experiment_id=ID,frequency_indices=INDICES)


if __name__=='__main__':
    main()
