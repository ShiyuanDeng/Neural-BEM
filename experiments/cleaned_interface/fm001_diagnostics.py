"""Evaluation-only FM-001 paths, radius scans and evidence-backed reporting."""
from dataclasses import replace
from pathlib import Path
from time import perf_counter
import traceback
import numpy as np
from scipy.optimize import minimize_scalar

from . import benchmark as b
from .fm001 import verify, rows_for, C_STARTS
from .io import read, write, digest, curve_from
from .physics import NodalKress, Execution
from .full_matrix import receiver_weights, apply_receiver_weights
from .geometry import resize, project
from experiments.shape_continuation.geometry import FourierCurve, grid_size
from experiments.shape_continuation.geometry_runtime import geometry_runtime


def phase_align(first, second):
    band = max(first.band, second.band)
    first, second = resize(first,band), resize(second,band)
    a, c, modes = first.coefficients, second.coefficients, first.modes
    angles = np.linspace(0,2*np.pi,2048,endpoint=False)
    values = np.real(np.exp(1j*np.outer(angles,modes))@(c*np.conj(a)))
    center = angles[np.argmax(values)]
    objective = lambda t:float(np.sum(abs(a-c*np.exp(1j*modes*t))**2))
    minimum = minimize_scalar(objective, bounds=(center-2*np.pi/2048,center+2*np.pi/2048), method='bounded',
                              options=dict(xatol=1e-13))
    return first, FourierCurve(c*np.exp(1j*modes*minimum.x)), float(minimum.x)


def aligned_rms_mm(first, second):
    band = max(192,first.band,second.band)
    count = grid_size(band)
    curves = [FourierCurve(project(c,np.zeros(1),band,count,.05)[0]) for c in (first,second)]
    a, c, _ = phase_align(*curves)
    return float(50*np.linalg.norm(a.coefficients-c.coefficients))


def templates_for(truth, problem, backend, gammas, frequencies):
    templates, qualifications = {}, []
    for gamma in gammas:
        observations = []
        for frequency in frequencies:
            original = next(o for o in problem.real if o.frequency_hz==frequency)
            scan = replace(original.acquisition, paired=False)
            obs = replace(original, wavenumber=original.wavenumber*(1+1j*gamma), acquisition=scan,
                          scattered=np.ones(scan.data_shape,complex), sigma_real_imag=0.)
            low = backend.evaluate(truth,obs,problem.contrast,1024).prediction
            high = backend.evaluate(truth,obs,problem.contrast,2048).prediction
            relative = float(np.linalg.norm(low-high)/np.linalg.norm(high))
            qualifications.append(dict(gamma=gamma,frequency_hz=frequency,relative=relative,passed=relative<=1e-8))
            observations.append(replace(obs,scattered=low))
        templates[gamma] = tuple(observations)
    return templates, qualifications


def objectives(curve, templates, contrast, backend, taus, nodes=512):
    losses = {}
    for gamma, observations in templates.items():
        label = 'real' if gamma==0 else 'damped_'+str(gamma)
        sums = {'paired_'+label:[], 'full_'+label:[]}
        if gamma==0:
            for tau in taus:
                sums.update({'paired_relaxed_'+str(tau):[], 'full_relaxed_'+str(tau):[]})
        for obs in observations:
            state = backend.evaluate(curve,obs,contrast,nodes)
            residual = state.prediction-obs.scattered
            norm = float(np.linalg.norm(obs.scattered)**2)
            paired_norm = float(np.linalg.norm(np.diag(obs.scattered))**2)
            sums['full_'+label].append(.5*float(np.linalg.norm(residual)**2)/norm)
            sums['paired_'+label].append(.5*float(np.linalg.norm(np.diag(residual))**2)/paired_norm)
            if gamma==0 and taus:
                h, rows = backend.relaxation_components(state)
                for tau in taus:
                    w = receiver_weights(h, rows, tau)
                    full = apply_receiver_weights(residual.reshape(-1), w, residual.shape)
                    paired = np.diag(residual)*receiver_weights(h, rows, tau, paired=True)
                    sums['full_relaxed_'+str(tau)].append(.5*float(np.linalg.norm(full)**2)/norm)
                    sums['paired_relaxed_'+str(tau)].append(.5*float(np.linalg.norm(paired)**2)/paired_norm)
            del state
        losses.update({name:float(np.mean(values)) for name,values in sums.items()})
    return losses


