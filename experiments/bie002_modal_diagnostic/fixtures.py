"""Frozen analytic and saved geometry inputs; no optimizer/controller imports."""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
from ordered_boundary import circle, ellipse, star, fourier_curve, PeriodicCurve2D

TOP018 = Path('results/validation/topology/TOP-018-20260915-resolution-qualified-pair')
SAVED_DIFFICULT = Path('results/validation/topology/TOP-017-followup-20260914-engineering/resolution/result.json')


def saved_curves(records):
    result = []
    for record in records:
        if record['chart'] != 'cartesian':
            raise ValueError('Frozen saved fixtures must remain Cartesian.')
        k, values = record['maximum_mode'], np.array(record['parameters'])
        cut = 2 * (k + 1)
        result.append(fourier_curve(values[:cut].reshape(-1, 2),
                                   np.vstack((np.zeros(2), values[cut:].reshape(-1, 2))),
                                   component_id=record['component_id']))
    return result


def inputs():
    spec = json.loads((TOP018 / 'scene_spec.json').read_text())
    acquisition_path = TOP018 / 'inputs/far-two-stars/observations.json'
    original = json.loads(acquisition_path.read_text())
    acquisition = {k: original[k] for k in ('source_points', 'receiver_points',
                                           'eps0', 'mu0', 'exterior', 'interior')}
    assert all(x == 1e-6 for x in original['source_strengths_real'])
    assert not any(original['source_strengths_imag'])
    acquisition['source_strength'] = 1e-6
    acquisition['provenance'] = str(acquisition_path)
    acquisition['selection'] = '24 paired source/receiver indices after transpose'
    acquisition['frequencies_hz'] = [500_000_000, 1_250_000_000]
    noncircular = next(x for x in spec['scenes'] if x['id'] == 'central-ellipse-star')['truth']
    common_path = TOP018 / 'inputs/far-two-stars/state.json'
    common = json.loads(common_path.read_text())
    difficult = json.loads(SAVED_DIFFICULT.read_text())['states']['F_rejected']['state']
    scenes = [dict(id='circle', geometry=[dict(kind='circle', center=[.5, .5], radius=.05)],
                   provenance='existing central-circle calibration dimensions'),
              dict(id='ellipse', geometry=[noncircular[0]], provenance=str(TOP018 / 'scene_spec.json')),
              dict(id='star', geometry=[noncircular[1]], provenance=str(TOP018 / 'scene_spec.json')),
              dict(id='saved_common', records=common, provenance=str(common_path)),
              dict(id='saved_difficult', records=difficult, provenance=str(SAVED_DIFFICULT))]
    return acquisition, scenes


def parameterizations(scene):
    if 'records' in scene:
        return saved_curves(scene['records'])
    factories = dict(circle=circle, ellipse=ellipse, star=star)
    curves = []
    for item in scene['geometry']:
        options = {k: v for k, v in item.items() if k != 'kind'}
        curves.append(factories[item['kind']](**options))
    return curves


def direction_jets(parameters, kind):
    if kind == 'translation':
        return [np.tile([1., 0.], (len(parameters), 1))] + [np.zeros((len(parameters), 2)) for _ in range(3)]
    if kind != 'shape5':
        raise ValueError(kind)
    return [5. ** order * np.column_stack((np.cos(5 * parameters + order * np.pi / 2),
                                           np.sin(5 * parameters + order * np.pi / 2)))
            for order in range(4)]


def perturb(curve, amplitude, kind):
    jets = direction_jets(curve.parameters, kind)
    return PeriodicCurve2D(curve.component_id, curve.parameters,
                          *[getattr(curve, name) + amplitude * jet for name, jet in
                            zip(('points', 'first_derivatives', 'second_derivatives', 'third_derivatives'), jets)],
                          period=curve.period)
