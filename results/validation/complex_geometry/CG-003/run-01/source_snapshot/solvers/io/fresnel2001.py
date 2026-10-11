"""2001 Institut Fresnel TM measurements in the Kress exp(-i omega t) convention.

Belkebir & Saillard, Inverse Problems 17 (2001), 1565--1571, section 6:
columns are source label, receiver label, GHz, Re/Im TOTAL, Re/Im INCIDENT.
Receiver labels are absolute azimuths on a 72-position ring, not 1..49 slots.
Original files have ten header lines; the pinned teaching mirror omits them.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from pathlib import Path

import numpy as np
from scipy.constants import c
from scipy.special import hankel1


@dataclass(frozen=True)
class Fresnel2001Data:
    frequencies_hz: np.ndarray
    total: np.ndarray  # (frequency, transmitter, relative receiver slot)
    incident: np.ndarray
    transmitter_labels: np.ndarray
    receiver_labels: np.ndarray  # (transmitter, relative receiver slot)
    source_points: np.ndarray
    receiver_points: np.ndarray  # all 72 absolute positions
    header: tuple[str, ...]
    source_sha256: str

    @property
    def scattered(self) -> np.ndarray:
        return self.total - self.incident

    def select_receiver_pairs(self, matrix: np.ndarray) -> np.ndarray:
        """Select the 49 observed receivers per source from a (36,72) solve."""
        values = np.asarray(matrix)
        if values.shape != (36, 72):
            raise ValueError("Expected a full (36, 72) source/receiver matrix.")
        return values[np.arange(36)[:, None], self.receiver_labels - 1]


def load_fresnel2001(path: str | Path, *, source_radius_m: float = 0.72,
                     receiver_radius_m: float = 0.76) -> Fresnel2001Data:
    """Read a complete 36 x 49 acquisition; reject missing/duplicate records.

    Frequencies are physical GHz values, with no lookup or index remapping.
    A headerless numeric mirror or an original ten-line header is accepted.
    All measurements are conjugated exactly once during import.
    """
    raw = Path(path).read_bytes()
    lines = raw.decode("utf-8-sig").splitlines()
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None:
        raise ValueError("Empty Fresnel file.")
    try:
        first_row = [float(x.replace("D", "E")) for x in lines[first].split()]
    except ValueError:
        first_row = []
    skip = first if len(first_row) == 7 else 10
    try:
        table = np.loadtxt(StringIO("\n".join(lines[skip:]).replace("D", "E")), ndmin=2)
    except ValueError as exc:
        raise ValueError("Expected seven numeric columns after zero or ten header lines.") from exc
    if table.shape[1] != 7 or not np.isfinite(table).all():
        raise ValueError("Fresnel records require seven finite numeric columns.")
    if not np.equal(table[:, :2], np.rint(table[:, :2])).all():
        raise ValueError("Transmitter and receiver labels must be integers.")
    tx, rx = table[:, 0].astype(int), table[:, 1].astype(int)
    if np.any((tx < 1) | (tx > 36) | (rx < 1) | (rx > 72)):
        raise ValueError("Expected transmitter labels 1..36 and receiver labels 1..72.")
    frequencies, fi = np.unique(table[:, 2], return_inverse=True)
    if np.any(frequencies <= 0):
        raise ValueError("Frequencies in GHz must be positive.")
    # rx-1 and 2(tx-1) are absolute azimuths measured in units of five degrees.
    offset = (rx - 1 - 2 * (tx - 1)) % 72
    if np.any((offset < 12) | (offset > 60)):
        raise ValueError("Receiver labels violate the measured relative 60..300 degree aperture.")
    slot = offset - 12
    shape = (len(frequencies), 36, 49)
    flat = np.ravel_multi_index((fi, tx - 1, slot), shape)
    if len(np.unique(flat)) != len(flat):
        raise ValueError("Duplicate frequency/transmitter/receiver record.")
    if len(flat) != np.prod(shape):
        raise ValueError("Missing data: every frequency requires 36 transmitters x 49 receivers.")
    total = np.empty(shape, complex)
    incident = np.empty(shape, complex)
    total[fi, tx - 1, slot] = table[:, 3] - 1j * table[:, 4]
    incident[fi, tx - 1, slot] = table[:, 5] - 1j * table[:, 6]
    for radius in (source_radius_m, receiver_radius_m):
        if not np.isfinite(radius) or radius <= 0:
            raise ValueError("Antenna radii must be finite and positive.")
    source_angle = np.deg2rad(np.arange(36) * 10)
    receiver_angle = np.deg2rad(np.arange(72) * 5)
    sources = source_radius_m * np.column_stack((np.cos(source_angle), np.sin(source_angle)))
    receivers = receiver_radius_m * np.column_stack((np.cos(receiver_angle), np.sin(receiver_angle)))
    labels = (2 * np.arange(36)[:, None] + np.arange(12, 61)[None, :]) % 72 + 1
    values = (frequencies * 1e9, total, incident, np.arange(1, 37), labels, sources, receivers)
    for array in values:
        array.setflags(write=False)
    return Fresnel2001Data(*values, tuple(lines[:skip]), sha256(raw).hexdigest())


@dataclass(frozen=True)
class LineSourceCalibration:
    source_strengths: np.ndarray  # (frequency, transmitter)
    predicted_incident: np.ndarray
    relative_incident_error: np.ndarray  # per frequency; antenna-model diagnostic


def calibrate_line_sources(data: Fresnel2001Data) -> LineSourceCalibration:
    """Fit one complex source amplitude at the receiver opposite each source.

    s[f,t] = conjugate(E_inc_raw[f,t,front]) / ((i/4) H0^(1)(k distance)).
    The measured scattered field retains its measured units. Do not also
    multiply data by this factor when supplying it as the solver strength.
    """
    paired = data.receiver_points[data.receiver_labels - 1]
    distance = np.linalg.norm(paired - data.source_points[:, None, :], axis=-1)
    greens = 0.25j * hankel1(0, 2 * np.pi * data.frequencies_hz[:, None, None] / c * distance)
    front_slot = 24  # relative angle 180 degrees
    front = data.incident[:, :, front_slot]
    if np.any(abs(front) <= np.finfo(float).tiny):
        raise ValueError("Cannot calibrate a zero measured incident field at the opposite receiver.")
    strengths = front / greens[:, :, front_slot]
    predicted = strengths[:, :, None] * greens
    errors = np.linalg.norm((predicted - data.incident).reshape(len(front), -1), axis=1)
    errors /= np.linalg.norm(data.incident.reshape(len(front), -1), axis=1)
    for array in (strengths, predicted, errors):
        array.setflags(write=False)
    return LineSourceCalibration(strengths, predicted, errors)
