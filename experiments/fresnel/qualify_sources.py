"""Bounded incident-only outgoing-multipole qualification; no scattering fit.

Run: PYTHONPATH=solvers:. python -m experiments.fresnel.qualify_sources
"""
from __future__ import annotations
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name] = '1'
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from scipy.constants import c
from scipy.special import hankel1
from solvers.io.fresnel2001 import load_fresnel2001, calibrate_line_sources
from .multipole_sources import multipole_basis, fit_multipoles, evaluate_fit

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'results/fresnel/source_qualification'
ORDERS = tuple(range(7))
RCOND = 1e-8
NOISE_RELATIVE = 1e-3
# Gates declared before computing the qualification. The target grid is fixed,
# not fitted to, aligned with, or selected from a recovered/true boundary.
GATES = dict(maximum_validation_error=.10, minimum_improvement_factor=2.,
    maximum_blocked_error=.10, maximum_target_split_change=.05,
    maximum_target_order_change=.05, maximum_target_position_change=.10,
    maximum_target_noise_bound=.05)


def relative(a, b):
    return float(np.linalg.norm(a-b)/np.linalg.norm(b))


def serial(value):
    if hasattr(value, 'tolist'): return value.tolist()
    raise TypeError(type(value).__name__)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=serial)+'\n')


def near_map(bases, k):
    # A single combined norm audits field and wavelength-scaled gradient.
    value, gradient, _ = bases
    return np.concatenate((value, gradient[..., 0]/k, gradient[..., 1]/k), axis=0)


def source_positions(data):
    return data.source_points[0], data.receiver_points[data.receiver_labels[0]-1]


def qualify(data, target, *, local=False):
    source, receivers = source_positions(data)
    slots = np.arange(49)
    window = (slots >= 12) & (slots <= 36) if local else np.ones(49, bool)
    orders = tuple(range(4)) if local else ORDERS
    folds = [window & (slots % 4 == 1), window & (slots % 4 == 3)]
    blocked = ((slots >= 21) & (slots <= 27)) if local else ((slots >= 18) & (slots <= 30))
    baseline = calibrate_line_sources(data)
    rows, arrays = [], {}
    for fi, frequency in enumerate(data.frequencies_hz):
        k = 2*np.pi*frequency/c
        # The physical transmitter is fixed while the target rotates. Averaging
        # equivalent relative angles estimates its field without object data.
        incident = data.incident[fi].mean(axis=0)
        rotational_noise = relative(data.incident[fi], np.broadcast_to(incident, (36,49)))
        candidates = []
        for order in orders:
            a = multipole_basis(receivers, source, k, order)[0]
            t = near_map(multipole_basis(target, source, k, order), k)
            fit = fit_multipoles(a[window], incident[window], rcond=RCOND)
            near = t@fit.coefficients
            validation, split_near, fold_fits = [], [], []
            for heldout in folds:
                partial = fit_multipoles(a[window & ~heldout], incident[window & ~heldout], rcond=RCOND)
                validation.append(relative(a[heldout]@partial.coefficients, incident[heldout]))
                split_near.append(t@partial.coefficients)
                fold_fits.append(partial)
            blocked_fit = fit_multipoles(a[window & ~blocked], incident[window & ~blocked], rcond=RCOND)
            blocked_error = relative(a[blocked]@blocked_fit.coefficients, incident[blocked])
            blocked_target = relative(t@blocked_fit.coefficients, near)
            # Exact worst-case bound for any complex perturbation of this size.
            gain = np.linalg.norm(t@fit.inverse_map, 2)*np.linalg.norm(incident[window])/np.linalg.norm(near)
            shifts = []
            for ds, dr in ((-.003,0),(.003,0),(0,-.003),(0,.003)):
                moved_source = source*(1+ds/np.linalg.norm(source))
                moved_receivers = receivers*(1+dr/np.linalg.norm(receivers[0]))
                perturbed_a = multipole_basis(moved_receivers,moved_source,k,order)[0]
                perturbed_fit = fit_multipoles(perturbed_a[window],incident[window],rcond=RCOND)
                perturbed_t = near_map(multipole_basis(target,moved_source,k,order),k)
                perturbed_near=perturbed_t@perturbed_fit.coefficients
                gauge=np.vdot(near,perturbed_near)/np.vdot(near,near)
                shifts.append(dict(source_radius_delta_m=ds,receiver_radius_delta_m=dr,
                    target_relative_change=relative(perturbed_near,near),
                    target_change_after_best_global_complex_gain=float(np.linalg.norm(perturbed_near-gauge*near)/np.linalg.norm(near)),
                    best_global_complex_gain_real=float(gauge.real),best_global_complex_gain_imag=float(gauge.imag)))
            inverse_norm = np.linalg.norm(fit.inverse_map,2)
            row = dict(order=order,parameters_complex=2*order+1,rank=fit.rank,
                scaled_condition=fit.scaled_condition,singular_values=fit.singular_values,
                train_relative_error=fit.relative_residual,validation_errors=validation,
                mean_validation_error=float(np.mean(validation)),blocked_front_error=blocked_error,
                blocked_target_change=blocked_target,target_split_change=relative(split_near[0],split_near[1]),
                target_noise_bound_0p1percent=NOISE_RELATIVE*gain,
                coefficient_noise_bound_0p1percent=float(NOISE_RELATIVE*inverse_norm*np.linalg.norm(incident[window])/np.linalg.norm(fit.coefficients)),
                position_perturbations=shifts,maximum_target_position_change=max(r['target_relative_change'] for r in shifts),
                coefficients_real=fit.coefficients.real,coefficients_imag=fit.coefficients.imag)
            candidates.append(row)
            arrays[f'f{fi}_m{order}_near'] = near
            arrays[f'f{fi}_m{order}_incident'] = a@fit.coefficients
        # Select on held-out incident data only, with a fixed parsimony tolerance.
        best = min(row['mean_validation_error'] for row in candidates)
        selected = next(row for row in candidates if row['mean_validation_error'] <= 1.15*best+.002)
        order = selected['order']
        neighbor = order+1 if order < max(orders) else order-1
        order_change = relative(arrays[f'f{fi}_m{neighbor}_near'],arrays[f'f{fi}_m{order}_near'])
        baseline_heldout = np.mean([relative(baseline.predicted_incident[fi].mean(axis=0)[held], incident[held]) for held in folds])
        gate = dict(validation=selected['mean_validation_error']<GATES['maximum_validation_error'],
            improvement=selected['mean_validation_error']*GATES['minimum_improvement_factor']<baseline_heldout,
            blocked_front=selected['blocked_front_error']<GATES['maximum_blocked_error'],
            target_split=max(selected['target_split_change'],selected['blocked_target_change'])<GATES['maximum_target_split_change'],
            target_order=order_change<GATES['maximum_target_order_change'],
            target_position=selected['maximum_target_position_change']<GATES['maximum_target_position_change'],
            target_noise=selected['target_noise_bound_0p1percent']<GATES['maximum_target_noise_bound'])
        row = dict(frequency_hz=frequency, rotational_incident_relative_variation=rotational_noise,
            opposite_calibration_full_error=baseline.relative_incident_error[fi],
            opposite_calibration_validation_error=baseline_heldout,selected_order=order,
            selected_neighbor_order=neighbor,selected_target_order_change=order_change,
            numerically_qualified=all(gate.values()),gates=gate,candidates=candidates)
        rows.append(row)
        print(json.dumps({k:v for k,v in row.items() if k!='candidates'}, default=serial),flush=True)
    return rows, arrays


