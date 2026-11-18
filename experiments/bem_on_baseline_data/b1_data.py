"""Read-only BRG table adapter, with TG-002 units. No truth in observation reads."""
from b1_runtime import ROOT, BASE, digest
import json
import numpy as np
from scipy.io import loadmat
from bem_inverse import Observation, PlaneWaveAcquisition

SOURCE = ROOT/'results/brg/tg002_shapes/2026-11-17'
REQUEST = SOURCE/'data_request.json'
SHAPES = ('circle', 'kite', 'peanut', 'star', 'asymmetric', 'c_shape', 'hook', 'cross', 'cog', 'aphex_twin')
CASES = tuple(f'{s}__c{eta:g}' for s in SHAPES for eta in (.5, 4.))
ORDER = ('circle__c4', *(c for c in CASES if c != 'circle__c4'))
LENGTH = .05
SCALE = .065/LENGTH


def catalog():
    return json.loads((BASE/'acquisition.json').read_text())['frequencies']


def verify_files(case):
    path = SOURCE/case/'bulk_manifest.json'
    recorded = {r['path']: r for r in json.loads(path.read_text())['files']} if path.exists() else {}
    rows = []
    for f in catalog():
        p = SOURCE/case/'local'/f'data_{f["index"]:03d}.mat'
        name = str(p.relative_to(ROOT))
        item = dict(index=f['index'], path=name, exists=p.exists(), recorded_sha256=recorded.get(name, {}).get('sha256'))
        if p.exists():
            item.update(sha256=digest(p), bytes=p.stat().st_size)
        item['passes'] = bool(item['exists'] and item['recorded_sha256'] and item['sha256']==item['recorded_sha256'])
        rows.append(item)
    return dict(case=case, files=rows, passes=all(r['passes'] for r in rows),
                manifest=str(path.relative_to(ROOT)), manifest_sha256=digest(path) if path.exists() else None)


def observation(case, f, source_hash):
    path = ROOT/source_hash['path']
    assert source_hash['passes'] and digest(path)==source_hash['sha256'], 'Observation hash changed or not verified.'
    saved = loadmat(path, simplify_cells=True)
    m, record = saved['measurement'], saved['data_record']
    nd, nr = int(record['directions']), int(record['receivers'])
    angles = np.asarray(m['t_dir']).reshape(-1)
    targets = np.asarray(m['tgt'])
    receivers_brg = targets[:, ::nd].T
    assert np.array_equal(targets, np.repeat(receivers_brg.T, nd, axis=1))
    assert np.array_equal(angles, np.tile(angles[:nd], nr))
    assert np.isclose(float(m['kh']), f['k'], rtol=1e-14, atol=0)
    directions = np.c_[np.cos(angles[:nd]), np.sin(angles[:nd])]
    assert np.allclose(directions, f['directions_xy'], rtol=0, atol=2e-14)
    assert np.allclose(receivers_brg, f['receivers_xy'], rtol=0, atol=2e-13)
    field = np.asarray(m['uscat_tgt']).reshape(nr, nd).T
    assert np.array_equal(field.T.reshape(-1), np.asarray(m['uscat_tgt']).reshape(-1))
    receivers = receivers_brg*SCALE
    k = f['k']/SCALE
    acquisition = PlaneWaveAcquisition(directions, receivers)
    obs = Observation(k, acquisition, field, f['frequency_hz'])
    request = json.loads((BASE/'acquisition.json').read_text())
    physical_k = 2*np.pi*f['frequency_hz']*np.sqrt(request['background']['mu']*request['background']['epsilon'])
    phase = f['k']*(directions@receivers_brg.T)
    converted_phase = k*(directions@receivers.T)
    phase_error = float(np.max(abs(phase-converted_phase)))
    assert phase_error < 1e-12
    assert np.isclose(k/LENGTH, physical_k, rtol=2e-15)
    assert np.allclose(receivers*LENGTH, receivers_brg*.065, rtol=0, atol=2e-16)
    return obs, dict(index=f['index'], frequency_hz=f['frequency_hz'], k_brg=f['k'], k_bem=k,
                     shape=field.shape, field_unchanged=True, source=source_hash,
                     phase_max_absolute_difference=phase_error,
                     physical_k_relative_error=abs(k/LENGTH-physical_k)/physical_k,
                     physical_receiver_max_difference=float(abs(receivers*LENGTH-receivers_brg*.065).max()),
                     data_record=record)


def truth_checked(case):
    """Called by checks only; fits use start_fixture, never this function."""
    from experiments.benchmark.scenes import truth_fixture, start_fixture
    from bem_inverse.io import curve_from
    shape = case.split('__c')[0]
    row = next(r for r in json.loads(REQUEST.read_text())['shapes'] if r['shape']==shape)
    assert digest(ROOT/row['source_path'])==row['source_sha256']
    truth = truth_fixture(shape)
    frozen = curve_from(json.loads((ROOT/row['source_path']).read_text()))
    assert np.allclose(truth.coefficients, frozen.coefficients, rtol=0, atol=1e-14)
    brg = np.asarray(row['coefficients_real'])+1j*np.asarray(row['coefficients_imag'])
    assert np.allclose(truth.coefficients, brg*SCALE, rtol=0, atol=1e-14)
    assert np.array_equal(np.arange(-truth.band, truth.band+1), row['modes'])
    encoded = np.asarray(np.c_[brg.real, brg.imag], dtype='<f8').tobytes()
    import hashlib
    assert hashlib.sha256(encoded).hexdigest()==row['coefficient_sha256']
    assert abs(start_fixture().coefficients[-1]*LENGTH-.065) < 1e-15
    return truth, dict(source=row['source_path'], sha256=row['source_sha256'],
                       coefficient_sha256=row['coefficient_sha256'],
                       converted_coefficient_max_error=float(abs(truth.coefficients-brg*SCALE).max()),
                       truth_fixture_max_error=float(abs(truth.coefficients-frozen.coefficients).max()))
