"""Small Laurent shape family and a matched joint self-calibrating inverse.

The acquisition is a surface line in a homogeneous, lossless 2-D medium.
Only scattered fields are used. This is not an antenna or layered-soil model.
"""
from dataclasses import dataclass, field
from time import perf_counter

import numpy as np
from scipy.optimize import least_squares

from experiments.modal_muller_research.coefficient_operator import LaurentGeometry
from experiments.modal_muller_research.deformable_scattering import compile_shape_jet
from experiments.modal_muller_research.scattering_library import (
    ScatteringScene, compile_template, parameterization,
)


PARAMETERS = ("center_x_10mm", "center_y_10mm", "radius_delta_2mm",
              "cos2_2mm", "sin2_2mm", "cos3_2mm", "sin3_2mm", "epsr_delta_0.5")
TARGET = np.arange(3, 7)
NUISANCE = np.array([0, 1, 2, 7])


def realify(a):
    return np.concatenate((a.real, a.imag), axis=0)


@dataclass
class Fixture:
    count: int = 12
    frequencies: tuple = (0.5e9, 1.25e9)
    anchor: complex = -.16j
    radius: float = .03
    eps0: float = 8.8541878128e-12
    mu0: float = 1.25663706212e-6
    sources: np.ndarray = field(init=False)
    receivers: np.ndarray = field(init=False)

    def __post_init__(self):
        line = np.linspace(-.22, .22, self.count)
        self.sources = np.c_[line, np.zeros(self.count)]
        self.receivers = np.c_[line + .004, np.full(self.count, .005)]

    def geometry(self, x):
        z = {1: 1 + .002*x[2]/self.radius}
        for q, a, b in [(2, x[3], x[4]), (3, x[5], x[6])]:
            z[1+q] = .001*(a-1j*b)/self.radius
            z[1-q] = .001*(a+1j*b)/self.radius
        return LaurentGeometry(z, 0j, self.radius)

    def directions(self):
        return [{1: .002/self.radius}] + [
            {1+q: .001*v/self.radius, 1-q: .001*np.conj(v)/self.radius}
            for q in (2, 3) for v in (1, -1j)
        ]

    def center(self, x):
        return self.anchor + .01*(x[0]+1j*x[1])

    def bounds(self):
        return np.array([-1., -1., -1.5, -1.5, -1.5, -1.5, -1.5, -2.]), np.array(
            [1., 1., 1.5, 1.5, 1.5, 1.5, 1.5, 3.])

    def acquisition(self, x):
        return dict(source_points=self.sources, receiver_points=self.receivers,
                    source_strength=1., exterior=dict(epsr=6., mur=1., sigma=0.),
                    interior=dict(epsr=3.+.5*x[7], mur=1., sigma=0.),
                    eps0=self.eps0, mu0=self.mu0)

    def boundary(self, x, count=1024):
        theta = np.arange(count)*2*np.pi/count
        g = self.geometry(x)
        return self.center(x) + g.scale*sum(v*np.exp(1j*j*theta) for j,v in g.coefficients.items())


class Evaluator:
    """Same continuous Laurent family with nodal or node-free compilation.

    Shape and translation derivatives use reciprocal identities; one material
    column uses centered differences of freshly compiled scattering matrices.
    """
    def __init__(self, fixture, backend="nodal", nodes=64, order=12, cutoff=24, bandwidth=48):
        self.fixture, self.backend = fixture, backend
        self.options = dict(nodes=nodes, order=order, cutoff=cutoff, bandwidth=bandwidth, terms=28)
        self.x = None
        self.evaluations = 0
        self.jac_evaluations = 0

    def forward(self, x):
        x = np.asarray(x)
        if self.x is not None and np.array_equal(x, self.x):
            return self.y
        f = self.fixture
        geometry = f.geometry(x)
        rows, columns, states = [], [], []
        for frequency in f.frequencies:
            factor = 2*np.pi*frequency*np.sqrt(f.eps0*f.mu0)
            ko, ki = factor*np.sqrt(6.), factor*np.sqrt(3.+.5*x[7])
            t, jets, _ = compile_shape_jet(geometry, f.directions(), ko, ki, .05,
                                         backend=self.backend, **self.options)
            scene = ScatteringScene([t], [f.center(x)], [0.], f.sources, f.receivers,
                                    strengths=1., paired=False)
            pose = scene.jacobian().reshape(f.count, f.count, 3)
            shape = np.stack([scene.receiver @ j @ scene.incident for j in jets], axis=-1)
            columns.append(np.concatenate((pose[:, :, :2], shape), axis=-1))
            rows.append(scene.full_output)
            states.append((scene, ko, factor))
        self.x, self.y, self.shape_jac = x.copy(), np.array(rows), np.array(columns)
        self.states, self.jac = states, None
        self.evaluations += 1
        return self.y

    def jacobian(self, x):
        self.forward(x)
        if self.jac is not None:
            return self.jac
        step = 2e-4
        material = []
        for scene, ko, factor in self.states:
            mats = []
            for sign in (-1, 1):
                ki = factor*np.sqrt(3.+.5*(x[7]+sign*step))
                mats.append(compile_template(self.fixture.geometry(x), ko, ki,
                    normalization_radius=.05, backend=self.backend, **self.options).matrix)
            material.append(scene.receiver @ ((mats[1]-mats[0])/(2*step)) @ scene.incident)
        self.jac = np.concatenate((self.shape_jac, np.array(material)[..., None]), axis=-1)
        self.jac_evaluations += 1
        return self.jac


