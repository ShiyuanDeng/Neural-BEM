"""Reproducible native-mode experiments; nodal code appears only as an oracle.

Run with PYTHONPATH=solvers:. and BLAS thread counts set to one.
Writes numerical evidence and a figure, without editing iteration documents.
"""
import argparse
import csv
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
import scipy
from scipy.linalg import lu_factor, lu_solve
from ordered_boundary import circle, ellipse, star
from gpr_bem_kress.execution import execution
from experiments.bie002_modal_diagnostic.fixtures import inputs
from .coefficient_operator import LaurentGeometry, CoefficientGeometry, ModalMomentFamily
from .coefficient_fields import solve
from .probe import assemble, relative


def cases():
    return {
        'circle': ([LaurentGeometry.circle(.5+.5j)], [circle((.5, .5), .05)]),
        'ellipse': ([LaurentGeometry.ellipse(.445+.445j)],
                    [ellipse((.445, .445), .045, .026, rotation=.55)]),
        'star': ([LaurentGeometry.star(.555+.555j)],
                 [star((.555, .555), .036, .24, 5, rotation=.2)]),
        'ellipse_star': ([LaurentGeometry.ellipse(.445+.445j), LaurentGeometry.star(.555+.555j)],
                         [ellipse((.445, .445), .045, .026, rotation=.55),
                          star((.555, .555), .036, .24, 5, rotation=.2)])}


def waves(frequency, acq):
    factor = 2*np.pi*frequency*np.sqrt(acq['eps0']*acq['mu0'])
    return factor*np.sqrt(acq['exterior']['epsr']), factor*np.sqrt(acq['interior']['epsr'])


def nodal(parameters, frequency, acq, count):
    started = perf_counter()
    curves = [p.discretize(count, require_even=True) for p in parameters]
    with execution(kernels='real_bessel'):
        a, b, c, _ = assemble(curves, frequency, acq)
    state = lu_solve(lu_factor(a), b)
    y = c@state
    return dict(y=y, state=state, a=a, b=b, c=c, curves=curves,
                seconds=perf_counter()-started)


def lift(state, curves, cutoff):
    size = 2*cutoff+1
    values = []
    fluxes = []
    for i, curve in enumerate(curves):
        theta = (curve.parameters-curve.parameter_origin)*2*np.pi/curve.period
        basis = np.exp(1j*theta[:, None]*np.arange(-cutoff, cutoff+1))
        block = state[2*i*size:2*(i+1)*size]
        values.append(basis@block[:size])
        fluxes.append((basis@block[size:])/(curve.speeds*curve.period/(2*np.pi))[:, None])
    return np.concatenate(values+fluxes)


