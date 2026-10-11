"""CG-003: bounded, ancestry-preserving loop search and real graph controls.

The saved CG-001 census selects routes only. Every complex root used here is
transported from q=1.3,t=0; real control crossings never seed the search.
"""
import argparse
from collections import deque
import gzip
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
from time import perf_counter
import traceback

import numpy as np
import scipy
from scipy.optimize import brentq

from bem_inverse.complex_paths import lollipop_path, radius_graph
from bem_inverse.complex_radius import ComplexDomainError, record_state, track
from bem_inverse.continuation.forward import solve
from bem_inverse.continuation.geometry import FourierCurve
from . import cg001 as C
from .cg002 import compressed


OUTPUT = C.ROOT/'results/validation/complex_geometry/CG-003/run-01'
SOURCE = C.ROOT/'results/validation/complex_geometry/CG-001/run-02'
PLAN = C.ROOT/'docs/iterations/complex_geometry/CG-003_plan.md'
SEED_PATH = (0j, .01j, 1+.01j, 1+0j)
Q0 = 1.3
TOLERANCE = 1e-8
ROOT_TOLERANCE = 1e-7


class DomainModel:
    """Give complex paths the same real coordinate window as the controls."""
    def __init__(self, model):
        self.model = model

    def __getattr__(self, name):
        return getattr(self.model, name)

    @staticmethod
    def check(q, t=None):
        if not .5 <= complex(q).real <= 2.:
            raise ComplexDomainError('Q_DOMAIN_BOUNDARY: CG-003 Re(q) outside shared [.5,2] window')
        if t is not None and not -2. <= complex(t).real <= 3.:
            raise ComplexDomainError('T_DOMAIN_BOUNDARY: CG-003 Re(t) outside shared [-2,3] window')

    def state(self, q, t):
        self.check(q, t)
        return self.model.state(q, t)

    def ab(self, q):
        self.check(q)
        return self.model.ab(q)


class WallBudget:
    def __init__(self, started, hard_seconds=900., discovery_seconds=720.):
        self.started = started
        self.hard_seconds = hard_seconds
        self.discovery_seconds = discovery_seconds

    def elapsed(self):
        return perf_counter()-self.started

    def check(self, discovery=False):
        limit = self.discovery_seconds if discovery else self.hard_seconds
        if self.elapsed() >= limit:
            raise TimeoutError(f'CG-003 {"discovery" if discovery else "overall"} '
                               f'{limit:g} second wall budget exhausted')


class BudgetModel:
    """Let existing trackers return their partial trajectories on time limits.

    Their domain-refusal path retains accepted/rejected states. Direct
    qualification and instrument calls retain the ordinary TimeoutError.
    """
    def __init__(self, model, budget, discovery=False):
        self.model, self.budget, self.discovery = model, budget, discovery
        self.budget_stop = None

    def __getattr__(self, name):
        return getattr(self.model, name)

    def _call(self, method, *args):
        try:
            self.budget.check(self.discovery)
            return getattr(self.model, method)(*args)
        except TimeoutError as exc:
            self.budget_stop = str(exc)
            raise ComplexDomainError(str(exc)) from exc

    def state(self, q, t):
        return self._call('state', q, t)

    def ab(self, q):
        return self._call('ab', q)


def counter_delta(before, after):
    return {key: after[key]-before[key] for key in before}


def path_indices(states, every=False):
    if not states:
        return []
    if every:
        return list(range(len(states)))
    indices = set(np.linspace(0, len(states)-1, min(65, len(states)), dtype=int))
    indices.update((len(states)-1,
        int(np.argmin([row['margin'] for row in states])),
        int(np.argmax([abs(row['q'].imag) for row in states]))))
    return sorted(indices)


def load_arm(path):
    with gzip.open(path, 'rt') as stream:
        result = json.load(stream)
    for state in result.get('states', []):
        for key in ('q', 't', 'F', 'Fq', 'Fqq', 'Ft'):
            state[key] = C.z(state[key])
    return result


