"""Numerical tests for the optional pinned Algoim experiment."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import pytest
from scipy.special import ellipe
from build import build
from run_comparison import quadrature


@pytest.fixture(scope="module")
def executable():
    if not Path("/tmp/neural_bem_algoim/algoim/quadrature_general.hpp").exists():
        pytest.skip("Run experiments/algoim/build.py to fetch the pinned optional dependency.")
    return build()


def test_ellipse_perimeter_nodes_and_positive_weights(executable):
    nodes, row = quadrature(executable,"ellipse",16,8,extent=.083)
    level_set = ((nodes[:,0]-.5)/.05)**2+((nodes[:,1]-.5)/.035)**2-1
    assert np.max(abs(level_set)) < 1e-12
    assert np.min(nodes[:,2]) > 0
    exact=4*.05*ellipe(1-(.035/.05)**2)
    assert abs(row['perimeter_m']-exact)/exact < 1e-9


def test_implicit_perimeter_derivative_against_recomputed_weights(executable):
    nodes,_=quadrature(executable,"ellipse",16,8,extent=.083)
    x,y,w=nodes.T
    gx,gy=2*(x-.5)/.05**2,2*(y-.5)/.035**2
    norm=np.hypot(gx,gy)
    curvature=((2/.05**2)*gy**2+(2/.035**2)*gx**2)/norm**3
    velocity=2*(x-.5)**2/(.05**3*norm)
    derived=np.sum(w*curvature*velocity)
    step=1e-6
    plus,_=quadrature(executable,"ellipse",16,8,delta=step,extent=.083)
    minus,_=quadrature(executable,"ellipse",16,8,delta=-step,extent=.083)
    difference=(plus[:,2].sum()-minus[:,2].sum())/(2*step)
    assert abs(difference-derived)/abs(derived) < 1e-7
