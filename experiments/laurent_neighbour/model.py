"""Multiple scattering, uncertain material/shape, and an additive-echo control."""
from dataclasses import dataclass, field
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.optimize import least_squares

from experiments.laurent_calibration.model import Fixture, incidence, realify, TARGET
from experiments.laurent_calibration.design import project_out
from experiments.modal_muller_research.coefficient_operator import LaurentGeometry
from experiments.modal_muller_research.deformable_scattering import compile_shape_jet
from experiments.modal_muller_research.scattering_library import ScatteringScene, compile_template, parameterization


@dataclass
class Body:
    chart: Fixture = field(default_factory=Fixture)
    epsr: float = 3.

    def permittivity(self, x):
        return self.epsr*(1+x[7]/6)


def bodies_at(distance=.105, angle=-np.pi/2, epsr=12., count=12):
    target = Body(Fixture(count=count))
    neighbour = Body(Fixture(count=count, anchor=target.chart.anchor+distance*np.exp(1j*angle), radius=.02), epsr)
    return [target, neighbour]


class Evaluator:
    """Full nonlinear maps with local reciprocal jets, and two material FD columns."""
    def __init__(self, bodies, interactions=True, backend="nodal", nodes=64, order=16):
        self.bodies, self.interactions, self.backend = bodies, interactions, backend
        self.fixture = bodies[0].chart
        self.options = dict(nodes=nodes, order=order, cutoff=24, bandwidth=48, terms=36)
        self.x = None
        self.cache = {}
        self.evaluations = self.jac_evaluations = 0

    def forward(self, x):
        x = np.asarray(x)
        if self.x is not None and np.array_equal(x, self.x):
            return self.y
        if len(x) != 8*len(self.bodies):
            raise ValueError("Eight physical coordinates are required for each body")
        f = self.fixture
        all_y, all_j, self.context = [], [], []
        for fi, frequency in enumerate(f.frequencies):
            factor = 2*np.pi*frequency*np.sqrt(f.eps0*f.mu0)
            ko = factor*np.sqrt(6.)
            templates, jets, material_jets = [], [], []
            for bi, body in enumerate(self.bodies):
                p = x[8*bi:8*(bi+1)]
                key = (bi, fi)
                signature = tuple(p[2:])
                if key not in self.cache or self.cache[key][0] != signature:
                    t, j, _ = compile_shape_jet(body.chart.geometry(p), body.chart.directions(),
                        ko, factor*np.sqrt(body.permittivity(p)), .05,
                        backend=self.backend, **self.options)
                    self.cache[key] = (signature, t, j)
                _, t, j = self.cache[key]
                templates.append(t)
                jets.append(j)
            centers = [b.chart.center(x[8*i:8*(i+1)]) for i,b in enumerate(self.bodies)]
            groups = [list(range(len(self.bodies)))] if self.interactions else [[i] for i in range(len(self.bodies))]
            y = np.zeros((f.count, f.count), complex)
            j = np.zeros((f.count, f.count, len(x)), complex)
            contexts = []
            for group in groups:
                scene = ScatteringScene([templates[i] for i in group], [centers[i] for i in group],
                    np.zeros(len(group)), f.sources, f.receivers, strengths=1., paired=False)
                y += scene.full_output
                pose = scene.jacobian().reshape(f.count, f.count, 3*len(group))
                transfer = lu_solve(scene.factors, scene.receiver.T, trans=1).T
                for li, bi in enumerate(group):
                    sl = scene.slices[li]
                    j[..., 8*bi:8*bi+2] = pose[..., 3*li:3*li+2]
                    j[..., 8*bi+2:8*bi+7] = np.stack([
                        transfer[:, sl] @ dj @ scene.local_incident[sl] for dj in jets[bi]], axis=-1)
                    contexts.append((bi, transfer[:, sl], scene.local_incident[sl], ko, factor))
            all_y.append(y)
            all_j.append(j)
            self.context.append(contexts)
        self.x, self.y, self.shape_jac = x.copy(), np.array(all_y), np.array(all_j)
        self.jac = None
        self.evaluations += 1
        return self.y

    def jacobian(self, x):
        self.forward(x)
        if self.jac is not None:
            return self.jac
        jac = self.shape_jac.copy()
        h = 2e-4
        for fi, contexts in enumerate(self.context):
            for bi, transfer, incident, ko, factor in contexts:
                body = self.bodies[bi]
                p = np.array(x[8*bi:8*(bi+1)], copy=True)
                matrices = []
                for sign in (-1, 1):
                    shifted = p.copy()
                    shifted[7] += sign*h
                    matrices.append(compile_template(body.chart.geometry(p), ko,
                        factor*np.sqrt(body.permittivity(shifted)), normalization_radius=.05,
                        backend=self.backend, **self.options).matrix)
                jac[fi, ..., 8*bi+7] = transfer @ ((matrices[1]-matrices[0])/(2*h)) @ incident
        self.jac = jac
        self.jac_evaluations += 1
        return jac