def write(output, name, records):
    (output/(name+'.json')).write_text(json.dumps(records, indent=2, allow_nan=False)+'\n')
    if records and isinstance(records, list):
        with (output/(name+'.csv')).open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in records for k in r)))
            writer.writeheader()
            writer.writerows(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('results/experiments/modal_muller_20260916/native'))
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    acq, _ = inputs()
    sources, receivers = acq['source_points'], acq['receiver_points']
    accuracy, convergence, timings, stress = [], [], [], []
    all_cases = cases()
    compiled_cache = {}
    started = perf_counter()
    for name, (geometries, params) in all_cases.items():
        prepared = [CoefficientGeometry(g, 96) for g in geometries]
        for frequency in [500e6, 1250e6]:
            ko, ki = waves(frequency, acq)
            reference = nodal(params, frequency, acq, 512)
            check = nodal(params, frequency, acq, 256)
            native = solve(geometries, ko, ki, sources, receivers, prepared=prepared)
            physical = lift(native['state'], reference['curves'], 40)
            row = dict(case=name, frequency_hz=frequency, components=len(geometries),
                       trace_modes_per_component=81, native_unknowns=len(native['a']),
                       reference_unknowns=len(reference['a']),
                       oracle_256_512_error=relative(check['y'], reference['y']),
                       data_error=relative(native['y'], reference['y']),
                       physical_residual=relative(reference['a']@physical, reference['b']),
                       physical_trace_error=relative(physical, reference['state']),
                       native_seconds=native['total_seconds']+sum(p.seconds for p in prepared),
                       boundary_nodes=0, point_pair_kernel_calls=0)
            accuracy.append(row)
            print('accuracy', json.dumps(row), flush=True)
            if frequency == 1250e6:
                for cutoff in [8, 12, 16, 24, 32, 40, 48]:
                    r = solve(geometries, ko, ki, sources, receivers, cutoff=cutoff, prepared=prepared)
                    u = lift(r['state'], reference['curves'], cutoff)
                    convergence.append(dict(case=name, axis='trace_cutoff', value=cutoff,
                        data_error=relative(r['y'], reference['y']),
                        physical_residual=relative(reference['a']@u, reference['b'])))
                if name in ('star', 'ellipse_star'):
                    for bandwidth, angular, terms in [(64,36,28),(128,36,28),(96,24,28),(96,48,28),(96,36,20),(96,36,36)]:
                        r = solve(geometries, ko, ki, sources, receivers, bandwidth=bandwidth,
                                  angular_order=angular, terms=terms)
                        convergence.append(dict(case=name, axis='independent_expansion_controls',
                            bandwidth=bandwidth, angular_order=angular, bessel_terms=terms,
                            data_error=relative(r['y'], reference['y']),
                            baseline_matrix_change=relative(r['a'], native['a']),
                            baseline_rhs_change=relative(r['b'], native['b'])))
                qualified = []
                for n in [32,64,128,256]:
                    candidate = nodal(params, frequency, acq, n)
                    error = relative(candidate['y'], reference['y'])
                    if error < 1e-7:
                        qualified.append(n)
                best_nodes = min(qualified)
                families = []
                for p in prepared:
                    key = tuple(p.geometry.coefficients.items()), p.geometry.scale
                    if key not in compiled_cache:
                        compiled_cache[key] = ModalMomentFamily(p,40,28)
                    families.append(compiled_cache[key])
                compile_seconds = sum(p.seconds+f.seconds for p,f in zip(prepared,families))
                for repetition in range(5):
                    methods = ['nodal', 'native', 'compiled'] if repetition%2 == 0 else ['compiled','native','nodal']
                    for method in methods:
                        if method == 'nodal':
                            r = nodal(params, frequency, acq, best_nodes)
                            seconds = r['seconds']
                        else:
                            r = solve(geometries,ko,ki,sources,receivers,
                                      prepared=families if method == 'compiled' else prepared)
                            seconds = r['total_seconds']
                        timings.append(dict(case=name,method=method,repetition=repetition,
                            seconds=seconds, data_error=relative(r['y'],reference['y']),
                            nodal_nodes_per_component=best_nodes,
                            one_time_setup_seconds=0 if method=='nodal' else (
                                compile_seconds if method=='compiled' else sum(p.seconds for p in prepared))))
                # Time just the frequency-dependent self operator, including all four blocks.
                for repetition in range(5):
                    tick = perf_counter()
                    for family in families:
                        family.assemble(ko,ki)
                    timings.append(dict(case=name,method='compiled_self_matrix',repetition=repetition,
                                         seconds=perf_counter()-tick,one_time_setup_seconds=compile_seconds))
        write(output,'accuracy',accuracy)
        write(output,'convergence',convergence)
        write(output,'timings',timings)
    # Stress frequency to reveal the cancellation limit of the entire-function series.
    geometries, params = all_cases['star']
    prepared = [CoefficientGeometry(geometries[0],96)]
    for frequency in [2.5e9,5e9,8e9]:
        ko,ki=waves(frequency,acq)
        ref=nodal(params,frequency,acq,512)
        for terms in [28,48]:
            r=solve(geometries,ko,ki,sources,receivers,prepared=prepared,cutoff=48,terms=terms,angular_order=48)
            row=dict(case='star',frequency_hz=frequency,bessel_terms=terms,
                     data_error=relative(r['y'],ref['y']),
                     physical_residual=relative(ref['a']@lift(r['state'],ref['curves'],48),ref['b']))
            stress.append(row)
            print('stress',json.dumps(row),flush=True)
    write(output,'stress',stress)
    manifest=dict(elapsed_seconds=perf_counter()-started,python=platform.python_version(),
                  numpy=np.__version__,scipy=scipy.__version__,
                  git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in Path('experiments/modal_muller_research').glob('*.py')},
                  acquisition_provenance=acq['provenance'],
                  note='Native forward has no boundary nodes; nodal evaluations are validation only. '
                       'Setup reuse requires unchanged geometry. Timings include sources and receivers.')
    write(output,'manifest',manifest)
    plot(output,convergence,timings)


def plot(output,convergence,timings):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
    for name in cases():
        rows=[r for r in convergence if r['case']==name and r['axis']=='trace_cutoff']
        axes[0].semilogy([2*r['value']+1 for r in rows],
                         [r['physical_residual'] for r in rows],'-o',label=name.replace('_',' + '),ms=4)
    axes[0].axhline(1e-6,color='.5',linestyle='--',linewidth=1)
    axes[0].set(xlabel='Fourier modes per trace and component',ylabel='Residual in 512-node physical Müller system',
                title='Native coefficient solve: convergence')
    axes[0].legend(fontsize=8)
    names=list(cases())
    for index,method in enumerate(['nodal','native','compiled']):
        values=[1e3*np.median([r['seconds'] for r in timings if r['case']==name and r['method']==method]) for name in names]
        axes[1].bar(np.arange(4)+(index-1)*.24,values,width=.24,label={'nodal':'tuned nodal','native':'native coefficients','compiled':'compiled geometry'}[method])
    axes[1].set_xticks(np.arange(4),[n.replace('_',' +\n') for n in names])
    axes[1].set(ylabel='Median full forward time (ms)',title='Fixed-geometry repeats; setup excluded')
    axes[1].legend(fontsize=8)
    fig.savefig(output/'native_modes.png',dpi=160)
    fig.savefig(output/'native_modes.pdf')


if __name__=='__main__':
    main()
