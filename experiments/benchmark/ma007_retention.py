"""Lossless local raw arrays referenced by committed MA-007 JSON receipts."""
import hashlib
import json
from pathlib import Path
import numpy as np
from bem_inverse.io import digest, write
from . import campaign as c

PAYLOADS={'curve','final_curve','coefficients','candidate_coefficients','step_m','a_used',
    'field_relative','jacobian_relative','jacobian_column_norm','relative_residual',
    'paired_relative_residual','prediction_discrepancy','prediction_discrepancy_ratios',
    'base_prediction_discrepancy','threshold_distance','reference_field_relative',
    'reference_jacobian_relative','column_profile'}


def array_reference(value, folder):
    if isinstance(value,dict) and set(value)=={'real','imag'}:
        array=np.asarray(value['real'])+1j*np.asarray(value['imag'])
        encoding='complex_curve_record'
    elif isinstance(value,list) and value and all(isinstance(x,(int,float)) for x in value):
        array=np.asarray(value); encoding='list'
    else:
        return None
    sha=hashlib.sha256(str(array.dtype).encode()+str(array.shape).encode()+array.tobytes()).hexdigest()
    path=folder/'array_payloads'/(sha+'.npz')
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        np.savez_compressed(path,value=array)
    with np.load(path,allow_pickle=False) as loaded:
        if loaded['value'].tobytes()!=array.tobytes():
            raise ValueError('Lossless array-payload retention failed')
    return dict(array_reference=str(path.relative_to(c.ROOT)),encoding=encoding,
        array='value',shape=list(array.shape),dtype=str(array.dtype),sha256=digest(path),bytes=path.stat().st_size)


def dehydrate(value, folder, parent=None):
    if parent in PAYLOADS:
        replacement=array_reference(value,folder)
        if replacement is not None:
            return replacement
    if isinstance(value,dict):
        return {k:dehydrate(v,folder,k) for k,v in value.items()}
    if isinstance(value,list):
        return [dehydrate(v,folder) for v in value]
    return value


def expand(value):
    if isinstance(value,dict) and 'array_reference' in value:
        path=c.ROOT/value['array_reference']
        if digest(path)!=value['sha256']:
            raise ValueError('Array payload hash changed: '+str(path))
        with np.load(path,allow_pickle=False) as loaded:
            array=loaded[value['array']]
        if list(array.shape)!=value['shape'] or str(array.dtype)!=value['dtype']:
            raise ValueError('Array payload shape/dtype changed')
        if value['encoding']=='complex_curve_record':
            return dict(real=array.real.tolist(),imag=array.imag.tolist())
        return array.tolist()
    if isinstance(value,dict):
        return {k:expand(v) for k,v in value.items()}
    if isinstance(value,list):
        return [expand(v) for v in value]
    return value


def read(path):
    return expand(json.loads(Path(path).read_text()))


def retain(folder):
    """Preserve original receipts byte for byte while removing array payloads."""
    rows=[]
    for path in sorted(folder.rglob('*.json')):
        original=path.read_bytes(); value=json.loads(original)
        encoded=dehydrate(value,folder)
        if encoded==value:
            continue
        raw=path.with_suffix('.json.raw')
        if raw.exists() and raw.read_bytes()!=original:
            if expand(value)!=json.loads(raw.read_text()):
                raise ValueError('Closed receipt changed since retention: '+str(path))
            continue
        raw.write_bytes(original); write(path,encoded)
        if expand(encoded)!=value:
            raise ValueError('Receipt expansion changed its numerical content')
        rows.append(dict(path=str(path.relative_to(c.ROOT)),raw_path=str(raw.relative_to(c.ROOT)),
            original_sha256=digest(raw),committed_receipt_sha256=digest(path)))
    write(folder/'payload_retention.json',dict(schema='MA007-JSON-arrays-1',converted=rows,
        raw_copies='local machine only',raw_npz='local machine only',metadata='committed and pushed'))
    return rows
