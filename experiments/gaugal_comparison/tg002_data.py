"""TG-002 cases in physical units for the MoM and GauGal arms (FW-001, GGB-002).

Every quantity is in metres relative to the scene centre (0.5, 0.5) m. The
background (sand, epsilon 6) enters only through the background wavenumber, so
a volume solver in free space reproduces it by matching that wavenumber.
Fields follow the benchmark convention: a source of strength s radiates
s * i H0^(1)(k r) / 4, and data are scattered fields at the paired receivers.
"""
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
from matplotlib.path import Path as Polygon

from bem_inverse.io import curve_from
from experiments.benchmark import scenes as S
from experiments.cleaned_interface import benchmark as ci

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT/'results/validation/cleaned_interfaces/TG-002/inputs'
BOX_HALF_WIDTH_M = .1          # every truth curve lies inside +-0.1 m of the centre


@dataclass(frozen=True)
class Case:
    case_id: str
    scene: str
    contrast: float              # k_i^2 / k_e^2 = epsilon_r against the background
    frequencies_hz: np.ndarray   # (19,)
    wavenumbers: np.ndarray      # (19,) real background wavenumbers, 1/m
    observed: np.ndarray         # (19, 24) clean scattered field at the 24 pairs
    sources: np.ndarray          # (24, 2) m
    receivers: np.ndarray        # (24, 2) m; receiver i pairs with source i
    strength: complex            # source strength
    boundary: np.ndarray         # (M,) complex truth boundary samples, m

    @property
    def susceptibility(self):
        return self.contrast - 1.


def load(case_id, boundary_samples=4096):
    scene, tag = case_id.split('__')
    contrast = float(tag[1:])
    folder = INPUTS/scene/tag
    rows = json.loads((folder/'observations.json').read_text())
    observed = (np.asarray(rows['clean_real'])+1j*np.asarray(rows['clean_imag'])).T
    frequencies = np.asarray(rows['frequencies_hz'], float)
    if tuple(frequencies) != ci.FREQUENCIES:
        raise ValueError('TG-002 frequencies changed')
    acquisition = ci.acquisition()
    # ci.observations uses k = 2 pi f sqrt(mu0 eps0 6) * LENGTH in package units.
    waves = np.array([2*np.pi*f*np.sqrt((4*np.pi*1e-7)*8.854187817e-12*6.) for f in frequencies])
    curve = curve_from(json.loads((INPUTS/scene/'truth.json').read_text()))
    boundary = S.LENGTH*curve.values(boundary_samples)
    if np.max(np.abs(boundary.real)) >= BOX_HALF_WIDTH_M or np.max(np.abs(boundary.imag)) >= BOX_HALF_WIDTH_M:
        raise ValueError(case_id+' leaves the imaging box')
    return Case(case_id, scene, contrast, frequencies, waves, observed,
                S.LENGTH*np.asarray(acquisition.sources), S.LENGTH*np.asarray(acquisition.receivers),
                complex(acquisition.strength), boundary)


def pixel_grid(cells, half_width=BOX_HALF_WIDTH_M):
    """Cell-centre grid matching mom_esi.make_domain: rows run top to bottom."""
    axis = np.linspace(-half_width, half_width, cells)
    return np.meshgrid(axis, -axis)


def fill_fraction(boundary, x, y, supersample=8):
    """Area fraction of each square cell inside the boundary (sub-cell sampling)."""
    step = float(x[0, 1]-x[0, 0])
    offsets = (np.arange(supersample)+.5)/supersample-.5
    ox, oy = np.meshgrid(offsets*step, offsets*step)
    inside = Polygon(np.column_stack((boundary.real, boundary.imag)))
    points = np.stack((x[..., None, None]+ox, y[..., None, None]+oy), -1).reshape(-1, 2)
    hits = inside.contains_points(points).reshape(*x.shape, supersample*supersample)
    return hits.mean(-1)


def relative_error(predicted, observed):
    """Per-frequency relative field error ||p - d|| / ||d|| over the 24 pairs."""
    return np.linalg.norm(predicted-observed, axis=-1)/np.linalg.norm(observed, axis=-1)
