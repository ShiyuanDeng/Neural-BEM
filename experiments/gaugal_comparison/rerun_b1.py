"""GGB-002 amendment B1: refit the nine MR-001 runs that the removed final check failed.

Overwrites those case folders in place (user, 2026-11-02). Settings are the saved
S1 manifest settings; S2 adds the weak start and ``MaterialUnknown`` as in MR-001.

    PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
        python -m experiments.gaugal_comparison.rerun_b1 known|material [case ...]

Optional case IDs refit only those cases, in the order given.
"""
import shutil
import sys

from bem_inverse.io import read
from bem_inverse.material import MaterialUnknown
from experiments.benchmark import campaign as C
from . import mr001

MR = C.ROOT/'results/validation/cleaned_interfaces/MR-001'
KNOWN = ('cog__c13.3', 'aphex_twin__c4', 'aphex_twin__c13.3')
MATERIAL = ('circle__c13.3', 'asymmetric__c13.3', 'cross__c13.3', 'cog__c13.3',
            'aphex_twin__c4', 'aphex_twin__c13.3')


def main():
    arm = sys.argv[1]
    settings = read(MR/'S1_slider_known_contrast/manifest.json')['settings']
    run_dir = MR/('S1_slider_known_contrast' if arm == 'known' else 'S2_slider_material_weak_start')
    for case in sys.argv[2:] or (KNOWN if arm == 'known' else MATERIAL):
        shutil.rmtree(run_dir/'runs'/case)
        row = C.row(case, C.INPUTS)
        if arm == 'known':
            C.run_case((run_dir, row, settings))
        else:
            mr001.run_case(run_dir, row, settings, 'weak', MaterialUnknown())
    if arm == 'material':
        mr001.summarize(run_dir)


if __name__ == '__main__':
    main()
