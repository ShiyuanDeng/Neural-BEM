import numpy as np
from .layered import Layered
from .core import green


def test_equal_media_recover_free_space():
    k=30+.8j;model=Layered(k,k,order=128)
    soil=np.array([[-.05,-.13],[.02,-.18],[.1,-.11]])
    air=np.array([[-.1,.04],[.15,.02]])
    actual=model.transmitted(soil,air);reference=green(k,soil,air)
    assert np.linalg.norm(actual-reference)/np.linalg.norm(reference)<2e-7
    assert np.max(abs(model.reflected(soil,soil)))==0.


def test_layered_refinement_reciprocity_and_helmholtz():
    ka=16.;kg=39+1.5j
    model=Layered(ka,kg,order=96);fine=Layered(ka,kg,order=192)
    soil=np.array([[-.05,-.13],[.02,-.18],[.1,-.11]]);air=np.array([[-.1,.04],[.15,.02]])
    actual=model.transmitted(soil,air);reference=fine.transmitted(soil,air)
    assert np.linalg.norm(actual-reference)/np.linalg.norm(reference)<2e-8
    ref=model.reflected(soil,soil)
    assert np.linalg.norm(ref-ref.T)<1e-13
    h=1e-5;lap=np.zeros_like(actual)
    for axis in (0,1):
        step=np.zeros(2);step[axis]=h
        lap+=(model.transmitted(soil+step,air)-2*actual+model.transmitted(soil-step,air))/h**2
    assert np.linalg.norm(lap+kg*kg*actual)/np.linalg.norm(kg*kg*actual)<2e-6
