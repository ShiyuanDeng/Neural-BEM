"""Repeat the exploratory two-frequency topology / six-frequency shape recipe."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    topology = args.output / 'topology'
    refinement = args.output / 'refinement'
    commands = [
        [sys.executable, '-m', 'experiments.topology_playground_20260916.run',
         '--scene', args.scene, '--output', str(topology),
         '--frequencies', '0,1', '--seed-modes', '3', '--initial-modes', '3',
         '--guard-nodes', '256', '512', '--true-jacobian',
         '--control', json.dumps(dict(bandwidth_promotion=True, maximum_cycles=16)),
         '--seconds', str(args.topology_seconds)],
        [sys.executable, '-m', 'experiments.topology_playground_20260916.expanded_fit',
         '--source', str(topology), '--output', str(refinement),
         '--seconds', str(args.fit_seconds)],
    ]
    (args.output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    for name, command in zip(('topology', 'refinement'), commands):
        with (args.output / f'{name}.log').open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        if name == 'topology':
            result = json.loads((topology / 'result.json').read_text())
            if result['status'] != 'TOPOLOGY_COMPLETE':
                raise RuntimeError(f"Topology did not complete: {result['status']}")
    print((refinement / 'result.json').read_text(), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--topology-seconds', type=float, default=900)
    parser.add_argument('--fit-seconds', type=float, default=1200)
    main(parser.parse_args())
