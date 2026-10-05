"""Read-only GGB-003 postprocessing: report, direct boundaries, saved-state video.

No inverse or forward calls. The MP4 encoder is the same ``encode`` function
used by GGB-002/F4/video/render.py. Run after either arm (including failed
runs) with ``python -m experiments.benchmark.ggb003_report``.
"""
import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import textwrap

import numpy as np

from bem_inverse.continuation.geometry import FourierCurve

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT/'results/validation/cleaned_interfaces/GGB-003'
DEFAULT_INPUT = ROOT/'results/validation/cleaned_interfaces/GGB-002/inputs.npz'
NAMES = {'B': 'Normal-only control', 'T': 'M3 translation + shape'}
COLORS = {'B': '#2a78d6', 'T': '#d85828'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_svg(path):
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


def finite(value):
    return isinstance(value, (int, float, np.number)) and np.isfinite(value)


def number(value, specification='.4g', scale=1.):
    return format(float(value)*scale, specification) if finite(value) else 'unavailable'


def boolean(value):
    return 'yes' if value is True else 'no' if value is False else 'unavailable'


def coefficients(row):
    raw = row.get('coefficients')
    if not isinstance(raw, dict) or not {'real', 'imag'} <= raw.keys():
        return None
    return FourierCurve(np.asarray(raw['real'])+1j*np.asarray(raw['imag'])).coefficients


def json_lines(path, warnings):
    lines = path.read_text().splitlines()
    rows = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines)-1:
                raise
            warnings.append(f'Ignored incomplete final line in {path.name}.')
    return rows


@dataclass
class Track:
    arm: str
    result: dict
    states: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stream_used: bool = False
    metrics_match_endpoint: bool = True

    def add(self, row, origin):
        c = coefficients(row)
        if c is None:
            return
        if self.states and np.array_equal(self.states[-1]['coefficients'], c):
            # Stage/block starts repeat the current accepted curve. Retain any
            # richer recorded scalar fields without inventing another update.
            for key in ('loss', 'relative_l2'):
                if not finite(self.states[-1].get(key)) and finite(row.get(key)):
                    self.states[-1][key] = row[key]
            return
        item = {k: row.get(k) for k in ('iteration', 'block', 'cycle', 'loss', 'relative_l2', 'work')}
        item.update(coefficients=c, stage_label=row.get('stage_label', row.get('stage', 'unknown stage')),
                    origin=origin, z=FourierCurve(c).values(4096))
        self.states.append(item)

    @property
    def stages(self):
        return self.result.get('stages') or []

    @property
    def outcome(self):
        if self.stages:
            last = self.stages[-1]
            return str(last.get('outcome', 'unavailable'))+'/'+str(last.get('stop_reason') or last.get('detail') or 'unspecified')
        return 'No completed stage receipt; '+str(self.result.get('status', 'unavailable'))

    @property
    def qualified(self):
        if not self.metrics_match_endpoint:
            return None
        required = [self.result.get('noise_discrepancy_met'), self.result.get('field_gates_passed'),
                    self.result.get('all_frequency_noise_targets_met')]
        active = [r for r in self.result.get('audit', []) if r.get('active_in_fit')]
        if required[2] is None and active:
            required[2] = all(r.get('noise_target_met') is True for r in active)
        return all(v is True for v in required) if all(v is not None for v in required) else None


