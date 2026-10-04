"""TG-001: five new single-object targets for the cleaned SC/MA inverse.

The targets add features that the 36-case regression set does not cover: the
Aphex Twin logo glyph (non-star, two thin strokes, a deep re-entrant notch),
an eight-tooth cog (high angular harmonics), a rounded plus sign (four
re-entrant corners), a heart (inward cusp and a tip), and a thick S (two
opposite concavities). Each is fitted from an off-centre start circle, like
the SC-050 far panel.

This module only adds cases. It never edits the frozen CI-001 descriptors or
seals: rows produced here are plain dictionaries that the unchanged
``benchmark.fitting_problem``, ``benchmark.run_case`` and ``benchmark.score``
consume. Fitting still receives a ``Problem`` only; truth paths are read by
scoring after the fit and audit return.

Commands (repository root, ``PYTHONPATH=solvers:.``, EMNerf environment)::

    python -m experiments.cleaned_interface.target_gallery prepare
    python -m experiments.cleaned_interface.target_gallery generate
    python -m experiments.cleaned_interface.target_gallery verify
    python -m experiments.cleaned_interface.target_gallery inventory
    python -m experiments.cleaned_interface.target_gallery figure
    python -m experiments.cleaned_interface.target_gallery plan --cases target__c13.3__aphex_twin
    python -m experiments.cleaned_interface.target_gallery run --cases target__c4__cog --run-dir <fresh dir>
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess
import tarfile
from time import perf_counter

import numpy as np

from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.geometry_runtime import geometry_runtime
from .io import read, write, digest, curve_record, curve_from, portable
from .physics import Execution, make_backend
from . import benchmark as b

ROOT = b.ROOT
DEFAULT_OUTPUT = ROOT/'results/validation/cleaned_interfaces/TG-001'
LOGO = Path(__file__).resolve().parent/'assets/aphex_twin_logo.svg'
LOGO_SHA256 = '05f73997e0bd08e6ba18073783c5e9824ba9d2664f699580995a443b9faa66ec'
LOGO_PROVENANCE = dict(
    source='https://en.wikipedia.org/wiki/File:Aphex_Twin_logo.svg', licence='Public domain',
    author='Original logo by Paul Nicholson; vectorized by Iwantmorelife',
    used='first path only (the central glyph); the surrounding ring is a separate annulus and is omitted')
CONTRASTS = (.5, 4., 13.3)
QUALIFICATION_NODES = (1024, 2048)
QUALIFICATION_TOLERANCE = 1e-8
LENGTH, CENTER = .05, .5+.5j   # package length unit and scene centre, in metres

# Outline units are arbitrary; each outline is centred at its area centroid
# and scaled so its maximum radius is `size` package units (5 cm each).
# `band`/`taper`: stored Fourier band and Gaussian taper width exp(-(n/taper)^2),
# which rounds polygon corners without Gibbs ringing. Frozen before any solve.
SCENES = {
    'aphex_twin': dict(size=1.15, band=32, taper=16, center=[.512, .488], rotation=0., start=[.33, .66]),
    'cog': dict(size=1.05, band=32, taper=20, center=[.48, .53], rotation=.17, start=[.68, .66]),
    'cross': dict(size=1.05, band=20, taper=10, center=[.53, .47], rotation=.35, start=[.32, .36]),
    'heart': dict(size=1.10, band=20, taper=12, center=[.49, .51], rotation=0., start=[.66, .33]),
    's_curve': dict(size=1.15, band=20, taper=12, center=[.51, .52], rotation=-.3, start=[.69, .50]),
}
START_RADIUS_M = .065


def logo_outline(path=LOGO):
    """Vertices of the glyph polygon (first SVG path), y up, ring centre at 0."""
    if digest(path) != LOGO_SHA256:
        raise ValueError('Vendored logo asset changed')
    d = re.search(r'<path d="([^"]+)"', Path(path).read_text()).group(1)
    tokens = re.findall(r'[MmLlHhVvZz]|-?\d*\.?\d+(?:e-?\d+)?', d)
    points, command, i, current = [], None, 0, 0j
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        if command in 'Zz':
            break
        if command in 'MLml':
            step = complex(float(tokens[i]), float(tokens[i+1]))
            current = step if command in 'ML' else current+step
            command = {'M': 'L', 'm': 'l'}.get(command, command)  # implicit lineto after moveto
            i += 2
        elif command in 'HhVv':
            value = float(tokens[i])
            current = {'H': complex(value, current.imag), 'V': complex(current.real, value),
                       'h': current+value, 'v': current+1j*value}[command]
            i += 1
        else:
            raise ValueError('Unsupported SVG path command: '+command)
        points.append(current)
    # The path's own transform flips SVG y; raw coordinates are already y up.
    return np.asarray(points) - (3196.54+3196.54j)


def _cog():
    t = 2*np.pi*np.arange(8192)/8192
    return (.94+.12*np.tanh(3*np.cos(8*t))/np.tanh(3))*np.exp(1j*t)


def _cross():
    a = .36
    corners = [(a, -a), (1, -a), (1, a), (a, a), (a, 1), (-a, 1), (-a, a), (-1, a), (-1, -a), (-a, -a), (-a, -1), (a, -1)]
    z = [complex(*p) for p in corners]
    return np.concatenate([np.linspace(p, q, 500, endpoint=False) for p, q in zip(z, z[1:]+z[:1])])


def _heart():
    t = 2*np.pi*np.arange(8192)/8192
    return 16*np.sin(t)**3 + 1j*(13*np.cos(t)-5*np.cos(2*t)-2*np.cos(3*t)-np.cos(4*t))


def _s_curve():
    """Thick S: two tangent arcs of a centreline, offset by a half-width, with round caps."""
    radius, half_width = .5, .21
    upper = .5j+radius*np.exp(1j*np.linspace(.15*np.pi, 1.5*np.pi, 1500))
    lower = -.5j+radius*np.exp(1j*np.linspace(np.pi/2, -.85*np.pi, 1500))
    line = np.r_[upper, lower[1:]]
    tangent = np.gradient(line)
    normal = 1j*tangent/np.abs(tangent)
    half = np.linspace(0, np.pi, 300)
    return np.r_[line+half_width*normal, line[-1]+half_width*normal[-1]*np.exp(-1j*half),
                 (line-half_width*normal)[::-1], line[0]-half_width*normal[0]*np.exp(-1j*half)]


OUTLINES = dict(aphex_twin=logo_outline, cog=_cog, cross=_cross, heart=_heart, s_curve=_s_curve)


def _arclength_samples(polygon, count=8192):
    p = np.asarray(polygon, complex)
    s = np.r_[0, np.cumsum(np.abs(np.diff(np.r_[p, p[0]])))]
    u = np.linspace(0, s[-1], count, endpoint=False)
    return np.interp(u, s, np.r_[p.real, p[0].real])+1j*np.interp(u, s, np.r_[p.imag, p[0].imag])


def _area_centroid(p):
    q = np.roll(p, -1)
    cross = p.real*q.imag-q.real*p.imag
    area = cross.sum()/2
    return area, ((p+q)*cross).sum()/(6*area)


def truth_fixture(scene):
    """Package-unit truth: centred, scaled, tapered, rotated and placed."""
    spec = SCENES[scene]
    z = _arclength_samples(OUTLINES[scene]())
    area, centroid = _area_centroid(z)
    if area < 0:
        z = z[::-1]
    z = z-centroid
    z *= spec['size']/np.abs(z).max()
    n = np.fft.fftfreq(len(z), 1/len(z))
    spectrum = np.fft.fft(z)/len(z)*np.exp(-(n/spec['taper'])**2)
    coefficients = spectrum[np.arange(-spec['band'], spec['band']+1) % len(z)]*np.exp(1j*spec['rotation'])
    coefficients[spec['band']] += (complex(*spec['center'])-CENTER)/LENGTH
    curve = FourierCurve(coefficients)
    curve.validate()
    return curve


def start_fixture(scene):
    return FourierCurve.circle(START_RADIUS_M/LENGTH, (complex(*SCENES[scene]['start'])-CENTER)/LENGTH)


def tag(contrast):
    return 'c'+f'{contrast:g}'


def case_id(contrast, scene):
    return f'target__{tag(contrast)}__{scene}'


def sources():
    paths = {Path(__file__).resolve(), LOGO, ROOT/'experiments/cleaned_interface/benchmark.py'}
    paths |= set(ROOT.glob('solvers/bem_inverse/**/*.py'))
    return sorted(paths)


def prepare(output=DEFAULT_OUTPUT):
    output = Path(output)
    if (output/'manifest.json').exists():
        raise FileExistsError('Preserve the existing TG-001 inputs; use another output directory')
    paths = sources()
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output/'sources.tar.gz', 'w:gz') as archive:
        for p in paths:
            archive.add(p, arcname=b.path_ref(p), recursive=False)
    for scene in SCENES:
        folder = output/'inputs'/scene
        folder.mkdir(parents=True, exist_ok=False)
        start = start_fixture(scene)
        start.validate()
        write(folder/'truth.json', curve_record(truth_fixture(scene)))
        write(folder/'initial.json', curve_record(start))
    write(output/'manifest.json', dict(
        experiment='TG-001', purpose='new target shapes for the cleaned SC/MA inverse; inputs only',
        scenes=SCENES, contrasts=CONTRASTS, start_radius_m=START_RADIUS_M, logo=LOGO_PROVENANCE,
        frequencies_hz=b.FREQUENCIES, damping_ratio=.25, acquisition='CI-001 frozen 24-pair ring',
        qualification=dict(nodes=QUALIFICATION_NODES, max_relative_difference=QUALIFICATION_TOLERANCE),
        noise='none; observed equals the N2048 prediction',
        sources={b.path_ref(p): digest(p) for p in paths}, archive_sha256=digest(output/'sources.tar.gz'),
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        initial_status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
        environment=b.environment(), inputs_sealed=False))
    return dict(prepared=list(SCENES), output=str(output))


def _template(scene, damped):
    # Placeholder values: generation uses only each template's wavenumber and acquisition.
    one = np.ones((24, len(b.FREQUENCIES)))
    return b.observations(dict(observed_real=one, observed_imag=0*one), dict(case=scene), damped=damped)


def _predict(physics, truth, template, contrast):
    columns = []
    for n in QUALIFICATION_NODES:
        with physics.ordered_calls(lambda o: physics.evaluate(truth, o, contrast, n).prediction, template) as calls:
            columns.append(np.column_stack([call() for call in calls]))
    coarse, fine = columns
    relative = np.linalg.norm(coarse-fine, axis=0)/np.linalg.norm(fine, axis=0)
    return fine, relative


def generate(output=DEFAULT_OUTPUT, execution=None):
    """Noiseless real and damped catalogs, each qualified by node doubling."""
    output = Path(output)
    manifest = verify(output)
    execution = execution or Execution(device='cpu', acceleration='reference', frequency_threads=4)
    physics = make_backend('nodal_kress', execution)
    failures = []
    for scene in SCENES:
        truth = curve_from(read(output/'inputs'/scene/'truth.json'))
        for contrast in CONTRASTS:
            folder = output/'inputs'/scene/tag(contrast)
            for damped, name in ((False, 'observations'), (True, 'damped')):
                stem = 'qualification' if not damped else 'damped_qualification'
                if (folder/f'{stem}.json').exists():
                    continue
                folder.mkdir(parents=True, exist_ok=True)
                template = _template(scene, damped)
                started = perf_counter()
                with geometry_runtime(execution.geometry):
                    clean, relative = _predict(physics, truth, template, contrast)
                passed = bool(np.isfinite(relative).all() and max(relative) <= QUALIFICATION_TOLERANCE)
                record = dict(observed_real=clean.real, observed_imag=clean.imag, clean_real=clean.real,
                              clean_imag=clean.imag, frequencies_hz=b.FREQUENCIES,
                              realized_noise_relative=np.zeros(len(b.FREQUENCIES)))
                if damped:
                    record.update(wavenumbers_real=[complex(o.wavenumber).real for o in template],
                                  wavenumbers_imag=[complex(o.wavenumber).imag for o in template], gamma=.25,
                                  sigma_real_imag=np.zeros(len(b.FREQUENCIES)), relative_complex_rms=0.)
                check = dict(passed=passed, contrast=contrast, damped=damped, refinement_relative=relative,
                             nodes=QUALIFICATION_NODES, tolerance=QUALIFICATION_TOLERANCE,
                             seconds=perf_counter()-started, execution=asdict(execution), physics=physics.receipt())
                if passed:
                    write(folder/f'{name}.json', record)
                    check['observations_sha256'] = digest(folder/f'{name}.json')
                    write(folder/f'{stem}.json', check)
                else:
                    write(folder/f'failed_{stem}.json', check)
                    failures.append(dict(scene=scene, contrast=contrast, damped=damped, worst=float(max(relative))))
                print('INPUT', scene, tag(contrast), name, passed, f'{max(relative):.2e}',
                      f'{check["seconds"]:.1f}s', flush=True)
    manifest.update(inputs_sealed=not failures, qualification_failures=failures,
                    inputs={str(p.relative_to(output)): digest(p) for p in sorted((output/'inputs').rglob('*.json'))
                            if not p.name.startswith('failed_')})
    write(output/'manifest.json', manifest)
    return dict(sealed=not failures, failures=failures, cases=len(descriptors(output)))


def verify(output=DEFAULT_OUTPUT, *, require_inputs=False):
    """Enforce the frozen inputs. Source digests are generation provenance only:
    these are reusable cases, so later solver changes may fit them."""
    output = Path(output)
    manifest = read(output/'manifest.json')
    if not manifest.get('inputs_sealed'):
        for path, expected in manifest['sources'].items():
            if digest(ROOT/path) != expected:
                raise RuntimeError('TG-001 source changed before inputs were sealed: '+path)
    if digest(output/'sources.tar.gz') != manifest['archive_sha256']:
        raise RuntimeError('TG-001 source snapshot changed')
    for path, expected in manifest.get('inputs', {}).items():
        if digest(output/path) != expected:
            raise RuntimeError('TG-001 input changed: '+path)
    if require_inputs and not manifest.get('inputs_sealed'):
        raise ValueError('TG-001 inputs are not generated and sealed')
    return manifest


def descriptors(output=DEFAULT_OUTPUT):
    """Rows in the CI-001 descriptor shape for every qualified case."""
    output = Path(output)
    rows = []
    for scene in SCENES:
        for contrast in CONTRASTS:
            folder = output/'inputs'/scene/tag(contrast)
            if not ((folder/'qualification.json').exists() and (folder/'damped_qualification.json').exists()):
                continue
            rows.append(dict(id=case_id(contrast, scene), panel='target', case=scene, contrast=contrast,
                data=b.path_ref(folder/'observations.json'), damped=b.path_ref(folder/'damped.json'),
                qualification=b.path_ref(folder/'qualification.json'),
                damped_qualification=b.path_ref(folder/'damped_qualification.json'),
                initial=b.path_ref(output/'inputs'/scene/'initial.json'),
                truth=b.path_ref(output/'inputs'/scene/'truth.json')))
    return rows


def _row(output, case):
    row = next((r for r in descriptors(output) if r['id'] == case), None)
    if row is None:
        raise ValueError('Unknown or unqualified TG-001 case: '+case)
    return row


def run(output, run_dir, execution, *, cases, solver='nodal_kress', geometry_update=None):
    """Fit selected cases into ``run_dir`` with the unchanged CI-001 policy and scoring.

    One run directory holds one execution setting; the sealed inputs stay untouched.
    """
    output, run_dir = Path(output), Path(run_dir)
    verify(output, require_inputs=True)
    rows = [_row(output, case) for case in cases]
    settings = portable(dict(solver=solver, execution=asdict(execution), geometry_update=geometry_update))
    if not (run_dir/'manifest.json').exists():
        run_dir.mkdir(parents=True, exist_ok=True)
        write(run_dir/'manifest.json', dict(experiment='TG-001 fit', inputs=b.path_ref(output/'manifest.json'),
            inputs_sha256=digest(output/'manifest.json'), settings=settings, environment=b.environment(),
            commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)))
    saved = read(run_dir/'manifest.json')
    if saved['settings'] != settings or saved['inputs_sha256'] != digest(output/'manifest.json'):
        raise ValueError('Do not mix settings or inputs in one run directory; use a new --run-dir')
    results = [b.run_case((run_dir, row, solver, execution, geometry_update)) for row in rows]
    return [dict(id=r['case']['id'], outcome=r.get('outcome'), recovered=r['recovered'], metrics=r.get('metrics'),
                 maximum_residual=r.get('maximum_residual')) for r in results]


def figure(output=DEFAULT_OUTPUT):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output = Path(output)
    ink, muted, spine, surface, accent, track = '#0b0b0b', '#52514e', '#c9c8c2', '#fcfcfb', '#eda100', '#2a78d6'
    fig, axes = plt.subplots(1, len(SCENES), figsize=(3.3*len(SCENES), 3.9), facecolor=surface)
    angles = np.linspace(0, 2*np.pi, 24, endpoint=False)
    for ax, scene in zip(axes, SCENES):
        truth = curve_from(read(output/'inputs'/scene/'truth.json'))
        start = curve_from(read(output/'inputs'/scene/'initial.json'))
        z, s = CENTER+LENGTH*truth.values(2048), CENTER+LENGTH*start.values(512)
        ax.set_facecolor(surface)
        ax.fill(100*z.real, 100*z.imag, color=track, alpha=.22, lw=0)
        ax.plot(100*np.r_[z, z[:1]].real, 100*np.r_[z, z[:1]].imag, color=track, lw=1.6)
        ax.plot(100*np.r_[s, s[:1]].real, 100*np.r_[s, s[:1]].imag, color=muted, lw=1.1, ls='--')
        ax.plot(100*(.5+.30*np.cos(angles)), 100*(.5+.30*np.sin(angles)), 'v', color=accent, ms=3)
        ax.set_xlim(17, 83)
        ax.set_ylim(17, 83)
        ax.set_aspect('equal')
        ax.tick_params(colors=muted, labelsize=7)
        for side in ax.spines.values():
            side.set_color(spine)
        spec = SCENES[scene]
        ax.set_title(scene.replace('_', ' '), color=ink, fontweight='bold', fontsize=11, loc='left', pad=16)
        ax.text(0, 1.01, f'K={spec["band"]}, max radius {50*spec["size"]:.1f} mm', transform=ax.transAxes,
                color=muted, fontsize=7.5, va='bottom')
    axes[0].set_ylabel('y (cm)', color=muted, fontsize=8)
    fig.text(.01, .01, 'TG-001 truths (filled), off-centre start circles (dashed) and the 24 sources (amber). '
             'Truth files only; no new solves.', color=muted, fontsize=7.5)
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(output/'gallery.png', dpi=150, facecolor=surface)
    return str(output/'gallery.png')


def main():
    from .geometry_selection import GEOMETRY_UPDATES, make_update, describe_plan
    from .policy import CumulativePolicy, readable_plan
    parser = argparse.ArgumentParser(description='TG-001 new target shapes')
    parser.add_argument('command', choices=('prepare', 'generate', 'verify', 'inventory', 'figure', 'plan', 'run'))
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--run-dir', type=Path, help='fresh directory for fit results (run only)')
    parser.add_argument('--solver', default='nodal_kress')
    parser.add_argument('--geometry-update', choices=GEOMETRY_UPDATES)
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--acceleration', choices=('reference', 'spd016'), default='spd016')
    parser.add_argument('--frequency-threads', type=int, default=4)
    parser.add_argument('--resolution', type=int, default=512)
    args = parser.parse_args()
    execution = Execution(args.device, args.frequency_threads, args.acceleration, resolution=args.resolution)
    if args.command == 'prepare':
        value = prepare(args.output)
    elif args.command == 'generate':
        value = generate(args.output)  # data generation always uses the CPU reference path
    elif args.command == 'verify':
        manifest = verify(args.output, require_inputs=True)
        value = dict(verified=True, sealed=manifest['inputs_sealed'], cases=len(descriptors(args.output)))
    elif args.command == 'inventory':
        value = [dict(id=r['id'], contrast=r['contrast']) for r in descriptors(args.output)]
    elif args.command == 'figure':
        value = figure(args.output)
    elif args.command == 'plan':
        row = _row(args.output, (args.cases or [case_id(13.3, 'aphex_twin')])[0])
        problem = b.fitting_problem(row, args.output)
        value = CumulativePolicy().plan(problem, make_backend(args.solver, execution))
        value = describe_plan(value, make_update(args.geometry_update, problem.length_unit_m, execution).settings(),
                              override_operations=args.geometry_update is not None)
        print(readable_plan(value))
        return
    else:
        if not args.cases or not args.run_dir:
            parser.error('run needs explicit --cases and --run-dir')
        value = run(args.output, args.run_dir, execution, cases=args.cases, solver=args.solver,
                    geometry_update=args.geometry_update)
    print(json.dumps(portable(value), indent=2))


if __name__ == '__main__':
    main()
