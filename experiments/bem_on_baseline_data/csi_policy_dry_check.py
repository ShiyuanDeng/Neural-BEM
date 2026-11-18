"""Dry check of the CSI frequency rule: stage lists without a fit.

Compares the plan for the measured cylinder and for the simulated 1-3 GHz list with the plans
saved in the manifests of the runs of 18 Nov 2026, and prints the stage lists for other
candidate lists. Reads only the tables (no truth), solves nothing.
"""
from csi_runtime import ROOT  # noqa: E402  first: pins threads
import argparse
import json

from bem_inverse import Execution, FourierCurve, Problem
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings

import csi_data as D
import csi_fit as F

SAVED = ROOT/'results/bem/baseline_data/csi_adapter/2026-11-18'
RAN = {'dielTM_dec8f, all eight': SAVED/'first_fit/dielTM_dec8f/cuda/attempt_01/manifest.json',
       'simulated 1, 2, 3 GHz': SAVED/'end_to_end/circle__c4/cuda/attempt_01/manifest.json'}
CANDIDATES = {'simulated 1-4 GHz': (1., 2., 3., 4.), 'simulated 1-5 GHz': (1., 2., 3., 4., 5.),
              'simulated 1, 2, 3, 5 GHz': (1., 2., 3., 5.)}


def plan(path, frequencies_ghz, start_contrast):
    real, _, _ = D.observations(path, frequencies_ghz)
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
    record = dict(rule=F.FREQUENCY_RULE, compared={}, candidates={})
    for name, manifest_path in RAN.items():
        manifest = json.loads(manifest_path.read_text())
        settings = manifest['settings']
        selection = settings['dataset_settings']['frequencies_ghz'] if 'dataset_settings' in settings else None
        path = F.case_input('dielTM_dec8f' if 'diel' in name else 'circle__c4')
        new, stages = plan(path, selection, settings['start_contrast'])
        same = new == settings['policy']
        differences = sorted(k for k in set(new) | set(settings['policy']) if new.get(k) != settings['policy'].get(k))
        record['compared'][name] = dict(manifest=str(manifest_path.relative_to(ROOT)), plan_identical=same,
                                        differing_keys=differences, stages=stages)
        show(f'{name}: plan identical to the run = {same} {differences or ""}', stages)
    for name, frequencies in CANDIDATES.items():
        _, stages = plan(F.case_input('circle__c4'), frequencies, 1.5)
        record['candidates'][name] = stages
        show(name, stages)
    if args.out:
        from pathlib import Path
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(record, indent=1)+'\n')


if __name__ == '__main__':
    main()
