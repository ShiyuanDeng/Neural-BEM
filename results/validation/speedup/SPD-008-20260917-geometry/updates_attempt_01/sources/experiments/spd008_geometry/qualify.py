"""Bounded geometry and one-update qualification; never a full campaign."""
import cProfile
from dataclasses import replace
import io
import json
import pstats
from statistics import median
import time
import numpy as np

from . import common as c
from ordered_boundary.validation_cache import geometry_validation, validation_cache
from sdf_inverse.runtime import inverse_runtime
from gpr_bem_kress.execution import execution
from sdf_inverse import topology_controller as tc

MODES = ('reference', 'cache', 'certified')


def geometry(bundle):
    fixture_path = bundle/'preparation/fixtures.json'
    fixtures = c.read(fixture_path)
    inputs = [fixture_path] + [c.ROOT/f['source'] for f in fixtures]
    output = bundle/'geometry'
    frozen = c.freeze(output, inputs)
    rows, status, error = [], 'PASS', None
    started = time.perf_counter()
    solve = c.p.driver.baseline.iteration01_solve_config()
    try:
        with c.wall_limit(300):
            for fixture in fixtures:
                if c.sha(c.ROOT/fixture['source']) != fixture['source_sha256']:
                    raise RuntimeError('Prepared fixture source drift')
                state = c.p.driver.deserialize_state(fixture['state'])
                expected = None
                for mode in MODES:
                    with validation_cache(mode) as cache:
                        decisions = []
                        for nodes in (64,128,256,512,512,256,128,64):
                            decisions.append(c.m.rt.multiradial_geometry_admissible(state,
                                c.p.driver.baseline._geometry_config(nodes), solve_config=solve))
                        snapshot = cache.snapshot()
                    if expected is None:
                        expected = decisions
                    if decisions != expected:
                        raise ValueError('Geometry mismatch: '+fixture['name']+' '+mode)
                    if fixture['name'] == 'top006_resolution_sensitive_abort':
                        assert decisions[:3] == [True,False,False]
                    rows.append(dict(fixture=fixture['name'], mode=mode, decisions=decisions,
                                     passed=True, geometry=snapshot))
                print('GEOMETRY',fixture['name'],'PASS',flush=True)
            c.verify(output)
    except Exception as exc:
        status, error = 'FAIL', repr(exc)
    result = dict(status=status,error=error,rows=rows,seconds=time.perf_counter()-started,
                  source_sha256=frozen, physical_solves=0, wall_ceiling_seconds=300)
    c.write(output/'qualification.json',result)
    if status != 'PASS':
        raise RuntimeError(error)
    return result


def _hard_update(scene, mode, destination, ledger):
    original = c.ARCHIVE/'compiled_0/runs'/scene
    handoff = c.read(original/'handoff.json')
    settings = c.read(original/'F/stage_1/optimizer.json')
    observed = c.read(c.ARCHIVE/'compiled_0/inputs'/scene/'training_observations.json')
    state = c.p.driver.deserialize_state(handoff['state'])
    values = np.array(observed['observed_real'])+1j*np.array(observed['observed_imag'])
    data = c.p.training_data(c.p.TRAIN[:1], values[:,:1])
    optimizer = replace(c.m.rt.ParameterFDConfig(**settings['config']),max_iterations=1)
    archived = next(json.loads(line) for line in (original/'F/stage_1/trajectory.jsonl').read_text().splitlines()
                    if json.loads(line)['iteration'] == 1)
    stats = []
    ledger.begin_stage(1,400)
    started = time.perf_counter()
    with geometry_validation(mode,on_fit=stats.append):
        _, terminal = c.m.fit_stage(state,data,(256,512),c.p.driver.baseline.iteration01_solve_config(),
                                   optimizer,.008,ledger,destination)
    elapsed = time.perf_counter()-started
    assert terminal['stage_outcome']=='NORMAL_OPTIMIZER_RETURN',terminal
    assert terminal['accepted_steps']==1 and terminal['effective_training_exposure']
    assert terminal['state_sha256']==archived['state_sha256'], (scene,mode,'archived update mismatch')
    assert len(stats)==1
    jacobians = [json.loads(line) for line in (destination/'jacobians.jsonl').read_text().splitlines()]
    candidates = [json.loads(line) for line in (destination/'production_candidates.jsonl').read_text().splitlines()]
    decisions = dict(final=terminal['state_sha256'],accepted_steps=terminal['accepted_steps'],
        stop=terminal['optimizer_stop'],unresolved=terminal['unresolved_columns'],one_sided=terminal['one_sided_columns'],
        jacobians=[{k:r[k] for k in ('state_sha256','directions','one_sided_columns','unresolved_columns')} for r in jacobians],
        candidates=[{k:r[k] for k in ('base_state_sha256','candidate_state_sha256','production_gain')} for r in candidates])
    return dict(scene=scene,mode=mode,seconds=elapsed,geometry=stats[0],decisions=decisions,matched_archive=True)


