"""Tabulate ``compare_clean_default_contrasts``: supplied contrast at 13.3 and the longer warm-up stage.

Writes ``comparison.csv`` beside the fits of ``default_known`` and ``default_known_warmup_long``.
Radius is the equal-area radius of an outline; centre error is the distance between centroids
(Fourier harmonic 0) of the fitted outline and the truth. Truth is read here, after the fits.
"""
import numpy as np

from bem_inverse.io import curve_from, read
from experiments.benchmark import campaign, scenes
from experiments.comparison.compare_clean_schedules import OUT, write_rows

SHAPES = ('circle', 'kite', 'peanut', 'star', 'asymmetric', 'c_shape', 'hook', 'cross', 'cog', 'aphex_twin')


def disk(record):
    """Equal-area radius and centroid coefficient, both in mm."""
    curve = curve_from(record)
    z = curve.values(4096)
    area = .5*abs(np.sum(z.real*np.roll(z.imag, -1)-np.roll(z.real, -1)*z.imag))
    centre = np.asarray(curve.coefficients)[np.asarray(curve.modes) == 0][0]
    return 1e3*scenes.LENGTH*np.sqrt(area/np.pi), 1e3*scenes.LENGTH*centre


def first_stage(stage, truth_radius, truth_centre, prefix):
    radius, centre = disk(stage['curve'])
    return {prefix+'steps': stage['accepted_steps'], prefix+'stop': stage['stop'],
            prefix+'entry_loss': stage['initial_loss'], prefix+'exit_loss': stage['final_loss'],
            prefix+'radius_mm': radius, prefix+'centre_error_mm': abs(centre-truth_centre),
            prefix+'area_error_pct': 100*stage['area_error'], 'true_equal_area_radius_mm': truth_radius}


def main():
    known, longer = [], []
    for shape in SHAPES:
        case = f'{shape}__c13.3'
        truth_radius, truth_centre = disk(read(campaign.ROOT / campaign.row(case)['truth']))
        fit = read(OUT / 'default_known' / f'{case}.json')
        known.append(dict(case=case, recovered_contrast_error_pct=100*fit['reference_area_error'],
                          supplied_contrast_error_pct=100*fit['area_error'],
                          recovered_pass=fit['reference_area_error'] <= .05, supplied_pass=fit['area_error'] <= .05,
                          recovered_outcome=fit['reference_outcome'], supplied_outcome=fit['outcome'],
                          stages=len(fit['stages']), work_units=fit['work_units'], fit_seconds=fit['seconds'],
                          **first_stage(fit['stages'][0], truth_radius, truth_centre, 'warmup_')))
        path = OUT / 'default_known_warmup_long' / f'{case}.json'
        if path.exists():
            stage = read(path)['stages'][0]
            longer.append({'case': case, **first_stage(fit['stages'][0], truth_radius, truth_centre, 'cap44_'),
                           **first_stage(stage, truth_radius, truth_centre, 'cap440_'),
                           'work_units': stage['work_units'], 'stage_quota': stage['stage_quota']})
    write_rows(OUT / 'default_known' / 'comparison.csv', known)
    write_rows(OUT / 'default_known_warmup_long' / 'comparison.csv', longer)
    print(sum(r['supplied_pass'] for r in known), 'of', len(known), 'recovered with the contrast supplied;',
          sum(r['recovered_pass'] for r in known), 'with recovered contrast')
    for r in known:
        print(f"{r['case']:20s} {r['recovered_contrast_error_pct']:8.2f} {r['supplied_contrast_error_pct']:8.2f} "
              f"{r['supplied_outcome']:19s} warm-up: {r['warmup_steps']:3d} steps {r['warmup_stop']:20s} loss "
              f"{r['warmup_entry_loss']:.3f}->{r['warmup_exit_loss']:.5f} radius {r['warmup_radius_mm']:5.1f} "
              f"(truth {r['true_equal_area_radius_mm']:5.1f}) centre error {r['warmup_centre_error_mm']:6.1f} mm")
    for r in longer:
        print(f"{r['case']:20s} cap 44: {r['cap44_steps']:3d} steps loss {r['cap44_exit_loss']:.5f} | cap 440: "
              f"{r['cap440_steps']:3d} steps {r['cap440_stop']:20s} loss {r['cap440_exit_loss']:.5f} "
              f"radius {r['cap440_radius_mm']:5.1f} centre error {r['cap440_centre_error_mm']:6.1f} mm")


if __name__ == '__main__':
    main()
