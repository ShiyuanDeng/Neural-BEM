"""Render recorded source qualification and a finite-sample nullspace witness."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.constants import c
from solvers.io.fresnel2001 import load_fresnel2001
from .multipole_sources import multipole_basis
from .qualify_sources import ROOT,OUTPUT,near_map,save


def main():
    qualification=json.loads((OUTPUT/'qualification.json').read_text())
    data=load_fresnel2001(ROOT/'data/fresnel/dielTM_dec8f.exp')
    source=data.source_points[0];receiver=data.receiver_points[data.receiver_labels[0]-1]
    k=2*np.pi*data.frequencies_hz[0]/c
    chosen=qualification['local_aperture_cases']['single']['frequencies'][0]['candidates'][3]
    coefficients=np.array(chosen['coefficients_real'])+1j*np.array(chosen['coefficients_imag'])
    x,y=np.meshgrid(np.linspace(-.08,.08,11),np.linspace(-.08,.08,11));target=np.column_stack((x.ravel(),y.ravel()))
    matrix=multipole_basis(receiver,source,k,25)[0];scales=np.linalg.norm(matrix,axis=0)
    _,singular,vh=np.linalg.svd(matrix/scales,full_matrices=True)
    perturbation=vh[-1].conj()/scales
    t=near_map(multipole_basis(target,source,k,25),k)
    near=near_map(multipole_basis(target,source,k,3),k)@coefficients
    perturbation*=.1*np.linalg.norm(near)/np.linalg.norm(t@perturbation)
    witness=dict(frequency_ghz=1,measurement_count=49,complex_coefficients=51,order=25,
        role='single linear-algebra nonidentifiability witness; not a fitted or proposed antenna model',
        relative_incident_change=float(np.linalg.norm(matrix@perturbation)/np.linalg.norm(data.incident[0].mean(axis=0))),
        relative_target_field_and_scaled_gradient_change=float(np.linalg.norm(t@perturbation)/np.linalg.norm(near)),
        coefficient_norm_relative_to_qualified_model=float(np.linalg.norm(perturbation)/np.linalg.norm(coefficients)),
        column_scaled_singular_values=singular,coefficients_real=perturbation.real,coefficients_imag=perturbation.imag,
        interpretation='Finite49point samples cannot identify unrestricted outgoing angular bandwidth. This witness uses large coefficients; an independently justified source-power/aperture bound could exclude it.')
    save(OUTPUT/'nonidentifiability_witness.json',witness)
    rows=[]
    for maximum in (1,3,4):
        path=OUTPUT/f'inverse_{maximum}ghz.json';result=json.loads(path.read_text())
        for arm,record in result['arms'].items():
            new=[s for s in record['stages'] if maximum!=4 or s['maximum_frequency_ghz']==4]
            frequency_evaluations=sum(s['objective_evaluations']*s['maximum_frequency_ghz'] for s in new)
            adapter_factor=2 if arm=='local_multipole' else 1
            rows.append(dict(run_maximum_ghz=maximum,arm=arm,reused_prefix=maximum==4,
                new_objective_frequency_evaluations=frequency_evaluations,
                analytic_jvp_frequency_solves=10*frequency_evaluations,
                endpoint_frequency_evaluations=2*maximum,
                derived_new_dense_factorizations=(10+adapter_factor)*frequency_evaluations+adapter_factor*2*maximum,
                elapsed_recorded_seconds=record['seconds']))
    save(OUTPUT/'work_summary.json',dict(scope='Latest recorded geometry comparisons and position controls; tests and exploratory linear-algebra probes excluded',
        counting='10 parameter JVP solves per objective frequency; line adapter1 forward factorization, multipole adapter2 (reference operator and replacement RHS); endpointN64/N128 counted',
        geometry_rows=rows,position_controls_dense_factorizations=160,
        total_recorded_dense_factorizations=sum(r['derived_new_dense_factorizations'] for r in rows)+160))
    plot(qualification)
    files=list((ROOT/'experiments/fresnel').glob('*multipole*.py'))+[ROOT/'experiments/fresnel'/name for name in
        ('qualify_sources.py','qualify_position_pair.py','audit_source_ceiling.py','compare_qualified_source.py','summarize_source_qualification.py')]
    artifacts=list(OUTPUT.glob('*.json'))+list(OUTPUT.glob('*.npz'))+list(OUTPUT.glob('*.png'))
    save(OUTPUT/'manifest.json',dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        artifact_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts if p.name!='manifest.json'},
        note='Per-run source hashes preserve earlier driver versions; current driver adds4GHz prefix reuse without changing the1–3GHz numerical policy.',
        cpu_only=True,blas_threads=1,production_defaults_changed=False))


def plot(qualification):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    result=json.loads((OUTPUT/'inverse_4ghz.json').read_text())
    arrays=np.load(OUTPUT/'inverse_4ghz.npz')
    ceiling=json.loads((OUTPUT/'higher_order_audit.json').read_text())
    fig,axes=plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
    for arm,label in [('opposite_line','Opposite receiver line source'),('local_multipole','Incident-only multipoles')]:
        p=arrays[arm+'_boundary_m']*1000;p=np.vstack((p,p[0]))
        axes[0].plot(p[:,0],p[:,1],label=label)
        axes[1].plot(np.arange(1,5),result['arms'][arm]['relative_scattered_error'],'o-',label=label)
    axes[0].set(xlabel='x (mm)',ylabel='y (mm)',aspect='equal',title='Recovered through 4 GHz; fixed eps=3')
    axes[0].legend(fontsize=7)
    axes[1].set(xlabel='Frequency (GHz)',ylabel='Relative scattered error',title='Matched cumulative 1→4 GHz inversion')
    axes[1].legend(fontsize=7)
    rows=qualification['local_aperture_cases']['single']['frequencies'][:3]
    chosen=[r['candidates'][r['selected_order']] for r in rows]
    fourth=next(r for r in ceiling['cases']['single']['frequencies'][0]['candidates'] if r['order']==4)
    axes[2].plot([1,2,3,4],[r['mean_validation_error'] for r in chosen]+[fourth['validation_error']],'o-',label='Withheld angles')
    axes[2].plot([1,2,3,4],[r['blocked_front_error'] for r in chosen]+[fourth['blocked_error']],'s-',label='Blocked boresight angles')
    axes[2].plot([1,2,3,4],[r['blocked_target_change'] for r in chosen]+[fourth['blocked_target_change']],'x-',label='Target field + gradient change')
    axes[2].set(xlabel='Frequency (GHz)',ylabel='Relative error / change',title='Incident-only checks; orders 3,3,3,4')
    axes[2].legend(fontsize=7)
    for ax in axes:ax.grid(alpha=.3)
    fig.savefig(OUTPUT/'qualified_comparison.png',dpi=170)
    plt.close(fig)


if __name__=='__main__':main()
