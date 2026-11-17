"""Hash retained CSI payloads and record the command, without moving any data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    run = args.run
    launch = json.loads((run / 'launch.json').read_text())
    entries = []
    for path in sorted(run.iterdir()):
        if not path.is_file() or path.name == 'manifest.json':
            continue
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        local = ((path.suffix == '.mat' and path.name != 'final_contrast.mat')
                 or path.suffix == '.fig' or path.name == 'upstream_matlab_sources.tar.gz')
        entries.append(dict(path=path.name, bytes=path.stat().st_size,
                            sha256=digest.hexdigest(), storage='local, git-ignored' if local else 'git'))
    repo = Path(__file__).resolve().parents[3]
    upstream = Path.home() / 'neural_bem_external/CC-CSI'
    summary = json.loads((run / 'matlab_summary.json').read_text())
    data_path, = upstream.rglob(summary['case_name'] + '.txt')
    record = dict(command=launch['command'],
                  wrapper_command=['python3', 'experiments/baselines/csi/run.py', launch['step'], '--attempt', 'reproduction'],
                  environment=dict(CSI_SCRIPT=str((run / 'executed_driver.m').resolve()), CSI_OUT=str(run.resolve()),
                                   CSI_REPO=str(repo), CSI_UPSTREAM=str(upstream), CSI_STEP=launch['step'],
                                   CSI_FIGURES=str(repo / launch.get('activity', 'docs/iterations/csi_adaptation/01_run_published_examples') / 'figures')),
                  input_data=dict(path=str(data_path), sha256=hashlib.sha256(data_path.read_bytes()).hexdigest()),
                  upstream_commit=launch['upstream_commit'],
                  wrapper_sources=[dict(path=str(p.relative_to(repo)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                                   for p in sorted((repo/'experiments/baselines/csi').iterdir())
                                   if p.suffix in ('.py', '.m')],
                  upstream_patches=[dict(path=str(p.relative_to(repo)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                                    for p in sorted((repo/'external/patches/cc-csi').glob('*.patch'))],
                  maxwellfdfd_commit=subprocess.check_output(['git', '-C', str(upstream.parent/'maxwellfdfd'),
                                                            'rev-parse', 'HEAD'], text=True).strip(),
                  started_utc=launch['started_utc'],
                  driver_sha256=launch['driver_sha256'], files=entries,
                  note='Pre-rule runs may already track files now marked local; no history is removed or rewritten.')
    (run / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(files=len(entries), total_bytes=sum(x['bytes'] for x in entries),
                          new_git_bytes=sum(x['bytes'] for x in entries if x['storage'] == 'git')), indent=2))


if __name__ == '__main__':
    main()
