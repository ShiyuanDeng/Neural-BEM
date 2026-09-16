"""Let the residual propose a missing shape harmonic; no truth-informed selection."""
import json
from pathlib import Path
from time import perf_counter
import numpy as np
from .inverse import ShapeChart,ShapeEvaluator,invert,rank_new_shape_modes
from .run_inverse import shape_metrics,save,relative


def main():
    root=Path('results/experiments/modal_muller_20260916')
    output=root/'adaptive_shape_modes'
    output.mkdir(parents=True,exist_ok=True)
    summary=[]
    for case in ['noise_1pct','unmodeled_mode7']:
        inputs=json.loads((root/'hadamard_inverse'/f'{case}_inputs.json').read_text())
        base=json.loads((root/'hadamard_inverse'/f'{case}_native_hadamard_0.json').read_text())
        acq,frequencies=inputs['acquisition'],inputs['frequencies']
        observed=np.array(inputs['observed_real'])+1j*np.array(inputs['observed_imag'])
        chart=ShapeChart(modes=tuple(inputs['fit_modes']))
        x=np.array(base['parameters'])
        tick=perf_counter()
        selection=rank_new_shape_modes(chart,x,acq,frequencies,observed,
            noise_fraction=inputs['noise_fraction'],cutoff=32,bandwidth=48)
        print(case,'mode ranking',json.dumps(selection),flush=True)
        result=None
        if selection['selected_mode'] is not None:
            chart=ShapeChart(chart.modes+(selection['selected_mode'],),chart.anchor,chart.scale)
            result=invert(chart,acq,frequencies,observed,np.r_[x,0.,0.],jacobian_kind='hadamard',
                cutoff=32,bandwidth=48,regularization=.001,continuation=False,verbose=True)
            x=np.array(result['parameters'])
        extra_seconds=perf_counter()-tick
        # Truth appears only here, after the model-selection and optimization work.
        truth_chart=ShapeChart(modes=tuple(inputs['truth_modes']))
        metrics=shape_metrics(chart,x,truth_chart,inputs['truth'])
        y=ShapeEvaluator(chart,acq,frequencies,backend='nodal',nodes=256).forward(x)
        clean=np.array(inputs['clean_real'])+1j*np.array(inputs['clean_imag'])
        metrics.update(observed_data_error=relative(y,observed),clean_data_error=relative(y,clean))
        held_acq=dict(acq)
        angle=.073
        rotate=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        for key in ['source_points','receiver_points']:
            held_acq[key]=((np.array(acq[key])-.5)@rotate.T+.5).tolist()
        held_truth=ShapeEvaluator(truth_chart,held_acq,[.875e9],backend='nodal',nodes=256).forward(inputs['truth'])
        held=ShapeEvaluator(chart,held_acq,[.875e9],backend='nodal',nodes=256).forward(x)
        metrics['held_out_data_error']=relative(held,held_truth)
        record=dict(case=case,selection=selection,result=result,final_modes=chart.modes,
                    final_parameters=x.tolist(),before=base['metrics'],after=metrics,
                    extra_seconds=extra_seconds,total_seconds=base['seconds']+extra_seconds,
                    source_inputs=str(root/'hadamard_inverse'/f'{case}_inputs.json'))
        save(output/(case+'.json'),record)
        summary.append(dict(case=case,selected_mode=selection['selected_mode'],
                            extra_seconds=extra_seconds,before=base['metrics'],after=metrics))
        save(output/'summary.json',summary)
        print('enrichment',json.dumps(summary[-1]),flush=True)


if __name__=='__main__':
    main()
