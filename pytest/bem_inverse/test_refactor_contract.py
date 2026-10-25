"""Exact behavior captured from the independent pre-refactor source snapshot."""
import json
from pathlib import Path

from refactor_reference import control_paths, stable


def test_optional_control_paths_match_the_original_implementation():
    reference = json.loads(
        (Path(__file__).parent / 'data/refactor_control_reference.json').read_text())
    assert stable(control_paths()) == stable(reference['control_paths'])


def test_ordinary_stage_evaluates_forward_and_residual_without_objective_production(monkeypatch):
    from bem_inverse import fit_stage as lm
    from bem_inverse.objective import Objective
    from bem_inverse.continuation.geometry import FourierCurve
    from test_resolution_resume import ScalarUpdate, setup

    def forbidden(*args, **kwargs):
        raise AssertionError('Ordinary stage forward solves must be explicit in fit_stage')

    monkeypatch.setattr(Objective, 'production', forbidden)
    physics, stage, config, ledger = setup(nodes=16, iterations=1)
    result = lm.fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(),
                          config, ledger, physics=physics)
    assert result.accepted_steps == 1
    assert result.final_loss < result.initial_loss
    assert {nodes for nodes, _ in physics.calls} == {16, 32}
