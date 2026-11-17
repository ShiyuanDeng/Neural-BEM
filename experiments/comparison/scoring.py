"""Truth-based scores of one saved fit. Only this module opens truth files.

The rules below are fixed before the 17 November 2026 run. A later change gets a new
``PROTOCOL['version']`` and a dated note in the plan; old fits are rescored,
not refitted.

Reconstructed region
- A curve method's region is the inside of its returned curve.
- An image method's region is where ``sign(peak)*chi >= 0.5*|peak|`` on the shared
  grid. ``peak`` is the value of largest magnitude in the image, so the threshold
  never uses the true contrast. The grid is padded with zeros, marching squares
  (scikit-image, low connectivity) traces every closed level line, and the region
  is the even-odd fill of all of them. Every component is kept, whatever its
  size, and holes stay holes.
- No output, a zero image or no closed level line gives an empty region.

Scores
- ``area_error``: area of the symmetric difference between the reconstructed
  region and the true region, divided by the true area. No shift, rotation or
  scaling is applied. An empty region scores 1.
- ``components`` and ``holes`` count the region's separate pieces and holes.
- ``material_l2``: on the shared grid, the norm of (reconstructed minus true
  signed susceptibility) over the norm of the true susceptibility. The true
  image, and a curve method's image, hold susceptibility times the fraction of
  each cell inside the boundary.
- Boundary distances use every boundary of both regions, holes included.
  Points are placed at most 0.05 mm apart; ``d(a, B)`` is the distance from a
  point to the nearest boundary of the other region. ``boundary_rms_mm`` is
  sqrt of the mean of the two arclength-weighted mean squares,
  ``chamfer_mm`` the mean of the two arclength-weighted means, and
  ``hausdorff_mm`` the larger of the two maxima; ``hausdorff_upper_mm`` adds half
  the largest point spacing. They are undefined (null) for an empty region.
- ``centroid_mm``: distance between the area centroids of the two regions.
- Image scores (RRMSE, PSNR, SSIM, contrast SNR) are GauGal's released functions
  on the shared grid.
- ``residual_over_limit``: the largest ratio of the per-frequency data residual
  to max(0.003, 3 x realized noise); at most 1 means the old residual limit holds.
"""
import numpy as np
from scipy.spatial import cKDTree
from shapely import make_valid
from shapely.geometry import Polygon
from shapely.ops import unary_union
from skimage import measure

from bem_inverse.io import read, curve_from
from experiments.benchmark import campaign as C, scenes as S
from experiments.cleaned_interface import benchmark as ci
from experiments.gaugal_comparison import tg002_data as D

from . import noise as N

PROTOCOL = dict(version=1, grid_cells=201, grid_half_width_m=D.BOX_HALF_WIDTH_M, support_fraction_of_peak=.5,
                sign='sign of the largest-magnitude image value', fill='even-odd over all closed level lines',
                connectivity='scikit-image marching squares, fully_connected=low', minimum_component='none',
                empty_region='area_error 1; boundary and centroid scores null',
                curve_samples=16384, boundary_spacing_m=5e-5, sensitivity_fractions=(.3, .7),
                residual_limit='max(0.003, 3 x realized noise) per frequency')
MM = 1e3


def support_rings(chi, fraction):
    """Closed level lines of an image region, as complex points in metres, and the peak used."""
    chi = np.asarray(chi, float)
    peak = float(chi.reshape(-1)[np.argmax(np.abs(chi))]) if chi.size and np.isfinite(chi).all() else 0.
    if peak == 0:
        return [], peak
    half = D.BOX_HALF_WIDTH_M
    step = 2*half/(chi.shape[0]-1)
    lines = measure.find_contours(np.pad(np.sign(peak)*chi, 1, constant_values=0.), fraction*abs(peak))
    # Padded index (row, col) is cell (row-1, col-1); rows run from the top (+y) down.
    return [(-half+step*(c[:, 1]-1))+1j*(half-step*(c[:, 0]-1)) for c in lines if np.allclose(c[0], c[-1])], peak


