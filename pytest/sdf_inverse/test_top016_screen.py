"""Screen algebra and decision tests, with zero physical solves."""
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('top016_screen',ROOT/'run_top016_screen.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def rows(gain=2.,count=8,small_gain=None):
    return [dict(usable=True,median_gain=gain,probes=[
        dict(amplitude_mm=a,sign=s,production=dict(gain=small_gain if small_gain is not None and a==.5 else gain),
             refined=dict(gain=small_gain if small_gain is not None and a==.5 else gain))
        for a in (.5,1.) for s in (-1,1)]) for _ in range(count)]


def test_binding_gate_requires_four_and_both_amplitudes():
    assert m.gate(rows())['passed']
    assert not m.gate(rows(count=3))['passed']
    assert not m.gate(rows(small_gain=1.))['passed']
    assert not m.gate(rows(gain=1.49))['passed']


def test_binding_gate_checks_refined_result():
    candidates=rows()
    for r in candidates:
        for probe in r['probes']:probe['refined']['gain']=1.
    assert not m.gate(candidates)['passed']


def test_data_change_uses_base_prediction_and_equal_frequency_rms():
    observed=np.ones((24,4),complex)*np.array([1,10,100,1000])
    base=observed*2
    candidate=base+observed*np.array([.1,.2,.3,.4])
    change=m.scaled_change(candidate,base,observed)
    assert m.rms_data(change)==pytest.approx(np.sqrt(np.mean(np.array([.1,.2,.3,.4])**2)))


def test_normal_displacement_scaling_is_physical():
    state=m.p.driver.deserialize_state(m.p.benchmark.read(m.p.PLATEAU)['final_state'])
    basis=state.gauge_tangent_basis();direction=np.eye(len(basis))[0]
    physical,per_unit=m.physical_direction(state,basis,direction)
    assert per_unit>0
    displaced=state.incremented(basis.T@physical)
    assert m.normal_rms(state,displaced)==pytest.approx(.001,rel=1e-10)
    assert [c.component_id for c in displaced.components]==[c.component_id for c in state.components]
