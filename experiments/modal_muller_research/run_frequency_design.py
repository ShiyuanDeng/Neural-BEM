"""Use a rejected mode's sensitivity to choose one new measurement frequency.

Frequency selection sees the current estimate, acquisition, and leading
residual candidate. Truth is consulted only by the synthetic instrument after
selection, and by independent final validation. The same procedure is run on
the noise-only control. Model-selection thresholds remain unchanged.
"""
import hashlib
import json
from pathlib import Path
from time import perf_counter
import numpy as np
from .inverse import ShapeChart,real_stack
from .coupled_inverse import SceneChart,SceneEvaluator,invert_scene,rank_scene_modes
from .run_coupled_inverse import FREQUENCIES,chart_record,metrics
from .run_inverse import save,relative


def chart_from_record(record):
    return SceneChart(tuple(ShapeChart(tuple(c['modes']),complex(*c['anchor']),c['scale']) for c in record))


def choose_frequency(chart,x,acq,target,candidates=(1.5e9,1.75e9,2.e9,2.5e9)):
    tick=perf_counter()
    expanded,v=chart.expanded(x,[target]);rows=[]
    component,mode=target
    c,sl=expanded.charts[component],expanded.slices[component]
    start=sl.start+3+2*c.modes.index(mode)
    old=np.concatenate([np.arange(sl.start,sl.start+c.size) for c,sl in zip(chart.charts,expanded.slices)])
    for frequency in candidates:
        e=SceneEvaluator(expanded,acq,[frequency],cutoff=32,bandwidth=56,terms=32,angular_order=32)
        prediction=e.forward(v)
        jac=real_stack(e.sensitivity(v).dense()/np.linalg.norm(prediction))
        u,s,_=np.linalg.svd(jac[:,old],full_matrices=False)
        nuisance=u[:,s>1e-10*s[0]]
        candidate=jac[:,start:start+2]
        candidate=candidate-nuisance@(nuisance.T@candidate)
        values=np.linalg.svd(candidate,compute_uv=False)
        rows.append(dict(frequency_hz=frequency,projected_singular_values=values.tolist(),score=float(values[-1]**2)))
    best=max(rows,key=lambda row:row['score'])
    return dict(target_component=component,target_mode=mode,candidates=rows,
                selected_frequency_hz=best['frequency_hz'],seconds=perf_counter()-tick,
                selection_uses_truth=False,criterion='Maximize the weaker normalized candidate sensitivity after projecting out existing shape directions.')


def qualify_final(root):
    output=root/'frequency_design';rows=[]
    for case in ['noise_1pct','missing_two_modes']:
        record=json.loads((output/(case+'.json')).read_text())
        acq=json.loads((root/(case+'_inputs.json')).read_text())['acquisition']
        chart=chart_from_record(record['final_chart']);x=np.array(record['final_parameters'])
        frequency=[record['design']['selected_frequency_hz']]
        ref=SceneEvaluator(chart,acq,frequency,backend='nodal',nodes=256)
        y=ref.forward(x);j=ref.base.operator_jacobian(True)
        e=SceneEvaluator(chart,acq,frequency,cutoff=32,bandwidth=56,terms=32,angular_order=32)
        native=e.forward(x);f=e.sensitivity(x,'traces');jac=f.dense()
        direction=np.random.default_rng(78).normal(size=chart.size);direction/=np.linalg.norm(direction)
        h=1e-4
        finite=(e.forward(x+h*direction)-e.forward(x-h*direction))/(2*h)
        rows.append(dict(case=case,frequency_hz=frequency[0],data_error=relative(native,y),
            jacobian_error=relative(jac,j),worst_column_error=float(np.max(
                np.linalg.norm(jac-j,axis=(0,1))/np.linalg.norm(j,axis=(0,1)))),
            finite_difference_error=relative(f.matvec(direction),finite)))
    save(output/'final_derivatives.json',rows)
    print('final derivative qualification',json.dumps(rows),flush=True)


