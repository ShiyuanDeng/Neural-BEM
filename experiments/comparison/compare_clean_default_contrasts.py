"""The default with its warm-up (19 November 2026) on clean TG-002: recovered or supplied contrast.

Both arms run ``experiments.comparison.bem.policy`` unchanged, which is the default schedule:

  recovered   the weak contrast estimate, contrast fitted (``bem/default_clean_uc_fc``). Check: it must
              repeat the saved experiment-side warm-up fit (``clean_tg002/warmup``) stage for stage.
  known       one change from ``recovered``: the true contrast is supplied and held, as in a ``kc`` run.

Truth enters after the fit, for scoring only; the ``known`` arm is given the true contrast and nothing else.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import traceback

import numpy as np

from bem_inverse.io import curve_from, digest, read, write
from bem_inverse.material import MaterialUnknown
from bem_inverse.problem import Problem
from bem_inverse.runner import fit
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import curve_region
from experiments.comparison.compare_clean_schedules import OUT, area_score, stage_settings
from experiments.comparison.runs import RESULTS, parse

ARMS = dict(recovered='bem/default_clean_uc_fc', known='bem/default_clean_kc_fc')
KEYS = ('stage', 'M', 'K_geometry', 'nodes', 'accepted_steps', 'initial_loss', 'final_loss',
        'entry_contrast', 'contrast', 'seconds', 'outcome', 'stop', 'detail')


def stage_row(stage, truth):
    return {**{k: stage.get(k) for k in KEYS}, 'work_units': stage['work']['stage_units'],
            'stage_quota': stage['work']['stage_quota'], 'area_error': area_score(stage['curve'], truth),
            'physics_refusal': '|'.join(sorted({f['message'] for f in stage['physics_failures']}))}


def difference(found, saved):
    a, b = curve_from(found).coefficients, curve_from(saved).coefficients
    return float(np.linalg.norm(a-b)/np.linalg.norm(b)) if a.shape == b.shape else None


def against_reference(stages, reference):
    """Stage-for-stage comparison with the saved warm-up fit; only the warm-up's label differs."""
    rows = []
    for new, old in zip(stages, reference['stages']):
        rows.append(dict(stage=new['stage'], reference_stage=old['stage'],
                         same_bands=(new['M'], new['K_geometry']) == (old['M'], old['K_geometry']),
                         same_steps=new['accepted_steps'] == old['accepted_steps'],
                         final_loss=new['final_loss'], reference_final_loss=old['final_loss'],
                         contrast=new['contrast'], reference_contrast=old['contrast'],
                         curve_relative_difference=difference(new['curve'], old['curve'])))
    return dict(same_stage_count=len(stages) == len(reference['stages']), stages=rows)


def run(arm, case):
    run_ = parse(ARMS[arm])
    row = campaign.row(case)
    reference = OUT / 'warmup' / f'{case}.json'
    saved = read(reference)
    real, damped = bem.observations(run_, row, RESULTS)
    initial = curve_from(read(campaign.ROOT / row['initial']))
    solver = bem.solver(run_)
    truth = curve_region(curve_from(read(campaign.ROOT / row['truth'])))
    if arm == 'known':
        contrast, material = float(row['contrast']), None
    else:
        contrast, _ = bem.weak_start(initial, real[0], solver, bem.EXECUTION)
        material = MaterialUnknown()
    policy = bem.policy(run_)
    physics, forward = campaign._physics(solver, bem.EXECUTION)
    try:
        result = fit(Problem(initial, real, damped, contrast), solver=solver, execution=bem.EXECUTION,
                     physics=physics, forward_solve=forward, geometry_update=bem.GEOMETRY_UPDATE,
                     policy=policy, material=material)
    finally:
        if hasattr(physics, 'close'):
            physics.close()
    current = stage_settings(result['decisions'])
    stages = [dict(**stage_row(stage, truth), curve=stage['curve'], settings=current[stage['stage']])
              for stage in result['stages']]
    return dict(reference=str(reference.relative_to(campaign.ROOT)), reference_sha256=digest(reference),
                reference_area_error=saved['area_error'], reference_outcome=saved['outcome'],
                real_data_sha256=digest(campaign.ROOT / row['data']), initial_sha256=digest(campaign.ROOT / row['initial']),
                true_contrast=float(row['contrast']), start_contrast=contrast,
                contrast_rule='supplied (true value), held' if arm == 'known' else 'weak estimate, then fitted',
                frequencies_hz=[o.frequency_hz for o in real], damping='real only',
                policy=dict(type=type(policy).__name__, name=policy.name, version=policy.version,
                            warmup=policy.warmup, frequency_schedule=policy.frequency_schedule),
                geometry_update=bem.GEOMETRY_UPDATE, solver=solver, localization='none',
                execution=result['physics']['execution'], devices=result['physics']['devices'],
                material=result.get('material'), work_limit=policy.fit_units, seconds_limit=policy.fit_seconds,
                work_units=result['fit_and_localization_units'], seconds=result['fit_and_localization_seconds'],
                outcome=result['outcome'], detail=result['detail'],
                area_error=area_score(result['final_curve'], truth),
                contrast=float(result.get('final_contrast', contrast)), stages=stages,
                against_reference=against_reference(stages, saved) if arm == 'recovered' else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('arm', choices=tuple(ARMS))
    parser.add_argument('case', choices=scenes.CASES)
    args = parser.parse_args()
    path = OUT / f'default_{args.arm}' / f'{args.case}.json'
    if path.exists():
        parser.error(f'Output already exists: {path}')
    header = dict(arm=f'default_{args.arm}', case=args.case, started_utc=datetime.now(timezone.utc).isoformat(),
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  driver_sha256=digest(Path(__file__)),
                  policy_sha256=digest(Path(bem.__file__).parents[2] / 'solvers/bem_inverse/real_only_policy.py'))
    try:
        result = run(args.arm, args.case)
    except Exception:
        write(path, {**header, 'outcome': 'WORKER_EXCEPTION', 'detail': traceback.format_exc()})
        raise
    write(path, {**header, **result})
    print(args.case, f'default_{args.arm}', result['outcome'], f'{result["area_error"]:.3%}',
          f'(recovered-contrast warm-up arm {result["reference_area_error"]:.3%})',
          f'contrast {result["contrast"]:.4g}', flush=True)


if __name__ == '__main__':
    main()
