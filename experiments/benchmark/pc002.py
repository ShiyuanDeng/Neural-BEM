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
    selections, caches = [], []
    for row in rows:
        result = read(OUTPUT/'NS/runs'/row['id']/'result.json')
        selections.extend(s['resolution_selection'] for s in result.get('stages', [])
                          if s.get('resolution_selection'))
        caches.append(result.get('physics', {}).get('geometry_cache', {}))
    summary.update(median_seconds=median(r['seconds'] for r in rows if r.get('seconds') is not None) if rows else None,
        total_seconds=sum(r.get('seconds') or 0 for r in rows),
        selected_nodes=sorted({s['selected'] for s in selections}),
        escalated_stages=sum(s['escalated'] for s in selections),
        geometry_builds=sum(c.get('builds', 0) for c in caches),
        geometry_hits=sum(c.get('hits', 0) for c in caches),
        geometry_build_seconds=sum(c.get('build_seconds', 0) for c in caches),
        peak_geometry_device_bytes=max((c.get('peak_device_bytes', 0) for c in caches), default=0),
        limitations=['Only NS executed; PC-001 M1/N1 times are historical, not a controlled speedup comparison.',
                    'Nodal LU/reciprocal solve CUDA, fields/Jacobian contraction CPU; modal LU CPU.',
                    'Stage-selection cost and cold startup included; fixed CUDA N1024/N2048 audits.',
                    'No trial promotion; failed cases and selection escalations retained.'])
    write(OUTPUT/'report.json', summary)
    lines = ['# PC-002 fair nodal+spline', '',
             f"Completed {summary['completed']}/30; recovered {summary['recovered']}/30; "
             f"by contrast {summary['by_contrast']}. Median total {summary['median_seconds'] or 0:.2f} s.", '',
             f"Selected stage nodes: {summary['selected_nodes']}; escalated stages: {summary['escalated_stages']}.", '',
             '| Case | Recovered | RMS mm | Residual | Total s | Outcome |',
             '|---|---:|---:|---:|---:|---|']
    for r in rows:
        fmt = lambda x: '—' if x is None else f'{x:.3g}'
        lines.append(f"| {r['id']} | {r['recovered']} | {fmt(r['rms_mm'])} | "
                     f"{fmt(r['maximum_residual'])} | {fmt(r['seconds'])} | {r['outcome']} |")
    lines += ['', *summary['limitations'], '']
    (OUTPUT/'README.md').write_text('\n'.join(lines))
    print({k:v for k,v in summary.items() if k != 'rows'}, flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'report'))
    args = parser.parse_args()
    if args.command == 'run':
        c.run(OUTPUT/'NS', list(S.CASES), solver='nodal_kress', geometry_update='spline',
              localization='none', execution=EXECUTION, workers=1, experiment='PC-002 approved NS priority')
    report()


if __name__ == '__main__':
    main()
