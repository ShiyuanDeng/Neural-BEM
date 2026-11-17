"""Bounded MATLAB launcher; upstream source is frozen alongside each run."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

REPO = Path(__file__).resolve().parents[3]
UPSTREAM = Path.home() / 'neural_bem_external/CC-CSI'
ACTIVITY = REPO / 'docs/iterations/csi_adaptation/01_run_published_examples'


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('step', choices=['shipped_i', 'shipped_ii', 'paper_tm'])
    args = parser.parse_args()
    out = REPO / 'results/csi/examples' / f'2026-11-17_{args.step}'
    out.mkdir(parents=True, exist_ok=False)
    source = UPSTREAM / ('Inv_Fresnel_I.m' if args.step == 'shipped_i' else 'Inv_Fresnel_II.m')
    original = source.read_text()
    script = original
    if args.step == 'paper_tm':
        # Only the settings specified in the authorized activity plan.
        script = script.replace("str = 'FoamDielExtTE'; fre = 2 : 2 : 10; para.pt = PT.TE; NTX = 8; centre = [-20 0, 0];",
                                "str = 'FoamTwinDielTM'; fre = 7 : 10; para.pt = PT.TM; NTX = 18; centre = [0 -15, 0];")
        script = script.replace('xs              = 100;', 'xs              = 82.5;')
        script = script.replace('ys              = 100;', 'ys              = 82.5;')
        script = script.replace('= 32;                   % set iteration number', '= 2048;                 % set iteration number')
        # Paper uses two methods. Keep a zero-size CSI placeholder for the saver/display.
        start = script.index("pars.recstr\t= ['RecMF' str '_CSI'];")
        end = script.index('%% save the inversion output', start)
        script = script[:start] + 'mchi3 = mchi2; chi3 = chi2; vJ3 = vJ2; eTot3 = eTot2; time3 = NaN;\n\n' + script[end:]
    (out / 'upstream_driver.m').write_text(original)
    driver = out / 'executed_driver.m'
    driver.write_text(script)
    env = dict(os.environ, CSI_SCRIPT=str(driver), CSI_OUT=str(out), CSI_REPO=str(REPO), CSI_UPSTREAM=str(UPSTREAM),
               CSI_FIGURES=str(ACTIVITY / 'figures'), CSI_STEP=args.step)
    command = ['matlab', '-batch', f"cd('{UPSTREAM}'); run('{REPO}/experiments/baselines/csi/run_example.m')"]
    record = dict(step=args.step, command=command, started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  driver_sha256=hashlib.sha256(script.encode()).hexdigest(),
                  upstream_commit=subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip(),
                  timeout_seconds=14400 if args.step == 'paper_tm' else 1800)
    (out / 'launch.json').write_text(json.dumps(record, indent=2) + '\n')
    start = time.monotonic()
    with (out / 'matlab.log').open('w') as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
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
