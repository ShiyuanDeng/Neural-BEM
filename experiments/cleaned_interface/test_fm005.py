"""FM-005 schedule and reporting helpers; no forward solves."""
import pytest

from . import fm005


def test_schedule_is_fm004_refusals_then_control_then_recoveries():
    runs = fm005.schedule()
    assert [i for _, _, i in runs] == [*fm005.REFUSED, fm005.g.CONTROL, *fm005.RECOVERED]
    assert runs[7][0] == fm005.f.LOW and all(c == fm005.f.HIGH for c, _, _ in runs if _ == 'phase1')
    assert set(fm005.NEAR) == set(fm005.REFUSED) - {399}


def test_first_difference_of_identical_archive_is_none(tmp_path):
    case, start = fm005.f.HIGH, 82
    folder = tmp_path/'runs'/case/f'{start:04d}'
    folder.mkdir(parents=True)
    (folder/'accepted.json').write_bytes(fm005.fm004_accepted(case, start).read_bytes())
    assert fm005.first_difference(case, start, tmp_path) is None


def test_resolution_summary_counts_events_and_stop():
    result = dict(resolution_promoted=True, stages=[
        dict(stage='stage_3_damped', outcome='NORMAL_OPTIMIZER_RETURN', nodes=512,
             resolution_events=[dict(action='reject_inaccurate_candidate')]),
        dict(stage='release_M11', outcome='STAGE_QUOTA_REACHED', nodes=1024,
             resolution_events=[dict(action='refinement_attempt'), dict(action='promoted')]),
        dict(stage='release_M15', outcome='NUMERICAL_FAILURE', nodes=1024, resolution_events=[])])
    s = fm005.resolution_summary(result)
    assert s == dict(promoted=True, promotion_stage='release_M11', rejected_unresolved=1,
                     refinement_attempts=1, stop_stage='release_M15')


def test_response_settings():
    assert (fm005.NODES, fm005.REFINED, fm005.FINER.resolution) == (1024, 2048, 1024)
    assert fm005.RUN_SECONDS > fm005.g.FIT_SECONDS
