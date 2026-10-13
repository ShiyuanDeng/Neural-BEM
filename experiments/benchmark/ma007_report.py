"""Read-only MA-007 pilot receipts; does not run fits, solvers, or atlas probes."""
import argparse
from pathlib import Path
import hashlib
import numpy as np
from bem_inverse.io import write, digest
from bem_inverse.continuation.lm_backend import normalize, BackendConfig, control_step
from .ma007_retention import read
from .ma007 import OUTPUT
from . import campaign as c


def relative(a,b,floor=1e-14):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),floor))


def validate_recording(folder):
    """Replay saved data-space arithmetic; never assemble a new operator."""
    from types import SimpleNamespace
    root=folder/'C0_recorded' if (folder/'C0_recorded').exists() else folder
    result=read(root/'result.json')
    index=read(root/'recording/index.json')
    rows=[]
    for path in sorted((root/'recording/chunks').glob('*.json')):
        receipt=read(path); artifact=c.ROOT/receipt['path']
        if digest(artifact)!=receipt['sha256']:
            raise ValueError('Recorded array chunk hash changed: '+str(artifact))
        with np.load(artifact,allow_pickle=False) as saved:
            arrays={k:saved[k] for k in saved.files}
        for key,metadata in receipt['arrays'].items():
            value=arrays[key]
            if (list(value.shape)!=metadata['shape'] or str(value.dtype)!=metadata['dtype'] or
                hashlib.sha256(value.tobytes()).hexdigest()!=metadata['sha256']):
                raise ValueError('Recorded array read-back defect: '+key)
        identity=receipt['identity']; kind=identity['kind']
        row=dict(event=identity['index'],kind=kind,artifact=receipt['path'],passed=True)
        if kind=='objective':
            residual=normalize(arrays['prediction']-arrays['observed'],arrays['observed'],
                               arrays['weights'],identity['floor'])
            loss=.5*float(residual@residual)
            row.update(residual_error=relative(residual,arrays['assembled_residual']),
                loss_error=abs(loss-identity['loss'])/max(abs(identity['loss']),1e-15))
            row['passed']=row['residual_error']<=1e-12 and row['loss_error']<=1e-12
        elif kind=='linearization':
            gradient=arrays['J_normalized'].T@arrays['assembled_residual']
            row['gradient_error']=relative(gradient,arrays['gradient'])
            row['passed']=row['gradient_error']<=1e-10
        elif kind=='proposal':
            lhs=arrays['normal']+identity['damping']*arrays['metric']
            proposed=np.linalg.solve(lhs,-arrays['gradient'])
            band=(len(proposed)-1)//2
            orders=np.r_[0,np.arange(1,band+1),np.arange(1,band+1)]
            bounded=control_step(proposed,SimpleNamespace(orders=orders),None,BackendConfig(**identity['config']))
            row.update(raw_step_error=relative(proposed,arrays['raw_proposed']),
                bounded_step_error=relative(bounded,arrays['bounded_proposed']))
            row['passed']=row['raw_step_error']<=1e-10 and row['bounded_step_error']<=1e-10
            if not row['passed']:
                row['condition']=float(np.linalg.cond(lhs))
                row['replay_flag']='retained exact inputs; replay unqualified'
        rows.append(row)
    counted={kind:sum(e['kind']==kind for e in index['events']) for kind in ('field','reciprocal','objective','proposal')}
    counts=[result['physics']['counts'],*[v['counts'] for v in result['physics'].get('workspace_services',{}).values()]]
    reconciliation=dict(fields=counted['field']==sum(v['evaluations'] for v in counts),
        reciprocals=counted['reciprocal']==sum(v['derivatives'] for v in counts),
        events=index['events_count']==len(index['events']))
    value=dict(readback_passed=True,replay_passed=all(x['passed'] for x in rows),
        reconciliation=reconciliation,rows=rows,counts=counted,
        chunks_verified=len(rows),raw_array_bytes=index['raw_array_bytes'],
        recording_seconds={k:index[k] for k in ('serialization_seconds','capture_inclusive_seconds',
            'pure_io_wait_seconds','offline_refusal_reciprocal_seconds')})
    write(folder/'recording_validation.json',value)
    return value


def validate_atlas(folder):
    """Hash/read-back and retained operator identities; no new physics calls."""
    atlas=read(folder/'response_atlas.json')
    expected={a['artifact']:a for role in atlas['roles'] for cell in role['cells'] for a in cell['artifacts']}
    rows=[]
    for path in sorted(folder.glob('*/chunks/*.json')):
        receipt=read(path); artifact=c.ROOT/receipt['path']
        if digest(artifact)!=receipt['sha256']:
            raise ValueError('Atlas chunk hash changed: '+str(artifact))
        with np.load(artifact,allow_pickle=False) as loaded:
            arrays={k:loaded[k] for k in loaded.files}
        for name,metadata in receipt['arrays'].items():
            array=arrays[name]
            if (list(array.shape)!=metadata['shape'] or str(array.dtype)!=metadata['dtype'] or
                hashlib.sha256(array.tobytes()).hexdigest()!=metadata['sha256']):
                raise ValueError('Atlas array shape/dtype/hash defect: '+str(artifact)+'/'+name)
        row=dict(path=receipt['path'],bytes=receipt['bytes'],sha256=receipt['sha256'],passed=True)
        if 'A' in arrays:
            source_residual=float(np.linalg.norm(arrays['A']@arrays['X_s']-arrays['B_s'])/np.linalg.norm(arrays['B_s']))
            prediction=np.einsum('ri,ir->r',arrays['R'],arrays['X_s'])
            norm_floor=1e-14*max(np.linalg.norm(arrays['observed']),1e-30)
            recorded_residual=expected[receipt['path']]['system_residual']
            row.update(system_residual=source_residual,recorded_system_residual=recorded_residual,
                residual_receipt_error=abs(source_residual-recorded_residual)/max(recorded_residual,1e-15),
                paired_prediction_error=relative(prediction,arrays['prediction'],norm_floor),
                reciprocal_system_residual=float(np.linalg.norm(arrays['A']@arrays['X_r']-arrays['B_r'])/
                                                max(np.linalg.norm(arrays['B_r']),1e-30)))
            row['passed']=row['residual_receipt_error']<=1e-12 and row['paired_prediction_error']<=1e-10
        rows.append(row)
    value=dict(readback_passed=all(x['passed'] for x in rows),rows=rows,chunks_verified=len(rows),
        raw_array_bytes=sum(x['bytes'] for x in rows),status=atlas['status'],
        full_atlas_complete=atlas['full_atlas_complete'],pending=atlas['pending'])
    write(folder/'readback.json',value)
    return value


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
    parser.add_argument('--kind',choices=('pilot','control','atlas'),default='pilot')
    args=parser.parse_args()
    value={'pilot':report,'control':validate_recording,'atlas':validate_atlas}[args.kind](args.folder.resolve())
    print(value['chunks_verified'],'chunks verified')


if __name__=='__main__':
    main()
