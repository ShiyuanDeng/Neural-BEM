"""PC-002 approved priority: fair nodal+spline, 30 frozen TG-002 cases."""
import argparse
from statistics import median
from bem_inverse.io import read, write
from bem_inverse.physics import Execution
from . import campaign as c, scenes as S

OUTPUT = c.ROOT/'results/validation/cleaned_interfaces/PC-002'
EXECUTION = Execution(device='cuda', frequency_threads=4, resolution=130,
                      nodal_geometry_reuse='per_curve', nodal_resolution_profile='band_matched')


def report():
    c.summarize(OUTPUT/'NS')
    summary = read(OUTPUT/'NS/summary.json')
    rows = summary['rows']
    selections, caches, refused_selections = [], [], []
    fits, audits = [], []
    for row in rows:
        result = read(OUTPUT/'NS/runs'/row['id']/'result.json')
        row['fit_seconds'] = result.get('fit_and_localization_seconds')
        row['audit_seconds'] = sum(read(OUTPUT/'NS/runs'/row['id']/name).get('seconds', 0.)
                                   for name in ('initial_audit.json', 'final_audit.json')
                                   if (OUTPUT/'NS/runs'/row['id']/name).exists())
        row['selected_nodes'] = sorted({s['nodes'] for s in result.get('stages', [])})
        row['escalated_stages'] = sum(s.get('resolution_selection', {}).get('escalated', False)
                                     for s in result.get('stages', []))
        if row['fit_seconds'] is not None:
            fits.append(row['fit_seconds'])
        audits.append(row['audit_seconds'])
        selections.extend(s['resolution_selection'] for s in result.get('stages', [])
                          if s.get('resolution_selection'))
        caches.append(result.get('physics', {}).get('geometry_cache', {}))
        refusal = OUTPUT/'NS/runs'/row['id']/'resolution_selection_failure.json'
        if refusal.exists():
            refused_selections.append(dict(case=row['id'], **read(refusal)))
    manifest = read(OUTPUT/'NS/manifest.json')
    summary.update(source_commit=manifest['commit'], inputs_sha256=manifest['inputs_sha256'],
        median_fit_seconds=median(fits) if fits else None,
        median_audit_seconds=median(audits) if audits else None,
        selection_seconds=sum(s['seconds'] for s in (*selections, *refused_selections)),
        refused_selections=refused_selections,
        median_seconds=median(r['seconds'] for r in rows if r.get('seconds') is not None) if rows else None,
        total_seconds=sum(r.get('seconds') or 0 for r in rows),
        selected_nodes=sorted({s['selected'] for s in selections}),
        escalated_stages=sum(s['escalated'] for s in selections),
        geometry_builds=sum(c.get('builds', 0) for c in caches),
        geometry_hits=sum(c.get('hits', 0) for c in caches),
        geometry_build_seconds=sum(c.get('build_seconds', 0) for c in caches),
        peak_geometry_device_bytes=max((c.get('peak_device_bytes', 0) for c in caches), default=0),
        limitations=['Only NS executed; PC-001 M1/N1 times are historical, not a controlled speedup comparison.',
                    'Nodal LU/reciprocal solve CUDA, fields/Jacobian contraction CPU; modal LU CPU.',
                    'Stage-selection cost and cold startup included; native-profile plus CUDA N1024/N2048 audits.',
                    'No trial promotion; failed cases and selection escalations retained.'])
    write(OUTPUT/'report.json', summary)
    lines = ['# PC-002 fair nodal+spline', '',
             f"Completed {summary['completed']}/30; recovered {summary['recovered']}/30; "
             f"by contrast {summary['by_contrast']}. Median total {summary['median_seconds'] or 0:.2f} s.", '',
             f"Median fitting {summary['median_fit_seconds'] or 0:.2f} s; "
             f"median audits {summary['median_audit_seconds'] or 0:.2f} s (medians do not add).", '',
             f"Source commit: `{manifest['commit']}`; input seal SHA256: `{manifest['inputs_sha256']}`.", '',
             f"Selected stage nodes: {summary['selected_nodes']}; escalated stages: {summary['escalated_stages']}.", '',
             '| Case | Recovered | RMS mm | Residual | Fit s | Audit s | Total s | Nodes | Outcome |',
             '|---|---:|---:|---:|---:|---:|---:|---|---|']
    for r in rows:
        fmt = lambda x: '—' if x is None else f'{x:.3g}'
        lines.append(f"| {r['id']} | {r['recovered']} | {fmt(r['rms_mm'])} | "
                     f"{fmt(r['maximum_residual'])} | {fmt(r['fit_seconds'])} | {fmt(r['audit_seconds'])} | "
                     f"{fmt(r['seconds'])} | {r['selected_nodes']} | {r['outcome']} |")
    lines += ['', *summary['limitations'], '', '![Final nodal curves](gallery.png)', '']
    (OUTPUT/'README.md').write_text('\n'.join(lines))
    print({k:v for k,v in summary.items() if k != 'rows'}, flush=True)
    return summary


