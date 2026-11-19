"""Single-stage CPU replays of four difficult warm-ups. No ladder stages can run."""
from collections import Counter
from dataclasses import replace

import numpy as np

from bem_inverse.continuation.geometry import resize
from bem_inverse.fit_stage import fit_stage
from bem_inverse.geometry_selection import make_update
from bem_inverse.io import curve_from, read, write
from bem_inverse.material import MaterialUnknown
from bem_inverse.physics import Execution
from bem_inverse.problem import Problem
from bem_inverse.work import Ledger
from experiments.benchmark import campaign
from experiments.comparison.compare_clean_schedules import OUT, write_rows
from experiments.comparison.compare_clean_warmups import Schedule
from experiments.comparison.localize_clean_real_disks import DIR, MM, observation

SHAPES = ['aphex_twin', 'star', 'c_shape', 'hook']


def one(case, arm):
    row = campaign.row(case)
    obs = observation(case)
    source = read(OUT/'warmup'/(case+'.json'))
    weak = source['start_contrast']
    q = 2-weak if case.startswith('hook__') else weak
    initial = curve_from(read(campaign.ROOT/row['initial']))
    problem = Problem(initial, (obs,), None, q)
    execution = Execution('cpu', 1)
    physics, forward = campaign._physics('modal_muller', execution)
    stage_op = Schedule(warmup_only=True, fit_seconds=120).operations(problem, physics)[0]
    settings = stage_op.optimizer
    if arm == 'shape_x4':
        settings = replace(settings, step_bounds_m=tuple(4*x for x in settings.step_bounds_m))
    material = MaterialUnknown(log_step_bound=1. if arm == 'log_x4' else .25)
    update, geometry = make_update('slider', problem.length_unit_m, execution)
    ledger = Ledger(cap=13412, seconds=120.)
    ledger.begin_stage(stage_op.label, stage_op.stage.quota)
    proposals = []

    def observe(kind, event):
        if kind == 'proposal':
            raw, bounded = event['raw_proposed'], event['bounded_proposed']
            proposals.append(dict(damping=float(event['damping']), shape_clipped=bool(np.any(raw[:-1]!=bounded[:-1])),
                                  material_clipped=bool(raw[-1]!=bounded[-1]),
                                  slope_raw=float(event['gradient']@raw), slope_bounded=float(event['gradient']@bounded),
                                  raw_log=float(raw[-1]), bounded_log=float(bounded[-1]),
                                  raw_shape_m=raw[:-1].tolist(), bounded_shape_m=bounded[:-1].tolist()))

    physics.observer = observe
    result = fit_stage(resize(initial, stage_op.stage.curve_modes), stage_op.stage, q, update,
                       settings, ledger, physics=physics, forward_solve=forward,
                       geometry_update=geometry, material=material)
    if hasattr(physics, 'close'):
        physics.close()
    # Proposals precede backtracking. Consecutive damping attempts can skip every tiny step.
    accepted_proposals = []
    pindex = 0
    for trial in result.trials:
        while pindex < len(proposals) and proposals[pindex]['damping'] != trial['damping']:
            pindex += 1
        if pindex >= len(proposals):
            raise ValueError('Trial damping not present in the proposal sequence')
        if trial['status']=='accepted':
            accepted_proposals.append(proposals[pindex])
            pindex += 1
    counts = Counter(t.get('reason', t['status']) for t in result.trials)
    c = result.curve.coefficients
    recent = result.history[-1]
    ref = source['stages'][0]
    metrics = dict(case=case, arm=arm, start_contrast=q, steps=result.accepted_steps, stop=result.stop_reason,
                   initial_loss=result.initial_loss, loss=result.final_loss, contrast=result.contrast,
                   x_mm=MM*c[4].real, y_mm=MM*c[4].imag, radius_mm=MM*abs(c[5]), work=ledger.units,
                   terminal_gradient=recent['gradient_inf'], gradient_tolerance=settings.gradient_tolerance,
                   prior_loss=result.history[-2]['loss'] if len(result.history)>1 else result.initial_loss,
                   trials=len(result.trials), refused=sum(t['status']=='refused' for t in result.trials),
                   nondecreasing=counts['nondecreasing'], proposals=len(proposals),
                   geometry_clipped_accepts=sum(p['shape_clipped'] for p in accepted_proposals),
                   material_clipped_accepts=sum(p['material_clipped'] for p in accepted_proposals),
                   last_accept_geom_clip=accepted_proposals[-1]['shape_clipped'] if accepted_proposals else None,
                   last_accept_mat_clip=accepted_proposals[-1]['material_clipped'] if accepted_proposals else None,
                   saved_loss=ref['final_loss'] if q==weak else None,
                   saved_curve_difference=None if q!=weak else np.linalg.norm(c-curve_from(ref['curve']).coefficients))
    receipt = dict(metrics=metrics, trials=[{k:t[k] for k in ('iteration','damping','backtrack','status','reason',
                          'step_norm_m','log_contrast_step','loss') if k in t} for t in result.trials],
                   trial_counts=dict(counts), proposals=proposals, history=[{k:h[k] for k in (
                       'iteration','loss','step_m','contrast','gradient_inf') if k in h} for h in result.history])
    write(DIR/'warmup_replays'/f'{case}_{arm}.json', receipt)
    return metrics


def main():
    rows = []
    for shape in SHAPES:
        for arm in ['reference','log_x4','shape_x4']:
            case = shape+'__c13.3'
            metrics = one(case, arm)
            rows.append(metrics)
            print(case, arm, metrics['stop'], metrics['steps'], metrics['loss'], flush=True)
    write_rows(DIR/'warmup_replays.csv', rows)


if __name__ == '__main__':
    main()
