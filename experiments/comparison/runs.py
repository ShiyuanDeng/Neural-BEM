"""Run names, the planned run table and the storage layout.

    results/
      _shared/noise/<data>/<case>.npz     noisy data, read by every family
      metrics.csv                         one row per fit, raw numbers only
      <family>/<run>/run.json             settings, written once
      <family>/<run>/<case>/fit.json fit.npz score.json

A run name is ``<variant>_<data>_<contrast>_<frequency>``; all four tags are
always present, in this order.

| Tag | Values | Meaning |
|---|---|---|
| variant | ``default``, ``nodal``, ``fixedband<M>`` | the one method change from the default |
| data | ``clean``, ``cleandamped``, ``n<percent>d<draw>`` | noise level and draw; ``damped`` adds the damped catalog |
| contrast | ``uc``, ``kc`` | unknown (recovered) or known (supplied) contrast |
| frequency | ``fc``, ``fs``, ``sf<GHz>`` | frequency continuation, simultaneous, single frequency |
"""
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from bem_inverse.io import read, write
from experiments.benchmark import scenes as S
from experiments.cleaned_interface import benchmark as ci

ROOT = ci.ROOT
RESULTS = ROOT/'results'
FAMILIES = ('bem', 'gaugal')
CASES_ALL = tuple(S.CASES)
CASES_20 = tuple(c for c in S.CASES if not c.endswith('__c13.3'))


@dataclass(frozen=True)
class Run:
    family: str
    variant: str
    data: str
    contrast: str
    frequency: str

    @property
    def name(self):
        return f'{self.variant}_{self.data}_{self.contrast}_{self.frequency}'

    @property
    def key(self):
        return f'{self.family}/{self.name}'

    @property
    def noise(self):
        """(percent, draw) for noisy data, otherwise None."""
        found = re.fullmatch(r'n(\d+(?:\.\d+)?)d(\d+)', self.data)
        return (float(found.group(1)), int(found.group(2))) if found else None

    @property
    def damped(self):
        return self.data == 'cleandamped'

    @property
    def single_frequency_hz(self):
        return 1e9*float(self.frequency[2:]) if self.frequency.startswith('sf') else None

    @property
    def fixed_band(self):
        return int(self.variant[len('fixedband'):]) if self.variant.startswith('fixedband') else None

    def folder(self, root=RESULTS):
        return Path(root)/self.family/self.name


def parse(key):
    """``bem/default_clean_uc_fc`` -> Run. Unknown tags are refused."""
    if key.count('/') != 1 or key.count('_') != 3:
        raise ValueError(f'Expected <family>/<variant>_<data>_<contrast>_<frequency>, got {key!r}')
    family, name = key.split('/')
    run = Run(family, *name.split('_'))
    if family not in FAMILIES:
        raise ValueError(f'Unknown family {family!r}; choose from {FAMILIES}')
    if not re.fullmatch(r'default|nodal|fixedband\d+', run.variant):
        raise ValueError(f'Unknown variant {run.variant!r}')
    if run.data not in ('clean', 'cleandamped') and run.noise is None:
        raise ValueError(f'Unknown data tag {run.data!r}')
    if run.contrast not in ('uc', 'kc'):
        raise ValueError(f'Unknown contrast tag {run.contrast!r}')
    if run.frequency not in ('fc', 'fs') and not re.fullmatch(r'sf\d+(?:\.\d+)?', run.frequency):
        raise ValueError(f'Unknown frequency tag {run.frequency!r}')
    if run.single_frequency_hz is not None and run.single_frequency_hz not in ci.FREQUENCIES:
        raise ValueError(f'{run.frequency}: not one of the 19 catalog frequencies')
    return run


def cases_for(run):
    """The default method on real data runs all 30 scenes; every other run drops contrast 13.3."""
    default = (run.family == 'bem' and run.variant == 'default' and run.contrast == 'uc'
               and run.frequency == 'fc' and not run.damped)
    return CASES_ALL if default else CASES_20


# The plan's run table, in running order. GauGal goes last.
PLAN = (
    (1, 'default method, clean', ('bem/default_clean_uc_fc',)),
    (2, 'default method, 1% noise, three draws',
     ('bem/default_n1d0_uc_fc', 'bem/default_n1d1_uc_fc', 'bem/default_n1d2_uc_fc')),
    (3, 'contrast supplied', ('bem/default_clean_kc_fc',)),
    (4, 'damped catalog added, old schedule', ('bem/default_cleandamped_uc_fc',)),
    (5, 'nodal backend', ('bem/nodal_clean_uc_fc', 'bem/nodal_n1d0_uc_fc')),
    (6, 'shape band 37 throughout', ('bem/fixedband37_clean_uc_fc',)),
    (7, 'all 19 frequencies from the start', ('bem/default_clean_uc_fs',)),
    (8, 'one frequency only', ('bem/default_clean_uc_sf0.5', 'bem/default_clean_uc_sf1',
                               'bem/default_clean_uc_sf1.5', 'bem/default_clean_uc_sf2')),
    (9, 'GauGal, untuned', ('gaugal/default_n1d0_uc_fs',)),
)


def commit():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--short', '--', 'solvers', 'experiments'], cwd=ROOT, text=True)
    return dict(commit=head, uncommitted_code=sorted(line[3:] for line in dirty.splitlines()))


def open_run(run, settings, cases, root=RESULTS):
    """Write ``run.json`` once. A later call with different settings is refused."""
    path = run.folder(root)/'run.json'
    record = dict(run=run.key, family=run.family, variant=run.variant, data=run.data, contrast=run.contrast,
                  frequency=run.frequency, settings=settings)
    if path.exists():
        saved = read(path)
        if {k: saved[k] for k in record} != read_back(record):
            raise ValueError(f'{run.key}: settings differ from the saved run.json; use another run name')
        return saved
    write(path, dict(record, planned_cases=list(cases), environment=ci.environment(), **commit()))
    return read(path)


def read_back(value):
    """``value`` as it reads after a JSON round trip, for comparing with a saved record."""
    import json
    from bem_inverse.io import portable
    return json.loads(json.dumps(portable(value)))


def fits(root=RESULTS):
    """Every (run folder, case folder) holding a fit, in name order."""
    root = Path(root)
    for family in sorted(p for p in root.glob('*') if p.is_dir() and not p.name.startswith('_')):
        for run in sorted(p for p in family.glob('*') if (p/'run.json').exists()):
            for case in sorted(p for p in run.glob('*') if (p/'fit.json').exists()):
                yield run, case