def region(rings):
    """Even-odd fill of closed rings as a shapely geometry; the flag reports a repaired ring."""
    out, repaired = Polygon(), False
    for ring in rings:
        if len(ring) < 4:
            continue
        piece = Polygon(np.column_stack((ring.real, ring.imag)))
        if not piece.is_valid:
            piece, repaired = unary_union(polygons(make_valid(piece))), True
        if piece.area > 0:
            out = out.symmetric_difference(piece)
    return out, repaired


def polygons(shape):
    return [g for g in getattr(shape, 'geoms', [shape]) if g.geom_type == 'Polygon' and g.area > 0]


def _dense(shape, spacing):
    """Boundary points at most ``spacing`` apart, their arclength weights and the closed rings."""
    points, weights, rings, widest = [], [], [], 0.
    for polygon in polygons(shape):
        for line in (polygon.exterior, *polygon.interiors):
            ring = np.asarray(line.coords)[:-1]
            edge = np.roll(ring, -1, axis=0)-ring
            pieces = np.maximum(1, np.ceil(np.linalg.norm(edge, axis=1)/spacing)).astype(int)
            start = np.repeat(np.arange(len(ring)), pieces)
            step = (np.arange(pieces.sum())-np.repeat(np.cumsum(pieces)-pieces, pieces))/np.repeat(pieces, pieces)
            dense = ring[start]+step[:, None]*edge[start]
            length = np.linalg.norm(np.roll(dense, -1, axis=0)-dense, axis=1)
            points.append(dense)
            weights.append(.5*(length+np.roll(length, 1)))
            rings.append(dense)
            widest = max(widest, float(length.max()))
    return np.concatenate(points), np.concatenate(weights), rings, widest


def _distance(points, rings, neighbours=8):
    """Distance from each point to the nearest ring: the segments at the nearest few vertices."""
    best = np.full(len(points), np.inf)
    for ring in rings:
        count = len(ring)
        _, index = cKDTree(ring).query(points, k=min(neighbours, count))
        index = np.asarray(index).reshape(len(points), -1)
        for offset in (0, -1):
            a = ring[(index+offset) % count]
            b = ring[(index+offset+1) % count]
            edge = b-a
            t = np.clip(np.einsum('nkd,nkd->nk', points[:, None, :]-a, edge) /
                        np.maximum(np.einsum('nkd,nkd->nk', edge, edge), 1e-300), 0, 1)
            best = np.minimum(best, np.linalg.norm(points[:, None, :]-(a+t[..., None]*edge), axis=2).min(axis=1))
    return best


def boundary_scores(found, truth):
    if found.is_empty:
        return dict(boundary_rms_mm=None, chamfer_mm=None, hausdorff_mm=None, hausdorff_upper_mm=None)
    spacing = PROTOCOL['boundary_spacing_m']
    a, wa, rings_a, widest_a = _dense(found, spacing)
    b, wb, rings_b, widest_b = _dense(truth, spacing)
    ab, ba = _distance(a, rings_b), _distance(b, rings_a)
    mean = lambda d, w, power: float(np.sum(w*d**power)/np.sum(w))
    hausdorff = float(max(ab.max(), ba.max()))
    return dict(boundary_rms_mm=MM*np.sqrt(.5*mean(ab, wa, 2)+.5*mean(ba, wb, 2)),
                chamfer_mm=MM*.5*(mean(ab, wa, 1)+mean(ba, wb, 1)),
                hausdorff_mm=MM*hausdorff, hausdorff_upper_mm=MM*(hausdorff+.5*max(widest_a, widest_b)))


def region_scores(found, truth):
    missing = truth.difference(found).area/truth.area
    excess = found.difference(truth).area/truth.area
    pieces = polygons(found)
    centroid = None if found.is_empty else MM*float(found.centroid.distance(truth.centroid))
    return dict(area_error=float(missing+excess), missing_area=float(missing), excess_area=float(excess),
                true_area_mm2=MM*MM*truth.area, area_mm2=MM*MM*found.area, components=len(pieces),
                holes=sum(len(p.interiors) for p in pieces), centroid_mm=centroid)


