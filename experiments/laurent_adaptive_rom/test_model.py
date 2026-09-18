import numpy as np
from scipy.linalg import lu_factor,lu_solve

from experiments.laurent_tangent_rom.model import solve,derivative
from experiments.laurent_tangent_rom.test_model import fixture,exact_derivative
from .model import bases,guard,protected_basis,rank_ladder,relative_bound,stability


def test_every_hierarchical_prefix_preserves_primal_span():
    case,ds = fixture()
    bank,_ = bases(case,ds[:4])
    for arm in ('PRIMAL_TANGENT','PRIMAL_DUAL_TANGENT'):
        item = bank[arm]
        for rank in rank_ladder(item['protected_rank'],item['snapshot_rank']):
            v = item['v'][:, :rank]
            np.testing.assert_allclose(v.conj().T@v,np.eye(rank),atol=3e-14)
            np.testing.assert_allclose(v@(v.conj().T@case.u),case.u,atol=3e-14)
            np.testing.assert_allclose(solve(case,v)['y'],case.c@case.u,atol=3e-13)


def test_hierarchical_dual_prefix_preserves_untrained_tangent():
    case,ds = fixture()
    bank,_ = bases(case,ds[:4])
    item = bank['PRIMAL_DUAL_TANGENT']
    solved = solve(case,item['v'][:, :item['protected_rank']])
    np.testing.assert_allclose(derivative(solved,ds[4]),exact_derivative(case,ds[4]),atol=3e-13)


def test_no_spurious_modes_when_corrections_are_already_protected():
    q = np.eye(12,dtype=complex)[:, :4]
    result = protected_basis([q],[2*q,1j*q])
    assert result['protected_rank']==result['snapshot_rank']==4


def test_complex_finite_system_bounds_cover_paired_field_and_derivative_errors():
    for seed in range(8):
        case,ds = fixture(seed)
        bank,_ = bases(case,ds[:4])
        spectrum = stability(case.a,ds[:4])
        for rank in (2,8,12):
            result = solve(case,bank['JOINT_TANGENT']['v'][:, :rank])
            g = guard(case.a,case.b,case.c,result,ds[:4],spectrum)
            err = np.linalg.norm(np.diag(case.c@case.u-result['y']))
            assert err<=g['field_absolute_bound']+1e-12
            for d,bound in zip(ds[:4],g['derivative_absolute_bounds']):
                err = np.linalg.norm(np.diag(exact_derivative(case,d)-derivative(result,d)))
                assert err<=bound+1e-12


def test_guard_rejects_exact_fields_with_wrong_derivatives():
    case,ds = fixture()
    bank,_ = bases(case,ds[:4])
    item = bank['PRIMAL_TANGENT']
    result = solve(case,item['v'][:, :item['protected_rank']])
    np.testing.assert_allclose(result['y'],case.c@case.u,atol=1e-12)
    g = guard(case.a,case.b,case.c,result,ds[:4],stability(case.a,ds[:4]))
    assert not g['accepted']
    assert g['worst_derivative_relative_bound']>1e-4


def test_full_span_guard_accepts_and_never_reads_a_full_state():
    case,ds = fixture()
    solved = solve(case,np.eye(len(case.a)))
    case.u[:] = np.nan  # matrices remain sufficient for the guard
    g = guard(case.a,case.b,case.c,solved,ds[:4],stability(case.a,ds[:4]))
    assert g['accepted']


def test_relative_bound_fails_closed_and_rank_ladder_protects_minimum():
    assert relative_bound(2.,np.ones(2))>1e300
    assert relative_bound(float('nan'),np.ones(2))>1e300
    assert min(rank_ladder(47,96))==47
    assert max(rank_ladder(47,96))==96
