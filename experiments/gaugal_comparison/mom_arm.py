"""FW-001 MoM arm: the pulse-basis volume solver of 2D-MOM-ESI on TG-002 cases.

mom_esi works in free space with E-field units and keeps EISP's constants
(eta0 = 120 pi, eps0 = 8.85e-12, c = 3e8), whose product is 1.000885 rather
than 1. Here the frequency is chosen so its wavenumber equals the TG-002
background wavenumber, the input susceptibility is divided by that product,
and the scattered E field is divided by i k eta0 to give the benchmark's
i H0 / 4 convention. The solver itself is unchanged.
"""
from time import perf_counter

import numpy as np

from mom_esi import solver as mom

from . import tg002_data as D

CONSTANT_PRODUCT = mom.ETA_0*mom.EPSILON_0*mom.C_0


def solve(case, cells, frequency_index, fraction=None):
    """Paired scattered field (24,) at one frequency on a cells x cells grid."""
    x, y = D.pixel_grid(cells)
    if fraction is None:
        fraction = D.fill_fraction(case.boundary, x, y)
    epsilon = 1.+case.susceptibility/CONSTANT_PRODUCT*fraction
    k = case.wavenumbers[frequency_index]
    result = mom.simulate(epsilon, frequency_ghz=k*mom.C_0/(2*np.pi)/1e9, x_grid=x, y_grid=y,
                          tx_xy=case.sources, rx_xy=case.receivers)
    paired = np.diagonal(result.E_scattered)          # rows are receivers, columns sources
    return case.strength*paired/(1j*k*mom.ETA_0)


def run_case(case, cells_list, frequencies=None):
    frequencies = range(len(case.frequencies_hz)) if frequencies is None else frequencies
    rows = []
    for cells in cells_list:
        x, y = D.pixel_grid(cells)
        fraction = D.fill_fraction(case.boundary, x, y)
        for i in frequencies:
            start = perf_counter()
            predicted = solve(case, cells, i, fraction)
            seconds = perf_counter()-start
            rows.append(dict(cells=cells, cell_mm=1e3*2*D.BOX_HALF_WIDTH_M/(cells-1),
                             active_cells=int(np.count_nonzero(fraction)), frequency_hz=case.frequencies_hz[i],
                             relative_error=float(D.relative_error(predicted, case.observed[i])),
                             seconds=seconds))
    return rows
