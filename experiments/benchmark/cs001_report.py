"""Read-only CS-001 validation, paired table and boundary overlays; no fitting."""
from pathlib import Path

import numpy as np

from bem_inverse.io import read, write, digest, curve_from
from . import cs001 as run, scenes as S


def main():
    run.verify()
    report = run.report()
    if report['completed'] != dict(control=8, revised=8):
        raise ValueError('The preregistered eight matched pairs are incomplete')
    results, evidence = {}, {}
    for case in run.CASES:
        results[case] = {}
        for arm in ('control', 'revised'):
            folder = run.OUTPUT/arm/'runs'/case
            result = read(folder/'result.json')
            results[case][arm] = result
            if result.get('process_returncode') != 0 or result['case']['id'] != case:
                raise ValueError('Worker failed or case identity changed: '+case+'/'+arm)
            if result['policy_settings'] != read(run.OUTPUT/'preparation/manifest.json')['policy'][arm]:
                raise ValueError('Policy settings changed')
            audit = read(folder/'final_audit.json')
            if result['final_audit_passed'] != audit['passed']:
                raise ValueError('Audit receipt mismatch')
            metrics = result['metrics']
            recovered = bool(audit['passed'] and metrics['rms_mm'] <= 1 and
                metrics['hausdorff_upper_mm'] <= 2 and
                np.all(np.asarray(result['relative_residual']) <= result['residual_limits']))
            if result['recovered'] != recovered:
                raise ValueError('Recovery gate mismatch')
            plan = read(folder/'plan.json')
            if arm == 'revised':
                initialization = next(o for o in plan['operations'] if o['label'] == 'initialize_translation_scale')
                if initialization.get('fit_geometry_update') != 'similarity':
                    raise ValueError('Missing restricted initialization')
                states = read(folder/'accepted.json')['states']
                for state in states:
                    if state['stage'] != 'initialize_translation_scale':
                        continue
                    curve = curve_from(state['curve'])
                    other = curve.coefficients.copy()
                    other[curve.band] = other[curve.band+1] = 0
                    if np.any(other != 0):
                        raise ValueError('Initial accepted state lost exact circularity')
                if result.get('stage_geometry_updates', {}).get('similarity', {}).get('settings', {}).get('coordinates') != [
                    'translation_x_m', 'translation_y_m', 'radius_change_m']:
                    raise ValueError('Wrong initialization coordinates')
            for path in folder.glob('*'):
                if path.is_file():
                    evidence[str(path.relative_to(run.OUTPUT))] = digest(path)
        prefix = lambda arm: [o for o in read(run.OUTPUT/arm/'runs'/case/'plan.json')['operations']
                              if o['label'].startswith('stage_')]
        if prefix('control') != prefix('revised'):
            raise ValueError('Paired frequency prefix changed: '+case)
    if not read(run.OUTPUT/'source_check.json')['passed']:
        raise ValueError('Post-run sources did not verify')
    write(run.OUTPUT/'verification.json', dict(passed=True, pairs=8, receipt_hashes=evidence,
        qualification_sha256=digest(run.OUTPUT/'preparation/qualification.json'),
        validation_log_sha256=digest(run.OUTPUT/'validation.log'),
        report_script_sha256=digest(Path(__file__))))
    lines = ['# CS-001 paired TG-002 screen', '',
        '| Case | Control recovery / RMS mm / output s | Revised recovery / RMS mm / output s | Revised Hausdorff upper mm | Revised max residual | Last revised stage |',
        '|---|---|---|---|---|---|']
    for row in report['rows']:
        cells = []
        for arm in ('control', 'revised'):
            r = row[arm]
            cells.append(f"{'PASS' if r['recovered'] else 'FAIL'} / {r['metrics']['rms_mm']:.4f} / {r['audited_output_seconds']:.2f}")
        r = row['revised']
        lines.append(f"| {row['case']} | {' | '.join(cells)} | {r['metrics']['hausdorff_upper_mm']:.4f} | "
                     f"{r['maximum_residual']:.6g} | {r['last_stage']} |")
    (run.OUTPUT/'table.md').write_text('\n'.join(lines)+'\n')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 4, figsize=(14, 7), constrained_layout=True)
    for ax, case in zip(axes.ravel(), run.CASES):
        truth = curve_from(read(run.c.INPUTS/'inputs'/case.split('__')[0]/'truth.json'))
        start = curve_from(read(run.c.start_path()))
        for curve, color, label, style in [(truth, '#111111', 'truth', '-'),
            (start, '#999999', 'start', ':'),
            (curve_from(results[case]['control']['final_curve']), '#1976d2', 'control', '--'),
            (curve_from(results[case]['revised']['final_curve']), '#d35d20', 'revised', '-')]:
            z = (S.CENTER+S.LENGTH*curve.values(4096))*1000
            ax.plot(np.r_[z.real, z.real[0]], np.r_[z.imag, z.imag[0]], style, color=color, label=label, lw=1.5)
        r = results[case]['revised']
        ax.set_title(case+'\n'+('PASS' if r['recovered'] else 'FAIL')+f" · RMS {r['metrics']['rms_mm']:.3f} mm", fontsize=10)
        ax.set_aspect('equal'); ax.grid(alpha=.15)
        ax.set_xlabel('x (mm)'); ax.set_ylabel('y (mm)')
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=4)
    fig.savefig(run.OUTPUT/'boundaries.png', dpi=180)
    plt.close(fig)
    print('CS-001 verified:', report['recovered'], 'regressions', report['recovery_regressions'],
          'new recoveries', report['new_recoveries'])


if __name__ == '__main__':
    main()
