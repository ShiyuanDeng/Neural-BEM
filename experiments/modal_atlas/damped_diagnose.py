"""MA-004 post-gate diagnosis. Evaluation only: nothing here feeds an inverse or selects an iterate.

Part 1 (trajectory). Boundary error against the truth at the end of every
stage of every MA-004 development attempt, from the saved stage records.

Part 2 (crossfit). Is the contrast-13.3 star's residual a fitting stop or a
band floor? The real contrast-13.3 star data are evaluated, per frequency, at
the truth and at the D star endpoints from every contrast. The lower-contrast
endpoints are 0.018-0.022 mm from the truth and passed their own residual
criterion.

Part 3 (frontier). The 1% observable frontier (MA-001's column-norm
definition, harmonics p = 0..96) at the star truth, at the top four catalog
frequencies, at contrasts 0.5, 4 and 13.3; against the final fixed band M = 37.

    PYTHONPATH=solvers:. python -m experiments.modal_atlas.damped_diagnose trajectory
    PYTHONPATH=solvers:. python -m experiments.modal_atlas.damped_diagnose crossfit
    PYTHONPATH=solvers:. python -m experiments.modal_atlas.damped_diagnose frontier
"""
import json
import sys
import warnings

import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.modal_atlas.contrast_screen import SC050, SCENES, sc050, set_contrast, tag
from experiments.modal_atlas.damped_screen import OUT, fitting_data, write


def truth_of(scene):
    source = 'new_asymmetric' if scene == 'noisy_asymmetric' else scene
    return ast.curve_from(sc.read(SC050 / 'inputs' / source / 'truth.json'))


def trajectory():
    s = sc050()
    out = {}
    for folder in sorted((OUT / 'runs').glob('*/*/*')):
        if not (folder / 'result.json').exists():
            continue
        truth = truth_of(folder.name)
        rows = []
        if (folder / 'localization.json').exists():
            x = sc.read(folder / 'localization.json')['parameters_m']
            from experiments.modal_atlas.repair_screen import ast_circle
            rows.append(dict(stage='localization', rms_mm=s.old.score(ast_circle(np.array(x)), truth)['rms_mm']))
        for stage in sc.read(folder / 'configuration.json')['stages']:
            path = folder / f"{stage['label']}.json"
            if not path.exists():
                break
            record = sc.read(path)
            metrics = s.old.score(ast.curve_from(record['curve']), truth)
            rows.append(dict(stage=stage['label'], M=stage['update_modes'], final_loss=record['final_loss'],
                             outcome=record['outcome'], stop=record['stop'], rms_mm=metrics['rms_mm'],
                             hausdorff_upper_mm=metrics['hausdorff_upper_mm']))
        key = '/'.join(folder.parts[-3:])
        out[key] = rows
        print(key, [(r['stage'], round(r['rms_mm'], 3)) for r in rows], flush=True)
    write(OUT / 'diagnosis_trajectory.json', out)


def crossfit():
    warnings.simplefilter('ignore')
    set_contrast(13.3)
    s = sc050()
    real, _, _ = fitting_data(13.3, 'shifted_star')
    observed = np.column_stack([o.scattered for o in real])
    truth = truth_of('shifted_star')
    curves = dict(truth=truth)
    for contrast in (0.5, 2.0, 4.0, 13.3):
        curves[f'D endpoint from contrast {contrast:g}'] = ast.curve_from(
            sc.read(OUT / 'runs/D' / tag(contrast) / 'shifted_star/result.json')['final_curve'])
    rows = {}
    for name, curve in curves.items():
        residual = ac.relative(s.predictions(curve, real, 1024), observed)
        metrics = s.old.score(curve, truth)
        rows[name] = dict(rms_mm=metrics['rms_mm'], relative_residual=residual,
                          maximum_residual=float(max(residual)), frequencies_above_0p003=int(np.sum(residual > .003)))
        print(name, round(metrics['rms_mm'], 4), round(float(max(residual)), 5), flush=True)
    write(OUT / 'diagnosis_crossfit.json', dict(data='real contrast-13.3 shifted_star observations',
                                                 frequencies_hz=list(ac.CATALOG_HZ), rows=rows))


def frontier():
    from experiments.modal_atlas import diagnose
    warnings.simplefilter('ignore')
    diagnose.PMAX = 96
    catalog = ast.catalog_only('circle_to_c')
    truth = truth_of('shifted_star')
    rows = []
    for contrast in (0.5, 4.0, 13.3):
        for obs in catalog[-4:]:
            row = diagnose.column_profile(truth, obs.wavenumber, contrast, obs.acquisition, nodes=1024)
            rows.append(dict(contrast=contrast, k=row['k'], frontier_1e_1=row['frontier_0.1'],
                             frontier_1e_2=row['frontier_0.01'], frontier_1e_3=row['frontier_0.001'],
                             relative_column=row['relative_data_sensitivity']))
            print(contrast, round(row['k'], 3), row['frontier_0.1'], row['frontier_0.01'], row['frontier_0.001'],
                  flush=True)
    write(OUT / 'diagnosis_frontier_star.json', dict(state='shifted_star truth', final_fixed_M=37, rows=rows))


if __name__ == '__main__':
    globals()[sys.argv[1]]()
