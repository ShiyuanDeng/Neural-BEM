"""GGB-002 scores shared by the BEM and GauGal arms (plan, "Scores, both methods").

- Image scores use GauGal's released functions on one 1 mm grid: SSIM, RRMSE and
  PSNR on absolute relative permittivity (the SingleTX convention) and contrast
  SNR on the susceptibility image.
- The BEM image fills its final curve with its final contrast.
- GauGal's boundary is its image traced at half its peak susceptibility (the
  extreme of either sign); the longest closed trace is kept. Both boundaries
  are then scored with TG-002's own boundary distances.
"""
import numpy as np
from skimage import measure

from bem_inverse.continuation.geometry import FourierCurve
from experiments.benchmark import scenes as S
from experiments.cleaned_interface import benchmark as ci
from gaugal.paper2d.metrics import single_tx_metrics, snr_db

from . import tg002_data as D

TRACE_BAND = 48


def truth_image(case, pixels):
    x, y = D.pixel_grid(pixels)
    return case.susceptibility*D.fill_fraction(case.boundary, x, y)


def bem_image(curve, contrast, pixels):
    x, y = D.pixel_grid(pixels)
    return (contrast-1.)*D.fill_fraction(S.LENGTH*curve.values(4096), x, y)


def image_scores(chi, chi_true):
    scores = single_tx_metrics(1.+chi, 1.+chi_true)
    scores['contrast_snr_db'] = snr_db(chi, chi_true)
    return scores


def trace(chi, pixels):
    """Half-peak boundary of a susceptibility image as a package-unit FourierCurve."""
    x, y = D.pixel_grid(pixels)
    step = float(x[0, 1]-x[0, 0])
    peak = float(chi.reshape(-1)[np.argmax(np.abs(chi))])
    if peak == 0:
        return None, dict(peak=0., traces=0)
    contours = [c for c in measure.find_contours(np.sign(peak)*chi, .5*abs(peak))
                if np.allclose(c[0], c[-1])]
    if not contours:
        return None, dict(peak=peak, traces=0)
    longest = max(contours, key=len)
    z = (x[0, 0]+step*longest[:, 1])+1j*(y[0, 0]-step*longest[:, 0])
    if (z.real*np.roll(z.imag, -1)-np.roll(z.real, -1)*z.imag).sum() < 0:
        z = z[::-1]
    # Resample uniformly in arclength before the Fourier fit.
    s = np.concatenate(([0.], np.cumsum(np.abs(np.diff(z)))))
    t = np.linspace(0., s[-1], 2048, endpoint=False)
    z = np.interp(t, s, z.real)+1j*np.interp(t, s, z.imag)
    curve = FourierCurve.from_samples(z/S.LENGTH, TRACE_BAND)
    inside = D.fill_fraction(S.LENGTH*curve.values(4096), x, y) > .5
    contrast = 1.+float(chi[inside].mean()) if inside.any() else float('nan')
    return curve, dict(peak=peak, traces=len(contours), traced_contrast=contrast)


def boundary_scores(case_id, curve):
    if curve is None:
        return dict(rms_mm=float('nan'), hausdorff_mm=float('nan'), hausdorff_upper_mm=float('nan'))
    from experiments.benchmark import campaign as C
    return ci.score(C.row(case_id, C.INPUTS), curve)
