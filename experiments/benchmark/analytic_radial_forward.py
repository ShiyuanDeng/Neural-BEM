"""AC-001 TG-002 high-frequency forward comparison with the archived DCT path."""
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
from scipy.fft import fft, ifft

from bem_inverse import modal_operator
from bem_inverse.modal_muller import ModalMuller, token
from bem_inverse.physics import Execution, NodalKress
from .analytic_radial_validation import sampled_coefficients
from .campaign import problem
from .scenes import truth_fixture


def relative(a, b):
    return float(np.linalg.norm(a-b)/np.linalg.norm(b))


def projected_matrix(state, cutoff):
    """Independent nodal-to-Fourier similarity on (u, J d_n u)."""
    nodes = state.curve.num_nodes
    speed = state.curve.speeds*state.curve.period/(2*np.pi)
    scale = np.r_[np.ones(nodes), speed]
    matrix = state.matrix*scale[:, None]/scale[None, :]
    blocks = (slice(0, nodes), slice(nodes, 2*nodes))
    for block in blocks:
        matrix[block] = fft(matrix[block], axis=0, norm='ortho')
    for block in blocks:
        matrix[:, block] = ifft(matrix[:, block], axis=1, norm='ortho')
    indices = np.r_[np.arange(-cutoff, cutoff+1) % nodes,
                    nodes+np.arange(-cutoff, cutoff+1) % nodes]
    return matrix[np.ix_(indices, indices)]


def archived_coefficients(ko, ki, upper, tolerance=1e-15):
    c = sampled_coefficients(ko, ki, upper, tolerance)
    return c, dict(radial_degree=c.shape[1]-1, radial_coefficient_method='archived_dct')


def main():
    rows = []
    for scene in ('circle', 'c_shape'):
        p = problem(scene+'__c13.3')
        curve = truth_fixture(scene)
        service = ModalMuller(Execution(device='cpu', frequency_threads=1))
        nodal = NodalKress(Execution(device='cpu', frequency_threads=1))
        geometry = service._geometry(curve, 160, 'cpu')
        for observation in (p.real[-1], p.damped[-1]):
            k = observation.wavenumber
            reference = nodal.evaluate(curve, observation, p.contrast, 1024)
            oracle = projected_matrix(reference._handle, 96)
            analytic_matrix, info = modal_operator.muller_matrix(geometry, k, k*np.sqrt(p.contrast), 96)
            analytic = service.evaluate(curve, observation, p.contrast, token(96))
            with patch.object(modal_operator, 'radial_coefficients', archived_coefficients):
                old_matrix, _ = modal_operator.muller_matrix(geometry, k, k*np.sqrt(p.contrast), 96)
                old = service.evaluate(curve, observation, p.contrast, token(96))
            matrix_error = relative(analytic_matrix, oracle)
            field_error = relative(analytic.prediction, reference.prediction)
            old_matrix_error = relative(old_matrix, oracle)
            old_field_error = relative(old.prediction, reference.prediction)
            matrix_gate = max(1e-8, 2*old_matrix_error) if k.imag else 1e-12
            field_gate = max(1e-7, 2*old_field_error) if k.imag else 1e-10
            row = dict(scene=scene, contrast=p.contrast, frequency=observation.frequency_hz,
                damping=float(k.imag/k.real), radial_upper=geometry.radial_upper,
                analytic_matrix_error=matrix_error, archived_dct_matrix_error=old_matrix_error,
                analytic_field_error=field_error, archived_dct_field_error=old_field_error,
                matrix_difference=relative(analytic_matrix, old_matrix),
                field_difference=relative(analytic.prediction, old.prediction),
                matrix_gate=matrix_gate, field_gate=field_gate, diagnostics=info,
                passed=matrix_error <= matrix_gate and field_error <= field_gate)
            rows.append(row)
            print(json.dumps(row), flush=True)
    output = Path('results/validation/cleaned_interfaces/AC-001/forward.json')
    output.write_text(json.dumps(dict(rows=rows, passed=all(r['passed'] for r in rows)), indent=2)+'\n')
    if not all(r['passed'] for r in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