def path_check(output, row, stage, backend):
    path = output/'phase2'/'paths'/row['id']/(stage+'.json')
    if path.exists() and read(path).get('complete'):
        return read(path)
    archived = read(b.DEFAULT_OUTPUT/'runs'/row['id']/'checkpoint.json')['stages']
    endpoint = curve_from(next(s['curve'] for s in archived if s['stage']==stage))
    truth = curve_from(read(b.ROOT/row['truth']))
    first, last, shift = phase_align(endpoint,truth)
    problem = b.fitting_problem(row,b.DEFAULT_OUTPUT)
    templates, qualifications = templates_for(truth,problem,backend,(0.,.25,.5,1.),(.5e9,.75e9))
    record = read(path) if path.exists() else dict(case=row['id'],stage=stage,nodes=512,
        truth_nodes=[1024,2048],truth_qualification=qualifications,truth_phase_shift=shift,
        construction='Straight coefficient segment; exact archived start and phase-shifted truth. No rotation or translation alignment.',
        start_aligned_arclength_rms_mm=aligned_rms_mm(endpoint,truth),points=[],complete=False)
    fractions = np.linspace(0,1,81)
    for index in range(len(record['points']),len(fractions)):
        fraction = float(fractions[index])
        curve = FourierCurve((1-fraction)*first.coefficients+fraction*last.coefficients)
        try:
            loss = objectives(curve,templates,problem.contrast,backend,(3.,30.))
            point = dict(fraction=fraction,losses=loss)
        except Exception:
            point = dict(fraction=fraction,failure=traceback.format_exc())
        record['points'].append(point)
        write(path,record)
    good = [p for p in record['points'] if 'losses' in p]
    record['complete'] = True
    record['all_points_valid'] = len(good)==len(fractions)
    if good and 'losses' in record['points'][0]:
        record['barriers'] = {name:float(max(p['losses'][name] for p in good)/start)
                              for name,start in record['points'][0]['losses'].items()}
        record['interior_local_maxima'] = {name:int(np.sum((np.diff([p['losses'][name] for p in good])[:-1]>0)&
            (np.diff([p['losses'][name] for p in good])[1:]<0))) for name in good[0]['losses']}
    write(path,record)
    print('PATH',row['id'],stage,record.get('barriers'),flush=True)
    return record


def radius_scan(output, backend):
    path = output/'phase2'/'radius.json'
    if path.exists() and read(path).get('complete'):
        return read(path)
    row = next(r for r in b.descriptors() if r['id']==C_STARTS[0])
    problem = b.fitting_problem(row,b.DEFAULT_OUTPUT)
    truth = FourierCurve.circle(1.06)
    templates, qualification = templates_for(truth,problem,backend,(0.,.25),(.25e9,.5e9,.75e9,1e9,1.25e9))
    record = read(path) if path.exists() else dict(contrast=13.3,true_radius_m=.053,nodes=512,
        reference_nodes=[1024,2048],qualification=qualification,
        radius_range_units=[.25,2.25],spacing_units=.005,points=[],complete=False)
    radii = np.linspace(.25,2.25,401)
    for index in range(len(record['points']),len(radii)):
        radius = float(radii[index])
        try:
            loss = objectives(FourierCurve.circle(radius),templates,13.3,backend,(.1,1.,3.,10.,30.,100.))
            point = dict(radius_units=radius,losses=loss)
        except Exception:
            point = dict(radius_units=radius,failure=traceback.format_exc())
        record['points'].append(point)
        write(path,record)
        if index%50==0:
            print('RADIUS',index,len(radii),flush=True)
    record['complete'] = True
    record['all_points_valid'] = all('losses' in p for p in record['points'])
    summary = {}
    if record['all_points_valid']:
        for name in record['points'][0]['losses']:
            values = np.array([p['losses'][name] for p in record['points']])
            minima = np.flatnonzero((values[1:-1]<values[:-2])&(values[1:-1]<values[2:]))+1
            maxima = np.flatnonzero((values[1:-1]>values[:-2])&(values[1:-1]>values[2:]))+1
            index = int(np.argmin(abs(radii-1.06)))
            lower = max([0]+[int(j) for j in maxima if j<index])
            upper = min([len(radii)-1]+[int(j) for j in maxima if j>index])
            summary[name] = dict(local_minima=len(minima),minima_radii_units=radii[minima],
                true_basin_width_units=float(radii[upper]-radii[lower]),
                basin_truncated_at_scan_boundary=lower==0 or upper==len(radii)-1)
    record['summary'] = summary
    write(path,record)
    return record


