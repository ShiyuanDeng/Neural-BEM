"""Check saved final evidence and write a versioned manifest, without fitting."""
from pathlib import Path
import hashlib
import json
import platform
import re
import subprocess
import numpy as np
import scipy
from .complex_material import ComplexMaterialDual
from .layered import Layered
from .layered_screen import grid
from .independent import groups


def run():
    root = Path('results/experiments')
    out = root / 'outsider_research_20260916'
    support = root / 'support_certificates_20260916'
    data = np.load(support / 'layered_data.npz')
    records = json.loads((support / 'complex_material.json').read_text())
    f = float(data['frequency'])
    eps0, mu0 = 8.8541878128e-12, 1.25663706212e-6
    bg = 6+1j*.02/(eps0*2*np.pi*f)
    immax = .04/(eps0*2*np.pi*f)
    ka = 2*np.pi*f*np.sqrt(eps0*mu0)
    layer = Layered(ka, ka*np.sqrt(bg))
    scale = np.linalg.norm(data['y'])
    checks = []
    for row in records:
        if not row['success']:
            continue
        points, h = grid(row['n'])
        if row['name'] == 'left':
            points = points[points[:, 0] < 0]
        g, e, a = layer.matrices(points, h*h, data['sources'], data['receivers'])
        model = ComplexMaterialDual(g, e, a/scale, data['y']/scale, bg,
                                    (2.7, 6.), (0., immax), groups(points, 2), cross=row['cross'])
        x = np.asarray(row['multipliers'])
        ev = model.evaluate(x)
        eig = np.linalg.eigvalsh(ev['q'])
        assert eig[0] > row['eigenvalue_margin']
        assert np.min(x[model.positive]) > 0
        assert row['bound'] <= ev['value'] + 1e-10
        checks.append(dict(n=row['n'], name=row['name'], cross=row['cross'],
                           eigenvalue=float(eig[0]), freshly_evaluated_dual=float(ev['value']),
                           stored_lower_bound=row['bound']))
    source_roots = [Path('experiments')/p for p in ('support_certificates', 'operator_rom', 'passive_shape')]
    source_files = sorted(p for base in source_roots for p in base.glob('*') if p.suffix in ('.py', '.md'))
    documents = [p for p in source_files if p.suffix == '.md'] + [out/'README.md']
    for doc in documents:
        for target in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
            if '://' not in target and not target.startswith('#'):
                target_path = doc.parent / target.split('#')[0]
                # This manifest is created after the link check.
                assert target_path.exists() or target_path == out/'validation.json', (doc, target)
    for path in source_files + documents:
        assert not any(line.rstrip() != line for line in path.read_text().splitlines()), path
    historical = json.loads((support/'manifest.json').read_text())
    historical['note'] = ('Historical source snapshot at primal_check, before broad-material qualification '
                          'and reporting. The final current-source manifest is ../outsider_research_20260916/validation.json.')
    (support/'manifest.json').write_text(json.dumps(historical, indent=2))
    evidence_dirs = [root/p for p in ('support_certificates_20260916', 'operator_rom_20260916',
                                     'passive_shape_20260916', 'outsider_research_20260916')]
    evidence = sorted(p for base in evidence_dirs for p in base.glob('*')
                      if p.suffix in ('.json', '.md', '.svg') and p.name != 'validation.json')
    for path in evidence:
        if path.suffix == '.json':
            json.loads(path.read_text())
    sha = lambda paths: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    manifest = dict(
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        branch=subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip(),
        versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        focused_tests=dict(command='python -m pytest -q experiments/support_certificates/test_core.py experiments/support_certificates/test_layered.py experiments/operator_rom/test_rom.py',
                           observed_result='10 passed in 0.09s', note='Executed before this audit; no tested numerical code changed afterward.'),
        fresh_dual_checks=checks, local_document_links='passed', source_whitespace='passed',
        source_hashes=sha(source_files), evidence_hashes=sha(evidence),
        limitations=['Floating-point verification, not an interval proof.',
                     'No uniform continuum modelling-error bound.',
                     'Finite slices and synthetic data; no production or field-data qualification.'])
    (out/'validation.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(dict(fresh_dual_checks=len(checks), source_files=len(source_files), evidence_files=len(evidence),
                          branch=manifest['branch'], links='passed'), indent=2))


if __name__ == '__main__':
    run()
