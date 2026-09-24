import numpy as np
from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
for case in ast.CASES:
    truth = ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
    z = truth.values(16384)*sc.LENGTH + sc.CENTER
    c = sc.to_cartesian(truth,'t').center; w = z-(c[0]+1j*c[1])
    a, r = np.angle(w), np.abs(w); o = np.argsort(a)
    if np.any(np.diff(np.unwrap(np.angle(w)))*np.sign(np.mean(np.diff(np.unwrap(np.angle(w)))))<=0):
        print(case, 'not star-shaped about c0'); continue
    g = np.linspace(-np.pi, np.pi, 4096, endpoint=False); rr = np.interp(g, a[o], r[o], period=2*np.pi)
    F = np.abs(np.fft.rfft(rr))/len(g)*2
    print(case, 'radial amplitudes mm by order 0..10:', np.round(1e3*F[:11],3), 'rms above 3: %.3f mm' % (1e3*np.sqrt(np.sum(F[4:]**2)/2)))