def _coarse_update(mode, ledger):
    state = c.p.driver.deserialize_state(c.read(c.previous.HISTORY/'inputs/merge/initial_state.json'))
    observed = c.read(c.previous.HISTORY/'inputs/merge/training_observations.json')
    values = np.array(observed['observed_real'])+1j*np.array(observed['observed_imag'])
    data = c.p.training_data(c.p.TRAIN[:1],values[:,:1])
    control = c.p.benchmark.controller_config(c.read(c.previous.HISTORY/'scene_spec.json'),'H')
    optimizer = tc._optimizer_config(state,control,iterations=1)
    stats, frames, decisions = [], [], []
    ledger.begin_stage(1,400)
    started = time.perf_counter()
    def diagnostic(event,payload):
        if event == 'candidate_evaluated':
            candidate = payload['candidate']
            decisions.append(None if candidate is None else c.m.state_hash(candidate.state))
    with geometry_validation(mode,on_fit=stats.append):
        result = c.m.rt.run_multiradial_fd_inverse(state,data,c.p.driver.baseline._geometry_config(64),
            solve_config=c.p.driver.baseline.iteration01_solve_config(),config=optimizer,
            minimum_component_radius_m=control.minimum_component_radius_m,cartesian_gauge=True,
            feasibility_geometry_configs=(c.p.driver.baseline._geometry_config(128),),
            feasible_fd_jacobian=True,jacobian_batch_callback=lambda n:ledger.reserve(n+3),
            progress_callback=lambda f:frames.append(c.m.state_hash(f.state)),diagnostic_callback=diagnostic)
    return dict(scene='coarse_merge',mode=mode,seconds=time.perf_counter()-started,geometry=stats[0],
        decisions=dict(final=c.m.state_hash(result.final_state),frames=frames,candidates=decisions,
                       one_sided=result.one_sided_jacobian_column_count,
                       unresolved=result.unresolved_jacobian_column_count,stop=result.stop_reason))


def updates(bundle):
    output = bundle/'updates'
    inputs = [bundle/'geometry/qualification.json']
    for scene in c.SCENES[2:]:
        original = c.ARCHIVE/'compiled_0/runs'/scene
        inputs += [original/'handoff.json',original/'F/stage_1/optimizer.json',
                   original/'F/stage_1/trajectory.jsonl',c.ARCHIVE/'compiled_0/inputs'/scene/'training_observations.json']
    inputs += [c.previous.HISTORY/'inputs/merge/initial_state.json',
               c.previous.HISTORY/'inputs/merge/training_observations.json',c.previous.HISTORY/'scene_spec.json']
    frozen = c.freeze(output,inputs)
    ledger = c.m.Ledger(cap=2000,seconds=1800)
    rows, status, error = [], 'PASS', None
    started = time.perf_counter()
    profile_row = None
    try:
        with c.wall_limit(1800), inverse_runtime('compiled'), execution(kernels='real_bessel'), ledger.instrument():
            for rep in range(2):
                for scene in c.SCENES[2:]:
                    for mode in (MODES if rep==0 else tuple(reversed(MODES))):
                        row = _hard_update(scene,mode,output/f'{scene}_{mode}_{rep}',ledger)
                        row['repetition'] = rep
                        rows.append(row)
                        c.write(output/'progress.json',rows)
                        print('UPDATE',scene,mode,rep,row['seconds'],row['geometry']['seconds'].get('stencil'),flush=True)
            for mode in MODES:
                rows.append(_coarse_update(mode,ledger))
            # All unprofiled timings finish before a separate diagnostic profile.
            profiler = cProfile.Profile()
            profiler.enable()
            try:
                profile_row = _hard_update('central-ellipse-star','certified',output/'profile_stage',ledger)
            finally:
                profiler.disable()
            profiler.dump_stats(str(output/'profile.pstats'))
            stream = io.StringIO()
            pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(60)
            (output/'profile.txt').write_text(stream.getvalue())
            for scene in (*c.SCENES[2:],'coarse_merge'):
                matching = [r for r in rows if r['scene']==scene]
                assert all(r['decisions']==matching[0]['decisions'] for r in matching),scene
            c.verify(output)
    except Exception as exc:
        status,error = 'FAIL',repr(exc)
    gates = []
    for scene in c.SCENES[2:]:
        times = {mode:[r['geometry']['seconds']['stencil'] for r in rows
                       if r['scene']==scene and r['mode']==mode] for mode in MODES}
        if all(len(v)==2 for v in times.values()):
            medians = {k:median(v) for k,v in times.items()}
            gates.append(dict(scene=scene,stencil_medians=medians,
                              speedup=medians['reference']/medians['certified'],
                              passed=medians['reference']/medians['certified']>=2))
    released = status=='PASS' and len(gates)==2 and all(g['passed'] for g in gates)
    result = dict(status=status,error=error,rows=rows,profile=profile_row,gates=gates,
                  full_campaign_released=released,seconds=time.perf_counter()-started,
                  work=ledger.snapshot(),source_sha256=frozen,limits=dict(seconds=1800,work_units=2000))
    c.write(output/'qualification.json',result)
    if status!='PASS':
        raise RuntimeError(error)
    return result
