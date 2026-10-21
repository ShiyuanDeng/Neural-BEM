"""Exact behavior captured from the independent pre-refactor source snapshot."""
import json
from pathlib import Path

from refactor_reference import control_paths, stable


def test_optional_control_paths_match_the_original_implementation():
    reference = json.loads(
        (Path(__file__).parent / 'data/refactor_control_reference.json').read_text())
    assert stable(control_paths()) == stable(reference['control_paths'])


def test_existing_import_paths_reach_the_canonical_implementation():
    from bem_inverse.continuation import lm_backend
    from bem_inverse import fit_stage, a_forward, modal_muller
    from bem_inverse import a1_geometry, modal_geometry, a2_muller, modal_operator
    from bem_inverse import c10_geometry_trial, certified, spectral
    from bem_inverse import b6_geometry_derivatives, batched, runner
    from bem_inverse import nodal_kress
    from bem_inverse.forward_solvers import modal_muller as modal_solver, nodal_kress as nodal_solver

    assert lm_backend is fit_stage
    assert runner.fit_stage is fit_stage.fit_stage
    assert modal_muller is a_forward
    assert modal_muller is modal_solver
    assert nodal_kress is nodal_solver
    assert modal_geometry is a1_geometry
    assert modal_operator is a2_muller
    assert certified is spectral is c10_geometry_trial
    assert batched is b6_geometry_derivatives


def test_ordinary_stage_evaluates_forward_and_residual_without_objective_production(monkeypatch):
    from bem_inverse import fit_stage as lm
    from bem_inverse.continuation.geometry import FourierCurve
    from test_resolution_resume import ScalarUpdate, setup

    def forbidden(*args, **kwargs):
        raise AssertionError('Ordinary stage forward solves must be explicit in fit_stage')

    monkeypatch.setattr(lm.Objective, 'production', forbidden)
    physics, stage, config, ledger = setup(nodes=16, iterations=1)
    result = lm.fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(),
                          config, ledger, physics=physics)
    assert result.accepted_steps == 1
    assert result.final_loss < result.initial_loss
    assert {nodes for nodes, _ in physics.calls} == {16, 32}
