"""Bounded MATLAB launcher; upstream source is frozen alongside each run."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

REPO = Path(__file__).resolve().parents[3]
UPSTREAM = Path.home() / 'neural_bem_external/CC-CSI'
ACTIVITY = REPO / 'docs/iterations/csi_adaptation/01_run_published_examples'


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('step', choices=['shipped_i', 'shipped_ii', 'paper_tm', 'diel_tm'])
    parser.add_argument('--attempt', default='', help='Distinct suffix for a retained repeat')
    parser.add_argument('--timeout-seconds', type=int, help='Wall limit, at most four hours')
    args = parser.parse_args()
    suffix = f'_{args.attempt}' if args.attempt else ''
    activity = (REPO / 'docs/iterations/csi_adaptation/02_run_fresnel_dielectric_cylinder'
                if args.step == 'diel_tm' else ACTIVITY)
    parent = 'fresnel' if args.step == 'diel_tm' else 'examples'
    out = REPO / f'results/csi/{parent}' / f'2026-11-17_{args.step}{suffix}'
    out.mkdir(parents=True, exist_ok=False)
    source = UPSTREAM / ('Inv_Fresnel_I.m' if args.step in ('shipped_i', 'diel_tm') else 'Inv_Fresnel_II.m')
    original = source.read_text()
    script = original
    if args.step == 'diel_tm':
        old = "str = 'uTM_shaped'; para.pt = PT.TM; centre = [0, 0, 0]; xs = 70; ys = 70; para.m_unit = 1.5e-3; fre = 2 : 2 : 16;"
        new = "str = 'dielTM_dec8f'; para.pt = PT.TM; centre = [0, 0, 0]; xs = 70; ys = 70; para.m_unit = 1.25e-3; fre = 1 : 8;"
        assert script.count(old) == 1
        script = script.replace(old, new).replace('= 16;                   % set iteration number', '= 2048;                 % set iteration number')
    if args.step == 'paper_tm':
        # Only the settings specified in the authorized activity plan.
        script = script.replace("str = 'FoamDielExtTE'; fre = 2 : 2 : 10; para.pt = PT.TE; NTX = 8; centre = [-20 0, 0];",
                                "str = 'FoamTwinDielTM'; fre = 7 : 10; para.pt = PT.TM; NTX = 18; centre = [0 -15, 0];")
        script = script.replace('xs              = 100;', 'xs              = 82.5;')
        script = script.replace('ys              = 100;', 'ys              = 82.5;')
        script = script.replace('= 32;                   % set iteration number', '= 2048;                 % set iteration number')
        # Paper uses two methods; do not manufacture a third result.
        start = script.index("pars.recstr\t= ['RecMF' str '_CSI'];")
        end = script.index('%% save the inversion output', start)
        script = script[:start] + script[end:]
        display = (UPSTREAM / 'show_output.m').read_text().split('mchi3{oi}')[0]
        script = script.replace('run show_output.m', display)
    (out / 'upstream_driver.m').write_text(original)
    driver = out / 'executed_driver.m'
    driver.write_text(script)
    with tarfile.open(out / 'upstream_matlab_sources.tar.gz', 'w:gz') as archive:
        for path in sorted(UPSTREAM.rglob('*.m')):
            archive.add(path, arcname=path.relative_to(UPSTREAM))
    env = dict(os.environ, CSI_SCRIPT=str(driver), CSI_OUT=str(out), CSI_REPO=str(REPO), CSI_UPSTREAM=str(UPSTREAM),
               CSI_FIGURES=str(activity / 'figures'), CSI_STEP=args.step)
    command = ['matlab', '-batch', f"cd('{UPSTREAM}'); run('{REPO}/experiments/baselines/csi/run_example.m')"]
    limit = args.timeout_seconds or (14400 if args.step in ('paper_tm','diel_tm') else 1800)
    assert 0 < limit <= 14400
    record = dict(step=args.step, command=command, activity=str(activity.relative_to(REPO)),
                  started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  driver_sha256=hashlib.sha256(script.encode()).hexdigest(),
                  upstream_commit=subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip(),
                  timeout_seconds=limit)
    (out / 'launch.json').write_text(json.dumps(record, indent=2) + '\n')
    start = time.monotonic()
    with (out / 'matlab.log').open('w') as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        record.update(matlab_pid=process.pid, launcher_pid=os.getpid())
        (out / 'launch.json').write_text(json.dumps(record, indent=2) + '\n')
        try:
            record['returncode'] = process.wait(timeout=record['timeout_seconds'])
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(process.pid, signal.SIGTERM)
            record['returncode'] = process.wait(timeout=30)
            record['timed_out'] = True
    record['wall_seconds'] = time.monotonic() - start
    record['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    (out / 'launch.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    raise SystemExit(record['returncode'])


if __name__ == '__main__':
    main()