def join_routes(names, routes):
    result = []
    for name in names:
        part = list(routes[name])
        if result:
            if abs(result[-1]-part[0]) > 1e-12:
                raise ValueError('Disconnected ancestry route')
            part = part[1:]
        result.extend(part)
    return result


def snapshot_manifest(output):
    original = json.loads((SOURCE/'manifest.json').read_text())
    sources = dict(original['source_hashes'])
    changed = [name for name, digest in sources.items()
               if not (C.ROOT/name).exists() or C.sha(C.ROOT/name) != digest]
    additions = (Path(__file__), C.ROOT/'solvers/bem_inverse/complex_paths.py',
        C.ROOT/'pytest/bem_inverse/test_complex_paths.py', PLAN,
        C.ROOT/'experiments/benchmark/cg002.py')
    for path in additions:
        sources[str(path.relative_to(C.ROOT))] = C.sha(path)
    manifest = dict(experiment='CG-003', source_hashes=sources,
        qualification_source_mismatches=changed,
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
            cwd=C.ROOT, text=True).strip(),
        branch=subprocess.check_output(['git', 'branch', '--show-current'],
            cwd=C.ROOT, text=True).strip(),
        qualification_sha256=C.sha(SOURCE/'qualification.json'),
        census_sha256=C.sha(SOURCE/'census_02.json'),
        source_manifest_sha256=C.sha(SOURCE/'manifest.json'),
        input_manifest_sha256=C.sha(C.campaign.INPUTS/'manifest.json'),
        qualified_input_manifest_sha256=original['input_manifest_sha256'],
        case='circle__c13.3', frequency_ghz=1.5, q0=Q0, seed_path=SEED_PATH,
        max_expanded_roots=3, max_discovery_loops=120, hard_seconds=900.,
        discovery_seconds=720., max_parameter_step=.004,
        half_parameter_step=.002, loop_height=.05, loop_segments=256,
        environment=dict(python=platform.python_version(), numpy=np.__version__,
            scipy=scipy.__version__, platform=platform.platform(), workers=1,
            threads={key: os.environ.get(key) for key in
                     ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')}))
    C.write(output/'manifest.json', manifest)
    for name, digest in sources.items():
        target = output/'source_snapshot'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((C.ROOT/name).read_bytes())
        if C.sha(target) != digest:
            raise ValueError(f'Source changed during snapshot: {name}')
    for name in ('manifest.json', 'qualification.json', 'census_02.json'):
        target = output/'qualification_snapshot'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((SOURCE/name).read_bytes())
    if changed:
        raise ValueError(f'Qualified numerical sources changed: {changed}')
    if manifest['input_manifest_sha256'] != original['input_manifest_sha256']:
        raise ValueError('Qualified input manifest changed')
    return manifest


class Experiment:
    def __init__(self, output, budget):
        self.output, self.budget = output, budget
        self.model = self.refined = None
        self.arms, self.routes, self.nodes, self.edges = {}, {}, [], []
        self.controls, self.confirmations = {}, []
        self.discovery_loops = self.expanded_roots = self.nodal_solves = 0
        self.initial = None

    def progress(self):
        C.write(self.output/'summary_progress.json', dict(arms=self.arms,
            nodes=self.nodes, edges=self.edges, controls=self.controls,
            confirmations=self.confirmations, initial=self.initial,
            discovery_loops=self.discovery_loops, expanded_roots=self.expanded_roots,
            seconds=self.budget.elapsed(), nodal_solves=self.nodal_solves,
            counters=None if self.model is None else self.model.counters(),
            refined_counters=None if self.refined is None else self.refined.counters()))

    def refine(self, result, every=False):
        checks = []
        result['refined_checks'] = checks
        result['refinement_scope'] = 'every_accepted_state' if every else '65_plus_extrema'
        result['numerically_qualified'] = False
        for index in path_indices(result.get('states', []), every):
            self.budget.check()
            row = result['states'][index]
            q, t = row['q'], row['t']
            coarse, fine = self.model.state(q, t), self.refined.state(q, t)
            checks.append(dict(index=int(index),
                field=C.relative(self.model.jets(q)[0][0], self.refined.jets(q)[0][0]),
                stationarity=abs(fine['F'])/fine['scale'],
                coarse_stationarity=abs(coarse['F'])/coarse['scale'],
                Fq_relative=abs(fine['Fq']-coarse['Fq'])/max(1., abs(coarse['Fq']))))
        result['numerically_qualified'] = bool(checks and all(
            max(check[key] for key in ('field', 'stationarity', 'coarse_stationarity',
                                      'Fq_relative')) <= TOLERANCE for check in checks))

    def summary(self, result):
        states = result.get('states', [])
        answer = dict(status=result['status'], path=result['receipt'],
            accepted_states=len(states), rejected_steps=len(result.get('rejected', [])),
            attempts=result.get('attempts'), seconds=result.get('seconds'),
            numerically_qualified=result.get('numerically_qualified', False),
            exception=result.get('exception'), budget_stop=result.get('budget_stop'))
        if states:
            last = states[-1]
            answer.update(endpoint_q=last['q'], endpoint_t=last['t'],
                stationarity=abs(last['F'])/last['scale'], Fq=last['Fq'],
                max_imaginary_radius=max(abs(row['q'].imag) for row in states),
                minimum_pole_margin=min(row['margin'] for row in states),
                min_real_q=min(row['q'].real for row in states),
                max_real_q=max(row['q'].real for row in states),
                min_real_t=min(row['t'].real for row in states),
                max_real_t=max(row['t'].real for row in states))
        if result.get('refined_checks'):
            answer['maximum_refinement_errors'] = {
                key: max(check[key] for check in result['refined_checks'])
                for key in ('field', 'stationarity', 'coarse_stationarity', 'Fq_relative')}
        for key in ('counter_delta', 'refined_counter_delta', 't1_crossings',
                    'graph_steps', 'accepted_steps', 'graph_options', 'last_reason'):
            if key in result:
                answer[key] = result[key]
        return answer

    def arm(self, name, q, waypoints=None, *, service=None, max_step=.004,
            graph_options=None, discovery=False, every=False):
        if name in self.arms:
            raise ValueError(f'Duplicate arm name: {name}')
        service = self.model if service is None else service
        proxy = BudgetModel(service, self.budget, discovery)
        started = perf_counter()
        before, before_fine = self.model.counters(), self.refined.counters()
        receipt = f'{name}.json.gz'
        result = dict(status='STARTED', states=[], rejected=[], start_q=complex(q),
            waypoints=waypoints, graph_options=graph_options, receipt=receipt,
            max_step=max_step, source_cutoffs=service.cutoffs,
            numerically_qualified=False)
        if waypoints is not None:
            self.routes[name] = list(map(complex, waypoints))
        compressed(self.output/receipt, result)
        self.arms[name] = self.summary(result)
        self.progress()
        try:
            self.budget.check(discovery)
            measured = (radius_graph(proxy, q, **graph_options) if graph_options is not None
                        else track(proxy, q, waypoints, max_step=max_step,
                                   min_step=1e-8, max_attempts=20000))
            result.update(measured)
            if proxy.budget_stop:
                result.update(status='TIME_BUDGET', budget_stop=proxy.budget_stop)
            # Preserve the full returned trajectory before any post-processing.
            compressed(self.output/receipt, result)
            self.refine(result, every)
        except Exception:
            result['exception'] = traceback.format_exc()
            result['status_before_exception'] = result['status']
            result['status'] = 'EXCEPTION'
            result['numerically_qualified'] = False
            result['partial_state_note'] = (
                'Returned states are retained; an exception before tracker return '
                'does not expose its local accepted/rejected lists.')
        finally:
            result['total_seconds_including_qualification'] = perf_counter()-started
            result['counter_delta'] = counter_delta(before, self.model.counters())
            result['refined_counter_delta'] = counter_delta(before_fine, self.refined.counters())
            compressed(self.output/receipt, result)
            self.arms[name] = self.summary(result)
            self.progress()
            print('ARM', name, result['status'], len(result['states']),
                  'qualified', result['numerically_qualified'], flush=True)
        return result

    def endpoint(self, q, t=1.):
        self.budget.check()
        coarse, fine = self.model.state(q, t), self.refined.state(q, t)
        real = abs(complex(q).imag) <= TOLERANCE and abs(complex(t).imag) <= TOLERANCE
        field = C.relative(self.model.jets(q)[0][0], self.refined.jets(q)[0][0])
        hessian_error = abs(fine['Fq']-coarse['Fq'])/max(1., abs(coarse['Fq']))
        stationary = max(abs(coarse['F'])/coarse['scale'], abs(fine['F'])/fine['scale'])
        regular = min(abs(coarse['Fq']), abs(fine['Fq'])) > 1e-6
        qualified = max(field, hessian_error, stationary) <= TOLERANCE
        loss = self.model.real_loss(q, t) if real else None
        return dict(q=complex(q), t=complex(t), radius_mm=50*complex(q), real=bool(real),
            Fq=coarse['Fq'], refined_Fq=fine['Fq'],
            hessian=float(coarse['Fq'].real) if real else None,
            scaled_stationarity=float(stationary), field_refinement=field,
            hessian_refinement=float(hessian_error), regular=bool(regular),
            qualified=bool(qualified), data_loss=loss,
            relative_residual=None if loss is None else float(np.sqrt(2*loss)),
            qualified_real_minimum=bool(real and qualified and regular and
                min(coarse['Fq'].real, fine['Fq'].real) > 1e-6))

    @staticmethod
    def completed(result, t):
        return (result['status'] == 'COMPLETED' and result['numerically_qualified']
                and bool(result['states']) and abs(result['states'][-1]['t']-t) <= 1e-10)

    def crossings(self, name, result):
        found = []
        for bracket in result.get('t1_brackets', []):
            check = dict(bracket=bracket)
            try:
                self.budget.check()
                lo, hi = sorted((float(np.real(bracket['q_left'])),
                                 float(np.real(bracket['q_right']))))
                if lo == hi:
                    raise ValueError('Degenerate real crossing bracket')
                q = brentq(lambda x: self.model.state(x, 1.)['F'].real, lo, hi,
                    xtol=np.nextafter(0., 1.), rtol=4*np.finfo(float).eps, maxiter=100)
                if not lo <= q <= hi:
                    raise ValueError('Bracketed t=1 root escaped accepted q interval')
                check.update(self.endpoint(q))
                previous = [row['q'] for row in found if 'q' in row]
                distance = min((abs(q-other) for other in previous), default=None)
                check['nearest_previous_crossing_distance'] = distance
                check['duplicate'] = distance is not None and distance <= ROOT_TOLERANCE
                check['control_path_qualified'] = result['numerically_qualified']
                check['endpoint_qualified'] = check['qualified']
                check['qualified'] = check['qualified'] and result['numerically_qualified']
                check['qualified_real_minimum'] = (check['qualified_real_minimum']
                                                   and result['numerically_qualified'])
            except Exception:
                check.update(qualified=False, qualified_real_minimum=False,
                             exception=traceback.format_exc())
            found.append(check)
        result['t1_crossings'] = found
        compressed(self.output/result['receipt'], result)
        self.arms[name] = self.summary(result)
        return found

    def real_controls(self):
        for direction in (1, -1):
            pair = []
            for half, step in ((False, 1e-5), (True, 5e-6)):
                self.budget.check()
                name = f'real_graph_{direction:+d}_{"half" if half else "base"}'
                options = dict(direction=direction, q_bounds=(.5, 2.), t_bounds=(-2., 3.),
                    max_dq=step, max_dt=.002, min_dq=1e-10, steps=20000)
                result = self.arm(name, Q0, graph_options=options)
                crossings = self.crossings(name, result)
                self.controls[name] = dict(status=result['status'],
                    numerically_qualified=result['numerically_qualified'], crossings=crossings,
                    endpoint_q=None if not result['states'] else result['states'][-1]['q'],
                    endpoint_t=None if not result['states'] else result['states'][-1]['t'])
                pair.append((name, result, crossings))
                self.progress()
            base, half = pair
            half_roots = [row['q'] for row in half[2]
                          if row.get('qualified') and not row.get('duplicate')]
            self.controls[f'real_graph_{direction:+d}_comparison'] = dict(
                base=base[0], half=half[0], note=(
                    'Identical accepted-step allowances can give different q exposure; '
                    'absence outside the common traced interval is not a replay failure.'),
                crossings=[dict(q=row['q'], nearest_half_distance=min(
                    (abs(row['q']-q) for q in half_roots), default=None))
                    for row in base[2] if row.get('qualified') and not row.get('duplicate')])
            self.progress()

    def nodal_endpoint(self, q):
        self.budget.check()
        if abs(complex(q).imag) > TOLERANCE:
            raise ValueError('Nodal endpoint check requires a numerically real radius')
        obs = self.model.observations[0]
        predictions = []
        for n in (512, 1024):
            self.budget.check()
            self.nodal_solves += 1
            predictions.append(solve(FourierCurve.circle(float(np.real(q))),
                obs.wavenumber, self.model.contrast, obs.acquisition, n,
                execution_backend='cpu').prediction)
        exact = self.model.jets(float(np.real(q)))[0][0]*self.model.scales[0]
        fine = self.refined.jets(float(np.real(q)))[0][0]*self.refined.scales[0]
        check = dict(nodal_error=C.relative(exact, predictions[1]),
            refined_nodal_error=C.relative(fine, predictions[1]),
            nodal_refinement=C.relative(predictions[0], predictions[1]),
            observed_data_norm=float(np.linalg.norm(obs.scattered)),
            refined_field_norm=float(np.linalg.norm(fine)), n=[512, 1024])
        check['passed'] = max(check[key] for key in
            ('nodal_error', 'refined_nodal_error', 'nodal_refinement')) <= TOLERANCE
        return check

    def confirm(self, candidate, ancestry):
        index = len(self.confirmations)
        check = dict(index=index, q=candidate['q'], ancestry=list(ancestry),
                     status='STARTED', passed=False)
        self.confirmations.append(check)
        self.progress()
        try:
            self.budget.check()
            waypoints = join_routes(ancestry, self.routes)
            check['full_waypoints'] = waypoints
            ancestry_checks = []
            check['ancestry_refinement'] = ancestry_checks
            for name in ancestry:
                result = load_arm(self.output/self.arms[name]['path'])
                try:
                    self.refine(result, every=True)
                finally:
                    compressed(self.output/result['receipt'], result)
                    self.arms[name] = self.summary(result)
                ancestry_checks.append(dict(name=name,
                    numerically_qualified=result['numerically_qualified']))
            half = self.arm(f'confirm_{index:02d}_full_half', Q0, waypoints,
                            max_step=.002, every=True)
            fine = self.arm(f'confirm_{index:02d}_full_fine', Q0, waypoints,
                            service=self.refined, max_step=.002, every=True)
            check['half_completed'] = self.completed(half, 1.)
            check['fine_completed'] = self.completed(fine, 1.)
            if not check['half_completed'] or not check['fine_completed']:
                check['status'] = 'FULL_REPLAY_FAILED'
                return check
            qh, qf = half['states'][-1]['q'], fine['states'][-1]['q']
            check.update(half_endpoint=self.endpoint(qh), fine_endpoint=self.endpoint(qf),
                half_error=abs(qh-candidate['q']), fine_error=abs(qf-candidate['q']),
                half_fine_error=abs(qh-qf))
            reverse = self.arm(f'confirm_{index:02d}_full_reverse', qh,
                               list(reversed(waypoints)), max_step=.002, every=True)
            check['reverse_completed'] = self.completed(reverse, 0.)
            check['reverse_error'] = (abs(reverse['states'][-1]['q']-Q0)
                                      if reverse['states'] else None)
            check['nodal'] = self.nodal_endpoint(qh)
            check['passed'] = bool(all(row['numerically_qualified'] for row in ancestry_checks)
                and check['half_endpoint']['qualified_real_minimum']
                and check['fine_endpoint']['qualified_real_minimum']
                and max(check['half_error'], check['fine_error'], check['half_fine_error'])
                    <= ROOT_TOLERANCE
                and check['reverse_completed'] and check['reverse_error'] <= ROOT_TOLERANCE
                and check['nodal']['passed'])
            check['status'] = 'CONFIRMED_REAL_MINIMUM' if check['passed'] else 'CONFIRMATION_FAILED'
        except Exception:
            check.update(status='CONFIRMATION_EXCEPTION', exception=traceback.format_exc())
        finally:
            C.write(self.output/f'confirmation_{index:02d}.json', check)
            self.progress()
        return check

    def search(self, folds):
        self.budget.check(discovery=True)
        seed = self.arm('seed', Q0, SEED_PATH, discovery=True)
        if not self.completed(seed, 1.):
            return 'SEED_NOT_QUALIFIED', None
        initial = self.endpoint(seed['states'][-1]['q'])
        if not initial['qualified'] or not initial['regular']:
            return 'SEED_NOT_QUALIFIED', None
        self.nodes.append(dict(id=0, endpoint=initial, ancestry=['seed'], parent=None,
                               depth=0, expanded=False))
        self.progress()
        if initial['qualified_real_minimum']:
            confirmation = self.confirm(initial, ['seed'])
            if confirmation['passed']:
                return 'CONFIRMED_REAL_MINIMUM', confirmation
        queue = deque([0])
        while queue and self.expanded_roots < 3 and self.discovery_loops < 120:
            if self.budget.elapsed() >= self.budget.discovery_seconds:
                return 'DISCOVERY_TIME_BUDGET', None
            node = self.nodes[queue.popleft()]
            node['expanded'] = True
            self.expanded_roots += 1
            root = node['endpoint']['q']
            ordered = sorted(folds, key=lambda fold:
                (abs(fold['q']-root), fold['t'], fold['q']))
            for fold in ordered:
                if self.discovery_loops >= 120:
                    return 'DISCOVERY_LOOP_BUDGET', None
                if self.budget.elapsed() >= self.budget.discovery_seconds:
                    return 'DISCOVERY_TIME_BUDGET', None
                distances = [abs(other['t']-fold['t']) for other in folds
                             if other['census_index'] != fold['census_index']]
                radius = min(.01, .2*min(distances), .2*abs(fold['t']-1.))
                edge = dict(id=len(self.edges), parent=node['id'], fold=fold,
                    radius=radius, discovery_number=None, status='STARTED')
                self.edges.append(edge)
                if radius < 1e-5:
                    edge['status'] = 'SKIPPED_SMALL_RADIUS'
                    self.progress()
                    continue
                self.discovery_loops += 1
                edge['discovery_number'] = self.discovery_loops
                name = f'edge_{edge["id"]:03d}'
                waypoints = lollipop_path(fold['t'], radius, base=1., height=.05, points=256)
                edge['arm'] = name
                result = self.arm(name, root, waypoints, discovery=True)
                if not self.completed(result, 1.):
                    edge['status'] = 'PATH_NOT_QUALIFIED'
                    self.progress()
                    continue
                endpoint = self.endpoint(result['states'][-1]['q'])
                edge['endpoint'] = endpoint
                if not endpoint['qualified'] or not endpoint['regular']:
                    edge['status'] = 'ENDPOINT_NOT_QUALIFIED'
                    self.progress()
                    continue
                nearest = min(self.nodes, key=lambda other:
                              abs(endpoint['q']-other['endpoint']['q']))
                edge['nearest_node'] = nearest['id']
                edge['nearest_root_distance'] = abs(endpoint['q']-nearest['endpoint']['q'])
                if edge['nearest_root_distance'] <= ROOT_TOLERANCE:
                    edge['status'] = 'KNOWN_ROOT'
                    self.progress()
                    continue
                half = self.arm(name+'_half', root, waypoints, max_step=.002)
                reverse = self.arm(name+'_reverse', endpoint['q'], list(reversed(waypoints)),
                                   max_step=.002)
                edge['half_error'] = (abs(half['states'][-1]['q']-endpoint['q'])
                                      if half['states'] else None)
                edge['reverse_error'] = (abs(reverse['states'][-1]['q']-root)
                                         if reverse['states'] else None)
                edge['qualified_new_edge'] = bool(self.completed(half, 1.)
                    and self.completed(reverse, 1.) and edge['half_error'] <= ROOT_TOLERANCE
                    and edge['reverse_error'] <= ROOT_TOLERANCE)
                if not edge['qualified_new_edge']:
                    edge['status'] = 'EDGE_REPLAY_FAILED'
                    self.progress()
                    continue
                child = dict(id=len(self.nodes), endpoint=endpoint, parent=node['id'],
                    via_edge=edge['id'], ancestry=node['ancestry']+[name],
                    depth=node['depth']+1, expanded=False)
                self.nodes.append(child)
                edge.update(status='NEW_QUALIFIED_ROOT', child=child['id'])
                queue.append(child['id'])
                self.progress()
                if endpoint['qualified_real_minimum']:
                    confirmation = self.confirm(endpoint, child['ancestry'])
                    edge['confirmation_index'] = confirmation['index']
                    if confirmation['passed']:
                        return 'CONFIRMED_REAL_MINIMUM', confirmation
        if self.expanded_roots >= 3:
            return 'EXPANDED_ROOT_BUDGET', None
        if self.discovery_loops >= 120:
            return 'DISCOVERY_LOOP_BUDGET', None
        return 'QUEUE_EXHAUSTED', None


def run(output=OUTPUT):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Preserve existing evidence; choose a fresh run directory')
    output.mkdir(parents=True)
    started = perf_counter()
    budget = WallBudget(started)
    previous_budget = C.ACTIVE_BUDGET
    C.ACTIVE_BUDGET = budget
    experiment = Experiment(output, budget)
    manifest = None
    outcome = dict(status='STARTED', experiment='CG-003')
    C.write(output/'outcome.json', outcome)
    try:
        manifest = snapshot_manifest(output)
        C.campaign.verify(require_inputs=True)
        saved = json.loads((SOURCE/'census_02.json').read_text())
        folds = [dict(q=float(row['q']), t=float(row['t']), census_index=index)
                 for index, row in enumerate(saved['folds']) if row['qualified']]
        if len(folds) != 46 or saved['contrast'] != 13.3 or saved['frequencies_ghz'] != [1.5]:
            raise ValueError('Frozen CG-001 qualified fold family does not match CG-003')
        experiment.model = DomainModel(C.instrument(13.3, (1.5,)))
        experiment.refined = DomainModel(C.instrument(13.3, (1.5,), 12))
        loss = experiment.model.real_loss(Q0)
        experiment.initial = dict(q=Q0, radius_mm=50*Q0, measured_data_loss=loss,
            relative_residual=float(np.sqrt(2*loss)),
            measured_state=record_state(experiment.model, Q0, 1.),
            initial_stationary_state=record_state(experiment.model, Q0, 0.),
            historical_cg002_positive_real_returns='0/3; comparison only, no imported endpoint')
        experiment.progress()
        experiment.real_controls()
        reason, confirmation = experiment.search(folds)
        outcome.update(status='CONFIRMED_REAL_MINIMUM' if confirmation else
                       'NO_CONFIRMED_REAL_MINIMUM_IN_BOUNDED_SEARCH',
                       stop_reason=reason, success=confirmation)
    except TimeoutError:
        outcome.update(status='TIME_BUDGET', stop_reason='OVERALL_OR_DISCOVERY_TIME_BUDGET',
                       exception=traceback.format_exc())
    except Exception:
        outcome.update(status='EXCEPTION', exception=traceback.format_exc())
        print(outcome['exception'], flush=True)
    finally:
        C.ACTIVE_BUDGET = previous_budget
        outcome.update(initial=experiment.initial, arms=experiment.arms,
            nodes=experiment.nodes, edges=experiment.edges, controls=experiment.controls,
            confirmations=experiment.confirmations, discovery_loops=experiment.discovery_loops,
            expanded_roots=experiment.expanded_roots, distinct_qualified_roots=len(experiment.nodes),
            nodal_solves=experiment.nodal_solves, seconds=perf_counter()-started,
            peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
            counters=None if experiment.model is None else experiment.model.counters(),
            refined_counters=None if experiment.refined is None else experiment.refined.counters())
        try:
            hashes = (manifest or json.loads((output/'manifest.json').read_text()))['source_hashes']
            outcome['sources_unchanged'] = all((C.ROOT/path).exists()
                and C.sha(C.ROOT/path) == digest for path, digest in hashes.items())
        except Exception:
            outcome['sources_unchanged'] = False
            outcome['source_check_exception'] = traceback.format_exc()
        if not outcome['sources_unchanged'] and outcome['status'] == 'CONFIRMED_REAL_MINIMUM':
            outcome['status_before_source_check'] = outcome['status']
            outcome['status'] = 'SOURCE_VALIDATION_FAILED'
        C.write(output/'outcome.json', outcome)
        experiment.progress()
        report(output)
        print('OUTCOME', outcome['status'], outcome['seconds'], flush=True)
    return outcome


def report(output=OUTPUT):
    """Generate a small read-only receipt summary, without evaluating physics."""
    output = Path(output)
    outcome = json.loads((output/'outcome.json').read_text())
    lines = ['# CG-003 saved measurements', '', f'Run status: **{outcome["status"]}**.', '',
        'Fixed-center transmission radius component study; no benchmark recovery claim.', '',
        f'Discovery loops: {outcome.get("discovery_loops", 0)}; expanded roots: '
        f'{outcome.get("expanded_roots", 0)}; qualified distinct roots: '
        f'{outcome.get("distinct_qualified_roots", 0)}.', '',
        '| Root | Radius mm, real + imaginary | Real | Hessian | Loss | Relative residual | Ancestry |',
        '|---|---|---|---:|---:|---:|---|']
    for node in outcome.get('nodes', []):
        row = node['endpoint']
        radius = 50*C.z(row['q'])
        lines.append(f'| {node["id"]} | {radius.real:.10g} {radius.imag:+.10g}i | '
            f'{row["real"]} | {row["hessian"]} | {row["data_loss"]} | '
            f'{row["relative_residual"]} | {" → ".join(node["ancestry"])} |')
    initial = outcome.get('initial')
    if initial:
        lines += ['', f'Initial measured-data loss: {initial["measured_data_loss"]:.12g}; '
            f'relative residual: {initial["relative_residual"]:.12g}.']
    lines += ['', 'Historical CG-002: 0/3 positive doglegs returned real; endpoints were not reused.', '',
        f'Seconds including controls and verification: {outcome.get("seconds")}.',
        f'Peak process RSS MiB: {outcome.get("peak_rss_mib")}.',
        f'Production counters: `{outcome.get("counters")}`.',
        f'Refinement counters: `{outcome.get("refined_counters")}`.', '',
        'See [outcome.json](outcome.json) for control crossings, replay and refinement gates, '
        'source checks and failures. Compressed arm receipts retain returned accepted/rejected states.', '']
    (output/'README.md').write_text('\n'.join(lines))
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'report'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    answer = run(args.output) if args.command == 'run' else report(args.output)
    if answer['status'] == 'EXCEPTION':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
