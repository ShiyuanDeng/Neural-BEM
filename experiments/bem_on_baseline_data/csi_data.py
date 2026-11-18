"""Read a CC-CSI seven-column TM table into masked point-source observations.

No truth is read here. The rules are CC-CSI's own, from ``functions/ReadFreData.m``
(TM branch) and the first-opus driver ``Inv_Fresnel_I.m``:

- columns: source index, receiver index, GHz, Re/Im total field, Re/Im incident field;
- source index i -> angle 10(i-1) - 2.5 deg at 0.72 m; receiver j -> 5(j-1) deg at 0.76 m;
- scattered = total - incident;
- one calibration factor per source and frequency, at row floor(NRX/2)+1 of that
  source's block in FILE order: measured incident / analytic unit-source field.

CC-CSI uses exp(+j w t); we use exp(-i w t). Every complex value is conjugated once.
Our factor is c = conj(Finc[cal]) / G(k r_cal), with G = i H0^(1)(k r)/4, which
equals conj(Enor * omega_n^2) in CC-CSI's normalized units. Data for the fit are
conj(scattered) / c, reordered from file order into the C-order measured vector
of ``PointSourceAcquisition(paired=False, mask=...)``.
See docs/iterations/adapt_bem_to_baseline_data/03_adapt_bem_to_csi_data/plan.md.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np
from scipy.special import hankel1

from bem_inverse import PointSourceAcquisition
from bem_inverse.problem import Observation

C0 = 299792458.0                 # m/s, as MaxwellFDFD PhysC.c0
LENGTH_M = .05                   # package length unit of the default method
TX_RADIUS_M, RX_RADIUS_M = .72, .76
NTX, RING = 36, 72
MEASURED = Path.home()/'neural_bem_external/CC-CSI/FresnelData/The_first_opus/dielTM_dec8f.txt'
# All ten simulated tables, frozen by the baseline side, each with a .sha256 beside it.
# Reported pass (the user, 18 Nov 2026): five frequencies, 0.5, 1, 1.5, 2 and 2.5 GHz, 8820 rows;
# both methods read these same files. The eight-frequency tables (commit 8d4c6123d, early look
# at 1-3 GHz) stay where they are; only the dry check reads them.
SIMULATED = 'results/csi/tg002/2026-11-18_five_frequency_data/{shape}/forward/synthetic_input.txt'
SIMULATED_EIGHT = 'results/csi/tg002/2026-11-18_low_band_data/{shape}/forward/synthetic_input.txt'


def source_positions_m():
    angle = np.radians(10.*np.arange(NTX)-2.5)
    return TX_RADIUS_M*np.c_[np.cos(angle), np.sin(angle)]


def receiver_positions_m():
    angle = np.radians(5.*np.arange(RING))
    return RX_RADIUS_M*np.c_[np.cos(angle), np.sin(angle)]


def unit_field(k_m, distance_m):
    """Our outgoing unit line-source field i H0^(1)(k r)/4, exp(-i w t)."""
    return .25j*hankel1(0, k_m*np.asarray(distance_m))


@dataclass(frozen=True)
class CsiFrequency:
    frequency_hz: float
    k_m: float
    file_rows: np.ndarray        # row indices in the input file, file order
    sources: np.ndarray          # 0-based source per file row
    receivers: np.ndarray        # 0-based receiver per file row
    permutation: np.ndarray      # file-order position of each C-order entry
    calibration_rows: np.ndarray # file-order position of each source's calibration row
    factors: np.ndarray          # (NTX,) our complex factor c
    total: np.ndarray            # conjugated, file order
    incident: np.ndarray         # conjugated, file order
    data: np.ndarray             # conj(scattered)/c, C order


def verify_sha256(path):
    """Check a frozen table against the .sha256 beside it; returns the digest."""
    path = Path(path)
    expected = Path(str(path)+'.sha256').read_text().split()[0]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f'{path}: SHA-256 {actual} does not match {expected}.')
    return actual


def read_table(path):
    """Parse one table. Returns (mask, [CsiFrequency, ...], sha256)."""
    path = Path(path)
    raw = path.read_bytes()
    table = np.loadtxt(path)
    if table.ndim != 2 or table.shape[1] != 7:
        raise ValueError('Expected the seven-column CC-CSI table.')
    tx, rx = source_positions_m(), receiver_positions_m()
    mask, out = None, []
    for ghz in np.unique(table[:, 2]):
        rows = np.flatnonzero(table[:, 2] == ghz)
        block = table[rows]
        sources = block[:, 0].astype(int)-1
        receivers = block[:, 1].astype(int)-1
        if not (np.array_equal(sources+1, block[:, 0]) and np.array_equal(receivers+1, block[:, 1])):
            raise ValueError('Non-integer source or receiver index.')
        nrx = len(block)//NTX
        if nrx*NTX != len(block):
            raise ValueError('Rows are not a whole number of source blocks.')
        by_source = sources.reshape(NTX, nrx)   # MATLAB reshape(.., NRX, NTX) = contiguous blocks
        if not (by_source == by_source[:, :1]).all() or len(set(by_source[:, 0])) != NTX:
            raise ValueError('Each source must own one contiguous block of rows.')
        key = sources*RING+receivers
        if len(set(key)) != len(key):
            raise ValueError('Repeated source/receiver pair.')
        frequency_mask = np.zeros((NTX, RING), bool)
        frequency_mask[sources, receivers] = True
        if mask is None:
            mask = frequency_mask
        elif not np.array_equal(mask, frequency_mask):
            raise ValueError('The measured pairs change with frequency.')
        total = (block[:, 3]+1j*block[:, 4]).conj()
        incident = (block[:, 5]+1j*block[:, 6]).conj()
        k_m = 2*np.pi*ghz*1e9/C0
        calind = nrx//2                          # MATLAB floor(NRX/2)+1, 0-based
        calibration_rows = np.arange(NTX)*nrx+calind
        cal_source, cal_receiver = sources[calibration_rows], receivers[calibration_rows]
        factors = np.empty(NTX, complex)
        factors[cal_source] = incident[calibration_rows]/unit_field(
            k_m, np.linalg.norm(rx[cal_receiver]-tx[cal_source], axis=1))
        permutation = np.argsort(key, kind='stable')
        if not np.array_equal(key[permutation], np.flatnonzero(frequency_mask.ravel())):
            raise ValueError('C-order permutation does not match the mask.')
        data = ((total-incident)/factors[sources])[permutation]
        out.append(CsiFrequency(float(ghz)*1e9, k_m, rows, sources, receivers, permutation,
                                calibration_rows, factors, total, incident, data))
    return mask, out, hashlib.sha256(raw).hexdigest()


def acquisition(mask):
    return PointSourceAcquisition(source_positions_m()/LENGTH_M, receiver_positions_m()/LENGTH_M,
                                  paired=False, mask=mask)


def _row_pattern(rows):
    step = np.unique(np.diff(rows))
    if len(step) == 1:
        return dict(start=int(rows[0]), stop=int(rows[-1]), step=int(step[0]), count=int(len(rows)))
    return dict(rows=rows.tolist())


def observations(path, frequencies_ghz=None):
    """Real-only observations for the fit, ascending frequency, no noise declared.

    ``frequencies_ghz`` selects rows of the retained file (dataset-level setting of the
    wrapper); the file itself is never rewritten. The record lists the rows used.
    """
    mask, frequencies, digest = read_table(path)
    if frequencies_ghz is not None:
        wanted = {float(f)*1e9 for f in frequencies_ghz}
        frequencies = [f for f in frequencies if f.frequency_hz in wanted]
        if {f.frequency_hz for f in frequencies} != wanted:
            raise ValueError(f'Frequencies {sorted(frequencies_ghz)} GHz are not all in {path}.')
    shared = acquisition(mask)
    real = tuple(Observation(f.k_m*LENGTH_M, shared, f.data, f.frequency_hz) for f in frequencies)
    rows = np.concatenate([f.file_rows for f in frequencies])
    used = dict(frequencies_ghz=[f.frequency_hz/1e9 for f in frequencies], row_count=int(len(rows)),
                rows_0based=[_row_pattern(f.file_rows) for f in frequencies],
                rows_sha256=hashlib.sha256(rows.astype(np.int64).tobytes()).hexdigest())
    return real, frequencies, dict(path=str(path), sha256=digest, rows_used=used)


def to_file_order(entry, values_c_order):
    """Inverse of the C-order permutation: values back in the file's row order."""
    values = np.empty_like(values_c_order)
    values[entry.permutation] = values_c_order
    return values
