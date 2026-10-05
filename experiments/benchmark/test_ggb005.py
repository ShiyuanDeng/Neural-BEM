"""Fit-frequency scoring must never be confused with holdout scoring."""
from types import SimpleNamespace

import numpy as np
import pytest

from .ggb005 import select_active


def fixture():
    return dict(audit=[dict(relative_residual=x,noise_target_met=i==1,
                           field_gate_passed=i==1,active_in_fit=i>0)
                       for i,x in enumerate((.1,.05,.2,.3,.4))])


def test_single_frequency_excludes_failed_holdouts_from_fit_score():
    result = select_active(fixture(),(1,),(1.,),SimpleNamespace(loss_tolerance=.002))
    assert [r['active_in_fit'] for r in result['audit']]==[False,True,False,False,False]
    assert result['all_frequency_noise_targets_met'] and result['field_gates_passed']
    assert result['noise_discrepancy_met']
    np.testing.assert_allclose(result['refined_joint_loss'],.00125)


def test_four_frequency_score_still_includes_all_fitted_rows():
    result = select_active(fixture(),(1,2,3,4),(.1,.2,.3,.4),SimpleNamespace(loss_tolerance=.002))
    assert not result['all_frequency_noise_targets_met'] and not result['field_gates_passed']
    np.testing.assert_allclose(result['refined_joint_loss'],.5*(.1*.05**2+.2*.2**2+.3*.3**2+.4*.4**2))


@pytest.mark.parametrize('indices,weights',[((1,1),(.5,.5)),((1,),(1.,1.)),((),()),((5,),(1.,))])
def test_invalid_active_frequency_selection_is_refused(indices,weights):
    with pytest.raises(ValueError):
        select_active(fixture(),indices,weights,SimpleNamespace(loss_tolerance=.002))
