"""Compare objectives on the same path from a stalled to a recovered state."""
from pathlib import Path
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .run import p,m,read,write
from sdf_inverse.runtime import inverse_execution
from sdf_inverse.radial_topology import evaluate_multiradial_objective
from sdf_inverse.analytic_jacobian import cartesian_residual_jacobian


@inverse_execution
def main():
    root=Path('results/experiments/meeting_20260916')
    output=root/'frequency_escape';output.mkdir(exist_ok=False)
    original=p.driver.deserialize_state(read(root/'far_two_stars_archived_restart/retained_state.json'))
    final=p.driver.deserialize_state(read(root/'far_two_stars_extra_frequencies/retained_state.json'))
    oracle=read(root/'far_two_stars_extra_frequencies/oracle.json')
    observed=np.array(oracle['observed_real'])+1j*np.array(oracle['observed_imag'])
    frequencies=np.array(oracle['frequencies_hz'])
    data=p.ComplexScatteredData(p.driver.baseline._problem(frequencies),observed,np.ones(6)/6)
    solve=p.driver.baseline.iteration01_solve_config();geometry=p.driver.baseline._geometry_config(256)
    delta=final.parameter_vector()-original.parameter_vector()
    rows=[];started=time.monotonic()
    for fraction in (0.,.001,.003,.01,.03,.1,.2,.35,.5,.7,.9,1.):
        state=original.incremented(fraction*delta).polar_angle_gauge_fixed()[0]
        if not p.feasible(state,(256,512),solve,.008):raise RuntimeError('Path crosses inadmissible geometry')
        evaluation=evaluate_multiradial_objective(state,data,geometry,solve_config=solve)
        errors=p.relative(evaluation.prediction,observed)
        row=dict(fraction=fraction,original_four_loss=.5*np.mean(errors[:4]**2),
                 augmented_six_loss=.5*np.mean(errors**2),per_frequency_errors=errors)
        rows.append(row);write(output/'path.json',rows);print(row,flush=True)
    basis=original.gauge_tangent_basis()
    jacobian,_=cartesian_residual_jacobian(original,data,geometry,solve_config=solve,directions=basis)
    original_jacobian=jacobian.reshape(2,24,6,-1)[:,:,:4,:].reshape(-1,len(basis))*np.sqrt(6/4)
    singular_four=np.linalg.svd(original_jacobian,compute_uv=False)
    singular_six=np.linalg.svd(jacobian,compute_uv=False)
    np.savez(output/'jacobians.npz',original_four=original_jacobian,augmented_six=jacobian,basis=basis)
    write(output/'spectrum.json',dict(singular_four=singular_four,singular_six=singular_six,
        minimum_singular_gain=singular_six[-1]/singular_four[-1],seconds=time.monotonic()-started))
    render(rows,singular_four,singular_six,output)


def render(rows,singular_four,singular_six,output):
    fig,axes=plt.subplots(1,2,figsize=(11,4.4))
    for key,label in [('original_four_loss','Original 0.5–1.25 GHz'),('augmented_six_loss','Add 1.75 + 2 GHz')]:
        axes[0].semilogy([r['fraction'] for r in rows],[r[key]/rows[0][key] for r in rows],'-o',label=label)
    axes[0].set(xlabel='Fraction from stalled shape to recovered shape',ylabel='Objective / starting objective',
                ylim=(1e-4,50),title='Original loss rises 23× along this path')
    axes[0].legend();axes[0].grid(alpha=.2)
    for s,label in [(singular_four,'Original four'),(singular_six,'Augmented six')]:
        axes[1].semilogy(np.arange(1,len(s)+1),s,label=label)
    axes[1].set(xlabel='Singular-value index',ylabel='Jacobian singular value at stalled shape',
                title=f'Smallest singular value improves {singular_six[-1]/singular_four[-1]:.1f}×')
    axes[1].legend();axes[1].grid(alpha=.2)
    fig.tight_layout();fig.savefig(output/'frequency_effect.png',dpi=180)


if __name__=='__main__':
    import sys
    if '--plot-only' in sys.argv:
        output=Path('results/experiments/meeting_20260916/frequency_escape')
        spectrum=read(output/'spectrum.json')
        render(read(output/'path.json'),spectrum['singular_four'],spectrum['singular_six'],output)
    else:main()
