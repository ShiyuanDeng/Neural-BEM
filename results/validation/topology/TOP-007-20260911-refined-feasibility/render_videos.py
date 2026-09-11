"""Render one video per saved run trajectory. Reads saved states only; solves nothing."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))
import run_topology_scene_benchmark as benchmark

# The guarded arm on every scene, plus the default arm wherever the guard changed
# the outcome, so those scenes have a before/after pair.
DEFAULT_ARM_SCENES = ('far-ellipse-star', 'empty-ellipse-star')


def main():
    spec = benchmark.read(HERE / 'scene_spec.json')
    records = []
    for scene in spec['scenes']:
        for arm in ('A', 'G'):
            if arm == 'A' and scene['id'] not in DEFAULT_ARM_SCENES:
                continue
            path = HERE / 'runs' / arm / scene['id']
            frames = benchmark.saved_run_frames(path)
            failed = (path / 'failure.json').exists()
            record = dict(scene=scene['id'], arm=arm, frames=len(frames), failed_run=failed,
                          outcome=benchmark.read(path / 'failure.json')['reason'] if failed else
                                  benchmark.read(path / 'metrics.json')['stop_reason'],
                          rendered=False, no_solves_for_this_rendering=True)
            if frames and not (path / 'inversion.mp4').exists():
                label = 'FAILED — ' if failed else ''
                benchmark.driver.render_case(
                    path, f"{label}{scene['title']} / {benchmark.ARM_LABELS[arm]}",
                    benchmark.truth_curves(scene), frames,
                    benchmark.read(path / 'events.json') if (path / 'events.json').exists() else ())
                record['rendered'] = True
            record['video'] = str((path / 'inversion.mp4').relative_to(HERE)) if (path / 'inversion.mp4').exists() else None
            records.append(record)
            print(json.dumps(record), flush=True)
    benchmark.driver.write_json(HERE / 'videos.json', records)


if __name__ == '__main__':
    main()