def image_scores(chi, chi_true):
    from gaugal.paper2d.metrics import single_tx_metrics, snr_db
    scores = single_tx_metrics(1.+chi, 1.+chi_true)
    scores['contrast_snr_db'] = snr_db(chi, chi_true)
    return scores


def truth_for(case):
    row = C.row(case)
    curve = curve_from(read(ci.ROOT/row['truth']))
    shape, _ = region([S.LENGTH*curve.values(PROTOCOL['curve_samples'])])
    chi = (row['contrast']-1.)*D.fill_fraction(S.LENGTH*curve.values(4096), *D.pixel_grid(PROTOCOL['grid_cells']))
    return row, shape, chi


def residual_limits(run, case, frequencies_hz, root):
    realized = np.zeros(len(ci.FREQUENCIES))
    if run.noise is not None:
        realized = N.load(*run.noise, case, root)['realized_relative']
    used = [ci.FREQUENCIES.index(f) for f in frequencies_hz]
    return np.maximum(.003, 3*realized[used]), realized[used]


def score(run, case, fit, arrays, root):
    """Scores of one fit. ``fit`` is its fit.json record and ``arrays`` its fit.npz content."""
    row, truth, chi_true = truth_for(case)
    grid = PROTOCOL['grid_cells']
    chi = np.asarray(arrays['image'], float) if 'image' in arrays else np.zeros((grid, grid))
    if chi.shape != (grid, grid) or not np.isfinite(chi).all():
        chi = np.zeros((grid, grid))
    out = dict(protocol=PROTOCOL, case=case, run=run.key, contrast_true=row['contrast'])
    sensitivity = None
    if fit.get('representation') == 'curve':
        rings = ([S.LENGTH*curve_from(fit['final_curve']).values(PROTOCOL['curve_samples'])]
                 if fit.get('final_curve') else [])
        estimate = fit.get('contrast')
    else:
        rings, peak = support_rings(chi, PROTOCOL['support_fraction_of_peak'])
        inside = np.sign(peak)*chi >= PROTOCOL['support_fraction_of_peak']*abs(peak) if peak else np.zeros_like(chi, bool)
        estimate = 1.+float(chi[inside].mean()) if inside.any() else None
        out['image_peak'] = peak
        sensitivity = {f'area_error_at_{f:g}': region_scores(region(support_rings(chi, f)[0])[0], truth)['area_error']
                       for f in PROTOCOL['sensitivity_fractions']}
    found, repaired = region(rings)
    out.update(region_scores(found, truth), ring_repaired=repaired, empty_region=bool(found.is_empty))
    out.update(boundary_scores(found, truth))
    norm = float(np.linalg.norm(chi_true))
    out.update(material_l2=float(np.linalg.norm(chi-chi_true))/norm, contrast_estimate=estimate,
               contrast_relative_error=None if estimate is None else estimate/row['contrast']-1.)
    out.update(image_scores(chi, chi_true))
    if sensitivity is not None:
        out['threshold_sensitivity'] = sensitivity
    residual = fit.get('residual')
    if residual is not None and fit.get('frequencies_hz'):
        limits, realized = residual_limits(run, case, fit['frequencies_hz'], root)
        out.update(residual_limits=limits, noise_realized=realized,
                   residual_over_limit=float(np.max(np.asarray(residual)/limits)))
    else:
        out.update(residual_limits=None, noise_realized=None, residual_over_limit=None)
    if fit.get('representation') == 'curve' and fit.get('final_curve'):
        # The TG-002 curve distances, as every earlier BEM result reported them.
        try:
            old = ci.score(row, curve_from(fit['final_curve']))
            out.update(tg002_rms_mm=old['rms_mm'], tg002_hausdorff_upper_mm=old['hausdorff_upper_mm'])
        except Exception as error:
            out.update(tg002_rms_mm=None, tg002_hausdorff_upper_mm=None, tg002_failure=repr(error))
    return out
