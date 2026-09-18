"""Small append-only evidence helpers and hard operation/resource ceilings."""
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from experiments.laurent_compression.run_screen import source_hashes, write_csv


def hashes():
    result = source_hashes()
    result.update({str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(Path('experiments/laurent_literature').glob('*.py'))})
    return result


class Evidence:
    def __init__(self, out, config):
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=False)
        self.start = perf_counter()
        self.counts = dict(assemblies=0, factorizations=0)
        self.initial = hashes()
        self.previous_excepthook = sys.excepthook
        sys.excepthook = self.record_failure
        self.json('config.json', config)
        self.json('manifest.json', dict(source_hashes=self.initial,
            commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            branch=subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip(),
            dirty=subprocess.check_output(['git', 'status', '--short'], text=True),
            python=platform.python_version(), platform=platform.platform(),
            threads={k: os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
            load=os.getloadavg(), ceilings=dict(seconds=1800, peak_gib=6, assemblies=160, factorizations=600)))

    def record_failure(self, kind, value, traceback):
        self.json('failure.json', dict(status='FAILED', error_type=kind.__name__,
            error=str(value), work=self.counts, seconds=perf_counter()-self.start,
            peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20))
        self.previous_excepthook(kind, value, traceback)

    def reserve(self, **counts):
        self.check()
        for k, v in counts.items():
            if self.counts[k]+v > dict(assemblies=160, factorizations=600)[k]:
                raise RuntimeError(f'LAU-002 {k} budget exhausted before operation')
        for k,v in counts.items():
            self.counts[k] += v

    def check(self):
        if perf_counter()-self.start > 1800 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20 > 6:
            raise RuntimeError('LAU-002 resource ceiling reached')

    def charge(self, **counts):
        self.reserve(**{k:v for k,v in counts.items() if k in ('assemblies','factorizations')})
        for k,v in counts.items():
            if k not in ('assemblies','factorizations'):
                self.counts[k] = self.counts.get(k,0)+v

    def json(self, name, obj):
        (self.out/name).write_text(json.dumps(obj, indent=2, default=float, allow_nan=False)+'\n')

    def csv(self, name, rows):
        write_csv(self.out/name, rows)

    def finish(self, **summary):
        self.check()
        final = hashes()
        drift = [p for p in set(final)|set(self.initial) if final.get(p) != self.initial.get(p)]
        summary.update(status='SOURCE_DRIFT' if drift else 'COMPLETE', source_drift=drift,
            work=self.counts, seconds=perf_counter()-self.start,
            peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)
        self.json('summary.json', summary)
        self.json('artifact_hashes.json', {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.out.iterdir()) if p.is_file() and p.name!='artifact_hashes.json'})
        if drift:
            raise RuntimeError('Measured source drift: bundle is invalid')
        return summary
