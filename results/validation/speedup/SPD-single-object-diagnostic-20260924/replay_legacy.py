"""Run the existing legacy ablation, resolving one moved provenance document.

No numerical code is changed. __file__ remains the original driver so its
relative data imports and source manifest keep their intended repository root.
"""
from pathlib import Path
path = Path.cwd()/'run_sdf_representation_ablation.py'
source = path.read_text()
old = 'ROOT / "docs/codex_sdf_kress_priorities_2026-09-05.md"'
new = 'ROOT / "docs/legacy/codex_sdf_kress_priorities_2026-09-05.md"'
assert source.count(old) == 1
exec(compile(source.replace(old, new), str(path), 'exec'),
     {'__file__': str(path), '__name__': '__main__'})
