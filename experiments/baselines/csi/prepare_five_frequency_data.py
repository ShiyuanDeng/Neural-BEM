"""Freeze shared five-frequency observations; forward solves only, never fits."""
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
ROOT = REPO/'results/csi/tg002/2026-11-18_five_frequency_data'
PARENT = REPO/'results/csi/tg002/2026-11-18_low_band_data'
ACT = REPO/'docs/iterations/csi_adaptation/06_prepare_five_frequency_data'
DRIVER = base.CODE/'generate_five_frequency_data.m'
FREQ = [.5, 1., 1.5, 2., 2.5]
SHAPES = [s for group in base.BATCHES for s in group]
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
    assert a.shape == (14112, 7) and np.isfinite(a).all()
    assert np.array_equal(a[:, 2].reshape(-1, 8), np.tile(np.arange(1, 9), (1764, 1)))
    layout = a[::8, :2]
    assert np.array_equal(a[:, :2], np.repeat(layout, 8, axis=0))
    assert np.unique(layout, axis=0).shape == (1764, 2)
    assert np.array_equal(np.unique(layout[:, 0], return_counts=True)[1], np.full(36, 49))
    return p, a


def verify_driver():
    original = base.CODE/'generate_synthetic.m'
    frozen = json.loads((REPO/'results/csi/tg002/2026-11-17_campaign/sources.json').read_text())
    expected = next(e['sha256'] for e in frozen['files'] if e['path'] == str(original.relative_to(REPO)))
    assert base.sha(original) == expected
    src = original.read_text()
    replacement = """% Pair layout is taken from one verified frozen parent frequency.
parent=load(getenv('CSI_PARENT'));
layout=parent(parent(:,3)==1,:);
assert(isequal(size(layout),[1764 7]));
raw=repelem(layout,5,1);
raw(:,3)=repmat([.5;1;1.5;2;2.5],size(layout,1),1);"""
    expected_text = src.replace("raw=load('dielTM_dec8f.txt');", replacement).replace(
        'fre=1:8;reports={};timer=tic;', 'fre=[.5 1 1.5 2 2.5];reports={};timer=tic;').replace(
        "fprintf('Generated %d GHz", "fprintf('Generated %g GHz")
    assert DRIVER.read_text() == expected_text, 'unexpected generator changes'
    return fingerprint(original)


def launch_capacity():
    policy_path = REPO/'results/csi/resource_policy.json'
    policy = json.loads(policy_path.read_text()) if policy_path.exists() else {'max_data_jobs': 1}
    data_jobs = 0
    growth = 0.
    workers = []
    for proc in psutil.process_iter(['pid', 'cmdline', 'memory_info']):
        try:
            cmd = proc.info['cmdline'] or []
            if not cmd or proc.pid == os.getpid():
                continue
            text = ' '.join(cmd)
            is_matlab = cmd[0].endswith('/bin/glnxa64/MATLAB') and '-batch' in cmd
            is_bem = ('python' in Path(cmd[0]).name and any(
                name in cmd for name in ('experiments.bem_on_baseline_data.csi_fit',
                                         'experiments.bem_on_baseline_data.brg_fit')))
            if not (is_matlab or is_bem):
                continue
            is_data = is_matlab and 'generate_' in text
            data_jobs += int(is_data)
            reserve = (3 if is_data else 6 if is_matlab else 4)*base.GIB
            rss = proc.memory_info().rss
            for child in proc.children(recursive=True):
                try:
                    rss += child.memory_info().rss
                except psutil.NoSuchProcess:
                    pass
            growth += max(0, reserve-rss)
            workers.append(dict(pid=proc.pid, reservation_bytes=reserve, rss_bytes=rss))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    available = base.memory()['MemAvailable']
    required = (14+2+3)*base.GIB+growth
    return data_jobs < policy.get('max_data_jobs', 1) and available >= required, dict(
        utc=now(), policy=policy, available_bytes=available, required_bytes=required,
        outstanding_growth_bytes=growth, workers=workers, existing_data_jobs=data_jobs)


def fields(a):
    total = a[:, 3]+1j*a[:, 4]
    incident = a[:, 5]+1j*a[:, 6]
    return {'total': total, 'incident': incident, 'scattered': total-incident}


def check_and_freeze(scene, parent, old):
    folder = ROOT/scene
    generated = folder/'generated/synthetic_input.txt'
    a = np.loadtxt(generated)
    assert a.shape == (8820, 7) and np.isfinite(a).all()
    assert np.array_equal(a[:, :2], np.repeat(old[::8, :2], 5, axis=0))
    assert np.array_equal(a[:, 2], np.tile(FREQ, 1764))
    report = json.loads((folder/'generated/forward_summary.json').read_text())
    assert report['threads'] == 8 and report['frequencies_GHz'] == FREQ
    residuals = [e['solve_residual'] for e in report['frequencies']]
    assert np.isfinite(residuals).all() and max(residuals) < 1e-9
    reproduction = []
    for f in (1, 2):
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
    lines = [parent_lines[8*j+int(f)-1] if f in (1, 2) else generated_lines[5*j+i]
             for j in range(1764) for i, f in enumerate(FREQ)]
    final_bytes = b''.join(lines)
    final = np.loadtxt(io.BytesIO(final_bytes))
    assert final.shape == (8820, 7) and np.isfinite(final).all()
    assert np.array_equal(final[:, :3], a[:, :3])
    assert all(lines[5*j+i] == parent_lines[8*j+int(f)-1]
               for j in range(1764) for i, f in enumerate(FREQ) if f in (1, 2))
    checks = dict(utc=now(), state='passed', rows=8820, columns=7, finite=True,
                  pair_order_exact=True, mask_exact=True, copied_parent_line_bytes_exact=True,
                  reproduction=reproduction, native_solve_residuals=residuals,
                  maximum_native_solve_residual=max(residuals))
    if scene == 'circle':
        boundary = loadmat(PARENT/scene/'truth/geometry.mat', simplify_cells=True)['boundary']
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
        parent=fingerprint(parent), geometry=fingerprint(PARENT/scene/'truth/geometry.mat'),
        drivers=drivers, original_generator=verify_driver(), checks=fingerprint(folder/'checks.json'),
        generated_table=fingerprint(generated), frequency_blocks=[dict(frequency_GHz=f, rows=1764,
            one_based_rows=f'{i+1}+5*j, j=0..1763',
            source='exact parent line bytes' if f in (1, 2) else 'new unchanged-generator forward solve',
            source_path=str(parent if f in (1, 2) else generated),
            source_sha256=base.sha(parent if f in (1, 2) else generated)) for i, f in enumerate(FREQ)])
    write(folder/'manifest.json', manifest)
    write(folder/'data.json', dict(state='frozen', scene=scene, path=str(path), sha256=digest,
        bytes=len(final_bytes), rows=8820, relative_permittivity=4, frequencies_GHz=FREQ,
        source_count=36, measured_receivers_per_source=49, mask_exact=True,
        forward_grid=[332, 332], forward_cell_m=.000625, sign_convention='exp(+j omega t); BEM conjugates once',
        parent_sha256=base.sha(parent), manifest_path=str(folder/'manifest.json')))
    return checks


