"""Fixed physical charts and existing-solver adapters for TR diagnostics."""
from dataclasses import replace
from pathlib import Path
from time import perf_counter
import subprocess
import tarfile
import traceback
import numpy as np
from scipy.linalg import eigh

from bem_inverse.continuation.geometry import FourierCurve, normal_basis, arclength_angles
from bem_inverse.continuation.geometry_runtime import geometry_runtime
from bem_inverse.continuation.lm_backend import normalize
from bem_inverse.geometry import ProjectedUpdate, resize, values
from bem_inverse.io import curve_from, curve_record, digest, read, write
from bem_inverse.physics import NodalKress, Execution
from bem_inverse.policy import CumulativePolicy
from experiments.cleaned_interface import benchmark as b, fm001

ROOT = b.ROOT
OUTPUT = ROOT/'results/validation/theory_radius'
PLAN = ROOT/'docs/iterations/theory_radius/iteration_01/03_plan.md'
CASES = ('circle_c13.3', 'modal__c4__development_c',
         'modal__c13.3__development_c', 'modal__c13.3__shifted_star')
FREQUENCIES = (.5e9, .75e9, 1e9, 1.25e9)
BANDS = (3, 5, 7, 9, 15)
EXECUTION = Execution(device='auto', frequency_threads=4)


def descriptor(case):
    return next(r for r in b.descriptors() if r['id'] == case)


def load_case(case):
    row = descriptor(CASES[2] if case == CASES[0] else case)
    problem = fm001.full_problem(row, fm001.OUTPUT)[0]
    truth = (FourierCurve.circle(.03/problem.length_unit_m) if case == CASES[0]
             else curve_from(read(ROOT/row['truth'])))
    return problem, truth


def select(observations, count=4):
    return tuple(next(o for o in observations if o.frequency_hz == f) for f in FREQUENCIES[:count])


def inverse_sqrt(a):
    w, v = eigh(a)
    if w[0] <= 1e-12*w[-1]:
        raise ValueError('Unresolved shape metric')
    return (v/np.sqrt(w))@v.T


class Chart:
    """q is real RMS mm at q=0; the Cartesian coefficient map is affine."""
    def __init__(self, base, band, length_unit_m=.05, projected=False, storage=192):
        self.base, self.band, self.unit = base, band, length_unit_m
        self.dimension = 2*band+1
        self.projected = projected
        if projected:
            if base.band > storage:
                raise ValueError('A diagnostic chart must not truncate its origin')
            base = resize(base, storage)  # stage entry pads without changing the curve
            self.update = ProjectedUpdate(length_unit_m)
            with geometry_runtime(EXECUTION.geometry):
                self.space = self.update.prepare(base, band, storage)
            raw = self.space.derivatives/1000.  # package coordinates per mm
            self.base = resize(base, storage)
        else:
            self.base = resize(base, max(storage, base.band))
            nodes = base.nodes(2048)
            basis = normal_basis(nodes, band)
            raw = np.fft.fft(basis*(nodes.normals@np.array([1, 1j]))[:, None], axis=0)/2048
            raw = raw[np.arange(-self.base.band, self.base.band+1) % 2048]/(1000*length_unit_m)
        nodes = self.base.nodes(2048)
        normals = nodes.normals@np.array([1, 1j])
        normal_mm = (values(raw, 2048)*np.conj(normals[:, None])).real*(1000*length_unit_m)
        metric = normal_mm.T@((nodes.arc_length_weights/nodes.perimeter)[:, None]*normal_mm)
        self.transform = inverse_sqrt(metric)
        self.vectors = raw@self.transform
        gram = self.transform.T@metric@self.transform
        self.metric_error = float(np.linalg.norm(gram-np.eye(self.dimension), 2))
        self.projection_error = 0.
        if not projected:
            requested = normal_basis(nodes, band)/(1000*length_unit_m)
            actual = (values(raw, 2048)*np.conj(normals[:, None])).real
            self.projection_error = float(np.linalg.norm(actual-requested)/np.linalg.norm(requested))

    def curve(self, q):
        return FourierCurve(self.base.coefficients+self.vectors@np.asarray(q))

    def velocities(self, space, nodes):
        return (values(self.vectors, nodes.num_nodes)*np.conj(
            (nodes.normals@np.array([1, 1j]))[:, None])).real

    def production_trial(self, q):
        if not self.projected:
            raise ValueError('Production retraction requires projected chart')
        with geometry_runtime(EXECUTION.geometry):
            return self.update.trial(self.space, self.transform@q/1000.)[0]


class Budget:
    def __init__(self, seconds, solves):
        self.started, self.seconds, self.cap = perf_counter(), seconds, solves
        self.attempted = self.completed = self.failed = self.derivatives = 0

    def reserve(self, count):
        if self.attempted+count > self.cap or perf_counter()-self.started >= self.seconds:
            raise TimeoutError('Declared diagnostic work/time cap reached')
        self.attempted += count

    def record(self):
        return dict(seconds=perf_counter()-self.started, seconds_cap=self.seconds,
                    frequency_solves_attempted=self.attempted, frequency_solves_completed=self.completed,
                    failed_frequency_solves=self.failed, derivatives=self.derivatives, solve_cap=self.cap)