def load_track(output, arm):
    folder = output/arm
    path = folder/'result.json'
    if not path.exists():
        return None
    row = json.loads(path.read_text())
    if row.get('arm') != arm or row.get('experiment_id') != 'GGB-003':
        raise ValueError(f'Unexpected experiment receipt: {path}')
    track = Track(arm, row, sources=[path])
    stream = folder/'accepted.jsonl'
    if stream.exists():
        track.sources.append(stream)
        accepted = json_lines(stream, track.warnings)
        for item in accepted:
            track.add(item, 'accepted.jsonl')
        track.stream_used = bool(track.states)
    if not track.states:
        for stage in row.get('stages', []):
            for item in stage.get('history', []):
                track.add(dict(item, stage_label=stage.get('stage_label')), 'stage history')
        if not track.states and (folder/'blocks.jsonl').exists():
            track.sources.append(folder/'blocks.jsonl')
            for block in json_lines(folder/'blocks.jsonl', track.warnings):
                for item in block.get('history', []):
                    track.add(dict(item, stage_label=block.get('stage_label'), block=block.get('block')),
                              'block history')
    saved = {}
    for name in ('curve.npz', 'endpoint.npz'):
        path = folder/name
        if path.exists():
            track.sources.append(path)
            with np.load(path) as archive:
                saved[name] = FourierCurve(archive['coefficients']).coefficients
    endpoint = saved.get('endpoint.npz', saved.get('curve.npz'))
    if endpoint is not None:
        if 'curve.npz' in saved and not np.array_equal(endpoint, saved['curve.npz']):
            if row.get('status') == 'COMPLETE':
                raise ValueError(f'{arm}: completed endpoint and curve archives disagree')
            track.warnings.append('Curve and endpoint archives disagree; retained latest accepted callback when available.')
            track.metrics_match_endpoint = False
        if not track.states or not np.array_equal(track.states[-1]['coefficients'], endpoint):
            if track.stream_used:
                if row.get('status') == 'COMPLETE':
                    raise ValueError(f'{arm}: completed endpoint differs from latest accepted callback')
                track.warnings.append('Latest accepted callback differs from saved endpoint; showing latest accepted callback.')
                track.metrics_match_endpoint = False
            else:
                track.add(dict(coefficients=dict(real=endpoint.real.tolist(), imag=endpoint.imag.tolist()),
                               stage_label='saved endpoint'), 'saved endpoint; acceptance history incomplete')
                track.warnings.append('Added saved endpoint absent from history; its acceptance metadata is unavailable.')
    return track


def target_edges(data):
    """Draw exposed supplied target-cell edges, as in the GGB-002 renderer."""
    x, y = data['x'], data['y']
    xs, ys = np.unique(x), np.unique(y)
    xe = np.r_[xs[0]-(xs[1]-xs[0])/2, (xs[:-1]+xs[1:])/2, xs[-1]+(xs[-1]-xs[-2])/2]
    ye = np.r_[ys[0]-(ys[1]-ys[0])/2, (ys[:-1]+ys[1:])/2, ys[-1]+(ys[-1]-ys[-2])/2]
    mask = np.zeros((len(ys), len(xs)), bool)
    mask[np.searchsorted(ys,y), np.searchsorted(xs,x)] = data['truth'] > 1+1e-5
    edges = []
    for j,i in np.argwhere(mask):
        if i == 0 or not mask[j,i-1]:
            edges.append(((xe[i],ye[j]),(xe[i],ye[j+1])))
        if i == len(xs)-1 or not mask[j,i+1]:
            edges.append(((xe[i+1],ye[j]),(xe[i+1],ye[j+1])))
        if j == 0 or not mask[j-1,i]:
            edges.append(((xe[i],ye[j]),(xe[i+1],ye[j])))
        if j == len(ys)-1 or not mask[j+1,i]:
            edges.append(((xe[i],ye[j+1]),(xe[i+1],ye[j+1])))
    return np.asarray(edges, dtype=float)


def boundary_metrics(track, data):
    if not track.states:
        return {}
    curve = FourierCurve(track.states[-1]['coefficients'])
    z, dz = curve.values(8192), curve.values(8192, 1)
    dt = 2*np.pi/len(z)
    area = .5*dt*np.sum(z.real*dz.imag-z.imag*dz.real)
    if not finite(area) or area <= 0:
        return {}
    centre = .5*dt*(np.sum(z.real**2*dz.imag)-1j*np.sum(z.imag**2*dz.real))/area
    active = data['truth'] > 1+1e-5
    target = np.mean(data['x'][active])+1j*np.mean(data['y'][active])
    cell = np.diff(np.unique(data['x'])).mean()*np.diff(np.unique(data['y'])).mean()
    return dict(centre_error_m=float(abs(centre-target)), radius_m=float(np.sqrt(area/np.pi)),
                target_radius_m=float(np.sqrt(active.sum()*cell/np.pi)))


def limits(tracks, edges):
    everything = [edges[...,0].ravel()+1j*edges[...,1].ravel()]
    everything += [s['z'] for t in tracks if t for s in t.states]
    z = np.concatenate(everything)
    centre = complex((z.real.min()+z.real.max())/2, (z.imag.min()+z.imag.max())/2)
    half = max(.1, .58*max(np.ptp(z.real),np.ptp(z.imag)))
    return (centre.real-half,centre.real+half),(centre.imag-half,centre.imag+half)