def report_docs():
    notes = ['# Shared five-frequency frozen observations', '', f'Updated {now()}.', '',
        'Column order: source index, receiver index, GHz, total real, total imaginary, incident real, incident imaginary.',
        '1764 source–receiver pairs; 36 sources and 49 receivers per source. Seven columns, %.16e format.',
        'Per pair: 0.5, 1, 1.5, 2, 2.5 GHz, in that order; one-based rows 5*j+i, j=0..1763, i=1..5.',
        'Pair order and mask equal the frozen parent. The 1 and 2 GHz lines are exact parent bytes.',
        'Sign convention: exp(+j omega t); BEM conjugates scattered fields once.',
        'Both methods read these same files by SHA-256. BEM true-shape checks are separate from this data freeze.', '']
    results = ['# Five-frequency data results', '', f'Updated {now()}. Forward solves only; no inverse fit.', '',
        '| Shape | State | Max native residual | Max reproduction relative L2 | Wall seconds |',
        '|---|---|---:|---:|---:|']
    for scene in SHAPES:
        folder = ROOT/scene
        if not (folder/'outcome.json').exists():
            continue
        outcome = json.loads((folder/'outcome.json').read_text())
        if outcome['state'] != 'frozen':
            results.append(f"| {scene} | failed; see failure.txt | — | — | — |")
            continue
        d = json.loads((folder/'data.json').read_text())
        c = json.loads((folder/'checks.json').read_text())
        launch = json.loads((folder/'generated/launch.json').read_text())
        maxrep = max(m['relative_L2'] for f in c['reproduction'] for m in f['fields'].values())
        results.append(f"| {scene} | frozen | {c['maximum_native_solve_residual']:.6g} | {maxrep:.6g} | {launch['wall_seconds']:.3f} |")
        notes += [f'## {scene}', '', f"Path: `{d['path']}`.", f"SHA-256: `{d['sha256']}`.",
                  f"Parent SHA-256: `{d['parent_sha256']}`.",
                  f"Checks: 8820 finite rows; exact pair order, mask and copied line bytes; maximum native residual {c['maximum_native_solve_residual']:.6g}; maximum reproduction relative L2 {maxrep:.6g}.",
                  f"Evidence: [manifest]({os.path.relpath(folder/'manifest.json', ACT)}), [checks]({os.path.relpath(folder/'checks.json', ACT)}).", '']
        if 'circle_exact_series' in c:
            table = ['| GHz | Error / table (%) | Error / exact (%) |', '|---:|---:|---:|']
            table += [f"| {e['frequency_GHz']:g} | {100*e['relative_L2_over_table']:.8f} | {100*e['relative_L2_over_exact']:.8f} |" for e in c['circle_exact_series']['per_frequency']]
            notes += table+['']
            results += ['', 'Circle exact-series errors (all below 1%):', '', *table, '']
    (ACT/'data_note.md').write_text('\n'.join(notes)+'\n')
    (ACT/'results.md').write_text('\n'.join(results)+'\n')


def publish(scene):
    report_docs()
    subprocess.run(['git', 'add', '--', *OWNED], check=True, cwd=REPO)
    subprocess.run(['git', 'commit', '-m', f'Freeze shared five-frequency data: {scene}', '--', *OWNED], check=True, cwd=REPO)
    subprocess.run(['git', 'push'], check=True, cwd=REPO)
    subprocess.run(['git', 'status', '--short', '--', *OWNED], check=True, cwd=REPO)


def run(scene):
    if scene != 'circle':
        assert json.loads((ROOT/'circle/outcome.json').read_text())['state'] == 'frozen'
    parent, old = checked_parent(scene)
    original = verify_driver()
    folder = ROOT/scene
    folder.mkdir(parents=True, exist_ok=False)
    write(folder/'sources.json', dict(utc=now(), parent=fingerprint(parent), original_generator=original,
        drivers=[fingerprint(DRIVER), fingerprint(Path(__file__).resolve())],
        geometry=fingerprint(PARENT/scene/'truth/geometry.mat'),
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
            CSI_GEOMETRY=str(PARENT/scene/'truth/geometry.mat'), CSI_CASE=f'tg002_{scene}_c4_TM'))
        job['record'].update(capacity_before_launch=capacity, nice=10, time_stop=False)
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
