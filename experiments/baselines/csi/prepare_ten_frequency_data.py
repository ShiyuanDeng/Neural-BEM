"""Freeze shared ten-frequency observations; forward solves only, never fits."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np
import psutil
from scipy.io import loadmat
from experiments.baselines.csi import campaign as base
from experiments.baselines.csi.circle_grid_check import exact_circle

REPO = base.REPO
ROOT = REPO/'results/csi/tg002/2026-11-18_ten_frequency_data'
PARENT = REPO/'results/csi/tg002/2026-11-18_five_frequency_data'
GEOMETRY = REPO/'results/csi/tg002/2026-11-18_low_band_data'
ACT = REPO/'docs/iterations/adapt_bem_to_baseline_data/08_fit_csi_tables_at_ten_frequencies'
DRIVER = base.CODE/'generate_ten_frequency_data.m'
FREQ = [i/4 for i in range(1, 11)]
OLD_FREQ = [.5, 1., 1.5, 2., 2.5]
SHAPES = ['circle', 'star', 'kite', 'hook', 'peanut', 'asymmetric', 'c_shape', 'cross', 'cog', 'aphex_twin']
OWNED = [str(p.relative_to(REPO)) for p in (ROOT, ACT, DRIVER, Path(__file__).resolve())]


def now():
    return subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip()


base.now = now


def write(path, value):
    base.write(path, value)


def fingerprint(path):
    return dict(path=str(path), sha256=base.sha(path))


def checked_parent(scene):
    p = PARENT/scene/'forward/synthetic_input.txt'
    expected = p.with_suffix('.txt.sha256').read_text().split()[0]
    assert base.sha(p) == expected, f'{scene}: parent SHA-256 mismatch'
    assert json.loads((PARENT/scene/'data.json').read_text())['sha256'] == expected
    a = np.loadtxt(p)
    assert a.shape == (8820, 7) and np.isfinite(a).all()
    assert np.array_equal(a[:, 2].reshape(-1, 5), np.tile(OLD_FREQ, (1764, 1)))
    layout = a[::5, :2]
    assert np.array_equal(a[:, :2], np.repeat(layout, 5, axis=0))
    assert np.unique(layout, axis=0).shape == (1764, 2)
    assert np.array_equal(np.unique(layout[:, 0], return_counts=True)[1], np.full(36, 49))
    return p, a


def provenance():
    return dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        solver_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain', '--', 'solvers/bem_inverse'], text=True).strip()))


def verify_driver():
    original = base.CODE/'generate_synthetic.m'
    frozen = json.loads((REPO/'results/csi/tg002/2026-11-17_campaign/sources.json').read_text())
    expected = next(e['sha256'] for e in frozen['files'] if e['path'] == str(original.relative_to(REPO)))
    assert base.sha(original) == expected
    five = base.CODE/'generate_five_frequency_data.m'
    expected_text = five.read_text().replace('raw=repelem(layout,5,1);', 'raw=repelem(layout,10,1);').replace(
        'repmat([.5;1;1.5;2;2.5]', 'repmat([.25;.5;.75;1;1.25;1.5;1.75;2;2.25;2.5]').replace(
        'fre=[.5 1 1.5 2 2.5];', 'fre=[.25 .5 .75 1 1.25 1.5 1.75 2 2.25 2.5];')
    assert DRIVER.read_text() == expected_text, 'unexpected generator changes'
    return fingerprint(original)


def launch_capacity():
    available = base.memory()['MemAvailable']
    required = 19*base.GIB
    return available >= required, dict(utc=now(), available_bytes=available,
        required_bytes=required, rule='one sequential data job; 14 GiB floor plus 5 GiB launch reserve; overnight ceilings lifted')


def fields(a):
    total = a[:, 3]+1j*a[:, 4]
    incident = a[:, 5]+1j*a[:, 6]
    return {'total': total, 'incident': incident, 'scattered': total-incident}


def check_and_freeze(scene, parent, old):
    folder = ROOT/scene
    generated = folder/'generated/synthetic_input.txt'
    a = np.loadtxt(generated)
    assert a.shape == (17640, 7) and np.isfinite(a).all()
    assert np.array_equal(a[:, :2], np.repeat(old[::5, :2], 10, axis=0))
    assert np.array_equal(a[:, 2], np.tile(FREQ, 1764))
    report = json.loads((folder/'generated/forward_summary.json').read_text())
    assert report['threads'] == 8 and report['frequencies_GHz'] == FREQ
    residuals = [e['solve_residual'] for e in report['frequencies']]
    assert np.isfinite(residuals).all() and max(residuals) < 1e-9
    reproduction = []
    for f in OLD_FREQ:
        x, y = fields(a[a[:, 2] == f]), fields(old[old[:, 2] == f])
        metrics = {}
        for name in x:
            delta = np.abs(x[name]-y[name])
            rel = float(np.linalg.norm(delta)/np.linalg.norm(y[name]))
            pair = float(np.max(delta/np.maximum(np.abs(y[name]), np.finfo(float).tiny)))
            metrics[name] = dict(relative_L2=rel, maximum_pair_relative=pair)
            assert rel <= 1e-9 and pair <= 1e-9, (scene, f, name, metrics[name])
        reproduction.append(dict(frequency_GHz=f, fields=metrics))
    parent_lines = parent.read_bytes().splitlines(keepends=True)
    generated_lines = generated.read_bytes().splitlines(keepends=True)
    # Prove reproduction on the generated output itself, before preserving old bytes.
    proof = []
    for f in OLD_FREQ:
        i, j = FREQ.index(f), OLD_FREQ.index(f)
        new_bytes = b''.join(generated_lines[i::10])
        old_bytes = b''.join(parent_lines[j::5])
        equal = new_bytes == old_bytes
        proof.append(dict(frequency_GHz=f, rows=1764, generated_bytes_exact=equal,
            parent_block_sha256=hashlib.sha256(old_bytes).hexdigest(),
            generated_block_sha256=hashlib.sha256(new_bytes).hexdigest()))
        assert equal, (scene, f, 'generated row bytes differ from frozen five-frequency rows')
    lines = [parent_lines[5*j+OLD_FREQ.index(f)] if f in OLD_FREQ else generated_lines[10*j+i]
             for j in range(1764) for i, f in enumerate(FREQ)]
    final_bytes = b''.join(lines)
    final = np.loadtxt(io.BytesIO(final_bytes))
    assert final.shape == (17640, 7) and np.isfinite(final).all()
    assert np.array_equal(final[:, :3], a[:, :3])
    assert all(lines[10*j+i] == parent_lines[5*j+OLD_FREQ.index(f)]
               for j in range(1764) for i, f in enumerate(FREQ) if f in OLD_FREQ)
    checks = dict(utc=now(), state='passed', rows=17640, columns=7, finite=True,
                  pair_order_exact=True, mask_exact=True, copied_parent_line_bytes_exact=True,
                  old_frequency_byte_proof=proof, reproduction=reproduction, native_solve_residuals=residuals,
                  maximum_native_solve_residual=max(residuals))
    if scene == 'circle':
        boundary = loadmat(GEOMETRY/scene/'truth/geometry.mat', simplify_cells=True)['boundary']
        centre = complex(boundary.mean())
        radius = float(np.mean(abs(boundary-centre)))
        accuracy = []
        for f in FREQ:
            b = final[final[:, 2] == f]
            key = (b[:, 0].astype(int)-1)*72+b[:, 1].astype(int)-1
            mask = np.zeros((36, 72), bool)
            mask.ravel()[key] = True
            data = fields(b)['scattered'].conj()[np.argsort(key, kind='stable')]
            exact = exact_circle(radius, 4., centre, f, mask)
            error = float(np.linalg.norm(data-exact))
            accuracy.append(dict(frequency_GHz=f, relative_L2_over_table=error/float(np.linalg.norm(data)),
                                 relative_L2_over_exact=error/float(np.linalg.norm(exact))))
        checks['circle_exact_series'] = dict(radius_m=radius, centre_m=[centre.real, centre.imag],
            relative_permittivity=4., per_frequency=accuracy, helper=fingerprint(
                base.CODE/'circle_grid_check.py'))
        passed = all(max(e['relative_L2_over_table'], e['relative_L2_over_exact']) <= .01 for e in accuracy)
        if not passed:
            checks['state'] = 'failed circle accuracy; not frozen'
            write(folder/'checks.json', checks)
            raise RuntimeError(f'Circle accuracy exceeds 1%: {accuracy}')
    write(folder/'checks.json', checks)
    assert base.sha(parent) == parent.with_suffix('.txt.sha256').read_text().split()[0]
    forward = folder/'forward'
    forward.mkdir()
    path = forward/'synthetic_input.txt'
    path.write_bytes(final_bytes)
    digest = base.sha(path)
    path.with_suffix('.txt.sha256').write_text(f'{digest}  synthetic_input.txt\n')
    drivers = [fingerprint(DRIVER), fingerprint(Path(__file__).resolve())]
    manifest = dict(state='frozen', frozen_utc=now(), scene=scene, table=fingerprint(path),
        parent=fingerprint(parent), geometry=fingerprint(GEOMETRY/scene/'truth/geometry.mat'),
        drivers=drivers, original_generator=verify_driver(), checks=fingerprint(folder/'checks.json'),
        generated_table=fingerprint(generated), frequency_blocks=[dict(frequency_GHz=f, rows=1764,
            one_based_rows=f'{i+1}+10*j, j=0..1763',
            source='exact parent line bytes' if f in OLD_FREQ else 'new unchanged-generator forward solve',
            source_path=str(parent if f in OLD_FREQ else generated),
            source_sha256=base.sha(parent if f in OLD_FREQ else generated)) for i, f in enumerate(FREQ)])
    write(folder/'manifest.json', manifest)
    write(folder/'data.json', dict(state='frozen', scene=scene, path=str(path), sha256=digest,
        bytes=len(final_bytes), rows=17640, relative_permittivity=4, frequencies_GHz=FREQ,
        source_count=36, measured_receivers_per_source=49, mask_exact=True,
        forward_grid=[332, 332], forward_cell_m=.000625, sign_convention='exp(+j omega t); BEM conjugates once',
        parent_sha256=base.sha(parent), manifest_path=str(folder/'manifest.json')))
    return checks


def report_docs():
    notes = ['# Ten-frequency data record', '', f'Updated {now()}.', '',
        'Same CSI forward, grid, material, source, calibration and receiver code as the frozen five-frequency run.',
        'Only pair-template size and the frequency list differ in the MATLAB driver.',
        'Columns: source, receiver, GHz, total real/imaginary, incident real/imaginary.',
        '17640 rows; 1764 pairs; 36 sources, 49 measured receivers each.',
        'Within each pair: 0.25 to 2.5 GHz in 0.25 GHz steps. Row: i+10*j, i=1..10, j=0..1763.',
        'Sign exp(+j omega t); BEM conjugates once. Old rows are proved equal before copying.', '']
    for scene in SHAPES:
        folder = ROOT/scene
        if not (folder/'outcome.json').exists():
            continue
        outcome = json.loads((folder/'outcome.json').read_text())
        notes += [f'## {scene}', '', f"State: {outcome['state']}.", '']
        if (folder/'checks.json').exists():
            checks = json.loads((folder/'checks.json').read_text())
            notes += [f"[Checks]({os.path.relpath(folder/'checks.json', ACT)}).", '',
                '| Old GHz | Generated and final row bytes equal parent | Block SHA-256 |',
                '|---:|---|---|']
            notes += [f"| {e['frequency_GHz']:g} | {e['generated_bytes_exact']} | {e['parent_block_sha256']} |" for e in checks['old_frequency_byte_proof']]
            if 'circle_exact_series' in checks:
                notes += ['', '| GHz | Error / table (%) | Error / exact (%) |', '|---:|---:|---:|']
                notes += [f"| {e['frequency_GHz']:g} | {100*e['relative_L2_over_table']:.8f} | {100*e['relative_L2_over_exact']:.8f} |" for e in checks['circle_exact_series']['per_frequency']]
        if (folder/'manifest.json').exists():
            d = json.loads((folder/'data.json').read_text())
            notes += ['', f"Table SHA-256: `{d['sha256']}`.", f"[Manifest]({os.path.relpath(folder/'manifest.json', ACT)})."]
        notes += ['']
    (ACT/'data_note.md').write_text('\n'.join(notes)+'\n')


def publish(scene):
    report_docs()
    subprocess.run(['git', 'add', '--', *OWNED], check=True, cwd=REPO)
    subprocess.run(['git', 'commit', '-m', f'Freeze shared ten-frequency data: {scene}', '--', *OWNED], check=True, cwd=REPO)
    subprocess.run(['git', 'push'], check=True, cwd=REPO)
    subprocess.run(['git', 'status', '--short', '--', *OWNED], check=True, cwd=REPO)


def run(scene):
    if scene != 'circle':
        assert json.loads((ROOT/'circle/outcome.json').read_text())['state'] == 'frozen'
    parent, old = checked_parent(scene)
    original = verify_driver()
    folder = ROOT/scene
    folder.mkdir(parents=True, exist_ok=False)
    write(folder/'sources.json', dict(utc=now(), provenance=provenance(), parent=fingerprint(parent), original_generator=original,
        drivers=[fingerprint(DRIVER), fingerprint(Path(__file__).resolve())],
        geometry=fingerprint(GEOMETRY/scene/'truth/geometry.mat'),
        upstream_commit=subprocess.check_output(['git', '-C', str(base.UP), 'rev-parse', 'HEAD'], text=True).strip(),
        upstream_sources=[fingerprint(p) for p in sorted(base.UP.rglob('*.m'))]))
    try:
        while True:
            ready, capacity = launch_capacity()
            if ready:
                break
            print(json.dumps(dict(state='waiting for capacity', scene=scene, **capacity)), flush=True)
            time.sleep(10)
        job = base.launch(folder/'generated', DRIVER, dict(CSI_PARENT=str(parent),
            CSI_GEOMETRY=str(GEOMETRY/scene/'truth/geometry.mat'), CSI_CASE=f'tg002_{scene}_c4_TM'))
        job['record'].update(provenance=provenance(), capacity_before_launch=capacity, nice=10, time_stop=False)
        while job['process'].poll() is None:
            if base.sample(job)['MemAvailable'] < 14*base.GIB:
                base.terminate(job, '14 GiB available memory floor')
            time.sleep(.5)
        rc = base.finish(job)
        assert rc == 0, f'MATLAB return code {rc}'
        checks = check_and_freeze(scene, parent, old)
        write(folder/'outcome.json', dict(state='frozen', utc=now()))
        print(json.dumps(dict(scene=scene, checks=checks)), flush=True)
    except BaseException:
        (folder/'failure.txt').write_text(traceback.format_exc())
        write(folder/'outcome.json', dict(state='failed; not frozen', utc=now()))
        publish(scene+' failed')
        raise
    publish(scene)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--shapes', nargs='+', choices=SHAPES, required=True)
    args = parser.parse_args()
    os.nice(10)
    ROOT.mkdir(parents=True, exist_ok=True)
    for scene in args.shapes:
        run(scene)


if __name__ == '__main__':
    main()
