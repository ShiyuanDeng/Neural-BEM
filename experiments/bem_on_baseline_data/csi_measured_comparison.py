"""Compare saved measured-cylinder attempts, including incomplete/failed attempts.

No fits or forward solves. All-frequency losses use saved residual evaluations;
missing evaluations remain missing rather than being replaced by circle losses.
"""
from csi_runtime import ROOT, provenance  # pins BLAS to one thread
import argparse
from collections import Counter
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from bem_inverse.io import curve_from
import csi_fit as csi
import csi_measured_schedule as matched

VARIANTS = ('warmup', 'first_cap', 'circle_ladder', 'circle_then_ladder',
            'frontier_capped', 'frontier_measured')
CONTROL = matched.CONTROL.parent


def read_optional(path):
    """A writer may not have finished a JSON file; report it as unavailable for now."""
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def discover_attempts(root=matched.OUTPUT):
    attempts = [('saved', CONTROL)]
    for variant in VARIANTS:
        attempts.extend((variant, p) for p in sorted((Path(root)/variant/csi.MEASURED_CASE/'cuda').glob('attempt_*'))
                        if p.is_dir())
    return attempts


@lru_cache(maxsize=1)
def registered_reference():
    from shapely.geometry import Point
    info = read_optional(ROOT/'results/bem/baseline_data/csi_adapter/2026-11-18/cylinder_info/cylinder_info.json')
    params = info['least_squares']['from_bem_fit']['end']
    centre = [params['x_mm'], params['y_mm']]
    # register_saved.py uses the same 15 mm disk and polygon resolution.
    truth = Point(centre[0]*1e-3, centre[1]*1e-3).buffer(.015, quad_segs=4096)
    return truth, centre


def geometry(record, contrast):
    from experiments.comparison.scoring import region, region_scores
    curve = curve_from(record)
    score = csi.score(csi.MEASURED_CASE, curve, contrast)
    found, repaired = region([csi.D.LENGTH_M*curve.values(16384)])
    truth, centre = registered_reference()
    registered = region_scores(found, truth)
    result = {k: score[k] for k in ('equivalent_radius_mm', 'centre_mm', 'area_error',
                                   'contrast_error', 'repaired_ring', 'area_mm2')}
    result.update(registered_area_error=registered['area_error'],
                  registered_missing_area=registered['missing_area'],
                  registered_excess_area=registered['excess_area'],
                  registered_centre_mm=centre, registered_radius_mm=15.,
                  registered_score_definition='Symmetric-difference area / reference area; 15 mm nominal disk translated to the fixed best-circle centre; recovered outline is not moved.')
    assert repaired == score['repaired_ring']
    return result


def decision_records(folder, fit=None):
    if fit and fit.get('decisions'):
        return fit['decisions']
    saved = read_optional(folder/'local/decisions.json') or {}
    return saved.get('decisions', [])


def resolved_operations(folder, manifest, fit=None):
    operations = {op['label']: op for op in manifest.get('settings', {}).get('policy', {}).get('operations', [])}
    for event in decision_records(folder, fit):
        if event.get('reason') == 'resolved stage entered':
            op = event['operation']
            operations[op['label']] = op
    return operations


def stage_records(folder, fit=None):
    if fit and 'stages' in fit:
        return fit['stages']
    checkpoint = read_optional(folder/'local/checkpoint.json')
    if checkpoint and 'stages' in checkpoint:
        return checkpoint['stages']
    stages = []
    for path in (folder/'local').glob('*.json'):
        record = read_optional(path)
        if isinstance(record, dict) and 'accepted_steps' in record and 'curve' in record:
            stages.append(record)
    plan = read_optional(folder/'local/plan.json') or {}
    order = {op['label']: i for i, op in enumerate(plan.get('operations', []))}
    return sorted(stages, key=lambda stage: (order.get(stage['stage'], 1000), stage['stage']))


