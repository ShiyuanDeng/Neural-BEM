"""Complete TR-003 branches after the retained zero-padding adapter failure."""
from .common import *
from .folds import homotopy


def run(folder, budget):
    parent = OUTPUT/'TR-003'
    evidence = sorted((parent/'endpoints').glob('*.json'))
    if len(evidence)!=4 or not all(read(p)['numerical_qualification'] for p in evidence):
        raise ValueError('Four qualified endpoint audits are required for reuse')
    failure = read(parent/'failure.json')
    if list((parent/'branches').glob('*.json')):
        raise ValueError('Unexpected partial branch; preserve and inspect before resuming')
    write(folder/'parent.json',dict(work=failure['work'],
        files={b.path_ref(p):digest(p) for p in evidence+[parent/'failure.json',parent/'manifest.json']},
        repair='Zero-pad chart origin to stage storage band before preparing production tangent',
        endpoint_audits='Reused unchanged; no endpoint re-execution',
        remaining_seconds=budget.seconds,remaining_frequency_solves=budget.cap))
    for p in evidence:
        write(folder/'endpoints'/p.name,read(p))
    for case in CASES[1:3]:
        homotopy(folder,budget,case)


if __name__=='__main__':
    used=read(OUTPUT/'TR-003/failure.json')['work']
    execute('TR-003-branches',run,3600.-used['seconds'],20000-used['frequency_solves_attempted'])
