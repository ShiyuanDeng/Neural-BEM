"""Make sibling archived comparison support importable in every pytest mode."""

from __future__ import annotations

from pathlib import Path
import sys


COMPARISON_TEST_ROOT = Path(__file__).resolve().parent
if str(COMPARISON_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPARISON_TEST_ROOT))
