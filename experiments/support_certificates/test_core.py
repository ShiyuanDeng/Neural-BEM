import itertools
import numpy as np
from .core import Dual,SectorDual,CrossDual,CrossSectorDual,green,volume_operator,scatter
from .complex_material import ComplexMaterialDual


def fixture(n=6):
    rng=np.random.default_rng(82)
    pts=rng.uniform([-.04,-.18],[.04,-.1],(n,2))
    k=30.;area=.0002;chi=-.5
    src=np.array([[-.1,0],[.1,0]])
    rx=np.c_[np.linspace(-.15,.15,8),np.zeros(8)]
    g=volume_operator(k,pts,area);e=green(k,pts,src)
    a=k*k*area*green(k,rx,pts)
    p=scatter(g,e,np.arange(n)<n//2,chi);y=a@p
    return Dual(np.eye(n)/chi-g,e,a/np.linalg.norm(y),y/np.linalg.norm(y)),g,e,a,y,chi


def test_dual_gradient_hessian():
    dual,*_=fixture()
    x=np.r_[np.full(dual.n,-.1),np.zeros(dual.n)]
    direction=np.random.default_rng(3).normal(size=len(x));direction/=np.linalg.norm(direction)
    for mu in (0.,.003):
        ev=dual.evaluate(x,mu,True);h=1e-6
        plus=dual.evaluate(x+h*direction,mu);minus=dual.evaluate(x-h*direction,mu)
        assert np.isclose((plus['objective']-minus['objective'])/(2*h),ev['gradient']@direction,rtol=2e-7)
        assert np.allclose((plus['gradient']-minus['gradient'])/(2*h),-ev['neg_hessian']@direction,rtol=2e-7,atol=1e-7)


def test_weak_duality_against_every_binary_shape():
    dual,g,e,a,y,chi=fixture()
    x=np.r_[np.full(dual.n,-.01),np.zeros(dual.n)]
    bound=dual.evaluate(x)['value']
    costs=[]
    for bits in itertools.product((False,True),repeat=dual.n):
        p=scatter(g,e,np.array(bits),chi)
        constraints=p.conj()*(dual.d@p-e)
        assert np.max(np.abs(constraints))<1e-14
        costs.append(np.linalg.norm(a@p-y)**2/np.linalg.norm(y)**2)
    assert bound<=min(costs)+1e-10
    solved=dual.solve(max_steps=30)
    assert solved['success']
    assert solved['bound']<=min(costs)+1e-8


def test_wrong_support_bound_below_enumerated_optimum():
    dual,g,e,a,y,chi=fixture()
    ids=np.arange(3,6)
    wrong=Dual(dual.d[np.ix_(ids,ids)],e[ids],a[:,ids]/np.linalg.norm(y),y/np.linalg.norm(y))
    costs=[]
    for bits in itertools.product((False,True),repeat=len(ids)):
        p=scatter(g[np.ix_(ids,ids)],e[ids],np.array(bits),chi)
        costs.append(np.linalg.norm(a[:,ids]@p-y)**2/np.linalg.norm(y)**2)
    result=wrong.solve(max_steps=30)
    assert result['success']
    assert result['bound']<=min(costs)+1e-8
    assert result['bound']>1e-5


def test_sector_derivatives_and_weak_duality():
    base,g,e,a,y,chi=fixture()
    dual=SectorDual(g,e,a/np.linalg.norm(y),y/np.linalg.norm(y),-.75,0.)
    x=np.r_[np.full(dual.n,.1),np.zeros(dual.n)]
    direction=np.random.default_rng(3).normal(size=len(x));direction/=np.linalg.norm(direction)
    ev=dual.evaluate(x,.003,True);h=1e-6
    plus=dual.evaluate(x+h*direction,.003);minus=dual.evaluate(x-h*direction,.003)
    assert np.isclose((plus['objective']-minus['objective'])/(2*h),ev['gradient']@direction,rtol=2e-7)
    assert np.allclose((plus['gradient']-minus['gradient'])/(2*h),-ev['neg_hessian']@direction,rtol=2e-7,atol=1e-7)
    rng=np.random.default_rng(22)
    for _ in range(30):
        contrast=rng.uniform(-.75,-.01,len(g))
        p=np.linalg.solve(np.diag(1/contrast)-g,e)
        cost=np.linalg.norm(dual.a@p-dual.y)**2
        assert dual.evaluate(x)['value']<=cost+1e-10


def test_cross_illumination_duality_and_derivatives():
    base,g,e,a,y,chi=fixture()
    groups=np.array([np.arange(len(g))<3,np.arange(len(g))>=3],float)
    dual=CrossDual(base.d,e,base.a,base.y,groups)
    x=np.r_[-.1*dual.start_pattern,np.zeros(dual.variables//2)]
    direction=np.random.default_rng(31).normal(size=len(x));direction/=np.linalg.norm(direction)
    ev=dual.evaluate(x,.003,True);h=1e-6
    plus=dual.evaluate(x+h*direction,.003);minus=dual.evaluate(x-h*direction,.003)
    assert np.isclose((plus['objective']-minus['objective'])/(2*h),ev['gradient']@direction,rtol=2e-7)
    assert np.allclose((plus['gradient']-minus['gradient'])/(2*h),-ev['neg_hessian']@direction,rtol=2e-7,atol=1e-7)
    for bits in itertools.product((False,True),repeat=6):
        p=scatter(g,e,np.array(bits),chi)
        cost=np.linalg.norm(base.a@p-base.y)**2
        assert dual.evaluate(x)['value']<=cost+1e-10


def test_cross_sector_inequalities_and_derivatives():
    base,g,e,a,y,chi=fixture()
    groups=np.array([np.arange(len(g))<3,np.arange(len(g))>=3],float)
    dual=CrossSectorDual(g,e,base.a,base.y,-.75,0.,groups)
    x=dual.start_vectors[3]
    direction=np.random.default_rng(19).normal(size=len(x));direction/=np.linalg.norm(direction)
    ev=dual.evaluate(x,.003,True);h=1e-6
    plus=dual.evaluate(x+h*direction,.003);minus=dual.evaluate(x-h*direction,.003)
    assert np.isclose((plus['objective']-minus['objective'])/(2*h),ev['gradient']@direction,rtol=2e-7)
    assert np.allclose((plus['gradient']-minus['gradient'])/(2*h),-ev['neg_hessian']@direction,rtol=2e-7,atol=1e-7)
    rng=np.random.default_rng(33)
    for _ in range(30):
        contrast=rng.uniform(-.75,-.01,len(g));p=np.linalg.solve(np.diag(1/contrast)-g,e).reshape(-1,1)
        constraints=np.einsum('jk,ijk->i',p.conj(),np.einsum('ijk,kl->ijl',dual.qi,p)-2*dual.bi).real+dual.constants
        assert np.max(constraints[dual.positive])<1e-12
        assert np.max(abs(constraints[len(dual.positive):]))<1e-12
        cost=np.linalg.norm(dual.a@p-dual.y)**2
        assert dual.evaluate(x)['value']<=cost+1e-10


def test_independent_complex_material_constraints():
    base,g,e,a,y,chi=fixture(n=4)
    model=ComplexMaterialDual(g,e,base.a,base.y,6+.4j,(2.7,6.),(0.,.8),np.ones((1,4)))
    x=model.start_vectors[3];ev=model.evaluate(x,.003,True)
    direction=np.random.default_rng(14).normal(size=len(x));direction/=np.linalg.norm(direction)
    # Keep the tiny positive half-space multipliers strictly inside their cone.
    h=1e-8
    plus=model.evaluate(x+h*direction,.003);minus=model.evaluate(x-h*direction,.003)
    assert np.isclose((plus['objective']-minus['objective'])/(2*h),ev['gradient']@direction,rtol=3e-4)
    assert np.allclose((plus['gradient']-minus['gradient'])/(2*h),-ev['neg_hessian']@direction,rtol=3e-4,atol=1e-2)
    rng=np.random.default_rng(21)
    for _ in range(30):
        eps=rng.uniform(2.7,6.,4)+1j*rng.uniform(0.,.8,4)
        contrast=eps/(6+.4j)-1
        pp=np.linalg.solve(np.eye(4)-contrast[:,None]*g,contrast[:,None]*e).reshape(-1,1)
        p=np.concatenate((pp.real,pp.imag))
        constraints=np.einsum('jk,ijk->i',p,model.qi@p-2*model.bi)+model.constants
        assert np.max(constraints[model.positive])<1e-12
        assert np.max(abs(constraints[len(model.positive):]))<1e-12
