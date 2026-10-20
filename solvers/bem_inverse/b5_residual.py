"""B5. Predicted data + observations → normalized real residual and loss.

Inputs have axes (receiver, frequency, optional trailing coordinate axes).
Rows stack all real entries followed by all imaginary entries.
"""
import numpy as np


def evaluate(curve, prediction, forwards, observed, weights, residual_floor):
    """Build the existing Evaluation record from receiver-by-frequency data.

    Curve and forward handles are retained by reference. Reduction order is
    residual normalization, relative data error, then half squared residual.
    """
    from .stage_types import Evaluation
    r = normalize(prediction - observed, observed, weights, residual_floor)
    relative = float(np.linalg.norm(prediction - observed) / np.linalg.norm(observed))
    return Evaluation(curve, 0.5 * float(r @ r), relative, r, prediction, tuple(forwards))


def normalize(values, observed, weights, floor=1e-12):
    """Linear SPD residual map: per-frequency relative scale and sqrt weight.

    Matches `sdf_inverse.optimization.normalized_complex_residual`, including
    its floor and real/imaginary row order. `values` may carry trailing axes.
    """
    observed = np.asarray(observed)
    norms = np.linalg.norm(observed, axis=0)
    reference = max(float(np.max(norms)), float(np.linalg.norm(observed)) / np.sqrt(observed.shape[1]), 1.0)
    scales = np.maximum(norms, max(floor * reference, np.finfo(float).tiny))
    values = np.asarray(values)
    shape = (1, -1) + (1,) * (values.ndim - 2)
    scaled = values / scales.reshape(shape) * np.sqrt(np.asarray(weights, float)).reshape(shape)
    tail = values.shape[2:]
    return np.concatenate((scaled.real.reshape((-1,) + tail), scaled.imag.reshape((-1,) + tail)))
