"""Run 10: one sealed TG-002 field against RegPy's boundary integral operators.

The sealed data came from this repository's ``nodal_kress`` solver. This check
recomputes the same scattered field with the operator matrices of
regpy-examples (``obstacles2d/functions``: ``op_S``, ``op_K``, ``op_T``,
``nearfield_matrix``), pinned to one commit and imported unchanged.

What is taken from RegPy and what is written here
- RegPy: the four operator matrices and the receiver evaluation matrix.
- Here: the block system and right-hand side of RegPy's ``TransmissionOp._eval``
  with density ratio 1 (equal densities), and the point-source incident field
  i H0(k r)/4 with its normal derivative. RegPy's own finite-source branch
  multiplies the incident trace by |z'|, which is only right on a unit-speed
  curve, so the incident field is written here instead. The ``regpy`` package
  itself needs Python 3.10 and is not imported.

Conventions matched to the benchmark: package length unit, exterior wavenumber
k, interior wavenumber k*sqrt(contrast), outgoing Hankel fields, source
strength 1e-6, scattered field at the receiver paired with each source.

The criterion is written down before the comparison: the relative difference
||regpy - sealed|| / ||sealed|| over the 24 pairs must be at most 1e-6 at each of
the 19 real frequencies. Agreement on this one case does not prove the other
29 inputs or any inverse result.
"""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
from scipy.special import hankel1

from bem_inverse.io import read, write, curve_from
from experiments.benchmark import campaign as C
from experiments.cleaned_interface import benchmark as ci

from . import runs as R

CASE = 'asymmetric__c4'
LIMIT = 1e-6
NODES = (512, 1024)            # boundary nodes; the first only shows RegPy's own convergence
REPOSITORY = 'https://github.com/regpy/regpy-examples.git'
COMMIT = '573affa2e7c2e9f00d9fff39e0590f46bff4d933'


def source_folder():
    """The pinned regpy-examples checkout, cloned outside this repository on first use."""
    folder = Path(os.environ.get('REGPY_EXAMPLES', Path.home()/'.cache'/'regpy-examples'))
    if not folder.exists():
        subprocess.run(['git', 'clone', REPOSITORY, str(folder)], check=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=folder, text=True).strip()
    if head != COMMIT:
        subprocess.run(['git', 'checkout', '--quiet', COMMIT], cwd=folder, check=True)
    return folder


def boundary(curve, nodes):
    """The curve fields RegPy's operators read, all of shape (2, nodes); the normal has length |z'|."""
    jets = [curve.values(nodes, d) for d in range(4)]
    z, zp, zpp, zppp = (np.vstack((v.real, v.imag)) for v in jets)
    return SimpleNamespace(z=z, zp=zp, zpp=zpp, zppp=zppp, zpabs=np.hypot(zp[0], zp[1]),
                           normal=np.vstack((zp[1], -zp[0])))


def scattered(curve, wavenumber, contrast, acquisition, nodes, functions):
    """Scattered field at each paired receiver, by RegPy's transmission system with density ratio 1."""
    op_S, op_K, op_T, nearfield_matrix, setup_iop_data = functions
    bd = boundary(curve, nodes)
    k_ex, k_in, rho = float(wavenumber), float(wavenumber)*np.sqrt(contrast), 1.
    ex, inside = setup_iop_data(bd, k_ex), setup_iop_data(bd, k_in)
    w_sl_ex, w_dl_ex, w_sl_in, w_dl_in = -1, 1, rho, -1
    speed = np.diag(bd.zpabs)
    system = np.block([
        [w_dl_ex*op_K(bd, ex)+w_dl_in*op_K(bd, inside)+(w_dl_ex-w_dl_in-4)*speed,
         w_sl_ex*op_S(bd, ex)+w_sl_in*op_S(bd, inside)],
        [w_dl_ex*op_T(bd, ex)+w_dl_in*op_T(bd, inside),
         w_sl_ex*op_K(bd, ex).T+w_sl_in*op_K(bd, inside).T+(w_sl_in-2*rho-w_sl_ex-2)*speed]])
    right = np.block([
        [-w_dl_in*op_K(bd, inside)+(w_dl_in+2)*speed, -w_sl_in*op_S(bd, inside)],
        [-w_dl_in*op_T(bd, inside), -w_sl_in*op_K(bd, inside).T+(2*rho-w_sl_in)*speed]])
    sources = np.asarray(acquisition.sources, float)
    difference = bd.z[:, None, :]-sources.T[:, :, None]                 # (2, sources, nodes)
    distance = np.linalg.norm(difference, axis=0)
    incident = .25j*hankel1(0, k_ex*distance)
    normal_derivative = (-.25j*k_ex*hankel1(1, k_ex*distance)*np.einsum('dsn,dn->sn', difference, bd.normal)
                         / (distance*bd.zpabs))
    traces = np.linalg.solve(system, right @ np.vstack((incident.T, normal_derivative.T)))
    receivers = np.asarray(acquisition.receivers, float)                # RegPy reads (points, 2) here
    field = np.hstack((nearfield_matrix(bd, receivers, k_ex, 0., w_dl_ex),
                       nearfield_matrix(bd, receivers, k_ex, w_sl_ex, 0.))) @ traces
    return complex(acquisition.strength)*np.diagonal(field)             # receiver i pairs with source i


def main(args):
    folder = source_folder()
    sys.path.insert(0, str(folder/'obstacles2d'))
    from functions.operator import op_S, op_K, op_T
    from functions.farfield_matrix import nearfield_matrix
    from functions.setup_iop_data import setup_iop_data
    functions = (op_S, op_K, op_T, nearfield_matrix, setup_iop_data)
    row = C.row(CASE)
    curve = curve_from(read(ci.ROOT/row['truth']))
    observations = ci.observations(read(ci.ROOT/row['data']), row)
    rows = []
    for observation in observations:
        fields = [scattered(curve, observation.wavenumber, row['contrast'], observation.acquisition, n, functions)
                  for n in NODES]
        sealed = np.asarray(observation.scattered).reshape(-1)
        rows.append(dict(frequency_hz=observation.frequency_hz, wavenumber=float(observation.wavenumber),
                         relative_difference=float(np.linalg.norm(fields[-1]-sealed)/np.linalg.norm(sealed)),
                         regpy_self_difference=float(np.linalg.norm(fields[-1]-fields[0])/np.linalg.norm(fields[-1]))))
        print(f"{observation.frequency_hz/1e9:5.3f} GHz: difference {rows[-1]['relative_difference']:.2e}, "
              f"RegPy {NODES[0]} vs {NODES[1]} nodes {rows[-1]['regpy_self_difference']:.2e}", flush=True)
    worst = max(r['relative_difference'] for r in rows)
    target = args.root/'_checks'/'forward_regpy'/f'{CASE}.json'
    write(target, dict(case=CASE, criterion=f'relative difference <= {LIMIT:g} at every frequency', limit=LIMIT,
                       passed=bool(worst <= LIMIT), worst_relative_difference=worst, nodes=NODES,
                       regpy_examples=dict(repository=REPOSITORY, commit=COMMIT),
                       sealed_solver='nodal_kress, N2048 (TG-002 qualification)', rows=rows, **R.commit()))
    print(f"forward check {'PASSED' if worst <= LIMIT else 'FAILED'}: worst difference {worst:.2e} "
          f"(limit {LIMIT:g}); saved {target}", flush=True)
