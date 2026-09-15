"""Exercise the actual tuple/list metadata seam without any physical calls."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.top018 import run as n


@pytest.mark.parametrize('arm',['S','F'])
def test_completed_schedule_binds_list_gradient_to_tuple_stage(tmp_path,arm):
    m,p=n.m,n.p
    state=p.driver.deserialize_state(m.read(n.HISTORY/'inputs/far-two-stars/state.json'))
    observed=np.ones((24,4),complex)
    def score(s):
        return dict(training_errors=[.1]*4,numerically_qualified=True,original_gates_pass=False)
    def fit(initial,data,nodes,solve,optimizer,floor,ledger,output):
        output.mkdir(parents=True)
        frequencies=(data.forward_problem.angular_frequencies/(2*np.pi)).tolist()
        gradient=dict(state_sha256=m.state_hash(initial),active_frequencies_hz=frequencies,
                      production_nodes=256,refined_nodes=512)
        return initial,dict(stage_outcome='STAGE_QUOTA_REACHED',effective_training_exposure=True,
            convergence='UNCONFIRMED',final_state=p.driver.serialize_state(initial),
            gradient=gradient,last_measured_gradient=dict(gradient))
    result=n.schedule(state,arm,observed,None,.008,m.Ledger(seconds=7200),tmp_path,score(state),
                       score,fit=fit,feasibility=lambda *a:True)
    assert result['schedule_complete']
    for stage in result['stages']:
        assert isinstance(stage['active_frequencies_hz'],tuple)
        terminal=stage['terminal']
        assert isinstance(terminal['last_measured_gradient']['active_frequencies_hz'],list)
        assert terminal['gradient']['objective_sha256']==stage['score']['objective_sha256']
        assert terminal['last_measured_gradient']['objective_sha256']==stage['score']['objective_sha256']
        saved=m.read(tmp_path/f'stage_{stage["stage"]}/objective_associations.json')
        assert saved['endpoint']['state_sha256']==m.state_hash(state)