def setup_axis(axis, edges, bounds):
    from matplotlib.collections import LineCollection
    axis.add_collection(LineCollection(edges, colors='#45515e', linewidths=1.5))
    axis.set(xlim=bounds[0],ylim=bounds[1],aspect='equal',xlabel='x (m)',ylabel='y (m)')
    axis.grid(alpha=.15)
    axis.tick_params(labelsize=9,colors='#52514e')
    for spine in axis.spines.values():
        spine.set_color('#d3d5d6')


def close_line(z):
    return np.r_[z.real,z.real[0]],np.r_[z.imag,z.imag[0]]


def comparison(output, tracks, edges, bounds):
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig, axes = plt.subplots(1,2,figsize=(13,7.7),dpi=100,facecolor='#fcfcfb')
    fig.subplots_adjust(left=.06,right=.97,bottom=.22,top=.76,wspace=.20)
    fig.suptitle('Case 8 | Stage-one translation test',fontsize=20,y=.955,weight='bold')
    fig.text(.5,.897,'Four frequencies: 0.50, 0.75, 1.00, 1.25 GHz',ha='center',fontsize=11,color='#52514e')
    for axis,arm,track in zip(axes,('B','T'),tracks):
        setup_axis(axis,edges,bounds)
        axis.set_facecolor('#fcfcfb')
        axis.set_title(f'{arm} | {NAMES[arm]}',fontsize=13,pad=13)
        if track is None or not track.states:
            axis.text(.5,.5,'Not run' if track is None else 'No saved boundary',transform=axis.transAxes,ha='center')
            continue
        axis.plot(*close_line(track.states[0]['z']),color='#b7bec5',lw=1.1,ls='--')
        axis.plot(*close_line(track.states[-1]['z']),color=COLORS[arm],lw=2.4)
        state = f"Receipt: {track.result.get('status','unavailable')} | Qualified endpoint: {boolean(track.qualified)}"
        axis.text(.5,-.16,state+'\n'+textwrap.fill(track.outcome,64),transform=axis.transAxes,
                  ha='center',va='top',fontsize=9,color='#52514e')
    handles = [Line2D([],[],color='#45515e',lw=1.5,label='Target cell boundary'),
               Line2D([],[],color='#b7bec5',ls='--',label='First saved state')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.86),ncol=2,frameon=False,fontsize=10)
    fig.text(.5,.03,'Direct Fourier outlines. Target used only for display and post-fit scoring.',ha='center',fontsize=9,color='#52514e')
    artifacts = []
    for suffix in ('svg','png'):
        path = output/f'boundary_comparison.{suffix}'
        fig.savefig(path,facecolor=fig.get_facecolor())
        if suffix == 'svg':
            clean_svg(path)
        artifacts.append(path)
    plt.close(fig)
    return artifacts