def paths(output, fallback=False):
    verify(output)
    backend = NodalKress(Execution())
    cases = [C_STARTS[0],'modal__c4__development_c']
    if fallback:
        cases += ['modal__c13.3__shifted_star','modal__c13.3__new_thin_c']
    results = []
    with geometry_runtime('both'):
        for case in cases:
            row = next(r for r in b.descriptors() if r['id']==case)
            for stage in ('stage_1_damped','stage_4_damped','stage_4_undamped'):
                results.append(path_check(output,row,stage,backend))
        radius = radius_scan(output,backend)
    value = dict(complete=True,fallback=fallback,path_count=len(results),
        all_points_valid=all(r['all_points_valid'] for r in results) and radius['all_points_valid'],
        production_nodes=512,qualification_nodes=[1024,2048])
    write(output/'phase2'/'summary.json',value)
    return value


def plots(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    files = sorted((output/'phase2'/'paths').glob('*/*.json'))
    if files:
        fig,axes = plt.subplots(len(files),1,figsize=(8,2.7*len(files)),squeeze=False)
        for ax,path in zip(axes[:,0],files):
            record = read(path)
            good = [p for p in record['points'] if 'losses' in p]
            for name in ('paired_real','full_real','paired_damped_0.25','full_relaxed_3.0'):
                if not good:
                    continue
                values = np.array([p['losses'][name] for p in good])
                ax.plot([p['fraction'] for p in good], values/values[0], label=name)
            ax.axhline(1,color='gray',linewidth=.6)
            ax.set(title=record['case']+' / '+record['stage'],xlabel='Fraction toward truth',ylabel='Loss / starting loss')
            ax.legend(fontsize=7,ncol=2)
        fig.tight_layout()
        fig.savefig(output/'phase2'/'paths.png',dpi=140)
        plt.close(fig)
    path = output/'phase2'/'radius.json'
    if path.exists():
        points = [p for p in read(path)['points'] if 'losses' in p]
        fig,ax = plt.subplots(figsize=(9,4))
        for name in ('paired_real','paired_damped_0.25','paired_relaxed_3.0','full_real','full_relaxed_3.0'):
            ax.semilogy([p['radius_units']*50 for p in points],[max(p['losses'][name],1e-20) for p in points],label=name)
        ax.axvline(53,color='gray',linewidth=.7)
        ax.set(xlabel='Radius (mm)',ylabel='Normalized loss',title='Contrast 13.3 disk, five frequencies, N=512')
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(output/'phase2'/'radius.png',dpi=160)
        plt.close(fig)


def report(output):
    summary = {}
    lines = ['# FM-001: full-matrix acquisition and relaxed receiver residuals','',
        'Baseline `b23dbf3e`; existing `feature/shape-frequency-continuation` branch. '
        'All parameters, budgets, recovery gates and stop rules follow the frozen plan.','',
        'FRr uses real-frequency data in its relaxed prefix, but still localizes on the '
        'damped paired diagonal. Each relaxed evaluation charges an additional adjoint batch '
        'against the unchanged work budget. Final audits use the ordinary real-data objective.','',
        'The archived 28/36 count is the combined historical retention contract, not a pure '
        'residual count. Archive recovery is 34/36. For comparability the tables also test '
        'the new endpoint on the unchanged paired diagonal against that historical contract. '
        'Full-matrix recovery uses the same geometric, numerical and residual thresholds '
        'on the new acquisition, with its recorded realized noise.','']
    for phase in ('phase0','phase1'):
        p = output/phase/'controls.json'
        if p.exists():
            lines += [f'{phase} paired replay gate: **{read(p)["passed"]}**.','']
    gate_path = output/'phase1'/'gates.json'
    if gate_path.exists():
        gates = read(gate_path)
        lines += [f'Phase-1 validation: {gates["regression_tests"]} regression tests passed. '
            f'Closed-form relative error {gates["closed_form_max_relative"]:.3g}; '
            f'large-tau relative error {gates["large_tau_relative"]:.3g}; '
            f'full-matrix Jacobian FD relative error {gates["full_matrix_fd_max_relative"]:.3g}.','']
    fix_path = output/'bugfixes.json'
    if fix_path.exists():
        lines += ['Implementation corrections (failures and prior source seals retained):','']
        lines += ['- '+item['description'] for item in read(fix_path)['fixes']]
        lines += ['']
    for arm in ('F','FRr'):
        status_path = output/arm/'status.json'
        status = read(status_path) if status_path.exists() else dict(completed=0,stopped=False,reason='not run',lost=[])
        entries = []
        for row in rows_for(arm):
            path = output/arm/'runs'/row['id']/'result.json'
            if path.exists():
                entries.append(read(path))
        c_results = {r['case']:r for r in entries if r['case'] in C_STARTS}
        gate1 = len(c_results)==2 and all(r['recovered'] for r in c_results.values())
        gate2 = len(entries)==len(rows_for(arm)) and not status['lost']
        summary[arm] = dict(status=status,G1=gate1,G2=gate2,
            recovered=sum(r['recovered'] for r in entries),
            historical_pass=sum(r.get('paired_historical_pass',False) for r in entries),
            paired_residual_retention_pass=sum(r.get('paired_historical_retention',{}).get('per_frequency_residual',False) for r in entries),
            full_recovery_residual_pass=sum(r.get('recovery_residual_pass',False) for r in entries))
        lines += [f'## Arm {arm}','',f'Completed {len(entries)}/{len(rows_for(arm))}; '
            f'recovered {summary[arm]["recovered"]}; historical paired retention passes {summary[arm]["historical_pass"]}; '
            f'paired residual-only retention passes {summary[arm]["paired_residual_retention_pass"]}. '
            f'Status: {status["reason"]}. G1={gate1}; G2={gate2}.','',
            '| Case | Outcome | Recovered | RMS mm | Hausdorff upper mm | Max full residual | Paired historical pass | Seconds |',
            '|---|---|---:|---:|---:|---:|---:|---:|']
        by_case = {r['case']:r for r in entries}
        for row in rows_for(arm):
            r = by_case.get(row['id'])
            if r is None:
                lines.append(f'| {row["id"]} | Not run | — | — | — | — | — | — |')
                continue
            m = r.get('metrics',{})
            fmt = lambda x:'—' if x is None else f'{x:.5g}'
            lines.append(f'| {row["id"]} | {r["outcome"]} | {r["recovered"]} | {fmt(m.get("rms_mm"))} | '
                f'{fmt(m.get("hausdorff_upper_mm"))} | {fmt(r.get("maximum_residual"))} | '
                f'{r.get("paired_historical_pass",False)} | {fmt(r.get("total_seconds"))} |')
        lines += ['']
    attribution = ('F recovers both C starts: acquisition is sufficient under the tested fixed policy.' if summary['F']['G1'] else
        'Only FRr recovers both C starts: evidence for an additional effect of relaxation in this tested schedule.' if summary['FRr']['G1'] else
        'Neither arm established recovery of both C starts; no successful acquisition/relaxation attribution is established.')
    summary['G3'] = attribution
    lines += ['## Attribution and stage distances','',attribution,'']
    distances = []
    for arm in ('F','FRr'):
        for case in C_STARTS:
            path = output/arm/'runs'/case/'result.json'
            if not path.exists():
                continue
            r = read(path)
            row = next(x for x in b.descriptors() if x['id']==case)
            truth = curve_from(read(b.ROOT/row['truth']))
            stages = [dict(stage=s['stage'],aligned_arclength_rms_mm=aligned_rms_mm(curve_from(s['curve']),truth))
                      for s in r.get('stages',[])]
            first_rise = next((c['stage'] for a,c in zip(stages,stages[1:]) if c['aligned_arclength_rms_mm']>=a['aligned_arclength_rms_mm']),None)
            distances.append(dict(arm=arm,case=case,stages=stages,first_non_decreasing_stage=first_rise))
            lines += [f'- {arm}, {case}: first non-decreasing stage {first_rise or "none among completed stages"}; '+
                ', '.join(f'{s["stage"]}: {s["aligned_arclength_rms_mm"]:.3f} mm' for s in stages)+'.']
    write(output/'stage_distances.json',dict(rows=distances))
    lines += ['','## Evaluation-only paths','',
        'Each entry is max(path loss)/starting loss on 81 phase-aligned coefficient samples. '
        'A ratio above 1 is a barrier on that path only. The stage-4 damped and real endpoints '
        'are both included to remove ambiguity about the switch.','',
        '| Case | Stage | Paired real | Full real | Paired damped .25 | Paired damped .5 | Paired damped 1 | Paired relaxed 3 | Full relaxed 3 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for path in sorted((output/'phase2'/'paths').glob('*/*.json')):
        r=read(path)
        names=('paired_real','full_real','paired_damped_0.25','paired_damped_0.5','paired_damped_1.0','paired_relaxed_3.0','full_relaxed_3.0')
        values=['—' if name not in r.get('barriers',{}) else f'{r["barriers"][name]:.3f}' for name in names]
        lines.append('| '+r['case']+' | '+r['stage']+' | '+' | '.join(values)+' |')
    radius=output/'phase2'/'radius.json'
    if radius.exists():
        lines += ['','## Disk scan','',
            'Radius 12.5–112.5 mm at 0.25 mm spacing; truth 53 mm; five frequencies '
            '0.25–1.25 GHz. Basin widths are between adjacent sampled maxima and are '
            'censored where they reach the scan boundary.','',
            '| Objective | Local minima | Basin width / 50 mm | Boundary censored |','|---|---:|---:|---:|']
        for name,r in read(radius).get('summary',{}).items():
            lines.append(f'| {name} | {r["local_minima"]} | {r["true_basin_width_units"]:.3f} | {r["basin_truncated_at_scan_boundary"]} |')
    lines += ['','## Limits and evidence','',
        'These are synthetic-data experiments with fixed 24-by-24 acquisition, a fixed '
        'optimizer and discrete path samples. Shape-dependent positive weights can in '
        'principle change extrema even for paired data; failure in a scan is empirical, '
        'not a theorem that reweighting can never remove a barrier.','',
        'Noise preserves every archived observed diagonal and draws independent '
        'off-diagonal entries at the full-matrix 1% scale. The effective sigma preserves '
        'the expected total noise energy of this mixed catalog. Clean diagonals and '
        '1024/2048 catalog agreement are checked before fitting.','',
        'All failures, tests, source seals, catalogs, stage receipts and plots are in '
        '`results/validation/cleaned_interfaces/FM-001/`. Runtime comparisons with '
        'historical runs are diagnostic; no matched-host speed claim is made.','']
    write(output/'summary.json',summary)
    plots(output)
    text='\n'.join(lines)
    for path in (b.ROOT/'docs/iterations/cleaned_interfaces/iteration_18/01_results.md',
                 b.ROOT/'docs/reports/overnight_2026-10-03.md'):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)
    return summary
