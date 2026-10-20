"""Put ``solvers/`` on the import path for tests, as ``PYTHONPATH=solvers:.`` does."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent/'solvers'))