def inspect_attempt(variant, folder):
    fit = read_optional(folder/'fit.json')
    metrics = read_optional(folder/'metrics.json') or {}
    manifest = read_optional(folder/'manifest.json') or {}
    stages = stage_records(folder, fit)
    operations = resolved_operations(folder, manifest, fit)
    frontiers = {}
    for event in decision_records(folder, fit):
        label = event.get('operation', {}).get('label', '')
        if label.startswith('frontier_before_') and 'measured' in event:
            frontiers[label[len('frontier_before_'):]] = dict(
                frontier=event['measured']['frontier'], **event['operation']['details'])
    rows = []
    for stage in stages:
        label = stage['stage']
        receipt = read_optional(folder/'local'/f'{label}.json') or {}
        trials = receipt.get('trials')
        statuses = Counter(t.get('status', 'unresolved') for t in trials) if trials is not None else None
        row = dict(stage=label, frontier_at_entry=frontiers.get(label), update_band=stage['M'], storage_band=stage.get('K_geometry'),
                   frequencies_hz=operations.get(label, {}).get('stage', {}).get('frequencies_hz'),
                   accepted_steps=stage['accepted_steps'], stop=stage.get('stop') or stage.get('outcome'),
                   outcome=stage.get('outcome'), physics_failures=stage.get('physics_failures', []),
                   loss_in=stage.get('initial_loss'), loss_out=stage.get('final_loss'),
                   contrast_in=stage.get('entry_contrast'), contrast_out=stage['contrast'],
                   proposals=stage.get('geometry_proposals'), recorded_trials=None if trials is None else len(trials),
                   nonaccepted_trials=None if statuses is None else len(trials)-statuses['accepted']-statuses['unresolved'],
                   unresolved_trials=None if statuses is None else statuses['unresolved'],
                   trial_status=None if statuses is None else dict(statuses),
                   geometry_refusals=None if statuses is None else statuses['refused'],
                   refusal_reasons=None if trials is None else dict(Counter(t.get('reason', 'unspecified') for t in trials if t.get('status') == 'refused')),
                   stage_work_units=stage.get('work', {}).get('stage_units'),
                   cumulative_work_units=stage.get('work', {}).get('work_units'),
                   **geometry(stage['curve'], stage['contrast']))
        rows.append(row)
    final_geometry = None
    if fit and fit.get('final_curve') is not None:
        final_geometry = geometry(fit['final_curve'], fit['final_contrast'])
    relative = metrics.get('final_residual')
    loss = .5*float(np.mean(np.square(list(relative.values())))) if relative and len(relative) == 8 else None
    status = ('complete' if metrics.get('bookkeeping') == 'complete' else
              'fit returned; final record pending' if fit else
              'failed' if metrics.get('outcome') == 'WORKER_EXCEPTION' else 'partial or running')
    if not fit and variant == 'frontier_measured' and folder.name == 'attempt_01':
        status = 'stopped by coordinator at 04:00 UTC; not a failure'
    elif not fit and variant == 'warmup' and folder.name == 'attempt_01':
        status = 'stopped by coordinator at 02:20 UTC; partial run'
    return dict(variant=variant, attempt=folder.name, folder=str(folder.relative_to(ROOT)) if folder.is_relative_to(ROOT) else str(folder),
                status=status, outcome=metrics.get('outcome', fit.get('outcome') if fit else None),
                detail=metrics.get('detail', fit.get('detail') if fit else None),
                last_stage=rows[-1]['stage'] if rows else None,
                final_contrast=fit.get('final_contrast') if fit else None, final_geometry=final_geometry,
                last_saved_geometry=rows[-1] if rows else None,
                loss_all_eight=loss, relative_residual=relative,
                work_units=metrics.get('work_units', fit.get('fit_and_localization_units') if fit else None),
                fit_seconds=metrics.get('fit_seconds', fit.get('fit_and_localization_seconds') if fit else None),
                global_limits=manifest.get('settings', {}).get('policy', {}), stages=rows,
                guard_stop=read_optional(folder/'guard_stop.json'))


