import numpy as np
from .screen import Wave,matrices,positive_qr
from .fixed_projection import FixedROM


def test_data_only_operator_matches_independent_interior_projection():
    wave=Wave(nx=18,nz=22,snapshots=10)
    d,dd,u,a=wave.data(return_snapshots=True)
    m,s,p=matrices(d,dd,10)
    assert np.allclose(m,u.T@u,rtol=1e-10,atol=1e-12)
    assert np.allclose(s,u.T@a@u,rtol=1e-10,atol=1e-11)
    rom=FixedROM(m,s,p,2,12)
    projection=rom.projection.copy()
    for depth in (.35,.52,.65):
        d,dd,u,a=wave.data(depth=depth,return_snapshots=True)
        m,s,p=matrices(d,dd,10);computed=rom.evaluate(m,s)
        q,_=positive_qr(u@projection)
        assert np.linalg.norm(computed-q.T@a@q)/np.linalg.norm(computed)<1e-8
        assert np.array_equal(projection,rom.projection)
