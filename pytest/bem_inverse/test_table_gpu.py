"""A1–A4/B7 table agreement using CUDA assembly and the shared host wave path."""
from dataclasses import replace
import json
import os
from pathlib import Path

import numpy as np
import pytest
import torch

from bem_inverse import Execution, FourierCurve, Observation, PlaneWaveAcquisition, PointSourceAcquisition
from bem_inverse.continuation.geometry import resize
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings, forward_solve
from bem_inverse.geometry_selection import make_update


@pytest.fixture(scope='module')
def table_results():
    if not torch.cuda.is_available():
        pytest.skip('CUDA table comparison requires a GPU')
    curve = resize(FourierCurve.circle(.8, .15-.2j), 8)
    coefficients = curve.coefficients.copy()
    coefficients[curve.band-2] = .03+.01j
    coefficients[curve.band+3] = .04-.01j
    curve = FourierCurve(coefficients)
    theta = np.array([.2, 1.3, 2.7])
    directions = np.c_[np.cos(theta), np.sin(theta)]
    phi = np.arange(7)*2*np.pi/7
    receivers = 10*np.c_[np.cos(phi), np.sin(phi)]
    acquisitions = dict(plane=PlaneWaveAcquisition(directions, receivers),
                        point=PointSourceAcquisition(4*directions, receivers,
                                                     strength=1.3+.2j, paired=False))
    mask = np.arange(21).reshape(3, 7)%3 != 0
    update, _ = make_update('slider', 1., Execution(device='cpu', frequency_threads=1))
    space = update.prepare(curve, 3, 8)
    contexts = {device: ModalMuller(Execution(device=device, frequency_threads=1),
                                   ModalSettings(table_mode=True)) for device in ('cpu', 'cuda', 'auto')}
    rows = {}
    try:
        for kind, acquisition in acquisitions.items():
            eta = .33 if kind == 'plane' else 2.
            for masked in (False, True):
                acq = replace(acquisition, mask=mask if masked else None)
                obs = Observation(1., acq, np.ones(acq.data_shape), 1.)
                for device, context in contexts.items():
                    state = forward_solve(curve, obs, eta, 512, context=context)
                    jacobian = context.derivative(state, update, space)
                    h = 1e-3
                    plus = forward_solve(curve, obs, eta+h, 512, context=context).prediction
                    minus = forward_solve(curve, obs, eta-h, 512, context=context).prediction
                    rows[kind, masked, device] = dict(prediction=state.prediction, jacobian=jacobian,
                                                      material=(plus-minus)/(2*h), diagnostics=state.diagnostics)
    finally:
        contexts.clear()
    return rows, mask


@pytest.mark.parametrize('kind', ['plane', 'point'])
@pytest.mark.parametrize('masked', [False, True])
@pytest.mark.parametrize('device', ['cuda', 'auto'])
def test_cpu_gpu_tables_and_derivatives_agree(table_results, kind, masked, device):
    rows, mask = table_results
    cpu = rows[kind, masked, 'cpu']
    gpu = rows[kind, masked, device]
    assert gpu['diagnostics']['device'] == 'cuda-modal'
    assert gpu['diagnostics']['fallback'] is None
    metrics = {}
    for field in ('prediction', 'jacobian', 'material'):
        a, b = cpu[field], gpu[field]
        assert a.shape == b.shape
        error = float(np.linalg.norm(a-b)/np.linalg.norm(a))
        metrics[field] = error
        assert error < 1e-10, (field, error)
        if masked:
            np.testing.assert_array_equal(b, rows[kind, False, device][field][mask])
    print(json.dumps(dict(kind=kind, masked=masked, device=device, relative_l2=metrics)))
    if directory := os.environ.get('BEM_GPU_TABLE_EVIDENCE'):
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        (out/f'{kind}_{"masked" if masked else "full"}_{device}.json').write_text(
            json.dumps(dict(kind=kind, masked=masked, device=device, relative_l2=metrics,
                            threshold=1e-10, passed=True), indent=2)+'\n')