def relative_curve_difference(left, right):
    a, b = curve_from(left).coefficients, curve_from(right).coefficients
    if len(a) != len(b):
        n = max(len(a), len(b))
        a = np.pad(a, ((n-len(a))//2,)*2)
        b = np.pad(b, ((n-len(b))//2,)*2)
    return float(np.linalg.norm(a-b)/np.linalg.norm(b))


def prefix_check(folder):
    """The first-cap arm must reproduce all original first-stage accepted states."""
    label = 'ladder_1_real'
    saved = read_optional(CONTROL/'local'/f'{label}.json')
    current = read_optional(folder/'local'/f'{label}.json')
    if not current:
        return dict(status='pending; first-stage receipt unavailable')
    left = {row['iteration']: row for row in saved['history']}
    right = {row['iteration']: row for row in current['history']}
    rows = []
    for iteration, a in left.items():
        if iteration not in right:
            continue
        b = right[iteration]
        rows.append(dict(iteration=iteration, loss_difference=b['loss']-a['loss'],
                         contrast_difference=b['contrast']-a['contrast'],
                         relative_curve_difference=relative_curve_difference(b['coefficients'], a['coefficients'])))
    all_present = len(rows) == len(left)
    matches = all(abs(r['loss_difference']) < 1e-10 and abs(r['contrast_difference']) < 1e-9
                  and r['relative_curve_difference'] < 1e-9 for r in rows)
    return dict(status='match' if all_present and matches else 'incomplete or different',
                saved_accepted_steps=saved['accepted_steps'], compared_states=len(rows),
                all_saved_states_present=all_present,
                max_absolute_loss_difference=max((abs(r['loss_difference']) for r in rows),default=None),
                max_absolute_contrast_difference=max((abs(r['contrast_difference']) for r in rows),default=None),
                max_relative_curve_difference=max((r['relative_curve_difference'] for r in rows),default=None),rows=rows)


def control_prefix_check(folder, reference):
    actual = stage_records(folder, read_optional(folder/'fit.json'))
    expected = {s['stage']: s for s in stage_records(reference, read_optional(reference/'fit.json'))}
    rows = []
    for stage in actual:
        if stage['stage'] not in expected:
            continue
        other = expected[stage['stage']]
        rows.append(dict(stage=stage['stage'], same_steps=stage['accepted_steps'] == other['accepted_steps'],
                         loss_in_difference=stage['initial_loss']-other['initial_loss'],
                         loss_out_difference=stage['final_loss']-other['final_loss'],
                         contrast_difference=stage['contrast']-other['contrast'],
                         relative_curve_difference=relative_curve_difference(stage['curve'], other['curve'])))
    match = bool(rows) and all(r['same_steps'] and abs(r['loss_in_difference']) < 1e-12
        and abs(r['loss_out_difference']) < 1e-12 and abs(r['contrast_difference']) < 1e-12
        and r['relative_curve_difference'] < 1e-12 for r in rows)
    return dict(status='match' if match else 'different or unavailable', compared_stages=len(rows), rows=rows,
                reference=str(reference.relative_to(ROOT)))


def best_circle_record():
    from bem_inverse import FourierCurve
    from bem_inverse.io import curve_record
    path = ROOT/'results/bem/baseline_data/csi_adapter/2026-11-18/cylinder_info/cylinder_info.json'
    best = read_optional(path)['least_squares']['from_bem_fit']
    p = best['end']
    curve = FourierCurve.circle(p['radius_mm']*.001/csi.D.LENGTH_M,
                               complex(p['x_mm'],p['y_mm'])*.001/csi.D.LENGTH_M)
    return dict(variant='best exact circle',attempt='diagnostic',status='exact-series least squares; not a BEM fit',
                outcome='DIAGNOSTIC',folder=str(path.relative_to(ROOT)),last_stage=None,
                final_contrast=p['permittivity'],final_geometry=geometry(curve_record(curve),p['permittivity']),
                loss_all_eight=best['loss'],relative_residual=dict(zip([f'{i}GHz' for i in range(1,9)],best['relative_residual'])),
                work_units=None,fit_seconds=best['seconds'],global_limits={},stages=[])


def csi_baselines():
    path=ROOT/'results/csi/preparation/2026-11-17_frame/registered_scores.json'
    source=read_optional(path)
    rows=[]
    for method in source['methods']:
        score=next(s for s in method['scores'] if s['fraction']==.5)
        rows.append(dict(method=method['method'],source=str(path.relative_to(ROOT)),fraction=.5,
            area_error=score['area_error'],equivalent_radius_mm=float(np.sqrt(score['area_mm2']/np.pi)),
            centre_mm=score['centroid_xy_mm'],mean_relative_permittivity=score['mean_relative_permittivity'],
            registered_to_best_circle_area_error=None,
            note='CSI image support at half signed peak; fixed nominal-centre score. Best-circle registration not computed from these saved scalar scores.'))
    return rows


def settings_check(variant, folder):
    saved = read_optional(CONTROL/'manifest.json')
    current = read_optional(folder/'manifest.json')
    if not current:
        return dict(status='pending; manifest unavailable')
    old, new = saved['settings'], current['settings']
    original = old['policy']['operations']; ops = new['policy']['operations']
    expected = json.loads(json.dumps(original))
    if variant == 'first_cap':
        expected[0]['stage']['iterations'] = 220
        retained = ops
    elif variant == 'warmup':
        retained = ops[1:]
    elif variant == 'circle_ladder':
        expected = [op for op in expected if not op['label'].startswith('ladder_')]
        retained = ops[5:]
    elif variant == 'circle_then_ladder':
        retained = ops[5:]
    elif variant in ('frontier_capped', 'frontier_measured'):
        # The manifest holds only the first fit and first frontier. Later stages
        # are resolved during the run; compare their frequency/limit invariants.
        resolved = resolved_operations(folder, current, read_optional(folder/'fit.json'))
        invariants = {}
        for baseline in original:
            label = baseline['label']
            if 'stage' not in baseline or label not in resolved:
                continue
            before, after = baseline['stage'], resolved[label]['stage']
            keys = ('frequencies_hz', 'weights', 'quota', 'iterations', 'ragged_data')
            same = all(before.get(k) == after.get(k) for k in keys)
            band_ok = (after['update_modes'] <= before['update_modes'] if variant == 'frontier_capped'
                       else after['update_modes'] == before['update_modes'])
            invariants[label] = same and band_ok
        retained = None
    else:
        retained = ops
    keys = ('solver', 'geometry_update', 'localization', 'start', 'data', 'material',
            'start_contrast', 'length_unit_m', 'origin_m', 'bounds_m')
    return dict(input_sha256_matches=current['input']['sha256'] == saved['input']['sha256'],
                unchanged_settings={k: old.get(k) == new.get(k) for k in keys},
                selected_frequencies_ghz_match=(old.get('dataset_settings', {}).get('frequencies_ghz') ==
                                                new.get('dataset_settings', {}).get('frequencies_ghz')),
                global_limits_match=all(old['policy'][k] == new['policy'][k] for k in ('fit_units', 'fit_seconds')),
                retained_operations_match=None if retained is None else retained == expected,
                dynamic_stage_invariants=invariants if variant in ('frontier_capped', 'frontier_measured') else None)


def cell(value, digits=6):
    return 'pending' if value is None else f'{value:.{digits}g}' if isinstance(value, (int, float)) else str(value)


def markdown(records, baselines):
    lines = ['# Saved measured-cylinder comparisons', '',
             'All-frequency losses use saved BEM residual evaluations. Nominal area error uses the 15 mm disk at (0,30) mm. Registered error translates that reference to the fixed best-circle centre; missing final evaluations stay pending.', '',
             '| Variant / attempt | Status | Loss, 1–8 GHz | Radius mm | Centre mm | Permittivity | Nominal area error | Registered area error | Units |',
             '|---|---|---:|---:|---|---:|---:|---:|---:|']
    for record in records:
        g = record['final_geometry'] or {}
        centre = g.get('centre_mm'); centre_text = 'pending' if centre is None else f'({centre[0]:.3f}, {centre[1]:.3f})'
        state = record['status'] + (f"; {record['outcome']}" if record['status']=='complete' else '')
        lines.append(f"| {record['variant']} / {record['attempt']} | {state} | {cell(record['loss_all_eight'])} | {cell(g.get('equivalent_radius_mm'))} | {centre_text} | {cell(record['final_contrast'])} | {cell(g.get('area_error'))} | {cell(g.get('registered_area_error'))} | {cell(record['work_units'])} |")
    for baseline in baselines:
        c=baseline['centre_mm']
        lines.append(f"| {baseline['method']} | CSI half-peak support | not evaluated | {cell(baseline['equivalent_radius_mm'])} | ({c[0]:.3f}, {c[1]:.3f}) | {cell(baseline['mean_relative_permittivity'])} (support mean) | {cell(baseline['area_error'])} | not evaluated | not comparable |")
    for record in records:
        lines.extend(['', f"## {record['variant']} / {record['attempt']}", '',
                      f"Evidence: `{record['folder']}`. Outcome: {record['outcome']}. Last saved stage: {record['last_stage']}.", '',
                      '| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |',
                      '|---|---|---:|---:|---|---|---|---:|---|---|---|'])
        for s in record['stages']:
            fs = s['frequencies_hz']; ftext = 'unknown' if fs is None else ','.join(f'{f/1e9:g}' for f in fs)
            c = s['centre_mm'];centre = 'none' if c is None else f'({c[0]:.3f}, {c[1]:.3f})'
            statuses = s['trial_status']; status = 'unavailable' if statuses is None else ', '.join(f'{k}:{v}' for k,v in statuses.items() if k != 'accepted')
            if s['refusal_reasons']:
                status += '; ' + ', '.join(f'{k}:{v}' for k,v in s['refusal_reasons'].items())
            lines.append(f"| {s['stage']} | {ftext} | {s['update_band']} | {s['accepted_steps']} | {s['stop']} | {cell(s['loss_in'])} → {cell(s['loss_out'])} | {cell(s['contrast_in'])} → {cell(s['contrast_out'])} | {cell(s['equivalent_radius_mm'])} | {centre} | {cell(s['recorded_trials'])} / {cell(s['nonaccepted_trials'])} | {status} |")
        if 'unchanged_prefix' in record:
            check = record['unchanged_prefix']
            lines.extend(['', f"First-stage prefix: {check['status']}; {check.get('compared_states', 0)} states compared."])
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=matched.OUTPUT)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    out = args.out or args.root/'analysis'
    records = []
    for variant, folder in discover_attempts(args.root):
        record = inspect_attempt(variant, folder)
        # Keep only limits here; operation records stay in their original manifests.
        record['global_limits'] = {k: record['global_limits'].get(k) for k in ('fit_units', 'fit_seconds')}
        record['matched_settings'] = settings_check(variant, folder)
        if variant == 'first_cap':
            record['unchanged_prefix'] = prefix_check(folder)
        if variant == 'frontier_measured':
            record['warmup_control_prefix'] = control_prefix_check(folder, args.root/'warmup'/csi.MEASURED_CASE/'cuda/attempt_02')
        records.append(record)
        print(variant, folder.name, record['status'], 'loss', record['loss_all_eight'])
    records.append(best_circle_record())
    baselines=csi_baselines()
    out.mkdir(parents=True, exist_ok=True)
    (out/'matched_fit_comparison.json').write_text(json.dumps(dict(provenance=provenance(), attempts=records, csi_baselines=baselines,
        registered_scoring=dict(centre_mm=registered_reference()[1], radius_mm=15.,
            definition='Symmetric-difference area / reference area (region_scores), with nominal disk translated to fixed best-circle centre.',
            baseline_definition_note='CSI registered_scores.json uses fixed coordinate-frame registration and explicitly no fitted alignment; this requested best-circle translation is a separate registered reference.'),
        missing_variants=[v for v in VARIANTS if not any(r['variant'] == v for r in records)]), indent=2)+'\n')
    (out/'matched_fit_comparison.md').write_text(markdown(records,baselines))


if __name__ == '__main__':
    main()
