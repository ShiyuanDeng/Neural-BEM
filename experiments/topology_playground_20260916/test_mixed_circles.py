import numpy as np
import pytest
from scipy.special import hankel1

from experiments.topology_playground_20260916.mixed_circles import one_frequency, wave
from multicylinder_ref import CircularCylinder2D, multicylinder_scattered_field

Q=np.array([[.43,.48,.030],[.58,.53,.022]])
ANGLE=np.arange(24)*2*np.pi/24
SOURCES=.5+.3*np.column_stack((np.cos(ANGLE),np.sin(ANGLE)))
RECEIVERS=.5+.3*np.column_stack((np.cos(ANGLE+.12),np.sin(ANGLE+.12)))


def test_homogeneous_matches_existing_independent_reference():
    for f in (.5e9,1.25e9,2.5e9):
        actual=one_frequency(Q,('plastic','plastic'),SOURCES,RECEIVERS,f,order=12)
        expected=multicylinder_scattered_field(RECEIVERS,SOURCES,
            cylinders=tuple(CircularCylinder2D(tuple(q[:2]),q[2]) for q in Q),
            k_exterior=wave(f,6),k_interior=wave(f,3),mode_order=12)
        np.testing.assert_allclose(actual,expected,atol=1e-13,rtol=1e-12)


@pytest.mark.parametrize('kinds',[('plastic','metal'),('metal','plastic'),('metal','metal')])
def test_analytic_geometry_jacobian_and_reciprocity(kinds):
    prediction,jac=one_frequency(Q,kinds,SOURCES,RECEIVERS,1.25e9,jacobian=True)
    step=1e-7
    fd=[]
    for i in range(6):
        plus=Q.copy().ravel();minus=plus.copy();plus[i]+=step;minus[i]-=step
        fd.append((one_frequency(plus,kinds,SOURCES,RECEIVERS,1.25e9)
                  -one_frequency(minus,kinds,SOURCES,RECEIVERS,1.25e9))/(2*step))
    fd=np.stack(fd,axis=1)
    assert np.linalg.norm(jac-fd)/np.linalg.norm(fd)<1e-7
    reverse=one_frequency(Q,kinds,RECEIVERS,SOURCES,1.25e9)
    np.testing.assert_allclose(reverse,prediction,atol=1e-13,rtol=1e-11)


def test_mixed_series_convergence():
    for f in (.5e9,1.25e9,2.5e9):
        a,b=[one_frequency(Q,('plastic','metal'),SOURCES,RECEIVERS,f,order=n) for n in (12,20)]
        assert np.linalg.norm(a-b)/np.linalg.norm(b)<1e-9


def test_metal_boundary_total_field_is_zero_in_mixed_scene():
    f=1.25e9;ke=wave(f,6)
    _,details=one_frequency(Q,('plastic','metal'),SOURCES[:1],RECEIVERS[:1],f,order=20,return_details=True)
    theta=np.arange(127)*2*np.pi/127
    points=Q[1,:2]+Q[1,2]*np.column_stack((np.cos(theta),np.sin(theta)))
    scattered=np.zeros(len(points),complex)
    modes=details['modes'];size=len(modes)
    for i,row in enumerate(Q):
        vector=points-row[:2];radius=np.linalg.norm(vector,axis=1);angle=np.arctan2(vector[:,1],vector[:,0])
        basis=hankel1(modes[None,:],ke*radius[:,None])*np.exp(1j*modes*angle[:,None])/details['scales'][i]
        scattered+=basis@details['outgoing'][i*size:(i+1)*size,0]
    incident=.25j*hankel1(0,ke*np.linalg.norm(points-SOURCES[0],axis=1))
    assert np.linalg.norm(incident+scattered)/np.linalg.norm(incident)<1e-10


def test_zero_contrast_is_zero():
    prediction=one_frequency(Q,('plastic','plastic'),SOURCES,RECEIVERS,1e9,plastic_epsr=6)
    np.testing.assert_array_equal(prediction,np.zeros(24,complex))


def test_mixed_bem_matches_independent_cylindrical_solution():
    from experiments.topology_playground_20260916.mixed_bem import predict as bem
    frequencies=[.5e9,1.25e9,2.5e9]
    expected=np.stack([one_frequency(Q,('plastic','metal'),SOURCES,RECEIVERS,f,order=20)
                       for f in frequencies],axis=1)
    for nodes in (32,64,128):
        actual,details=bem(Q,SOURCES,RECEIVERS,frequencies,nodes=nodes,return_details=True)
        assert np.max(np.linalg.norm(actual-expected,axis=0)/np.linalg.norm(expected,axis=0))<1e-8
        assert max(d['relative_residual'] for d in details)<1e-12


def test_analytic_jacobian_matches_independent_mixed_bem_geometry_changes():
    from experiments.topology_playground_20260916.mixed_bem import predict as bem
    _,analytic=one_frequency(Q,('plastic','metal'),SOURCES,RECEIVERS,1.25e9,jacobian=True)
    step=1e-7;columns=[]
    for i in range(6):
        plus=Q.copy().ravel();minus=plus.copy();plus[i]+=step;minus[i]-=step
        columns.append((bem(plus,SOURCES,RECEIVERS,[1.25e9],nodes=48)[:,0]
                        -bem(minus,SOURCES,RECEIVERS,[1.25e9],nodes=48)[:,0])/(2*step))
    independent=np.stack(columns,axis=1)
    assert np.linalg.norm(analytic-independent)/np.linalg.norm(independent)<1e-7


@pytest.mark.parametrize('q,kinds',[
    (Q[:1],('metal',)),
    (Q,('plastic','plastic')),
    (Q,('metal','metal')),
    (np.vstack((Q,[.46,.62,.018])),('plastic','metal','plastic')),
])
def test_general_mixed_bem_component_counts(q,kinds):
    from experiments.topology_playground_20260916.mixed_bem import predict as bem
    expected=one_frequency(q,kinds,SOURCES,RECEIVERS,1.25e9,order=20)
    actual=bem(q,SOURCES,RECEIVERS,[1.25e9],nodes=64,kinds=kinds)[:,0]
    np.testing.assert_allclose(actual,expected,atol=1e-11,rtol=1e-9)
