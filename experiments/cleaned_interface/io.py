"""Portable atomic receipts; no research driver imports."""
import hashlib
import json
from pathlib import Path
import numpy as np

from experiments.shape_continuation.geometry import FourierCurve


def portable(value):
    if isinstance(value, np.ndarray):
        return portable(value.tolist())
    if isinstance(value, (complex, np.complexfloating)):
        return dict(real=float(value.real), imag=float(value.imag))
    if isinstance(value, np.generic):
        return portable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): portable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [portable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(portable(value), indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def curve_record(curve):
    return dict(real=curve.coefficients.real, imag=curve.coefficients.imag)


def curve_from(row):
    return FourierCurve(np.asarray(row['real'])+1j*np.asarray(row['imag']))