def render_video(output, track, edges, bounds, frames_per_state):
    import matplotlib.pyplot as plt
    from experiments.shape_continuation import render_videos as video
    arm, states = track.arm, track.states
    last = len(states)-1
    frames = [(0,False)]*(2*video.FPS)
    for i in range(1,len(states)):
        frames.extend([(i,False)]*frames_per_state)
    frames.extend([(last,True)]*(5*video.FPS))
    fig = plt.figure(figsize=(12.8,8),dpi=100,facecolor=video.SURFACE)
    fig.text(.065,.945,f'Case 8 | {arm}: {NAMES[arm]}',fontsize=20,weight='bold',color=video.INK)
    fig.text(.065,.895,'0.50, 0.75, 1.00, 1.25 GHz fitted together | GGB-003',fontsize=11.5,color=video.MUTED)
    axis = fig.add_axes([.065,.22,.50,.61],facecolor=video.SURFACE)
    setup_axis(axis,edges,bounds)
    axis.plot(*close_line(states[0]['z']),color='#b7bec5',lw=1.1,ls='--')
    boundary, = axis.plot([],[],color=COLORS[arm],lw=2.6)
    progress = fig.text(.64,.795,'',fontsize=16,weight='bold')
    detail = fig.text(.64,.733,'',fontsize=10.5,color=video.MUTED)
    loss_axis = fig.add_axes([.65,.40,.30,.245],facecolor=video.SURFACE)
    residual = np.array([float(s['relative_l2'])*100 if finite(s.get('relative_l2')) else np.nan for s in states])
    loss_axis.plot(np.arange(len(states)),residual,color='#dde0e3',lw=1.2)
    path, = loss_axis.plot([],[],color=COLORS[arm],lw=2)
    marker, = loss_axis.plot([],[],'o',color=COLORS[arm],ms=5)
    top = max(1.,float(np.nanmax(residual))*1.1) if np.isfinite(residual).any() else 100.
    loss_axis.set(xlim=(-.3,max(1,last)+.3),ylim=(0,top),xlabel='Saved state',ylabel='Saved data residual (%)')
    loss_axis.tick_params(labelsize=8,colors=video.MUTED)
    loss_axis.grid(alpha=.15)
    readout = fig.text(.64,.29,'',fontsize=11)
    ending = fig.text(.64,.20,'',fontsize=10,color='#a92d24',va='top')
    fig.text(.065,.098,'Direct Fourier outlines | All saved states shown | No interpolated shapes',fontsize=10,color=video.MUTED)
    fig.text(.065,.061,f"Fit time: {number(track.result.get('fit_seconds'),'.3f')} s. Playback is not solve time. Target is display-only.",fontsize=10,color=video.MUTED)

    def draw(frame):
        index,stopped = frame
        state = states[index]
        boundary.set_data(*close_line(state['z']))
        progress.set_text(f'Saved state {index} / {last}')
        label = str(state['stage_label'])
        if state.get('block'):
            label += ' | '+str(state['block'])
        detail.set_text(textwrap.fill(label,42))
        path.set_data(np.arange(index+1),residual[:index+1])
        marker.set_data([index],[residual[index]])
        readout.set_text(f"Saved residual: {number(state.get('relative_l2'),'.2f',100)}%\nSaved loss: {number(state.get('loss'),'.5g')}")
        ending.set_text(('Receipt '+str(track.result.get('status','unavailable'))+'; qualified endpoint: '+boolean(track.qualified)+'\n'+
                         textwrap.fill(track.outcome,43)) if stopped else '')

    destination = output/arm/'video'
    destination.mkdir(exist_ok=True)
    mp4 = destination/'case8_stage1_translation_boundary.mp4'
    try:
        encoded = video.encode(fig,mp4,frames,draw)
        draw((last,True))
        fig.savefig(destination/'final.svg',facecolor=video.SURFACE)
        clean_svg(destination/'final.svg')
        fig.savefig(destination/'final.png',facecolor=video.SURFACE)
    finally:
        plt.close(fig)
    return dict(path=str(mp4.relative_to(output)),encoding=encoded,
                renderer='experiments.shape_continuation.render_videos.encode',
                states=len(states),shown_state_indices=sorted({i for i,_ in frames}))