def synthetic_aperture_control(target):
    """Independent finite line-source aperture, not a multipole-generated truth."""
    source=np.array([.72,0.]); angle=np.deg2rad(np.arange(60,301,5))
    receivers=.76*np.column_stack((np.cos(angle),np.sin(angle)))
    aperture=source+np.array([[-.008,-.022],[.003,-.011],[.006,0.],[.003,.011],[-.008,.022]])
    strengths=np.array([.08+.03j,.2-.01j,.44,.2+.01j,.08-.03j])
    def exact(points,k):
        delta=points[:,None]-aperture[None]
        r=np.linalg.norm(delta,axis=-1)
        value=(.25j*hankel1(0,k*r))@strengths
        gradient=np.einsum('pa,pad,a->pd',-.25j*k*hankel1(1,k*r),delta/r[...,None],strengths)
        return np.concatenate((value,gradient[:,0]/k,gradient[:,1]/k))
    rows=[]
    rng=np.random.default_rng(2001)
    held=np.arange(49)%4==1
    for ghz in (1,4,8):
        k=2*np.pi*ghz*1e9/c
        measured=exact(receivers,k)[:49]
        target_exact=exact(target,k)
        noise=rng.normal(size=49)+1j*rng.normal(size=49)
        noise*=NOISE_RELATIVE*np.linalg.norm(measured)/np.linalg.norm(noise)
        for noise_level in (0.,1.):
            y=measured+noise_level*noise
            candidates=[]
            for order in ORDERS:
                a=multipole_basis(receivers,source,k,order)[0]
                fit=fit_multipoles(a[~held],y[~held],rcond=RCOND)
                candidates.append((relative(a[held]@fit.coefficients,y[held]),order))
            best=min(error for error,order in candidates)
            order=next(order for error,order in candidates if error<=1.15*best+.002)
            a=multipole_basis(receivers,source,k,order)[0]
            fit=fit_multipoles(a,y,rcond=RCOND)
            t=near_map(multipole_basis(target,source,k,order),k)
            rows.append(dict(frequency_ghz=ghz,relative_added_noise=NOISE_RELATIVE*noise_level,
                selected_order=order,heldout_error=candidates[order][0],
                target_field_and_scaled_gradient_error=relative(t@fit.coefficients,target_exact)))
    return rows


