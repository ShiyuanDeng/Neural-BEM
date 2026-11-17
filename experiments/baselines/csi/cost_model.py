"""Indicative fixed-iteration CSI cost model; no inversion is launched."""
import argparse
import json
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
METHODS = ['MF-CC-CSI','MF-MR-CSI','CSI']


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    observations = []
    for path in sorted((REPO/'results/csi').rglob('matlab_summary.json')):
        s = json.loads(path.read_text())
        tm = 'TM' in s['case_name']
        cells = int(np.prod(s['Ninv']))
        for method, seconds in zip(METHODS,s['time_seconds']):
            if seconds is None: continue
            work = cells * s['source_count'] * len(s['frequencies_GHz']) * (1 if tm else 2)
            observations.append(dict(run=str(path.parent.relative_to(REPO)),method=method,tm=tm,
                grid_cells=cells,components=1 if tm else 2,sources=s['source_count'],frequencies=len(s['frequencies_GHz']),
                iterations=s['iterations'],native_seconds=seconds,seconds_per_iteration=seconds/s['iterations'],
                seconds_per_cell_source_frequency=seconds/s['iterations']/work))
    target_work = 112*112*36*8
    predictions = []
    for method in METHODS:
        group = [x for x in observations if x['method']==method and x['tm']]
        rates = [x['seconds_per_cell_source_frequency'] for x in group]
        coefficient = float(np.median(rates))
        matched = [x for x in group if x['grid_cells']==112*112 and x['sources']==36 and x['frequencies']==8]
        predictions.append(dict(method=method,coefficient=coefficient,
            pooled_seconds_per_iteration=coefficient*target_work,
            coefficient_observed_range=[min(rates),max(rates)],
            matched_seconds_per_iteration=matched[-1]['seconds_per_iteration'] if matched else None))
    single = sum(x['pooled_seconds_per_iteration'] for x in predictions)*2048
    matched = (sum(x['matched_seconds_per_iteration'] for x in predictions)*2048
               if all(x['matched_seconds_per_iteration'] is not None for x in predictions) else None)
    record = dict(model='seconds/iteration = coefficient * grid_cells * source_count * frequency_count; separate TM and TE',
        observations=observations,target=dict(grid_cells=112*112,sources=36,frequencies=8,iterations=2048),
        predictions=predictions,three_method_compute_seconds=single,
        preflight_total_seconds_with_20percent_plus_120s_and_30min_reading=single*1.2+120+1800,
        tg002=dict(shapes=10,relative_permittivities=[.5,4],methods=3,fits=60,
            pooled_inverse_hours=single*20/3600,matched_inverse_hours=matched*20/3600 if matched else None,
            matched_compute_seconds_per_three_methods=matched),
        limits=['Indicative overlap timings; thread count eight.',
                'All runs are listed; TE has two components and is not pooled into TM forecasts.',
                'Cells, sources and frequencies were not varied independently; exponents are assumed, not identified.',
                'Receiver count, sparse factorization, contrast and line search can change the rate.',
                'Forward simulation/data generation is not timed by these inverse measurements.',
                'Relative permittivity 0.5 gives negative contrast, excluded by the unchanged positivity constraint.'])
    domain_path=args.output.parent/'tg002_domain_check.json'
    if domain_path.exists():
        domain=json.loads(domain_path.read_text())
        axis=domain['conditional_cells_per_axis']; factor=axis**2/(112*112)
        record['tg002']['domain_check']=str(domain_path.resolve().relative_to(REPO))
        record['tg002']['conditional_coverage_grid']=dict(
            half_width_mm=domain['conditional_common_half_width_mm'],cells_per_axis=axis,
            work_multiplier=factor,pooled_inverse_hours=single*20/3600*factor,
            matched_inverse_hours=matched*20/3600*factor if matched else None,
            status='cost scenario only; not a selected or authorized simulation setting')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ('three_method_compute_seconds','preflight_total_seconds_with_20percent_plus_120s_and_30min_reading','tg002')},indent=2))


if __name__=='__main__': main()