def main():
    root=Path('results/experiments/modal_muller_20260916/coupled_inverse')
    output=root/'frequency_design';output.mkdir(parents=True,exist_ok=True)
    summary=[]
    for case_index,case in enumerate(['noise_1pct','missing_two_modes']):
        raw=json.loads((root/(case+'_inputs.json')).read_text())
        previous=json.loads((root/(case+'_enrichment.json')).read_text())
        chart=chart_from_record(previous['final_chart']);x=np.array(previous['final_parameters'])
        acq=raw['acquisition']
        observed=np.array(raw['observed_real'])+1j*np.array(raw['observed_imag'])
        clean=np.array(raw['clean_real'])+1j*np.array(raw['clean_imag'])
        leading=previous['rounds'][-1]['selection']['ranking'][0]
        tick=perf_counter()
        design=choose_frequency(chart,x,acq,(leading['component'],leading['mode']))
        print('frequency design',case,json.dumps(design),flush=True)
        # The synthetic instrument is called only after choosing the frequency.
        truth_chart=chart_from_record(raw['truth_chart']);truth=np.array(raw['truth'])
        frequency=design['selected_frequency_hz']
        data_tick=perf_counter()
        fresh=SceneEvaluator(truth_chart,acq,[frequency],backend='nodal',nodes=256).forward(truth)
        finer=SceneEvaluator(truth_chart,acq,[frequency],backend='nodal',nodes=384).forward(truth)
        rng=np.random.default_rng(20260930+case_index)
        noise=rng.normal(size=fresh.shape)+1j*rng.normal(size=fresh.shape)
        noise*=.01*np.linalg.norm(fresh)/np.linalg.norm(noise)
        observations=np.concatenate((observed,fresh+noise))
        data_seconds=perf_counter()-data_tick
        frequencies=FREQUENCIES+[frequency]
        options=dict(cutoff=32,bandwidth=56,terms=32,angular_order=32)
        base=invert_scene(chart,acq,frequencies,observations,x,continuation=False,**options)
        x=np.array(base['parameters']);rounds=[]
        for _ in range(2):
            selection=rank_scene_modes(chart,x,acq,frequencies,observations,noise_fraction=.01,**options)
            print('new data selection',case,json.dumps(selection),flush=True)
            record=dict(selection=selection);rounds.append(record)
            if selection['selected'] is None:
                break
            chart,x=chart.expanded(x,[selection['selected']])
            result=invert_scene(chart,acq,frequencies,observations,x,continuation=False,**options)
            x=np.array(result['parameters']);record['result']=result
        compute_seconds=perf_counter()-tick-data_seconds
        after=metrics(chart,x,truth_chart,truth,acq,observed,clean)
        native=SceneEvaluator(chart,acq,frequencies,**options).forward(x)
        reference=SceneEvaluator(chart,acq,frequencies,backend='nodal',nodes=256).forward(x)
        record=dict(case=case,design=design,refit=base,rounds=rounds,compute_seconds=compute_seconds,
                    synthetic_instrument_seconds=data_seconds,new_oracle_256_384_error=relative(fresh,finer),
                    final_native_nodal_error=relative(native,reference),training_data_error=relative(reference,observations),
                    final_chart=chart_record(chart),final_parameters=x.tolist(),before=previous['after'],after=after,
                    observations_real=observations.real.tolist(),observations_imag=observations.imag.tolist(),
                    extra_noise_seed=20260930+case_index)
        save(output/(case+'.json'),record)
        summary.append(dict(case=case,frequency_hz=frequency,accepted=[r['selection']['selected'] for r in rounds
                            if r['selection']['selected'] is not None],compute_seconds=compute_seconds,
                            before=previous['after'],after=after,new_oracle_error=record['new_oracle_256_384_error'],
                            native_nodal_error=record['final_native_nodal_error']))
        save(output/'summary.json',summary)
        print('frequency result',json.dumps(summary[-1]),flush=True)
    qualify_final(root)
    save(output/'manifest.json',dict(source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
         for p in Path('experiments/modal_muller_research').glob('*.py')},
         scope='One extra independently simulated frequency for each case, including the noise-only control; fixed 1% noise; unchanged mode-selection threshold.'))


if __name__=='__main__':
    main()
