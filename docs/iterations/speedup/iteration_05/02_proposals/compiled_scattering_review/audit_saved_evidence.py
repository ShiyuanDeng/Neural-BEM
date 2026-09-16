"""Read saved evidence only: hashes, timing medians, and coefficient bounds.

No solver imports, field evaluations, optimization, or timing experiments.
Run from the repository root; prints JSON without modifying source artifacts.
"""
import hashlib
import itertools
import json
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[6]
TOPOLOGY = ROOT / 'results/validation/topology/TOP-025-20260915-210356-all-scenes-current'
BIE = ROOT / 'results/experiments/modal_muller_20260916/deformable_scattering'
inputs = {}


def read(path):
    raw = path.read_bytes()
    inputs[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def bounds(state, acquisition):
    objects = []
    for component in state or []:
        assert component['chart'] == 'cartesian'
        mode = component['maximum_mode']
        values = component['parameters']
        assert len(values) == 4 * mode + 2
        cosine = [complex(*values[2*i:2*i+2]) for i in range(mode+1)]
        tail = values[2*(mode+1):]
        sine = [complex(*tail[2*i:2*i+2]) for i in range(mode)]
        # Exact change of coordinates, z_+k=(C_k-i S_k)/2,
        # z_-k=(C_k+i S_k)/2. Matches compile_template's sum-|z_j| bound.
        radius = sum(abs((c-1j*s)/2) + abs((c+1j*s)/2)
                     for c, s in zip(cosine[1:], sine))
        objects.append((cosine[0], radius))
    gaps = [abs(a[0]-b[0])-a[1]-b[1]
            for a, b in itertools.combinations(objects, 2)]
    clearance = [abs(complex(*p)-center)-radius for center, radius in objects
                 for key in ('source_points', 'receiver_points') for p in acquisition[key]]
    return dict(components=len(objects), min_circle_gap_m=min(gaps, default=None),
                min_acquisition_clearance_m=min(clearance, default=None),
                bounding_circle_checks_pass=bool(objects) and all(g > 0 for g in gaps+clearance))


def main():
    manifest = read(BIE / 'manifest.json')
    changed = [name for name, expected in manifest['source_hashes'].items()
               if not (ROOT/name).is_file()
               or hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected]
    runs = read(BIE / 'summary.json')
    saved_findings = read(BIE / 'findings.json')
    timings = {}
    for case in sorted({r['case'] for r in runs}):
        timings[case] = {arm: median(r['seconds'] for r in runs
                                    if r['case'] == case and r['arm'] == arm)
                         for arm in sorted({r['arm'] for r in runs})}
    assert timings == saved_findings['median_seconds']
    scenes = []
    for folder in sorted((TOPOLOGY/'inputs').iterdir()):
        acquisition = read(folder/'observations.json')
        scene = dict(scene=folder.name, initial=bounds(read(folder/'initial_state.json'), acquisition))
        handoff = TOPOLOGY/'runs'/folder.name/'handoff.json'
        scene['handoff'] = bounds(read(handoff)['state'], acquisition) if handoff.is_file() else None
        trajectory = TOPOLOGY/'runs'/folder.name/'topology/trajectory.jsonl'
        raw = trajectory.read_bytes()
        inputs[str(trajectory.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
        scene['saved_topology_states'] = [dict(label=r['label'], **bounds(r['state'], acquisition))
                                         for r in map(json.loads, raw.splitlines())]
        scenes.append(scene)
    handoffs = [s['handoff'] for s in scenes if s['handoff'] is not None]
    states = [r for s in scenes for r in s['saved_topology_states']]
    nonempty = [r for r in states if r['components']]
    result = dict(scope='Saved-evidence arithmetic only; no numerical solver run or accuracy qualification.',
                  benchmark_source_count=len(manifest['source_hashes']), changed_benchmark_sources=changed,
                  successful_saved_inverses=sum(r['success'] for r in runs), saved_inverse_count=len(runs),
                  median_seconds=timings, scenes=scenes,
                  totals=dict(handoffs=len(handoffs),
                              handoffs_passing_bounds=sum(r['bounding_circle_checks_pass'] for r in handoffs),
                              saved_topology_states=len(states), nonempty_saved_topology_states=len(nonempty),
                              nonempty_states_passing_bounds=sum(r['bounding_circle_checks_pass'] for r in nonempty),
                              minimum_saved_pair_gap_m=min(r['min_circle_gap_m'] for r in nonempty
                                                           if r['min_circle_gap_m'] is not None)),
                  limits=['Bounding checks do not establish angular-order or derivative convergence.',
                          'Saved trajectory states do not include every trial, rejected candidate, or continuation state.',
                          'Empty states require the existing free-space path.',
                          'Existing test results were reviewed; tests were not rerun.'],
                  input_sha256=inputs, audit_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
