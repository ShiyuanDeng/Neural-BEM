"""Portable source provenance for reproducible inverse experiment bundles."""
import hashlib
from pathlib import Path
import subprocess
import sys


def source_provenance(root):
    root = Path(root)
    files = sorted(set(root.glob('run_*topology*.py'))
                   | set((root / 'solvers').rglob('*.py'))
                   | set((root / 'config').rglob('*.py')))
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    return dict(commit=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
                dirty_status=git('status', '--porcelain'), python=sys.version,
                source_sha256={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in files})
