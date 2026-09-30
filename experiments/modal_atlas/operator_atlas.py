"""MA-006: persistent modal operators and projection/reduced/Schur cutoff controls.

Run under EMNerf with PYTHONPATH=solvers:., one BLAS thread, from the repo root.
The stored-parameter flux/DFT basis is deliberately distinct from MA-001's
arclength trace projection. No production defaults or historical modules change.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np
from scipy.linalg import lu_factor, lu_solve, svdvals

from experiments.modal_muller_research.modal import ModalSystem, fft_left, mode_indices
from experiments.shape_continuation import forward as F
from experiments.shape_continuation.atlas import orthonormal_normal_basis
from experiments.shape_continuation.geometry import FourierCurve
from gpr_bem_kress.execution import execution

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'docs/iterations/modal_atlas/iteration_06/03_plan.md'
CUTOFFS = (8, 12, 16, 24, 32, 48, 64, 96, 128, 192)
NODES, REFINED, BAND, DIRECTION_BAND = 512, 1024, 12, 192
SELECTED = (0, 11)  # constant, cosine-6 in interleaved atlas columns
LIMITS = dict(data_grid=1e-7, jacobian_grid=1e-5, finite_derivative=1e-4,
              derivative_refinement=5e-3, direction_projection=1e-4, algebra=1e-9)


def relative(value, reference):
    return float(np.linalg.norm(value-reference)/max(np.linalg.norm(reference), 1e-300))


def write(path, value):
    def default(x):
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, np.generic):
            return x.item()
        raise TypeError(type(x).__name__)
    Path(path).write_text(json.dumps(value, default=default, indent=2, allow_nan=False)+'\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable_cutoff(rows, predicate):
    for j, row in enumerate(rows):
        if all(predicate(r) for r in rows[j:]):
            return row['cutoff']
    return None


def cutoff_solve(a, b, exact, retained):
    """Three factorizations; exact Schur control includes omitted RHS and traces."""
    omitted = np.setdiff1d(np.arange(len(a)), retained)
    ll, lh = a[np.ix_(retained, retained)], a[np.ix_(retained, omitted)]
    hl, hh = a[np.ix_(omitted, retained)], a[np.ix_(omitted, omitted)]
    started = time.perf_counter()
    factors = lu_factor(ll)
    reduced = np.zeros_like(b)
    reduced[retained] = lu_solve(factors, b[retained])
    reduced_seconds = time.perf_counter()-started
    started = time.perf_counter()
    high_factors = lu_factor(hh)
    high_action = lu_solve(high_factors, np.column_stack((hl, b[omitted])))
    elimination, high_rhs = high_action[:, :len(retained)], high_action[:, len(retained):]
    correction, rhs_correction = lh @ elimination, lh @ high_rhs
    schur = np.zeros_like(b)
    schur[retained] = lu_solve(lu_factor(ll-correction), b[retained]-rhs_correction)
    schur[omitted] = high_rhs-elimination @ schur[retained]
    schur_seconds = time.perf_counter()-started
    feedback = lu_solve(factors, lh @ exact[omitted])
    singular = svdvals(ll)
    return dict(reduced=reduced, schur=schur, feedback=feedback, factors=factors,
                omitted=omitted, correction=correction, rhs_correction=rhs_correction,
                condition=float(singular[0]/singular[-1]),
                reduced_seconds=reduced_seconds, schur_seconds=schur_seconds)


def discrete_tangent(a, b, c, da, db, dc, retained, *, factors=None, state=None):
    """Derivative of the actual retained system, including both acquisition maps."""
    if factors is None:
        factors = lu_factor(a[np.ix_(retained, retained)])
    if state is None:
        state = lu_solve(factors, b[retained])
    tangent = lu_solve(factors, db[retained]-da[np.ix_(retained, retained)] @ state)
    return dc[:, retained] @ state + c[:, retained] @ tangent


def directions(shape, band=BAND, window=DIRECTION_BAND):
    """Fixed Cartesian velocities; no moving/reparameterized basis in differences."""
    curve = shape.nodes(4096)
    h = orthonormal_normal_basis(curve, band)
    normal = curve.normals[:, 0]+1j*curve.normals[:, 1]
    dz = np.fft.fft(h*normal[:, None], axis=0)/curve.num_nodes
    return dz[np.arange(-window, window+1) % curve.num_nodes]


def actual_basis(shape, coefficients, nodes):
    velocity = np.stack([FourierCurve(c).values(nodes) for c in coefficients.T], axis=1)
    curve = shape.nodes(nodes)
    normal = curve.normals[:, 0]+1j*curve.normals[:, 1]
    return np.real(velocity*normal.conj()[:, None])


def moved(shape, direction, step):
    width = len(direction)//2
    coefficients = np.zeros(len(direction), complex)
    coefficients[width-shape.band:width+shape.band+1] = shape.coefficients
    return FourierCurve(coefficients+step*direction)


def maps(shape, k, contrast, acquisition, nodes, matrix=None):
    """Build nodal reference maps then use the existing flux/DFT similarity."""
    curve = shape.nodes(nodes)
    assemble, receivers, incident = F._operators(curve)
    with execution(kernels='reference', device='cpu'):
        if matrix is None:
            matrix = np.asarray(assemble(curve, k, k*np.sqrt(contrast)).system_matrix)
        field, normal = incident(curve, acquisition.sources, k, acquisition.strength)
        rfield, rnormal = incident(curve, acquisition.receivers, k)
        b = np.column_stack((np.vstack((field.T, normal.T)), np.vstack((rfield.T, rnormal.T))))
        c = receivers(curve, acquisition.receivers, k).state_rows
    return ModalSystem.from_nodal(matrix, b, c, (curve,))


def physical(modal, z):
    return fft_left(z, modal.curves, inverse=True)/modal.scale[:, None]


def quantities(modal, z, h, k, contrast, count):
    traces = physical(modal, z)
    n = modal.curves[0].num_nodes
    product = traces[:n, :count]*traces[:n, count:]
    jacobian = (contrast-1)*k*k * ((product*modal.curves[0].arc_length_weights[:, None]).T @ h)
    data = np.diag(modal.c @ z[:, :count])
    return data, jacobian


def local_update(data, jacobian, observed, scale, ridge):
    j, residual = jacobian/scale, (data-observed)/scale
    gradient = np.real(j.conj().T @ residual)
    step = np.linalg.solve(np.real(j.conj().T @ j)+ridge*np.eye(j.shape[1]), -gradient)
    return gradient, step


def case_specs():
    from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast
    observations = ast.catalog_only('circle_to_c')
    catalog = {round(f/1e9, 3): o for f, o in zip(ac.CATALOG_HZ, observations)}
    states = dict(circle=FourierCurve.circle(), star=ac.truth_curve('circle_to_star'),
                  c=ac.truth_curve('circle_to_c'))
    paths = [ast.source_folder('circle_to_c') / 'observations.json']
    for name, scene in [('star_D', 'shifted_star'), ('c_D', 'development_c')]:
        path = ROOT / f'results/validation/modal_atlas/MA-004/runs/D/c13.3/{scene}/result.json'
        states[name] = ast.curve_from(json.loads(path.read_text())['final_curve'])
        paths.append(path)
    settings = [('circle', .5, .5), ('circle', .5, 2.5), ('circle', 13.3, 2.5),
                ('star', .5, .5), ('star', .5, 2.5), ('star', 13.3, 2.5),
                ('c', .5, 2.5), ('c', 13.3, 2.5), ('star_D', 13.3, 2.5), ('c_D', 13.3, 2.5)]
    return [(f'{name}_c{contrast:g}_f{frequency:g}', states[name], contrast, frequency, catalog[frequency])
            for name, contrast, frequency in settings], paths


def collect_cell(spec, folder):
    name, shape, contrast, frequency, observation = spec
    k, acq = observation.wavenumber, observation.acquisition
    count = len(acq.sources)
    started = time.perf_counter()
    work = dict(nodal_assemblies=0, nodal_factorizations=0, modal_factorizations=0,
                reference_rhs_columns=0, reduced_rhs_columns=0, derivative_rhs_columns=0)
    folder.mkdir(parents=True, exist_ok=False)
    coeff = directions(shape)
    h = actual_basis(shape, coeff, NODES)
    qualification = dict(direction_projection=relative(h, orthonormal_normal_basis(shape.nodes(NODES), BAND)))
    states = []
    for n in (NODES, REFINED):
        full_acq = F.PointSourceAcquisition(acq.sources, acq.receivers, acq.strength, paired=False)
        state = F.solve(shape, k, contrast, full_acq, n)
        work['nodal_assemblies'] += 1
        work['nodal_factorizations'] += 1
        modal = maps(shape, k, contrast, acq, n, state.matrix)
        # Reuse nodal LU for both forward and reciprocal fields. No modal factorization.
        rhs_physical = physical(modal, modal.b)
        traces, _ = F._solve(state.matrix, state.factors, rhs_physical)
        work['reference_rhs_columns'] += count*3  # original forward + joint solve
        z = fft_left(traces*modal.scale[:, None], modal.curves)
        hn = actual_basis(shape, coeff, n)
        y, j = quantities(modal, z, hn, k, contrast, count)
        states.append((state, modal, z, y, j))
    state, modal, exact, y, jac = states[0]
    refined_y, refined_j = states[1][3:]
    qualification.update(data_grid=relative(y, refined_y), jacobian_grid=relative(jac, refined_j),
                         algebra=relative(modal.a @ exact, modal.b),
                         modal_nodal_data=relative(y, np.diag(state.prediction)))
    # Fixed normalized local residual and fixed ridge across every arm.
    eta = np.zeros(2*BAND+1)
    eta[[0, 5, 12]] = [1, -.7, .4]
    scale = np.linalg.norm(y)
    response = jac @ eta
    observed = y+.01*scale*response/np.linalg.norm(response)
    ridge = float(1e-3*svdvals(jac/scale)[0]**2)
    gradient, step = local_update(y, jac, observed, scale, ridge)
    arrays = dict(A=modal.a, B=modal.b, R=modal.c, trace_coefficients=exact,
                  geometry_coefficients=shape.coefficients, direction_coefficients=coeff,
                  h=h, points=state.curve.points, normals=state.curve.normals,
                  weights=state.curve.arc_length_weights, speed=state.curve.speeds,
                  modes=np.fft.fftfreq(NODES)*NODES, flux_scale=modal.scale,
                  sources=acq.sources, receivers=acq.receivers, source_strength=np.asarray(acq.strength),
                  y_reference=y, J_reference=jac, y_refined=refined_y, J_refined=refined_j,
                  diagnostic_observed=observed, diagnostic_gradient=gradient, diagnostic_step=step,
                  selected_columns=np.array(SELECTED), ridge=np.array(ridge))
    derivatives, derivative_rows = [], []
    for column in SELECTED:
        differences = []
        eps = 1e-4*np.sqrt(state.curve.perimeter)
        for delta in (eps, eps/2):
            sides = [maps(moved(shape, coeff[:, column], sign*delta), k, contrast, acq, NODES)
                     for sign in (1, -1)]
            work['nodal_assemblies'] += 2
            differences.append(tuple((getattr(sides[0], field)-getattr(sides[1], field))/(2*delta)
                                     for field in ('a', 'b', 'c')))
        derivative = differences[-1]
        da, db, dc = derivative
        # Differentiate full modal system via the original nodal LU.
        forcing = db-da @ exact
        tangent_phys, _ = F._solve(state.matrix, state.factors, physical(modal, forcing))
        tangent = fft_left(tangent_phys*modal.scale[:, None], modal.curves)
        dy = np.diag(dc @ exact[:, :count]+modal.c @ tangent[:, :count])
        work['derivative_rhs_columns'] += 2*count
        row = dict(column=column, rms_step=5e-5,
                   map_refinement={label:relative(fine, coarse) for label, fine, coarse
                                   in zip(('A','B','R'), differences[1], differences[0])},
                   data_derivative_error=relative(dy, jac[:, column]))
        derivative_rows.append(row)
        derivatives.append(derivative)
        arrays[f'dA_{column}'], arrays[f'dB_{column}'], arrays[f'dR_{column}'] = derivative
        arrays[f'dy_discrete_{column}'] = dy
    qualification['finite_derivative'] = max(r['data_derivative_error'] for r in derivative_rows)
    qualification['derivative_refinement'] = max(max(r['map_refinement'].values()) for r in derivative_rows)
    rows = []
    for cutoff in CUTOFFS:
        retained = mode_indices(modal.curves, cutoff)
        solved = cutoff_solve(modal.a, modal.b, exact, retained)
        work['modal_factorizations'] += 3
        work['reduced_rhs_columns'] += 2*count
        omitted = solved['omitted']
        projected = np.zeros_like(exact)
        projected[retained] = exact[retained]
        row = dict(cutoff=cutoff, unknowns=len(retained), full_unknowns=len(modal.a),
                   retained_condition=solved['condition'], reduced_seconds=solved['reduced_seconds'],
                   schur_seconds=solved['schur_seconds'], arms={},
                   feedback_relative=float(np.linalg.norm(solved['feedback'])/np.linalg.norm(exact[retained])),
                   feedback_identity_error=float(np.linalg.norm(solved['reduced'][retained]-exact[retained]-solved['feedback'])/np.linalg.norm(exact[retained])),
                   schur_trace_error=relative(solved['schur'], exact),
                   schur_correction_relative=float(np.linalg.norm(solved['correction'])/np.linalg.norm(modal.a[np.ix_(retained,retained)])),
                   schur_rhs_correction_relative=float(np.linalg.norm(solved['rhs_correction'])/np.linalg.norm(modal.b[retained])),
                   tails={}, block_coupling={})
        for block, offset in [('dirichlet', 0), ('flux', NODES)]:
            high = omitted[(omitted>=offset)&(omitted<offset+NODES)]
            for illumination, cols in [('source',slice(0,count)), ('reciprocal',slice(count,None))]:
                row['tails'][block+'_'+illumination] = float(np.linalg.norm(exact[high,cols])/np.linalg.norm(exact[offset:offset+NODES,cols]))
        for i in range(2):
            for j in range(2):
                il = retained[(retained>=i*NODES)&(retained<(i+1)*NODES)]
                jh = omitted[(omitted>=j*NODES)&(omitted<(j+1)*NODES)]
                ih = omitted[(omitted>=i*NODES)&(omitted<(i+1)*NODES)]
                jl = retained[(retained>=j*NODES)&(retained<(j+1)*NODES)]
                denom = np.linalg.norm(modal.a[i*NODES:(i+1)*NODES,j*NODES:(j+1)*NODES])
                row['block_coupling'][f'{i}{j}'] = dict(LH=float(np.linalg.norm(modal.a[np.ix_(il,jh)])/denom),
                                                       HL=float(np.linalg.norm(modal.a[np.ix_(ih,jl)])/denom))
        for arm, z in [('projection',projected), ('reduced',solved['reduced']), ('schur',solved['schur'])]:
            ya, ja = quantities(modal,z,h,k,contrast,count)
            ga, sa = local_update(ya,ja,observed,scale,ridge)
            row['arms'][arm] = dict(data_error=relative(ya,y), jacobian_error=relative(ja,jac),
                                   worst_column_scaled=float(np.max(np.linalg.norm(ja-jac,axis=0))/np.max(np.linalg.norm(jac,axis=0))),
                                   gradient_error=relative(ga,gradient), step_error=relative(sa,step))
            arrays[f'{arm}_y_K{cutoff}'], arrays[f'{arm}_J_K{cutoff}'] = ya,ja
            arrays[f'{arm}_gradient_K{cutoff}'], arrays[f'{arm}_step_K{cutoff}'] = ga,sa
        arrays[f'reduced_z_K{cutoff}'] = solved['reduced'][retained]
        arrays[f'feedback_K{cutoff}'] = solved['feedback']
        row['selected_discrete_derivatives'] = []
        for column, (da,db,dc) in zip(SELECTED,derivatives):
            dy = np.diag(discrete_tangent(modal.a,modal.b[:,:count],modal.c,da,db[:,:count],dc,retained,
                                         factors=solved['factors'],state=solved['reduced'][retained,:count]))
            work['derivative_rhs_columns'] += count
            jh = arrays[f'reduced_J_K{cutoff}'][:,column]
            row['selected_discrete_derivatives'].append(dict(column=column,
                physical_error=relative(dy,jac[:,column]), hadamard_disagreement=relative(dy,jh)))
            arrays[f'reduced_dy_{column}_K{cutoff}'] = dy
        rows.append(row)
    qualification['algebra'] = max(qualification['algebra'], qualification['modal_nodal_data'],
        max(max(r['schur_trace_error'],r['feedback_identity_error']) for r in rows))
    qualified = all(qualification[key]<=value for key,value in LIMITS.items())
    cutoffs = {}
    for arm in ('projection','reduced'):
        accuracy = lambda r: all(r['arms'][arm][key]<=1e-3 for key in ('data_error','jacobian_error'))
        inverse = lambda r: accuracy(r) and all(r['arms'][arm][key]<=1e-2 for key in ('gradient_error','step_error'))
        cutoffs[arm] = dict(data_jacobian=stable_cutoff(rows,accuracy) if qualified else None,
                            local_update=stable_cutoff(rows,inverse) if qualified else None)
    path = folder/'atlas.npz'
    np.savez_compressed(path, **arrays)
    report = dict(id=name, frequency_ghz=frequency,k=float(k),contrast=contrast,nodes=NODES,refined_nodes=REFINED,
                  shape_band=shape.band,shape_direction_band=BAND,qualified=qualified,qualification=qualification,
                  qualification_limits=LIMITS,cutoffs=cutoffs,derivatives=derivative_rows,rows=rows,
                  basis=dict(trace='stored parameter t; unitary DFT; flux q=|gamma_t| dn u',
                             shape='L2(ds) arclength normal harmonics projected to fixed Cartesian velocities',
                             trace_block_order=['Dirichlet','flux'],rhs_order=['24 sources','24 reciprocal receivers']),
                  diagnostic='fixed 1% linear synthetic residual; fixed ridge; not an inverse trajectory',
                  work=work,seconds=time.perf_counter()-started,artifact_bytes=path.stat().st_size,
                  artifact_sha256=digest(path))
    write(folder/'metrics.json',report)
    print(name,'qualified',qualified,'cutoffs',cutoffs,'seconds',round(report['seconds'],2),flush=True)
    return report


def collect(output):
    output.mkdir(parents=True,exist_ok=False)
    specs, inputs = case_specs()
    files = subprocess.check_output(['git','ls-files','*.py'],cwd=ROOT,text=True).splitlines()
    files += [str(PLAN.relative_to(ROOT)), 'experiments/modal_atlas/operator_atlas.py',
              'experiments/modal_atlas/test_operator_atlas.py']
    manifest = dict(experiment='MA-006',parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    cases=[s[0] for s in specs],sources={p:digest(ROOT/p) for p in sorted(set(files)) if (ROOT/p).is_file()},
                    inputs={str(p.relative_to(ROOT)):digest(p) for p in inputs},cutoffs=CUTOFFS,
                    limits=dict(seconds=1800,nodal_assemblies=120,modal_factorizations=320,artifact_bytes=2**30),
                    command=' '.join(sys.argv),python=sys.executable,
                    environment={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','SC_FORWARD_BACKEND')})
    write(output/'manifest.json',manifest)
    started = time.perf_counter()
    rows=[]
    status='COMPLETE'
    for index,spec in enumerate(specs):
        remaining=1800-(time.perf_counter()-started)
        used=sum(r['artifact_bytes'] for r in rows)
        if remaining<=0 or used+100*2**20>2**30:
            status='BUDGET_STOP';break
        if sum(r['work']['nodal_assemblies'] for r in rows)+10>120 or sum(r['work']['modal_factorizations'] for r in rows)+30>320:
            status='BUDGET_STOP';break
        with (output/f'{spec[0]}.log').open('w') as handle:
            try:
                result=subprocess.run([sys.executable,'-m','experiments.modal_atlas.operator_atlas','worker',
                                       '--output',str(output),'--index',str(index)],cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT,
                                      timeout=remaining)
            except subprocess.TimeoutExpired:
                status='WALL_TIME_STOP';break
        if result.returncode:
            status='CELL_FAILURE';break
        row=json.loads((output/spec[0]/'metrics.json').read_text());rows.append(row)
        print(spec[0],row['qualified'],row['cutoffs'],flush=True)
        if index==0 and not row['qualified']:
            status='PILOT_GATE_FAILED';break
    write(output/'index.json',dict(status=status,cells=[r['id'] for r in rows],seconds=time.perf_counter()-started,
                                  qualified=sum(r['qualified'] for r in rows),
                                  artifact_bytes=sum(r['artifact_bytes'] for r in rows),
                                  work={k:sum(r['work'][k] for r in rows) for k in rows[0]['work']} if rows else {}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=('collect','worker'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.phase=='collect':
        collect(args.output.resolve())
    else:
        manifest=json.loads((args.output/'manifest.json').read_text())
        for group in ('sources','inputs'):
            for path,value in manifest[group].items():
                if digest(ROOT/path)!=value:
                    raise RuntimeError('Measured source/input changed: '+path)
        spec=case_specs()[0][args.index]
        try:
            collect_cell(spec,args.output/spec[0])
        except Exception:
            write(args.output/f'{spec[0]}_failure.json',dict(traceback=traceback.format_exc()))
            raise


if __name__=='__main__':
    main()