class Evaluator:
    def __init__(self, problem, budget):
        self.problem, self.budget = problem, budget
        self.physics = NodalKress(EXECUTION)
        self.physics.validate(problem)

    def evaluate(self, chart, q, observations, nodes=512, jacobian=True, curve=None):
        curve = chart.curve(q) if curve is None else curve
        self.budget.reserve(len(observations))
        def one(obs):
            try:
                state = self.physics.evaluate(curve, obs, self.problem.contrast, nodes)
                self.budget.completed += 1
                derivative = self.physics.derivative(state, chart, None) if jacobian else None
                if jacobian:
                    self.budget.derivatives += 1
                return state.prediction, derivative
            except Exception:
                self.budget.failed += 1
                raise
        result = []
        # Consume each frequency promptly; at most four dense states are live.
        with self.physics.ordered_calls(one, observations) as calls:
            for call in calls:
                result.append(call())
        g = np.stack([x[0] for x in result], axis=1)
        j = np.stack([x[1] for x in result], axis=1) if jacobian else None
        return g, j


def rows(array, paired):
    # arrays: source, frequency, receiver[, coordinate]
    if not paired:
        return array.transpose((0, 2, 1)+tuple(range(3, array.ndim))).reshape(
            (-1, array.shape[1])+array.shape[3:])
    index = np.arange(array.shape[0])
    return array[index, :, index]


def normalized(array, observations, paired):
    target = np.stack([o.scattered for o in observations], axis=1)
    return normalize(rows(array, paired), rows(target, paired), np.ones(len(observations))/len(observations))


def residual_jacobian(g, j, observations, paired):
    d = np.stack([o.scattered for o in observations], axis=1)
    return normalized(g-d, observations, paired), normalized(j, observations, paired)


def spectrum(j):
    # A thin SVD omits structural zeros when there are fewer rows than columns.
    _, s, vt = np.linalg.svd(j, full_matrices=j.shape[0] < j.shape[1])
    s = np.pad(s, (0, j.shape[1]-len(s)))
    return s, vt[-1]


def op_problem(case, full, label):
    row = descriptor(case)
    problem = fm001.full_problem(row, fm001.OUTPUT)[0]
    # Always solve full data and select its archived paired diagonal as needed.
    physics = NodalKress(EXECUTION)
    op = next(o for o in CumulativePolicy().operations(problem, physics) if o.label == label)
    return problem, op


def archived(case, full, stage):
    root = fm001.OUTPUT/'F' if full else b.DEFAULT_OUTPUT
    return root/'runs'/case/(stage+'.json')


def seal(folder, phase):
    if folder.exists():
        raise FileExistsError('Preserve existing experiment: '+str(folder))
    folder.mkdir(parents=True)
    sources = sorted(set((ROOT/'solvers').rglob('*.py')) |
                     set((ROOT/'experiments/theory_radius').glob('*.py')) |
                     set((ROOT/'experiments/cleaned_interface').glob('*.py')) |
                     set((ROOT/'experiments/shape_continuation').glob('*.py')) |
                     {ROOT/'experiments/modal_atlas/mie_localize.py', PLAN})
    inputs = {ROOT/'docs/theory_directions_cartesian_fourier_2026-10-03.md', b.SOURCE_MANIFEST}
    for case in CASES[1:]:
        row = descriptor(case)
        inputs.update(ROOT/row[k] for k in ('truth', 'data', 'initial', 'damped') if k in row)
        inputs.update((fm001.OUTPUT/'catalogs'/case).glob('*'))
        for full in (False, True):
            for stage in ('stage_1_damped', 'stage_2_damped', 'stage_3_damped',
                          'stage_4_damped', 'stage_4_undamped'):
                inputs.add(archived(case, full, stage))
    if phase != 'TR-001':
        inputs.update((OUTPUT/'TR-001').glob('*.json'))
        inputs.update((OUTPUT/'TR-001/rows').glob('*.json'))
    if phase == 'TR-003-branches':
        inputs.update((OUTPUT/'TR-003').rglob('*.json'))
    with tarfile.open(folder/'sources.tar.gz', 'w:gz') as archive:
        for p in sources:
            archive.add(p, arcname=b.path_ref(p), recursive=False)
    record = dict(phase=phase, commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
                  sources={b.path_ref(p):digest(p) for p in sources},
                  inputs={b.path_ref(p):digest(p) for p in sorted(inputs) if p.is_file()},
                  source_archive_sha256=digest(folder/'sources.tar.gz'), execution=EXECUTION.__dict__,
                  concurrency=subprocess.check_output(['ps','-eo','pid,comm,args'],text=True).splitlines(),
                  environment=b.environment())
    # Retain only relevant processes, not unrelated command arguments.
    record['concurrency'] = [x for x in record['concurrency'] if 'python' in x and
                             ('fm003' in x or 'theory_radius' in x)]
    write(folder/'manifest.json', record)


def verify(folder):
    record = read(folder/'manifest.json')
    for group in ('sources', 'inputs'):
        for name, value in record[group].items():
            if digest(ROOT/name) != value:
                raise ValueError('Sealed file changed: '+name)
    if digest(folder/'sources.tar.gz') != record['source_archive_sha256']:
        raise ValueError('Source archive changed')
    return True


def execute(phase, function, seconds, solves):
    folder = OUTPUT/phase
    seal(folder, phase)
    budget = Budget(seconds, solves)
    try:
        with geometry_runtime(EXECUTION.geometry):
            function(folder, budget)
        verify(folder)
        write(folder/'completion.json', dict(complete=True, work=budget.record()))
    except Exception:
        write(folder/'failure.json', dict(complete=False, traceback=traceback.format_exc(), work=budget.record()))
        raise