def oracle(fixture, x, nodes=256):
    """Full boundary solve, without cylindrical source/receiver truncation."""
    from experiments.modal_muller_research.run_native import nodal
    g = fixture.geometry(x)
    moved = LaurentGeometry(g.coefficients, fixture.center(x), g.scale)
    acq = fixture.acquisition(x)
    return np.array([nodal([parameterization(moved)], freq, acq, nodes)["y"]
                     for freq in fixture.frequencies])


def incidence(edges, count):
    """Log gains: every receiver and all transmitters except reference Tx 0."""
    b = np.zeros((len(edges), 2*count-1))
    b[np.arange(len(edges)), edges[:, 0]] = 1
    nonzero = edges[:, 1] > 0
    b[np.flatnonzero(nonzero), count+edges[nonzero, 1]-1] = 1
    return b


def apply_gains(y, gains):
    """gains[f, real_log_amplitude_or_phase, receiver_then_nonreference_tx]."""
    nf, n, _ = y.shape
    edges = np.indices((n, n)).reshape(2, -1).T
    b = incidence(edges, n)
    z = gains[:, 0]+1j*gains[:, 1]
    return y*np.exp(z @ b.T).reshape(nf, n, n)


class JointObjective:
    def __init__(self, evaluator, mask, observed, sigma, known_gains=None):
        self.evaluator, self.mask = evaluator, mask
        self.edges = np.argwhere(mask)
        self.b = incidence(self.edges, mask.shape[0])
        self.observed = observed[:, mask]
        self.sigma = np.asarray(sigma)[:, None]
        self.nf, self.k = len(sigma), self.b.shape[1]
        self.known_gains = known_gains

    def _prediction(self, x):
        gains = (x[8:].reshape(self.nf, 2, self.k) if self.known_gains is None
                 else self.known_gains)
        mult = np.exp((gains[:, 0]+1j*gains[:, 1]) @ self.b.T)
        y = self.evaluator.forward(x[:8])[:, self.mask]
        return mult*y, mult

    def residual(self, x):
        pred, _ = self._prediction(x)
        return realify(((pred-self.observed)/self.sigma).ravel())

    def jacobian(self, x):
        pred, mult = self._prediction(x)
        shape = self.evaluator.jacobian(x[:8])[:, self.mask]
        physical = (shape*mult[..., None]/self.sigma[..., None]).reshape(-1, 8)
        if self.known_gains is not None:
            return realify(physical)
        nuisance = np.zeros((pred.size, self.nf*2*self.k), complex)
        e = pred.shape[1]
        for f in range(self.nf):
            block = pred[f, :, None]*self.b/self.sigma[f]
            nuisance[f*e:(f+1)*e, f*2*self.k:(f+1)*2*self.k] = np.c_[block, 1j*block]
        return realify(np.c_[physical, nuisance])


def fit(fixture, mask, observed, sigma, initial, known_gains=None, max_nfev=160):
    tick = perf_counter()
    ev = Evaluator(fixture)
    obj = JointObjective(ev, mask, observed, sigma, known_gains)
    lo, hi = fixture.bounds()
    x = np.array(initial, copy=True)
    if known_gains is None:
        ng = len(fixture.frequencies)*2*(2*fixture.count-1)
        x = np.r_[x, np.zeros(ng)]
        lo, hi = np.r_[lo, np.full(ng, -3.)], np.r_[hi, np.full(ng, 3.)]
    result = least_squares(obj.residual, x, jac=obj.jacobian, bounds=(lo, hi),
                           x_scale="jac", ftol=1e-9, xtol=1e-9, gtol=1e-7,
                           max_nfev=max_nfev)
    return dict(parameters=result.x[:8].tolist(), gains=result.x[8:].tolist(),
                success=bool(result.success), status=int(result.status), message=result.message,
                nfev=result.nfev, njev=result.njev, cost=float(result.cost),
                optimality=float(result.optimality), seconds=perf_counter()-tick,
                active_bounds=np.flatnonzero(result.active_mask).tolist(),
                forward_evaluations=ev.evaluations, jacobian_evaluations=ev.jac_evaluations)
