"""Cost the ten-case CSI campaign from saved evidence, without launching it."""
import json
from pathlib import Path
import numpy as np

REPO=Path(__file__).resolve().parents[3]
METHODS=['MF-CC-CSI','MR-CSI','CSI']


def main():
    root=REPO/'results/csi/preparation'
    probe=json.loads((root/'2026-11-17_probe/matlab_summary.json').read_text())
    probe_launch=json.loads((root/'2026-11-17_probe/launch.json').read_text())
    resources=json.loads((root/'2026-11-17_probe/scores.json').read_text())['resources']
    snapshots=json.loads((root/'2026-11-17_snapshots/scores.json').read_text())
    generation=json.loads((root/'2026-11-17_generate/forward_summary.json').read_text())
    gen_launch=json.loads((root/'2026-11-17_generate/launch.json').read_text())
    matched=json.loads((REPO/'results/csi/fresnel/2026-11-17_diel_tm/matlab_summary.json').read_text())
    ratios=np.asarray(matched['time_seconds'])/matched['time_seconds'][0]
    rates=probe['time_seconds']/probe['iterations']*ratios
    overhead=probe_launch['wall_seconds']-probe['time_seconds']
    forecasts=[]
    selected=snapshots['minimum_checked_iterations_within_one_percent']
    for iterations in sorted(set([selected,2048])):
        for methods in [METHODS[:1],METHODS]:
            native=sum(float(rates[METHODS.index(m)]) for m in methods)*iterations*10
            setup=overhead*len(methods)*10
            forward=gen_launch['wall_seconds']*10
            tasks=[float(rates[METHODS.index(m)])*iterations+overhead for m in methods for _ in range(10)]
            workers=[0.,0.,0.]
            for task in sorted(tasks,reverse=True):workers[int(np.argmin(workers))]+=task
            forecasts.append(dict(iterations=iterations,methods=methods,fits=10*len(methods),
                inverse_native_hours=native/3600,inverse_wrapper_overhead_hours=setup/3600,
                forward_generation_hours=forward/3600,total_serial_wall_hours=(native+setup+forward)/3600,
                ideal_three_worker_inverse_hours=(native+setup)/3600/3,
                ideal_three_worker_total_with_serial_forward_hours=((native+setup)/3+forward)/3600,
                three_worker_scheduled_total_with_serial_forward_hours=(max(workers)+forward)/3600))
    observations=[]
    for path in sorted((REPO/'results/csi').rglob('matlab_summary.json')):
        s=json.loads(path.read_text());times=np.atleast_1d(s['time_seconds'])
        for method,seconds in zip(METHODS,times):
            if seconds is None:continue
            cells=int(np.prod(s['Ninv']));nf=len(s['frequencies_GHz']);ns=s['source_count']
            components=1 if 'TM' in s['case_name'] else 2
            observations.append(dict(run=str(path.parent.relative_to(REPO)),method=method,
                cells=cells,sources=ns,frequencies=nf,components=components,iterations=s['iterations'],
                native_seconds=float(seconds),seconds_per_iteration=float(seconds)/s['iterations'],
                seconds_per_cell_source_frequency=float(seconds)/s['iterations']/(cells*ns*nf*components)))
    record=dict(shapes=10,relative_permittivity=4,grid=[166,166],cell_m=.00125,sources=36,frequencies=8,
        selected_measured_snapshot_iterations=selected,
        seconds_per_iteration={m:float(r) for m,r in zip(METHODS,rates)},
        per_method_rate_basis='CC measured on 64-iteration synthetic circle; MR/CC and CSI/CC ratios from measured-cylinder 2048 runs',
        measured_method_ratios={m:float(r) for m,r in zip(METHODS,ratios)},
        per_fit_wrapper_overhead_seconds=overhead,forward_generation_native_seconds=generation['seconds'],
        forward_generation_wrapper_wall_seconds=gen_launch['wall_seconds'],
        forecasts=forecasts,resources=resources,all_completed_observations=observations,
        limitations=['No campaign has started; only one shape and 64 synthetic iterations were timed.',
            'BRG overlap affects these wall rates; three-worker columns are ideal arithmetic lower bounds, not measured speedups.',
            'MR/CSI on the larger grid are not directly timed; ratios and all ten shapes are extrapolations.',
            'The measured-cylinder convergence count is not a validated stopping rule for simulated shapes.',
            'Native time includes the algorithm loop, not driver assembly, calibration or forward data generation.',
            'The 14 GiB memory reserve and the current three-heavy-worker limit still apply.'])
    out=root/'2026-11-17_cost';out.mkdir(exist_ok=True)
    (out/'campaign_cost.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(seconds_per_iteration=record['seconds_per_iteration'],forecasts=forecasts),indent=2))


if __name__=='__main__':main()
