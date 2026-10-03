"""Campaign-contract checks; do not run a basin census in tests."""
from dataclasses import replace

import numpy as np
import pytest

from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.geometry import resize
from bem_inverse.io import curve_from
from bem_inverse.policy import CumulativePolicy
from . import fm003 as f
from .fm001_diagnostics import aligned_rms_mm


def test_phase_distance_matches_fm001_and_preserves_translation():
    a = FourierCurve(np.array([.014+.002j, 0, .1+.2j, 1., .07j]))
    c = FourierCurve(a.coefficients*np.exp(1j*a.modes*.713))
    shifted = c.coefficients.copy()
    shifted[c.band] += .012-.007j
    c = FourierCurve(shifted)
    distance = f.aligned_preprojected_mm(f.arclength_curve(a), f.arclength_curve(c))
    assert distance == pytest.approx(aligned_rms_mm(a,c),abs=1e-9)
    assert distance > .5


def test_centroid_and_rigid_rotation():
    curve = FourierCurve.circle(1.3, .27-.15j)
    center = f.area_centroid(curve)
    assert center == pytest.approx(.27-.15j,abs=1e-14)
    values=curve.coefficients*np.exp(1j*.71)
    values[curve.band] += center*(1-np.exp(1j*.71))
    assert f.area_centroid(FourierCurve(values)) == pytest.approx(center,abs=1e-14)


def test_start_draw_reproduces_registered_rng_and_projected_units(tmp_path):
    index=5
    result=f.make_start(f.HIGH,index,tmp_path)
    assert result['valid']
    draw=result['attempts'][0]
    rng=np.random.default_rng(20261004+index)
    alpha,beta=rng.normal(0.,.1/(1+np.arange(6)),size=(2,6))
    assert np.array_equal(draw['alpha'],alpha)
    assert np.array_equal(draw['beta'],beta)
    assert draw['rotation'] == rng.uniform(0.,2*np.pi)
    base=resize(f.z1(f.HIGH),12)
    sigma=base.nodes(1024).perimeter/(2*np.pi)
    assert np.array_equal(draw['normal_coefficients_m'],sigma*.05*np.r_[alpha,beta[1:]])
    assert f.make_start(f.HIGH,index,tmp_path) == result
    curve_from(result['curve']).validate()


def test_single_linkage_includes_chain_but_respects_loss():
    curves=[f.arclength_curve(FourierCurve.circle(1.,x)) for x in (0.,.008,.016,.024)]
    rows=[dict(index=i,final_loss=loss) for i,loss in enumerate((1.,1.01,1.02,2.))]
    groups,edges=f.single_linkage(rows,curves)
    assert sorted(sorted(g) for g in groups) == [[0,1,2],[3]]
    assert len(edges) == 2
    assert f.wilson(0,512)['zero_hit_one_sided_exact95_upper'] == pytest.approx(.0058339556,rel=1e-8)


def test_stage2_and_suffix_preserve_frozen_policy():
    problem,physics,op=f.stage_problem(f.HIGH)
    original=CumulativePolicy().operations(problem,physics)
    old=next(item for item in original if item.label=='stage_2_damped')
    assert op.stage == replace(old.stage,iterations=200,quota=10000)
    assert op.optimizer == old.optimizer
    assert (op.stage.update_modes,op.stage.curve_modes,op.stage.nodes,op.stage.refined_nodes)==(5,12,512,1024)
    suffix=f.ContinuationPolicy(fit_units=13250,fit_seconds=1784.5).operations(problem,physics)
    index=next(i for i,item in enumerate(original) if item.label=='stage_3_damped')
    assert suffix == (original[0],*original[index:])


def test_lifting_failure_blocks_replay_before_a_fit(tmp_path,monkeypatch):
    monkeypatch.setattr(f,'verify',lambda output:None)
    monkeypatch.setattr(f,'lift_gates',lambda output:dict(passed=False))
    monkeypatch.setattr(f,'run_stage',lambda *a,**kw:pytest.fail('No fit permitted after failed lifting gates'))
    with pytest.raises(ValueError,match='Phase L'):
        f.replay(tmp_path)