def markdown(tracks, data, videos):
    lines = ['# GGB-003 — Exact translation during stage one', '',
        'Case 8; unchanged GGB-002 four-frequency observations and centred start. '
        'T alternates exact translation and M3 shape updates; B uses the original shape update. '
        'M7/M11 retain ordinary shape updates.', '',
        '`COMPLETE` means the driver finished its reporting/audit path. It does not imply convergence or recovery. '
        'A qualified endpoint below requires every fitted-frequency noise target, the joint discrepancy target, and field-refinement gates.', '',
        '| Arm | Receipt | Fit s | Final optimizer outcome | Qualified endpoint | Centre error mm | Radius mm |',
        '|---|---|---:|---|---|---:|---:|']
    for arm,track in zip(('B','T'),tracks):
        if track is None:
            lines.append(f'| {arm} | NOT RUN | unavailable | unavailable | unavailable | unavailable | unavailable |')
            continue
        metric = boundary_metrics(track,data)
        lines.append(f"| {arm} | {track.result.get('status','unavailable')} | {number(track.result.get('fit_seconds'),'.3f')} | "
            f"{track.outcome.replace('|','/')} | {boolean(track.qualified)} | {number(metric.get('centre_error_m'),'.2f',1000)} | "
            f"{number(metric.get('radius_m'),'.2f',1000)} |")
    lines += ['', 'Centre and radius diagnostics are recomputed from the displayed endpoint; truth is used only after fitting.', '',
              '| Arm | Joint loss | Work units | Saved distinct states | SSIM | RRMSE | Contrast SNR dB |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for track in filter(None,tracks):
        row = track.result if track.metrics_match_endpoint else {}
        image = row.get('image_metrics') or {}
        lines.append(f"| {track.arm} | {number(row.get('refined_joint_loss'),'.6g')} | "
            f"{number((track.result.get('ledger') or {}).get('work_units'),'.0f')} | {len(track.states)} | "
            f"{number(image.get('ssim'),'.5f')} | {number(image.get('rrmse'),'.5f')} | {number(image.get('snr_db'),'.2f')} |")
    lines += ['', '| Arm | GHz | Fitted | Residual % | Noise target % | Field refinement |',
              '|---|---:|---|---:|---:|---:|']
    for track in filter(None,tracks):
        audit = track.result.get('audit') if track.metrics_match_endpoint else None
        if not audit:
            lines.append(f'| {track.arm} | unavailable | unavailable | unavailable | unavailable | unavailable |')
        for row in audit or []:
            lines.append(f"| {track.arm} | {number(row.get('frequency_hz'),'.2f',1e-9)} | {boolean(row.get('active_in_fit'))} | "
                f"{number(row.get('relative_residual'),'.3f',100)} | {number(row.get('noise_target_relative'),'.3f',100)} | "
                f"{number(row.get('field_refinement_relative_error'),'.3g')} |")
    lines += ['', '![Direct Fourier endpoint comparison](boundary_comparison.png)', '',
              '[Vector boundary comparison](boundary_comparison.svg).']
    for record in videos:
        lines.append(f"[Arm {record['arm']} trajectory]({record['path']}).")
    lines += ['', 'Video states are recorded curves, with no interpolation or material-image rasterization. '
              'Accepted callbacks take precedence when terminal linearization failed before history recording. '
              'Missing metrics remain unavailable. Single-run wall times do not establish a general speedup.']
    for track in filter(None,tracks):
        for warning in track.warnings:
            lines.append(f'\n- {track.arm}: {warning}')
        if track.result.get('traceback'):
            last = track.result['traceback'].strip().splitlines()[-1]
            lines.append(f'\n- {track.arm} exception: `{last.replace("`", "")}`.')
    return '\n'.join(lines)+'\n'


def report(output=DEFAULT_OUTPUT, input_path=DEFAULT_INPUT, *, videos=True, frames_per_state=6):
    import matplotlib
    matplotlib.use('Agg')
    output, input_path = Path(output), Path(input_path)
    if frames_per_state < 1:
        raise ValueError('Every saved state must receive at least one video frame.')
    tracks = [load_track(output,arm) for arm in ('B','T')]
    if not any(tracks):
        raise ValueError('No GGB-003 arm receipts exist; no report has been written.')
    with np.load(input_path) as archive:
        data = {k:archive[k] for k in ('x','y','truth')}
    sources = [Path(__file__),input_path,ROOT/'solvers/bem_inverse/continuation/geometry.py']
    sources += [p for track in tracks if track for p in track.sources]
    sources += [ROOT/'experiments/shape_continuation/render_videos.py',
                ROOT/'results/validation/cleaned_interfaces/GGB-002/F4/video/render.py']
    hashes = {str(p.resolve()):digest(p) for p in sources}
    edges = target_edges(data)
    bounds = limits(tracks,edges)
    artifacts = comparison(output,tracks,edges,bounds)
    encoded = []
    if videos:
        for track in filter(None,tracks):
            if track.states:
                encoded.append(dict(arm=track.arm,**render_video(output,track,edges,bounds,frames_per_state)))
    path = output/'report.md'
    path.write_text(markdown(tracks,data,encoded))
    artifacts.append(path)
    if any(digest(p) != value for p,value in hashes.items()):
        raise ValueError('Saved sources changed during postprocessing; rerender from a stable snapshot.')
    manifest = dict(experiment_id='GGB-003',source_hashes=hashes,physics_calls=0,inverse_calls=0,
        drawing='Direct Fourier boundary lines and exposed supplied target-cell edges',
        material_rasterization=False,state_interpolation=False,videos=encoded,
        arms={t.arm:dict(states=len(t.states),accepted_stream_used=t.stream_used,warnings=t.warnings,
                       recorded_status=t.result.get('status'),qualified_endpoint=t.qualified,
                       scalar_metrics_match_displayed_endpoint=t.metrics_match_endpoint,
                       final_coefficients_sha256=hashlib.sha256(t.states[-1]['coefficients'].tobytes()).hexdigest() if t.states else None)
              for t in tracks if t},
        artifact_hashes={str(p.relative_to(output)):digest(p) for p in artifacts})
    (output/'rendering_manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--inputs',type=Path,default=DEFAULT_INPUT)
    parser.add_argument('--no-video',action='store_true')
    parser.add_argument('--frames-per-state',type=int,default=6)
    args = parser.parse_args()
    result = report(args.output,args.inputs,videos=not args.no_video,frames_per_state=args.frames_per_state)
    print(json.dumps(dict(arms=result['arms'],videos=[r['path'] for r in result['videos']]),indent=2))


if __name__ == '__main__':
    main()
