"""Verify delivered videos, preserved inputs, timelines and endpoint receipts."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = read(HERE / 'manifest.json')
    checks = []

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    check(manifest['policy'] == 'fixed', 'user-selected fixed release')
    check(manifest['new_inverse_fits'] == 0, 'no new inverse fitting')
    check(len(manifest['outputs']) == 6, 'all six scenes delivered')
    durations = set()
    for case, receipt in manifest['outputs'].items():
        prepared = read(HERE / 'prepared' / (case + '.json'))
        check(prepared['policy'] == 'fixed', case + ': common policy')
        for path, expected in receipt['sources'].items():
            check(digest(ROOT / path) == expected, case + ': unchanged input ' + path)
        video = next(path for path in HERE.glob('*.mp4') if digest(path) == receipt['sha256'])
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,nb_frames,duration,pix_fmt,codec_name', '-of', 'json', str(video)], text=True))['streams'][0]
        check(probe['codec_name'] == 'h264' and probe['pix_fmt'] == 'yuv420p', case + ': portable H.264 encoding')
        check((probe['width'], probe['height'], int(probe['nb_frames'])) == (1800, 1100, 498),
              case + ': expected dimensions and frame count')
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'],
                                 capture_output=True, text=True)
        check(decoded.returncode == 0 and not decoded.stderr.strip(), case + ': full video decodes cleanly')
        durations.add(float(probe['duration']))
        check(len(receipt['timeline']) == 498, case + ': complete timeline')
        check(receipt['checks']['max_log10_refinement'] < .01, case + ': displayed values refine within .01 dex')
        check(receipt['checks']['frontier_changes'] == 0, case + ': stable displayed frontiers')
        for k, track in enumerate(prepared['tracks']):
            check(len(track) == receipt['states'][k], case + f': track {k} state count')
            check({frame[k + 1] for frame in receipt['timeline']} == set(range(len(track))),
                  case + f': track {k} every saved state shown')
            check(receipt['timeline'][-1][k + 1] == len(track) - 1, case + f': track {k} actual final state')
            check(abs(track[-1]['rms_mm'] - receipt['expected_rms_mm'][k]) <=
                  1e-9 * max(receipt['expected_rms_mm'][k], 1e-3), case + f': track {k} recorded endpoint score')
            for state in track:
                check(len(state['heat']) == 49 and len(state['heat'][0]) == 19,
                      case + f': track {k} full order/frequency map')
    check(durations == {41.5}, 'synchronized durations across all six videos')
    result = dict(passed=True, checks=len(checks), labels=checks,
                  note='Visual QA is separate; assertions inspect numerical and encoding receipts.')
    (HERE / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, checks=len(checks))))


if __name__ == '__main__':
    main()
