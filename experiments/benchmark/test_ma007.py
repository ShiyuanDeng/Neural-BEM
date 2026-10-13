"""Structural MA-007 checks; numerical qualification uses actual hook states."""
from dataclasses import replace
import numpy as np
import pytest

from bem_inverse.continuation.globalization import insufficient_progress, shortened_stagnation
from bem_inverse.continuation.lm_backend import FitStage
from bem_inverse.modal_muller import ModalMuller, ModalSettings, token
from .ma007 import CASE, EXECUTION, Chunks, permutation, subblock_indices
from . import campaign as c


def test_independent_storage_trace_workspace_and_preserved_nodal_guard():
    physics=ModalMuller(EXECUTION,ModalSettings(trace_cutoff=64,coefficient_workspace=512))
    for band in (4,32,192,384):
        profile=physics.resolution_profile(band)
        assert profile['K_trace']==64
        assert profile['coefficient_workspace']==dict(production=512,refined=512)
    observation=c.problem(CASE).damped[0]
    stage=FitStage('hook', (observation,), (1.,), (1e-5,), 95,384,token(64),token(96),60,
                   resolution_kind='modal')
    with pytest.raises(ValueError,match='Nodes must resolve'):
        replace(stage,resolution_kind='nodal')
    with pytest.raises(ValueError,match='multiples of eight'):
        replace(stage,nodes=513)


def test_plain_progress_uses_five_accepted_iterations_without_shortening():
    history=[dict(loss=1.-i*.001,accepted_fraction=1.) for i in range(6)]
    assert insufficient_progress(history,5,.01)
    assert not insufficient_progress(history[:5],5,.01)
    assert not shortened_stagnation(history,5,.01)
    assert not insufficient_progress([dict(loss=1.-i*.01) for i in range(6)],5,.01)


def test_export_order_and_trace_blocks():
    assert permutation(3).tolist()==[0,1,4,2,5,3,6]
    ids=subblock_indices(64,384)
    assert len(ids)==258 and len(set(ids))==258
    assert ids[0]==320 and ids[128]==448 and ids[129]==1089


def test_actual_initial_chunk_is_lossless(tmp_path):
    coefficients=c.problem(CASE).initial.coefficients
    # Chunks record paths relative to the repository; isolate this schema check
    # with a temporary root so no numerical campaign or alternate curve is used.
    from . import ma007
    root=ma007.c.ROOT
    try:
        ma007.c.ROOT=tmp_path
        chunks=Chunks(tmp_path/'chunks')
        result=chunks.save('hook_initial',dict(coefficients=coefficients),dict(case=CASE))
        assert result['readback']=='bitwise_passed'
        assert result['arrays']['coefficients']['dtype']=='complex128'
        with np.load(tmp_path/result['path']) as value:
            np.testing.assert_array_equal(value['coefficients'],coefficients)
    finally:
        ma007.c.ROOT=root
