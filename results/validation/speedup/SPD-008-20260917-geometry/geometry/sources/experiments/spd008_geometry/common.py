"""Existing pipeline seams and frozen provenance for SPD-008."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import shutil
import signal

from experiments.spd006_compiled import run as prior
from ordered_boundary.validation_cache import geometry_validation

previous = prior.previous
ROOT, p, m, pipeline = previous.ROOT, previous.p, previous.m, previous.pipeline
read, write, sha = previous.read, previous.write, previous.sha
PLAN = ROOT/'docs/iterations/speedup/iteration_07/03_plan.md'
ARCHIVE = ROOT/'results/validation/speedup/SPD-006-20260916-full-inverse'
SCENES = ('death', 'merge', 'central-ellipse-star', 'far-two-stars')
ARMS = ('reference', 'certified')
TESTS = (
    'pytest/sdf_inverse/test_spd008.py', 'pytest/sdf_inverse/test_spd008_experiment.py',
    'pytest/ordered_boundary',
    'pytest/gpr_bem_kress/test_isolation_and_api.py', 'pytest/gpr_bem_kress/test_multicomponent.py',
    'pytest/sdf_inverse/test_refined_feasibility_guard.py',
    'pytest/sdf_inverse/test_feasible_finite_differences.py',
    'pytest/sdf_inverse/test_cartesian_fourier_chart.py',
    'pytest/sdf_inverse/test_spd001.py', 'pytest/sdf_inverse/test_spd006.py',
    'pytest/sdf_inverse/test_spd007.py', 'pytest/sdf_inverse/test_top025.py',
)


def sources():
    files = list(Path(__file__).parent.glob('*.py'))
    for name in TESTS:
        path = ROOT/name
        files.extend(path.glob('*.py') if path.is_dir() else [path])
    return {**prior.sources(), **{str(x.relative_to(ROOT)):sha(x) for x in sorted(files)}}


def freeze(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    frozen = sources()
    for name in frozen:
        target = folder/'sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    write(folder/'manifest.json',dict(source_sha256=frozen,
        input_sha256={str(path.relative_to(ROOT)):sha(path) for path in inputs},
        environment=previous.environment(), prepared_utc=datetime.now(timezone.utc).isoformat()))
    return frozen


def verify(folder):
    manifest = read(folder/'manifest.json')
    if sources() != manifest['source_sha256']:
        raise RuntimeError('SPD-008 source drift')
    for name, digest in manifest['input_sha256'].items():
        if sha(ROOT/name) != digest:
            raise RuntimeError('SPD-008 input drift: '+name)


@contextmanager
def wall_limit(seconds):
    def expired(*_):
        raise TimeoutError('SPD-008 phase wall ceiling reached')
    old = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def record_fit(snapshots):
    # Fits run sequentially. This retains tiny diagnostics, not cache entries.
    def record(snapshot):
        snapshots.append(snapshot)
    return record
