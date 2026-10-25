"""Exact control-path behaviour, pinned by a saved reference.

The reference was regenerated from the NR-001 step 2 source, after the fit
stopped re-solving at a finer resolution. Later reorganisations must match it.
"""
import json
from pathlib import Path

from refactor_reference import control_paths, stable


def test_optional_control_paths_match_the_saved_reference():
    reference = json.loads(
        (Path(__file__).parent / 'data/refactor_control_reference.json').read_text())
    assert stable(control_paths()) == stable(reference['control_paths'])
