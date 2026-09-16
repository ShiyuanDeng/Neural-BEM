"""Score a saved endpoint without further fitting."""
import argparse
from pathlib import Path
from .run import p,m,suite,pipeline,SOURCE,read,write
from sdf_inverse.runtime import inverse_execution


@inverse_execution
def run(source):
    config=read(source/'config.json')
    state=p.driver.deserialize_state(read(source/'retained_state.json'))
    _,observed,evaluation,scene,spec=suite.load_scene(SOURCE,config['scene'])
    solve=p.driver.baseline.iteration01_solve_config()
    ledger=m.Ledger(cap=100,seconds=300)
    with ledger.instrument():
        score=pipeline.base.score_endpoint(state,scene,spec,observed,evaluation,solve,ledger,source/'endpoint_check.json')
    write(source/'score.json',dict(score=score,work=ledger.snapshot(),fitted_frequencies_hz=config.get('frequencies_hz')))
    print(score,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path)
    run(parser.parse_args().source)
