"""Real shape-Jacobian spectra with physical normal coordinates and resolution checks.

The continuous reciprocal identity uses the existing Kress primal/reciprocal
solves. Five seeded columns are checked against the existing analytic discrete
operator derivative and independent central differences. Real stacking is
mandatory: geometry coefficients are real even though measurements are complex.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter
for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_key, '1')
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.linalg import svd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'solvers'))
from ordered_boundary import circle, ellipse, star, OrderedBoundary2D, PeriodicParameterization2D
from gpr_bem_kress import Material
from gpr_bem_kress.coupled_shape_derivative import build_coupled_base, directional_operators, tangent_response
from gpr_bem_kress.shape_derivative import KressDirection
from gpr_bem_kress.multicomponent import multicomponent_incident_trace_on_boundary
from gpr_bem_kress.execution import execution
from run_star_observability import real_stack, relative, rotate
from audit_star_observability_spectra import rank_intervals
EPS0, MU0 = 8.8541878128e-12, 1.25663706212e-6


class NormalBasis:
    """1,sqrt(2)cos(ms),sqrt(2)sin(ms), with s scaled to one perimeter.

    Each coefficient has units metres and the modes are orthonormal in ds/L.
    The spectral speed primitive follows run_star_observability.star_probes.
    """
    def __init__(self, producer, maximum_mode):
        self.producer, self.maximum_mode = producer, maximum_mode
        t = np.linspace(0, 2*np.pi, 8192, endpoint=False)
        q = np.linalg.norm(producer.evaluate(t).first_derivatives, axis=1)
        modes = np.fft.fftfreq(len(t), 1/len(t))
        primitive = np.zeros(len(t), complex)
        primitive[1:] = np.fft.fft(q)[1:] / (1j*modes[1:])
        p = np.fft.ifft(primitive).real
        self.primitive = CubicSpline(np.r_[t, 2*np.pi], np.r_[p, p[0]], bc_type='periodic')
        self.mean_speed = float(q.mean())
        self.length = self.mean_speed*2*np.pi
        self.modes = [(0, False)] + [(m, s) for m in range(1, maximum_mode+1) for s in (False, True)]

    def values(self, t):
        s = np.asarray(t) + (self.primitive(np.asarray(t) % (2*np.pi))-self.primitive(0.))/self.mean_speed
        return np.stack([np.ones_like(s) if m == 0 else np.sqrt(2)*(np.sin(m*s) if sine else np.cos(m*s))
                         for m, sine in self.modes], axis=-1)

    def jets(self, t, index):
        v = self.producer.evaluate(t)
        x1, x2, x3 = v.first_derivatives, v.second_derivatives, v.third_derivatives
        if x3 is None:
            raise ValueError('Normal jets require a third geometry derivative.')
        q = np.linalg.norm(x1, axis=-1)
        q1 = np.sum(x1*x2, axis=-1)/q
        q2 = (np.sum(x2*x2+x1*x3, axis=-1)-q1*q1)/q
        n = rotate(x1/q[:, None], clockwise=True)
        n1 = rotate(x2/q[:, None]-x1*(q1/q**2)[:, None], clockwise=True)
        n2 = rotate(x3/q[:, None]-2*x2*(q1/q**2)[:, None]-x1*(q2/q**2)[:, None]
                    +2*x1*(q1*q1/q**3)[:, None], clockwise=True)
        m, sine = self.modes[index]
        f = self.values(t)[:, index]
        s = np.asarray(t)+(self.primitive(np.asarray(t) % (2*np.pi))-self.primitive(0.))/self.mean_speed
        fs = np.zeros_like(f) if m == 0 else np.sqrt(2)*m/self.mean_speed*(np.cos(m*s) if sine else -np.sin(m*s))
        f1 = fs*q
        f2 = -(m/self.mean_speed)**2*f*q*q+fs*q1
        return f[:, None]*n, f1[:, None]*n+f[:, None]*n1, f2[:, None]*n+2*f1[:, None]*n1+f[:, None]*n2

    def perturbed(self, index, step):
        def evaluate(t):
            base, jets = self.producer.evaluate(t), self.jets(t, index)
            return tuple(getattr(base, key)+step*v for key, v in zip(
                ('points', 'first_derivatives', 'second_derivatives'), jets))
        return PeriodicParameterization2D(self.producer.component_id, evaluate)


def acquisition(count=12):
    # Same ring and physical offset as the existing star observability study.
    from run_sdf_inverse_comparison import _ring_scan
    return _ring_scan(center=(.5, .5), standoff=.3, num_pairs=count)


def solve(producers, frequency_ghz, epsr, nodes, sources, receivers, exterior_epsr=1., strength=1.):
    boundary = OrderedBoundary2D(tuple(p.discretize(nodes, require_even=True) for p in producers))
    return build_coupled_base(boundary, sources, receivers, 2*np.pi*frequency_ghz*1e9,
                              strength, exterior=Material(exterior_epsr), interior=Material(epsr),
                              eps0=EPS0, mu0=MU0)


def jacobian(base, bases):
    boundary = base.system.geometry
    d, n = multicomponent_incident_trace_on_boundary(boundary, base.receivers, base.system.k_exterior, 1.)
    rhs = np.concatenate((d, n), axis=1).T
    reciprocal = base.factors.solve(rhs)[:boundary.num_nodes]
    primal = base.U[:boundary.num_nodes]
    blocks = []
    for curve, sl, basis in zip(boundary.components, boundary.component_slices, bases):
        weights = basis.values(curve.parameters)*curve.arc_length_weights[:, None]
        blocks.append(np.einsum('np,ns,nr->srp', weights, primal[sl], reciprocal[sl], optimize=True))
    return (base.system.k_interior**2-base.system.k_exterior**2)*np.concatenate(blocks, axis=2)


def spectral(matrix, coarse=None, threshold=1e-3):
    real = real_stack(matrix)
    # Economy SVD when tall; retain all right-null directions when wide.
    _, s, vh = svd(real, full_matrices=real.shape[0] < real.shape[1], lapack_driver='gesvd')
    s = np.pad(s, (0, real.shape[1]-len(s)))
    delta = float(np.linalg.norm(matrix-coarse)) if coarse is not None else 0.
    _, intervals = rank_intervals(s.tolist(), delta, *real.shape, thresholds=(threshold,))
    return s, vh, dict(real_rows=real.shape[0], columns=real.shape[1],
                      structural_nullity=max(0, real.shape[1]-real.shape[0]),
                      rank=int(np.sum(s > threshold*s[0])),
                      first_below_index_0based=next((i for i, v in enumerate(s) if v <= threshold*s[0]), None),
                      coarse_fine_frobenius=delta, refinement_relative_to_sigma1=delta/s[0],
                      rank_interval=intervals[0])


def validate_columns(producer, basis, frequency, epsr, nodes, sources, receivers, columns):
    base = solve((producer,), frequency, epsr, nodes, sources, receivers)
    normal_j = jacobian(base, (basis,))
    scale = float(np.linalg.norm(normal_j.reshape(-1,normal_j.shape[-1]), ord=2))
    rows = []
    t = base.system.geometry.components[0].parameters
    for index in columns:
        direction = KressDirection(*basis.jets(t, int(index)))
        discrete = tangent_response(base, directional_operators(base, (direction,))).T
        for step in (1e-6, 3e-7):
            plus = solve((basis.perturbed(int(index), step),), frequency, epsr, nodes, sources, receivers).Y.T
            minus = solve((basis.perturbed(int(index), -step),), frequency, epsr, nodes, sources, receivers).Y.T
            fd = (plus-minus)/(2*step)
            norm = float(np.linalg.norm(discrete))
            rows.append(dict(column=int(index), mode=basis.modes[index][0], step_m=step,
                             analytic_norm=norm, fd_relative=relative(fd, discrete),
                             fd_absolute=float(np.linalg.norm(fd-discrete)),
                             reciprocal_relative=relative(normal_j[:, :, index], discrete),
                             resolved_column=bool(norm > 1e-8*scale),
                             fd_error_over_jacobian_norm=float(np.linalg.norm(fd-discrete)/scale),
                             reciprocal_error_over_jacobian_norm=float(np.linalg.norm(normal_j[:,:,index]-discrete)/scale)))
    return rows


def circle_mie(frequency, epsr, sources, receivers, radius=.03):
    import gpr_bem_ref
    from scipy.special import hankel1
    k = 2*np.pi*frequency*1e9*np.sqrt(EPS0*MU0)
    modes = np.arange(-60, 61)
    a, b = sources-.5, receivers-.5
    ds, dr = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1)
    phase = np.arctan2(b[:,1], b[:,0])[None,:]-np.arctan2(a[:,1], a[:,0])[:,None]
    ratio = gpr_bem_ref.penetrable_cylinder_scattering_coefficient_ratio(modes, k, k*np.sqrt(epsr), radius)
    return .25j*np.einsum('sm,rm,srm,m->sr', hankel1(modes[None], k*ds[:,None]),
                         hankel1(modes[None], k*dr[:,None]), np.exp(1j*phase[:,:,None]*modes), ratio)


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--nodes', type=int, default=256)
    p.add_argument('--refined-nodes', type=int, default=512)
    p.add_argument('--maximum-mode', type=int, default=40)
    p.add_argument('--frequencies', type=float, nargs='+', default=np.linspace(.5, 8., 12).tolist())
    p.add_argument('--epsr', type=float, nargs='+', default=[2.,4.,9.])
    p.add_argument('--shapes', nargs='+', choices=['circle','ellipse','star'], default=['circle','ellipse','star'])
    args = p.parse_args(argv)
    if args.nodes % 2 or args.refined_nodes % 2 or args.refined_nodes <= args.nodes or args.nodes <= 2*args.maximum_mode:
        p.error('Use even increasing resolutions above twice the maximum shape harmonic.')
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError('Use a new output directory.')
    args.output.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    sources, receivers = acquisition()
    producers = dict(circle=circle((.5,.5), .03), ellipse=ellipse((.5,.5), .04,.025), star=star((.5,.5), .03,.2,5))
    rng = np.random.default_rng(20261002)
    columns = sorted(rng.choice(2*args.maximum_mode+1, min(5, 2*args.maximum_mode+1), replace=False).tolist())
    manifest = dict(command=[sys.executable, '-m', 'experiments.atlas.run_jacobian_spectrum', *sys.argv[1:]],
                    nodes=args.nodes, refined_nodes=args.refined_nodes, maximum_mode=args.maximum_mode,
                    basis='arclength normal harmonics, real orthonormal in ds/L; coefficients in metres',
                    star_mean_radius_m=.03, star_relative_amplitude=.2, ellipse_semiaxes_m=[.04,.025],
                    sources=sources.tolist(), receivers=receivers.tolist(), exterior_epsr=1.,
                    strength=1., threshold=1e-3, seeded_fd_columns=columns,
                    weighting='unwhitened absolute complex fields, real stacked',
                    acquisition='paired-12 existing ring; full-12x12 additional diagnostic with same positions',
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    write_json(args.output/'manifest.json', manifest)
    rows, validation = [], []
    with execution(device='cpu'):
        for name in args.shapes:
            producer = producers[name]
            basis = NormalBasis(producer, args.maximum_mode)
            # Validate at highest frequency/contrast, where high modes are measurable.
            checks = validate_columns(producer, basis, max(args.frequencies), max(args.epsr), args.refined_nodes,
                                      sources, receivers, columns)
            validation.extend([dict(shape=name, frequency_ghz=max(args.frequencies), epsr=max(args.epsr), **r) for r in checks])
            write_json(args.output/'derivative_validation.json', validation)
            # Refuse scientific output if the independent derivative check fails.
            # Near-zero columns cannot be checked by a relative error to that
            # column. Retain their raw ratios and bound their absolute errors
            # against the Jacobian scale used by the spectral cutoff instead.
            if any((r['resolved_column'] and (r['fd_relative'] > 1e-3 or r['reciprocal_relative'] > 1e-3))
                   or r['fd_error_over_jacobian_norm'] > 1e-5
                   or r['reciprocal_error_over_jacobian_norm'] > 1e-5 for r in checks):
                raise RuntimeError(f'{name} derivative validation failed; inspect saved checks.')
            for epsr in args.epsr:
                for frequency in args.frequencies:
                    tick = perf_counter()
                    coarse = solve((producer,), frequency, epsr, args.nodes, sources, receivers)
                    fine = solve((producer,), frequency, epsr, args.refined_nodes, sources, receivers)
                    jc, jf = jacobian(coarse, (basis,)), jacobian(fine, (basis,))
                    key = f'{name}_eps{epsr:g}_f{frequency:.6f}'
                    arrays = dict(jacobian=jf, coarse_jacobian=jc, field=fine.Y.T)
                    for arm in ('paired', 'multistatic'):
                        if arm == 'paired':
                            c, f = jc[np.arange(len(sources)), np.arange(len(sources))], jf[np.arange(len(sources)), np.arange(len(sources))]
                        else:
                            c, f = jc.reshape(-1,jc.shape[-1]), jf.reshape(-1,jf.shape[-1])
                        s, vh, metrics = spectral(f, c)
                        arrays[arm+'_singular_values'], arrays[arm+'_right_vectors'] = s, vh
                        kR = float(fine.system.k_exterior.real*basis.length/(2*np.pi))
                        rows.append(dict(shape=name, epsr=epsr, frequency_ghz=frequency, acquisition=arm,
                                         kR=kR, kiR=kR*np.sqrt(epsr), radius_definition='perimeter/(2*pi)',
                                         field_refinement=relative(coarse.Y, fine.Y),
                                         mie_relative=relative(fine.Y.T, circle_mie(frequency, epsr,sources,receivers)) if name=='circle' else None,
                                         **metrics))
                    np.savez_compressed(args.output/(key+'.npz'), **arrays)
                    write_json(args.output/'spectra.json', rows)
                    print(f'{key} ranks {rows[-2]["rank"]}/{rows[-1]["rank"]}, refinement {rows[-1]["refinement_relative_to_sigma1"]:.2g}, {perf_counter()-tick:.2f}s', flush=True)
    write_json(args.output/'completion.json', dict(seconds=perf_counter()-started, spectra=len(rows), validation_passed=True))
    plot(args.output)


def plot(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = json.loads((output/'spectra.json').read_text())
    names = list(dict.fromkeys(r['shape'] for r in rows))
    fig, axes = plt.subplots(len(names), 3, figsize=(14,4*len(names)), squeeze=False, constrained_layout=True)
    for i,name in enumerate(names):
        selected = [r for r in rows if r['shape']==name and r['acquisition']=='multistatic']
        for epsr in sorted(set(r['epsr'] for r in selected)):
            subset = [r for r in selected if r['epsr']==epsr]
            axes[i,0].plot([r['kR'] for r in subset],[r['rank'] for r in subset], 'o-', label=f'εr={epsr:g}')
            axes[i,1].plot([r['kiR'] for r in subset],[r['rank'] for r in subset], 'o-', label=f'εr={epsr:g}')
        chosen = [r for r in selected if r['epsr']==max(r['epsr'] for r in selected)]
        frequencies = [r['frequency_ghz'] for r in chosen]
        norm = matplotlib.colors.Normalize(min(frequencies), max(frequencies) if len(frequencies)>1 else min(frequencies)+1)
        for r in chosen:
            bundle = np.load(output/f'{name}_eps{r["epsr"]:g}_f{r["frequency_ghz"]:.6f}.npz')
            s = bundle['multistatic_singular_values']
            axes[i,2].semilogy(np.arange(len(s)), np.maximum(s/s[0],1e-16), color=plt.cm.viridis(norm(r['frequency_ghz'])))
        for j,label in enumerate(('exterior kL/(2π)', 'interior kL/(2π)', 'singular index (zero based)')):
            axes[i,j].set_xlabel(label); axes[i,j].set_title(name); axes[i,j].grid(alpha=.2)
        axes[i,0].set_ylabel('rank above 0.001 σ₁'); axes[i,0].legend()
        axes[i,2].axhline(1e-3,color='k',ls=':'); axes[i,2].set_ylim(1e-12,2)
        axes[i,2].set_title(f'{name}, εr={chosen[0]["epsr"]:g}')
        axes[i,2].set_ylabel('σⱼ / σ₁')
        fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap='viridis'),ax=axes[i,2],label='frequency (GHz)')
    fig.savefig(output/'sensitivity_atlas.png',dpi=180); plt.close(fig)
    fig, axes = plt.subplots(1,len(names),figsize=(6*len(names),5),squeeze=False, constrained_layout=True)
    for i,name in enumerate(names):
        r = max((r for r in rows if r['shape']==name), key=lambda r:(r['epsr'],r['frequency_ghz']))
        b = np.load(output/f'{name}_eps{r["epsr"]:g}_f{r["frequency_ghz"]:.6f}.npz')
        im=axes[0,i].imshow(abs(b['multistatic_right_vectors']), aspect='auto', origin='lower', cmap='magma',vmin=0,vmax=1)
        axes[0,i].set_title(f'{name}, εr={r["epsr"]:g}, {r["frequency_ghz"]:g} GHz')
        axes[0,i].set_xlabel('normal harmonic coordinate: 0, cos1, sin1, …'); axes[0,i].set_ylabel('singular direction')
        fig.colorbar(im,ax=axes[0,i],label='absolute coordinate')
    fig.savefig(output/'right_singular_vectors.png',dpi=180); plt.close(fig)

if __name__ == '__main__':
    main()
