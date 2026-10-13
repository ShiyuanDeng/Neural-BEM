"""Read-only MA-007 pilot receipts; does not run fits, solvers, or atlas probes."""
import argparse
from pathlib import Path
import hashlib
import numpy as np
from bem_inverse.io import read, write, digest
from .ma007 import OUTPUT
from . import campaign as c


def report(folder):
    pilot=read(folder/'pilot.json')
    chunks=[]
    for path in sorted(folder.glob('*/chunks/*.json')):
        receipt=read(path)
        array_path=c.ROOT/receipt['path']
        if digest(array_path)!=receipt['sha256'] or array_path.stat().st_size!=receipt['bytes']:
            raise ValueError('Chunk hash/size defect: '+str(array_path))
        with np.load(array_path,allow_pickle=False) as arrays:
            if set(arrays.files)!=set(receipt['arrays']):
                raise ValueError('Array keys changed')
            for name,metadata in receipt['arrays'].items():
                value=arrays[name]
                if (list(value.shape)!=metadata['shape'] or str(value.dtype)!=metadata['dtype'] or
                    hashlib.sha256(value.tobytes()).hexdigest()!=metadata['sha256']):
                    raise ValueError('Array readback defect: '+str(array_path)+'/'+name)
        chunks.append(dict(path=receipt['path'],bytes=receipt['bytes'],sha256=receipt['sha256']))
    value=dict(experiment='MA-007',pilot_status=pilot['status'],full_study_complete=False,
        full_fits=pilot['full_fits'],chunks_verified=len(chunks),
        raw_array_bytes=sum(x['bytes'] for x in chunks),raw_arrays_retention='this machine only; gitignored',
        chunks=chunks,resources=pilot.get('resources'),outstanding=pilot['outstanding'])
    write(folder/'readback.json',value)
    lines=['# MA-007 maximum-dimension pilot','',
        '**This is partial qualification, not the continuation study. No policy fit or upper bound is established.**','',
        f"Status: {pilot['status']}. Full fits: {pilot['full_fits']}. Read-back verified {len(chunks)} chunks.",
        'Raw arrays remain on this machine only. Committed manifests carry paths, bytes and SHA-256; arrays are not pushed.','',
        '| State | Status | Computed / attempted cells | Sub-block check | Elapsed s | RSS GiB |',
        '|---|---|---:|---|---:|---:|']
    for row in pilot['states']:
        lines.append(f"| {row['state']} | {row['status']} | {sum(x['status']=='computed' for x in row['cells'])}/{len(row['cells'])} | {row['subblock_all_passed']} | {row['elapsed_seconds']:.2f} | {row['peak_rss_bytes']/2**30:.2f} |")
    lines+=['','Outstanding required work:','']+[f'- {x}' for x in pilot['outstanding']]
    (folder/'report.md').write_text('\n'.join(lines)+'\n')
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,required=True)
    args=parser.parse_args()
    print(report(args.folder.resolve())['chunks_verified'],'chunks verified')


if __name__=='__main__':
    main()
