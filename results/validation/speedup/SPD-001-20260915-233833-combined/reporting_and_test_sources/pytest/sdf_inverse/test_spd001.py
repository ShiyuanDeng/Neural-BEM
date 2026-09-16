"""Numerical equivalence and integration checks for opt-in SPD-001 paths."""
from dataclasses import replace
import numpy as np
import pytest
from scipy import special
import torch
import run_top016_preflight as p
from gpr_bem_kress.execution import execution, current_execution, hankel1, jv, Factorization
from gpr_bem_kress.coupled_shape_derivative import directional_operators, build_coupled_base
from experiments.bie004_multi_derivative.operators import directional_operators as archived_operators
from sdf_inverse import radial_topology as rt
from sdf_inverse import analytic_jacobian as aj
from sdf_inverse.explicit_fourier import circle_cartesian_fourier_state
from sdf_inverse.optimization import ComplexScatteredData, ParameterFDConfig


@pytest.mark.parametrize("order", [-3, -2, -1, 0, 1, 2, 3])
def test_real_bessel_values_and_complex_fallback(order):
    x = np.geomspace(1e-5, 100., 157)
    with execution(kernels="real_bessel"):
        np.testing.assert_allclose(hankel1(order, x+0j), special.hankel1(order, x), rtol=3e-12, atol=3e-14)
        np.testing.assert_allclose(jv(order, x+0j), special.jv(order, x), rtol=3e-12, atol=3e-14)
        z=x+0.07j
        np.testing.assert_array_equal(hankel1(order, z), special.hankel1(order, z))
        np.testing.assert_array_equal(jv(order, z), special.jv(order, z))
    assert current_execution() is None


@pytest.mark.parametrize("device", ["cpu", "cuda"])
def test_lu_reuses_factors_for_multiple_complex_rhs(device):
    if device == "cuda" and not torch.cuda.is_available():pytest.skip("no CUDA")
    rng=np.random.default_rng(12)
    a=rng.normal(size=(48,48))+1j*rng.normal(size=(48,48))+48*np.eye(48)
    with execution(device=device) as work:
        factors=Factorization(a)
        for count in (3,7):
            b=rng.normal(size=(48,count))+1j*rng.normal(size=(48,count))
            np.testing.assert_allclose(a@factors.solve(b),b,rtol=2e-13,atol=2e-13)
        assert work.counts['factorization']==1 and work.counts['rhs_solve']==2


def setup_case(count):
    centers=[(.35,.43),(.50,.50),(.65,.57)] if count==3 else [(.43,.47),(.58,.54)][:count]
    state=rt.MultiRadialFourierState(tuple(circle_cartesian_fourier_state(c,.025,f'c{i}',maximum_mode=3)
                                          for i,c in enumerate(centers)))
    problem=p.driver.baseline._problem(np.array([.5e9,1.25e9]))
    data=ComplexScatteredData(problem,np.full((24,2),1e-6+2e-7j),np.array([.2,.8]))
    return state,data,p.driver.baseline._geometry_config(32),p.driver.baseline.iteration01_solve_config()


@pytest.mark.parametrize("count", [1,3])
def test_weighted_multifrequency_jacobian_and_backend_parity(count):
    state,data,geom,solve=setup_case(count)
    basis=state.gauge_tangent_basis()
    # A translation and a shape direction, including the last component.
    dirs=basis[[0,-1]]
    with execution():
        jac,pred=aj.cartesian_residual_jacobian(state,data,geom,solve_config=solve,directions=dirs)
    fd=[]
    for d in dirs:
        values=[rt.evaluate_multiradial_objective(state.incremented(sign*1e-6*d).polar_angle_gauge_fixed()[0],
                data,geom,solve_config=solve).residual for sign in (1,-1)]
        fd.append((values[0]-values[1])/2e-6)
    np.testing.assert_allclose(jac,np.column_stack(fd),rtol=2e-4,atol=2e-7)
    for device in (['cpu','cuda'] if torch.cuda.is_available() else ['cpu']):
        with execution(kernels='real_bessel',device=device):
            fast,yp=aj.cartesian_residual_jacobian(state,data,geom,solve_config=solve,directions=dirs)
        np.testing.assert_allclose(fast,jac,rtol=2e-10,atol=2e-10)
        np.testing.assert_allclose(yp,pred,rtol=2e-11,atol=1e-20)


def test_promoted_operator_is_the_qualified_coupled_formula():
    state,data,geom,solve=setup_case(3)
    problem=data.forward_problem; boundary=state.boundary(geom)
    material=lambda spec:rt.Material(spec.epsr,spec.sigma,spec.mur)
    base=build_coupled_base(boundary,problem.source_points,problem.receiver_points,problem.angular_frequencies[0],
        problem.source_strengths[0],exterior=material(problem.exterior),interior=material(problem.interior),
        eps0=problem.eps0,mu0=problem.mu0,config=solve)
    direction=aj.state_directions(state,boundary,state.gauge_tangent_basis()[-1])
    actual,expected=directional_operators(base,direction),archived_operators(base,direction)
    for name in ('dA','dB','dC'):np.testing.assert_array_equal(getattr(actual,name),getattr(expected,name))


def test_fd_default_and_analytic_constraint_policies(monkeypatch):
    state=rt.MultiRadialFourierState((circle_cartesian_fourier_state((.5,.5),.03,'one',maximum_mode=3),))
    target=state.parameter_vector()+np.linspace(1e-4,3e-4,state.parameter_count)
    def objective(s,*a,**k):
        residual=s.parameter_vector()-target
        return rt.MultiRadialObjectiveEvaluation(s,.5*float(residual@residual),float(np.linalg.norm(residual)),
            residual,np.zeros(1,complex),0.,0.)
    monkeypatch.setattr(rt,'evaluate_multiradial_objective',objective)
    monkeypatch.setattr(aj,'cartesian_residual_jacobian',lambda s,d,g,**k:(k['directions'].T.copy(),np.zeros(1,complex)))
    config=ParameterFDConfig(max_iterations=1,max_parameters=64,finite_difference_steps=1e-4,
        gradient_tolerance=1.,loss_tolerance=1e-30,infeasible_trial_policy='reject')
    def run(**kw):return rt.run_multiradial_fd_inverse(state,None,p.driver.baseline._geometry_config(32),
        solve_config=p.driver.baseline.iteration01_solve_config(),config=config,
        minimum_component_radius_m=.03,cartesian_gauge=True,feasible_fd_jacobian=True,**kw)
    default,fd=run(),run(jacobian_mode='fd')
    compatible=run(jacobian_mode='analytic',analytic_constraint_policy='fd_compatible')
    true=run(jacobian_mode='analytic',analytic_constraint_policy='true')
    np.testing.assert_array_equal(default.iterations[0].gradient,fd.iterations[0].gradient)
    np.testing.assert_allclose(compatible.iterations[0].gradient,fd.iterations[0].gradient,atol=1e-12)
    assert compatible.unresolved_jacobian_column_count==fd.unresolved_jacobian_column_count>0
    assert compatible.one_sided_jacobian_column_count==fd.one_sided_jacobian_column_count
    assert true.unresolved_jacobian_column_count==0
