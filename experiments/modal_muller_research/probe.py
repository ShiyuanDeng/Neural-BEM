"""Compare scalar-normal and flux-density expansions on original fixtures."""
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from ordered_boundary import OrderedBoundary2D
from gpr_bem_kress import Material
from gpr_bem_kress.execution import execution
from gpr_bem_kress.system import build_kress_tmz_frequency_system
from gpr_bem_kress.forward import kress_incident_trace_on_boundary, build_exterior_receiver_operator
from gpr_bem_kress.multicomponent import (
    build_multicomponent_kress_tmz_frequency_system,
    multicomponent_incident_trace_on_boundary,
    build_multicomponent_exterior_receiver_operator)
from experiments.bie002_modal_diagnostic.fixtures import inputs, parameterizations
from .modal import ModalSystem


def assemble(curves, frequency, acquisition):
    started = perf_counter()
    single = len(curves) == 1
    geometry = curves[0] if single else OrderedBoundary2D(tuple(curves))
    system_fn = build_kress_tmz_frequency_system if single else build_multicomponent_kress_tmz_frequency_system
    rhs_fn = kress_incident_trace_on_boundary if single else multicomponent_incident_trace_on_boundary
    receiver_fn = build_exterior_receiver_operator if single else build_multicomponent_exterior_receiver_operator
    system = system_fn(geometry, 2*np.pi*frequency,
                       **{name: Material(**acquisition[name]) for name in ('exterior', 'interior')},
                       **{name: acquisition[name] for name in ('eps0', 'mu0')})
    d, n = rhs_fn(geometry, np.array(acquisition['source_points']), system.k_exterior,
                  acquisition['source_strength'])
    b = np.concatenate((d, n), axis=1).T
    c = receiver_fn(geometry, np.array(acquisition['receiver_points']), system.k_exterior).state_rows
    return system.system_matrix, b, c, perf_counter()-started


def relative(a, b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b), 1e-300))


def main():
    acquisition, scenes = inputs()
    output = Path('results/experiments/modal_muller_20260916')
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    with execution(kernels='real_bessel'):
        for scene in scenes:
            n = 256 if 'records' not in scene else 512
            curves = [p.discretize(n, require_even=True) for p in parameterizations(scene)]
            for frequency in [500e6, 1250e6]:
                a, b, c, assembly_time = assemble(curves, frequency, acquisition)
                started = perf_counter()
                u = lu_solve(lu_factor(a), b)
                exact = c@u
                direct_seconds = perf_counter()-started
                for kind in ['constant', 'flux']:
                    modal = ModalSystem.from_nodal(a, b, c, curves, kind)
                    for cutoff in [8, 12, 16, 24, 32, 40, 48, 64, 80, 96, 120, 160, 192, 240]:
                        if cutoff >= n//2:
                            continue
                        result = modal.solve(cutoff)
                        row = dict(scene=scene['id'], frequency=frequency, n=n, kind=kind, cutoff=cutoff,
                                   unknowns=len(result['indices']), full_unknowns=len(a),
                                   data_error=relative(result['y'], exact),
                                   physical_residual=relative(a@result['physical'], b),
                                   flux_residual=result['residual'],
                                   trace_error=relative(result['physical'], u),
                                   assembly_seconds=assembly_time, direct_seconds=direct_seconds,
                                   transform_seconds=modal.transform_seconds, solve_seconds=result['seconds'])
                        rows.append(row)
                        if row['physical_residual'] < 1e-6 and row['data_error'] < 1e-6:
                            print(json.dumps(row), flush=True)
                            break
                    else:
                        print('NO_PASS', json.dumps(row), flush=True)
                (output/'flux_probe.json').write_text(json.dumps(rows, indent=2)+'\n')


if __name__ == '__main__':
    main()
