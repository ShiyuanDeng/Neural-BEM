"""GC-001 attribution continuation: output-grid aliasing on the same six moves.

The main factorial panel holds the output grid fixed. This continuation varies
only that grid first, then the native primitive's integration grid, without new
fits, new states, or changed production code. See iteration-29 attribution note.
"""
import argparse
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np
from scipy.interpolate import CubicSpline

from bem_inverse.continuation.geometry import FourierCurve, arclength_angles
from bem_inverse.io import read, write, digest, curve_from
from .gc001 import (DEFAULT_OUTPUT, UNIT, moved_curve, sparse_evaluate, field_error)


def resampled(moved, integration_count, output_count, band, *, direct=False):
    """Hold the moved curve fixed; vary integration/target grids independently."""
    nodes=moved.nodes(integration_count)
    angles,_=arclength_angles(nodes)
    inverse=CubicSpline(np.r_[angles,2*np.pi],np.r_[nodes.parameters,2*np.pi])
    target=2*np.pi*np.arange(output_count)/output_count
    theta=inverse(target)
    if direct:
        z,bound=sparse_evaluate(moved.coefficients,moved.modes,theta)
    else:
        position=CubicSpline(np.r_[nodes.parameters,2*np.pi],
                            np.r_[moved.values(integration_count),moved.values(integration_count)[0]],bc_type='periodic')
        z,bound=position(theta),0.
    return FourierCurve.from_samples(z,band).coefficients,bound


def run(output):
    output=Path(output)
    destination=output/'aliasing'
    destination.mkdir(exist_ok=False)
    begin=time.perf_counter()
    try:
        states={r['id']:r for r in read(output/'manifest.json')['states']}
        paths=sorted((output/'interpolation').glob('*.json'))
        assert len(paths)==6
        write(destination/'manifest.json',dict(experiment='GC-001 attribution continuation',
            purpose='same six cases; hold moved curve/inverse/position fixed while varying output-grid FFT sampling',
            physics_calls=0,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            source_sha256=digest(Path(__file__)),main_manifest_sha256=digest(output/'manifest.json'),
            selection_hashes={str(p.relative_to(output)):digest(p) for p in paths}))
        for p in paths:
            selected=read(p)
            item=selected['selection'];state=states[item['state']]
            curve=curve_from(state['curve']);n=state['N'];band=curve.band
            original=read(output/'precision'/item['state']/(item['move']+'.json'))
            a=np.asarray(original['move']['coefficients'])
            moved=moved_curve(curve,a,n)
            base=moved_curve(curve,np.zeros_like(a),n)
            reference=np.array([complex(v['real'],v['imag']) for v in original['reference_coefficients']])
            outputs={}
            for label,integration,direct in [('native_cubic',n,False),('native_inverse_Fourier_position',n,True)]:
                coefficients={}
                bounds={}
                for factor in (1,2,4,8):
                    m,mb=resampled(moved,integration,n*factor,band,direct=direct)
                    b,bb=resampled(base,integration,n*factor,band,direct=direct)
                    coefficients[factor]=curve.coefficients+m-b
                    bounds[factor]=(mb+bb)*UNIT
                outputs[label]=dict(errors={str(f):field_error(v-reference,2*n,state['sigma0'])
                                          for f,v in coefficients.items()},
                    output_4N_8N=field_error(coefficients[4]-coefficients[8],2*n,state['sigma0']),
                    omitted_l1_m=bounds)
            integrations={}
            for factor in (1,2,4,8):
                m,mb=resampled(moved,n*factor,n*8,band,direct=True)
                b,bb=resampled(base,n*factor,n*8,band,direct=True)
                integrations[factor]=curve.coefficients+m-b
            row=dict(selection=item,reference_qualified=original['reference_qualified'],output_grids=outputs,
                integration_grids=dict(errors={str(f):field_error(v-reference,2*n,state['sigma0'])
                                               for f,v in integrations.items()},
                    integration_4N_8N=field_error(integrations[4]-integrations[8],2*n,state['sigma0'])),
                native_reproduction_relative=abs(outputs['native_cubic']['errors']['1']['maximum_m']-
                                              selected['errors']['native']['maximum_m'])/max(selected['errors']['native']['maximum_m'],1e-30))
            assert row['native_reproduction_relative']<1e-5
            write(destination/p.name,row)
            print('ALIASING',selected['rank'],item['state'],flush=True)
        write(destination/'completion.json',dict(completed=True,cases=6,physics_calls=0,seconds=time.perf_counter()-begin))
    except BaseException:
        write(destination/'failure.json',dict(traceback=traceback.format_exc(),seconds=time.perf_counter()-begin))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    run(parser.parse_args().output)