def main():
    started=time.perf_counter()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    axis=np.linspace(-.08,.08,11)
    x,y=np.meshgrid(axis,axis)
    target=np.column_stack((x.ravel(),y.ravel()))
    report=dict(model='source-centered outgoing Helmholtz multipoles, common rotated antenna coefficients',
        orders=ORDERS,rcond=RCOND,selection='smallest order within 15 percent plus .002 of minimum mean withheld incident error',
        validation_slots=[np.flatnonzero(np.arange(49)%4==i) for i in (1,3)],
        blocked_validation_slots=list(range(18,31)),target_grid_bounds_m=[[-.08,-.08],[.08,.08]],
        synthetic_relative_noise=NOISE_RELATIVE,gates=GATES,
        calibration_uses='incident columns only; no scattered measurements or target geometry',
        target_interpretation='conditional on 2D point-field measurements and a compact antenna source; receive-pattern de-embedding is not identified',
        cases={},synthetic_aperture_control=synthetic_aperture_control(target))
    arrays=dict(target_points_m=target)
    for label,filename in [('single','dielTM_dec8f.exp'),('twin','twodielTM_8f.exp')]:
        data=load_fresnel2001(ROOT/'data/fresnel'/filename)
        rows,local=qualify(data,target)
        report['cases'][label]=dict(data_sha256=data.source_sha256,frequencies=rows)
        arrays.update({f'{label}_{key}':value for key,value in local.items()})
    report['local_aperture_cases']={}
    for label,filename in [('single','dielTM_dec8f.exp'),('twin','twodielTM_8f.exp')]:
        data=load_fresnel2001(ROOT/'data/fresnel'/filename)
        rows,local=qualify(data,target,local=True)
        report['local_aperture_cases'][label]=dict(data_sha256=data.source_sha256,frequencies=rows,
            fit_slots=list(range(12,37)),blocked_slots=list(range(21,28)),orders=list(range(4)),
            rationale='120..240 degree receiver window covers source angles about ±31 degrees; blocked165..195 degree receivers cover source angles about ±8 degrees, matching fixed target box angular support')
        arrays.update({f'local_{label}_{key}':value for key,value in local.items()})
    report['elapsed_seconds']=time.perf_counter()-started
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'experiments/fresnel/multipole_sources.py',Path(__file__),ROOT/'solvers/io/fresnel2001.py')}
    save(OUTPUT/'qualification.json',report)
    np.savez_compressed(OUTPUT/'calibration.npz',**arrays)
    plot(report,arrays)


def plot(report, arrays):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
    rows=report['cases']['single']['frequencies']
    frequencies=np.arange(1,9)
    selected=[row['candidates'][row['selected_order']] for row in rows]
    axes[0].semilogy(frequencies,[r['opposite_calibration_validation_error'] for r in rows],'o-',label='Opposite-receiver line source')
    axes[0].semilogy(frequencies,[r['mean_validation_error'] for r in selected],'s-',label='Selected multipoles: held out')
    axes[0].semilogy(frequencies,[r['blocked_front_error'] for r in selected],'x-',label='Blocked central angles')
    axes[0].set(xlabel='Frequency (GHz)',ylabel='Relative incident error',title='Incident-only validation')
    axes[0].legend(fontsize=7)
    for fi in (0,3,7):
        axes[1].semilogy(ORDERS,[r['mean_validation_error'] for r in rows[fi]['candidates']],'.-',label=f'{fi+1} GHz')
    axes[1].set(xlabel='Maximum multipole order',ylabel='Withheld incident error',title='Fixed order range 0–6')
    axes[1].legend()
    axes[2].plot(frequencies,[r['selected_target_order_change'] for r in rows],'o-',label='Adjacent order')
    axes[2].plot(frequencies,[r['maximum_target_position_change'] for r in selected],'s-',label='±3 mm antenna position')
    axes[2].plot(frequencies,[r['target_noise_bound_0p1percent'] for r in selected],'x-',label='0.1% noise upper bound')
    axes[2].set(xlabel='Frequency (GHz)',ylabel='Relative field + scaled gradient change',title='Continuation into fixed ±80 mm region')
    axes[2].legend(fontsize=7)
    for ax in axes:ax.grid(alpha=.3)
    fig.savefig(OUTPUT/'qualification.png',dpi=160)
    plt.close(fig)


if __name__=='__main__':main()
