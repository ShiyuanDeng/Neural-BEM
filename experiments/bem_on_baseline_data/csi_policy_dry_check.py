"""Dry check of the CSI frequency rule: stage lists without a fit.

Compares the plan for the measured cylinder and for the simulated 1-3 GHz list (early look,
eight-frequency tables) with the plans saved in the manifests of the runs of 18 Nov 2026, and
prints the stage list for the reported five-frequency list. Reads only the tables (no truth),
solves nothing. The only expected difference from the saved plans is ``fit_seconds``: the GPU
pass had a 3600 s ceiling then and has no elapsed-time stop now.
"""
from csi_runtime import ROOT  # noqa: E402  first: pins threads
import argparse
import json

import numpy as np

from bem_inverse import Execution, FourierCurve, Problem
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings

from bem_inverse.problem import Observation

import csi_data as D
import csi_fit as F

SAVED = ROOT/'results/bem/baseline_data/csi_adapter/2026-11-18'
EIGHT = ROOT/D.SIMULATED_EIGHT.format(shape='circle')
RAN = {'dielTM_dec8f, all eight': (SAVED/'first_fit/dielTM_dec8f/cuda/attempt_01/manifest.json', D.MEASURED),
       'simulated 1, 2, 3 GHz (early look)': (SAVED/'end_to_end/circle__c4/cuda/attempt_01/manifest.json', EIGHT)}
EXPECTED_DIFFERENCES = ['fit_seconds']


def placeholder(frequencies_ghz):
    """Unit data on the frozen layout (mask of the eight-frequency circle table): enough for a stage list."""
    mask, _, _ = D.read_table(EIGHT)
    shared = D.acquisition(mask)
    return tuple(Observation(2*np.pi*f*1e9/D.C0*D.LENGTH_M, shared, np.ones(int(mask.sum()), complex), f*1e9)
                 for f in frequencies_ghz)


def plan(path, frequencies_ghz, start_contrast):
    real = placeholder(frequencies_ghz) if path is None else D.observations(path, frequencies_ghz)[0]
    problem = Problem(FourierCurve.circle(F.START_RADIUS_M/D.LENGTH_M), real, None, start_contrast,
                      length_unit_m=D.LENGTH_M, origin_m=0j, bounds_m=F.BOUNDS_M)
    context = ModalMuller(Execution(device='cpu', frequency_threads=1), ModalSettings(table_mode=True))
    policy = F.policy_for(real, 'cuda')
    stages = [dict(label=op.label, M=op.stage.update_modes, storage=op.stage.curve_modes, quota=op.stage.quota,
                   ghz=[o.frequency_hz/1e9 for o in op.stage.observations], ragged=op.stage.ragged_data)
              if getattr(op, 'stage', None) is not None else dict(label=op.label)
              for op in policy.operations(problem, context)]
    return json.loads(json.dumps(policy.plan(problem, context), default=str)), stages


def show(name, stages):
    print(f'\n{name}')
    for s in stages:
        print('  ', s['label'], *(f"M{s['M']} quota {s['quota']} GHz {s['ghz']}",) if 'M' in s else ())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=None, help='optional JSON record')
    args = parser.parse_args()
    record = dict(rule=F.FREQUENCY_RULE, ladder_quotas={str(k): list(v) for k, v in F.LADDER_QUOTAS.items()},
                  compared={}, reported={})
    for name, (manifest_path, path) in RAN.items():
        manifest = json.loads(manifest_path.read_text())
        settings = manifest['settings']
        selection = settings['dataset_settings']['frequencies_ghz'] if 'dataset_settings' in settings else (
            None if 'diel' in name else (1., 2., 3.))
        new, stages = plan(path, selection, settings['start_contrast'])
        differences = sorted(k for k in set(new) | set(settings['policy']) if new.get(k) != settings['policy'].get(k))
        same = differences in ([], EXPECTED_DIFFERENCES)
        record['compared'][name] = dict(manifest=str(manifest_path.relative_to(ROOT)), plan_as_run=same,
                                        differing_keys=differences, expected_differences=EXPECTED_DIFFERENCES,
                                        stages=stages)
        show(f'{name}: plan as run, apart from {EXPECTED_DIFFERENCES} = {same}; differing keys {differences}', stages)
    selected = F.DATASETS['simulated']['frequencies_ghz']
    table = F.case_input('circle__c4')
    source = 'frozen table' if table.exists() else 'placeholder data on the frozen layout (table not made yet)'
    full, stages = plan(table if table.exists() else None, selected, 1.5)
    record['reported'] = dict(frequencies_ghz=list(selected), observations=source, fit_units=full['fit_units'],
                              fit_seconds=full['fit_seconds'], ladder_quota_total=sum(s['quota'] for s in stages
                                                                                     if s['label'].startswith('ladder')),
                              stages=stages)
    show(f'simulated {list(selected)} GHz (reported pass; {source}); fit units {full["fit_units"]}, '
         f'fit seconds {full["fit_seconds"]}', stages)
    if not all(c['plan_as_run'] for c in record['compared'].values()):
        raise SystemExit('A saved plan is not reproduced; see the differing keys.')
    if args.out:
        from pathlib import Path
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(record, indent=1)+'\n')


if __name__ == '__main__':
    main()