def oracle(bodies, x, interactions=True, nodes=192):
    """Full nodal BIE with individual interior self blocks and exterior cross blocks.

    The existing multi-component builder has a shared interior. Its off-diagonal
    blocks use ONLY the exterior medium; replacing each diagonal self block by
    that body's Muller block gives the different-material system. No cylindrical
    translation or acquisition expansion enters this reference solver.
    """
    from experiments.modal_muller_research.probe import assemble
    from gpr_bem_kress.system import build_muller_system
    from gpr_bem_kress.execution import execution
    f = bodies[0].chart
    if not interactions and len(bodies) > 1:
        return sum(oracle([b], x[8*i:8*(i+1)], nodes=nodes) for i,b in enumerate(bodies))
    curves = []
    for i,b in enumerate(bodies):
        p = x[8*i:8*(i+1)]
        g = b.chart.geometry(p)
        moved = LaurentGeometry(g.coefficients, b.chart.center(p), g.scale)
        curves.append(parameterization(moved, f"body-{i}").discretize(nodes, require_even=True))
    acq = f.acquisition(x[:8])
    acq["interior"]["epsr"] = bodies[0].permittivity(x[:8])
    values = []
    with execution(kernels="real_bessel"):
        for frequency in f.frequencies:
            a, rhs, c, _ = assemble(curves, frequency, acq)
            a = a.copy()
            factor = 2*np.pi*frequency*np.sqrt(f.eps0*f.mu0)
            total = nodes*len(bodies)
            for i,b in enumerate(bodies):
                ki = factor*np.sqrt(b.permittivity(x[8*i:8*(i+1)]))
                self_matrix = build_muller_system(curves[i], factor*np.sqrt(6.), ki).system_matrix
                indices = np.r_[np.arange(i*nodes, (i+1)*nodes), total+np.arange(i*nodes, (i+1)*nodes)]
                a[np.ix_(indices, indices)] = self_matrix
            values.append(c @ lu_solve(lu_factor(a), rhs))
    return np.array(values)


def information(y, jac, mask, sigma, neighbour_unknown=True, gains_unknown=True):
    edges = np.argwhere(mask)
    b = incidence(edges, len(mask))
    rows = []
    for fi in range(len(y)):
        j = jac[fi][mask]/sigma[fi]
        if gains_unknown:
            j, _ = project_out(j, y[fi][mask, None]*b/sigma[fi])
        rows.append(realify(j))
    j = np.concatenate(rows)
    nuisance = [0, 1, 2, 7]
    if neighbour_unknown:
        nuisance.extend(range(8, jac.shape[-1]))
    target, rank = project_out(j[:, TARGET], j[:, nuisance])
    gram = target.T@target
    eig = np.linalg.eigvalsh(gram)
    if eig[0] <= 0:
        raise ValueError("Shape information is not positive definite at this fixture")
    return dict(gram=gram, eigenvalues=eig, nuisance_rank=rank,
                radial_rms_crlb_mm=float(np.sqrt(2*np.trace(np.linalg.inv(gram)))))


class JointObjective:
    def __init__(self, evaluator, mask, observed, sigma, physical_initial, neighbour_known=False):
        self.evaluator, self.mask = evaluator, mask
        self.fixed = np.asarray(physical_initial).copy()
        self.active = np.arange(8 if neighbour_known else len(self.fixed))
        self.p = len(self.active)
        self.nf = len(sigma)
        self.b = incidence(np.argwhere(mask), len(mask))
        self.k = self.b.shape[1]
        self.observed = observed[:, mask]
        self.sigma = np.asarray(sigma)[:, None]

    def physical(self, x):
        p = self.fixed.copy()
        p[self.active] = x[:self.p]
        return p

    def predict(self, x):
        gains = x[self.p:].reshape(self.nf, 2, self.k)
        mult = np.exp((gains[:, 0]+1j*gains[:, 1]) @ self.b.T)
        physical = self.physical(x)
        y = self.evaluator.forward(physical)[:, self.mask]
        return mult*y, mult, physical

    def residual(self, x):
        y, _, _ = self.predict(x)
        return realify(((y-self.observed)/self.sigma).ravel())

    def jacobian(self, x):
        y, mult, physical = self.predict(x)
        j = self.evaluator.jacobian(physical)[:, self.mask][:, :, self.active]
        j = (j*mult[..., None]/self.sigma[..., None]).reshape(-1, self.p)
        n = np.zeros((y.size, self.nf*2*self.k), complex)
        e = y.shape[1]
        for fi in range(self.nf):
            block = y[fi, :, None]*self.b/self.sigma[fi]
            n[fi*e:(fi+1)*e, fi*2*self.k:(fi+1)*2*self.k] = np.c_[block, 1j*block]
        return realify(np.c_[j, n])


def fit(bodies, mask, observed, sigma, initial, interactions=True, neighbour_known=False, max_nfev=180):
    tick = perf_counter()
    ev = Evaluator(bodies, interactions=interactions)
    objective = JointObjective(ev, mask, observed, sigma, initial, neighbour_known)
    ng = objective.nf*2*objective.k
    initial = np.r_[np.array(initial)[objective.active], np.zeros(ng)]
    lo, hi = zip(*(b.chart.bounds() for b in bodies))
    lo, hi = np.concatenate(lo)[objective.active], np.concatenate(hi)[objective.active]
    result = least_squares(objective.residual, initial, jac=objective.jacobian,
        bounds=(np.r_[lo, np.full(ng, -3.)], np.r_[hi, np.full(ng, 3.)]), x_scale="jac",
        ftol=1e-9, xtol=1e-9, gtol=1e-7, max_nfev=max_nfev)
    return dict(parameters=objective.physical(result.x).tolist(), gains=result.x[objective.p:].tolist(),
                success=bool(result.success), nfev=result.nfev, njev=result.njev,
                cost=float(result.cost), optimality=float(result.optimality), seconds=perf_counter()-tick,
                active_bounds=np.flatnonzero(result.active_mask).tolist(), message=result.message,
                active_physical_count=objective.p)