def gallery():
    """Truth is read only for reporting after returned fit/audit results."""
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from bem_inverse.io import curve_from
    fig, axes = plt.subplots(3, 10, figsize=(22, 7.5), facecolor='#fcfcfb')
    closed = lambda z: np.r_[z, z[:1]]
    start = S.CENTER+S.LENGTH*S.start_fixture().values(2048)
    for i, contrast in enumerate(S.CONTRASTS):
        for j, scene in enumerate(S.SCENES):
            ax = axes[i, j]
            case = S.case_id(contrast, scene)
            truth = S.CENTER+S.LENGTH*curve_from(read(c.INPUTS/'inputs'/scene/'truth.json')).values(2048)
            ax.fill(100*truth.real, 100*truth.imag, color='#d9d8d3', lw=0)
            ax.plot(100*closed(start).real, 100*closed(start).imag, color='#aaa9a2', lw=.7, ls='--')
            path = OUTPUT/'NS/runs'/case/'result.json'
            if path.exists():
                r = read(path)
                if r.get('final_curve'):
                    z = S.CENTER+S.LENGTH*curve_from(r['final_curve']).values(2048)
                    ax.plot(100*closed(z).real, 100*closed(z).imag,
                            color='#2676b6' if r['recovered'] else '#bb4a39', lw=1.3)
                rms = (r.get('metrics') or {}).get('rms_mm')
                label = ('PASS' if r['recovered'] else 'FAIL')+('' if rms is None else f'  {rms:.3f} mm')
                ax.text(.03, .03, label, transform=ax.transAxes, fontsize=7.5,
                        color='#2676b6' if r['recovered'] else '#bb4a39')
            ax.set(xlim=(35,65), ylim=(35,65), aspect='equal', xticks=[], yticks=[])
            for spine in ax.spines.values():
                spine.set_color('#c9c8c2')
            if i == 0:
                ax.set_title(scene.replace('_',' '), fontsize=10, loc='left')
            if j == 0:
                ax.set_ylabel(f'contrast {contrast:g}', fontsize=10)
    fig.legend(handles=[Line2D([], [], color='#d9d8d3', lw=5, label='truth'),
                        Line2D([], [], color='#aaa9a2', ls='--', label='centred 65 mm start'),
                        Line2D([], [], color='#2676b6', label='recovered nodal+spline'),
                        Line2D([], [], color='#bb4a39', label='failed recovery')],
               loc='lower center', ncol=4, frameon=False)
    fig.suptitle('PC-002: fair nodal+spline on TG-002 — geometry reuse and accuracy-selected nodes',
                 fontsize=13, x=.02, ha='left')
    fig.subplots_adjust(left=.035, right=.99, bottom=.075, top=.91, wspace=.08, hspace=.12)
    fig.savefig(OUTPUT/'gallery.png', dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'report'))
    args = parser.parse_args()
    if args.command == 'run':
        c.run(OUTPUT/'NS', list(S.CASES), solver='nodal_kress', geometry_update='spline',
              localization='none', execution=EXECUTION, workers=1, experiment='PC-002 approved NS priority')
    report()
    gallery()


if __name__ == '__main__':
    main()
