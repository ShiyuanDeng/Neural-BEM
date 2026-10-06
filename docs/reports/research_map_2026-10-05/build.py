"""Build the research-map slide deck (HTML -> PDF) from template.html.

python docs/reports/research_map_2026-10-05/build.py   (repository root)

Reads saved TG-002 result files only (no solves); writes research_map.html next to
this script and docs/reports/research_map_2026-10-05.pdf via headless Chrome.
"""
import glob
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = ROOT/'results/validation/cleaned_interfaces'
PDF = HERE.parent/'research_map_2026-10-05.pdf'

INK, MUTED, SPINE = '#0b0b0b', '#52514e', '#c9c8c2'
GREEN, BLUE, ORANGE, GREY = '#1baf7a', '#2a78d6', '#eb6834', '#8a8984'
NAVY, SKY = '#123a6b', '#9cc7f2'


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def text(x, y, s, size=12, weight=400, fill=INK, anchor='start', extra=''):
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" {extra}>{esc(s)}</text>')


# ---------------------------------------------------------------- schedule strip
def schedule_svg():
    stages = [('warm-up', '0.25', 1, 'd'), ('prefix', '0.5', 3, 'd'), ('prefix', '≤0.75', 5, 'd'),
              ('prefix', '≤1.0', 7, 'd'), ('prefix', '≤1.25', 9, 'd'), ('return', '≤1.25', 9, 'r'),
              ('release', 'all 19', 11, 'r'), ('release', 'all 19', 15, 'r'), ('release', 'all 19', 19, 'r'),
              ('cleanup', 'crop to 64', None, 'c'), ('fixed', 'all 19', 25, 'r'), ('fixed', 'all 19', 31, 'r'),
              ('fixed', 'all 19', 37, 'r'), ('tail, if seen', 'all 19', None, 't')]
    slot, base, scale, bw = 1168/len(stages), 126, 2.15, 34
    out = [f'<line x1="0" y1="{base}" x2="1168" y2="{base}" stroke="{SPINE}" stroke-width="1"/>']
    for i, (kind, freq, m, cat) in enumerate(stages):
        cx = slot*i + slot/2
        if cat in 'dr':
            h = m*scale
            out.append(f'<rect x="{cx-bw/2:.1f}" y="{base-h:.1f}" width="{bw}" height="{h:.1f}" rx="3" '
                       f'fill="{SKY if cat == "d" else NAVY}"/>')
            out.append(text(cx, base-h-5, f'M{m}', 11.5, 700, anchor='middle'))
        elif cat == 't':
            h = 37*scale + 8
            out.append(f'<rect x="{cx-bw/2:.1f}" y="{base-h:.1f}" width="{bw}" height="{h:.1f}" rx="3" fill="none" '
                       f'stroke="{NAVY}" stroke-width="1.5" stroke-dasharray="4 3"/>')
            out.append(text(cx, base-h-5, 'M43…91', 11.5, 700, anchor='middle'))
        else:
            out.append(text(cx, base-10, '✂', 15, 400, MUTED, 'middle'))
        out.append(text(cx, base+15, freq, 10.5, 400, INK, 'middle'))
        out.append(text(cx, base+28, kind, 10, 400, MUTED, 'middle'))

    def bracket(i0, i1, label, colour):
        x0, x1, y = slot*i0+8, slot*(i1+1)-8, base+40
        return (f'<path d="M{x0:.1f},{y-5} V{y} H{x1:.1f} V{y-5}" fill="none" stroke="{SPINE}" stroke-width="1.2"/>'
                f'<rect x="{(x0+x1)/2-150:.1f}" y="{y+7}" width="10" height="10" rx="2" fill="{colour}"/>'
                + text((x0+x1)/2-135, y+16, label, 11, 400, MUTED))
    out.append(bracket(0, 4, 'damped k(1+0.25i) · K = 2M+2 = 4…20 · K_t 64', SKY))
    out.append(bracket(6, 13, 'real data, all 19 frequencies · K = 192 · K_t 128 · tail = observable frontier', NAVY))
    out.append(text(slot*5+slot/2, base+56, 'real, 4 freq.', 10, 400, MUTED, 'middle'))
    out.append(text(0, 12, 'frequency set (GHz) below each bar; M = normal-update harmonics', 10.5, 400, MUTED))
    return '\n'.join(out)


# ---------------------------------------------------------------- research tree
PILL_W, PILL_H, PILL_TOP = 132, 56, 232
PILL_BOT = PILL_TOP+PILL_H
PILLS = [('Ordered-boundary', 'Kress reference', 'from 1 Sep'),
         ('Explicit Cartesian', 'Fourier boundary', '8–11 Sep'),
         ('Shape–frequency', 'continuation', 'SC · 22–30 Sep'),
         ('Damped frequency', 'ladder', 'MA · 29–30 Sep'),
         ('Cleaned inverse', 'contract', 'CI-001 · 30 Sep'),
         ('Node-free modal +', 'certified update', 'NU · 1–3 Oct'),
         ('TG-002 benchmark', '+ speed options', 'ON · DP · 4–5 Oct')]


def pill_x(i):
    return 66+154*i


def marker(kind, x, y, colour):
    if kind == 'closed':
        return (f'<path d="M{x-6},{y-6} L{x+6},{y+6} M{x-6},{y+6} L{x+6},{y-6}" stroke="{colour}" '
                f'stroke-width="3" stroke-linecap="round"/>')
    if kind == 'paused':
        return (f'<path d="M{x},{y-8} V{y+8} M{x+6},{y-8} V{y+8}" stroke="{colour}" stroke-width="3" '
                f'stroke-linecap="round"/>')
    if kind == 'kept':
        return f'<circle cx="{x+4}" cy="{y}" r="6" fill="{colour}"/>'
    if kind == 'open':
        return f'<circle cx="{x+5}" cy="{y}" r="6" fill="#fcfcfb" stroke="{INK}" stroke-width="1.8"/>'
    return ''


def branch(x0, y0, lane, x_end, colour, end, name, detail, *, anchor='start', merge=None, dashed=False,
           label_ys=None, r=12):
    """A fork from (x0, y0) to a horizontal lane that ends in a marker at x_end, or merges up at x=merge."""
    s = -1 if lane < y0 else 1
    d = f'M{x0},{y0} V{lane-s*r} Q{x0},{lane} {x0+r},{lane}'
    d += f' H{x_end}' if merge is None else f' H{merge-r} Q{merge},{lane} {merge},{lane-r} V{PILL_BOT+9}'
    dash = ' stroke-dasharray="6 4"' if dashed else ''
    out = [f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="3" stroke-linejoin="round"{dash}/>']
    if merge is None:
        out.append(marker(end, x_end, lane, colour))
    else:
        out.append(f'<path d="M{merge-6},{PILL_BOT+11} L{merge},{PILL_BOT+1} L{merge+6},{PILL_BOT+11} Z" '
                   f'fill="{colour}"/>')
    lx = x0+22 if anchor == 'start' else 1160
    ny, dy = label_ys or (lane-9, lane+17)
    out.append(text(lx, ny, name, 13, 700, INK, anchor))
    out.append(text(lx, dy, detail, 11, 400, MUTED, anchor))
    return '\n'.join(out)


def tree_svg():
    out = []
    for i, (a, b, date) in enumerate(PILLS):
        cx = pill_x(i)
        if i < len(PILLS)-1:
            x1, x2 = cx+PILL_W/2, pill_x(i+1)-PILL_W/2
            out.append(f'<line x1="{x1}" y1="260" x2="{x2-6}" y2="260" stroke="{INK}" stroke-width="3"/>'
                       f'<path d="M{x2-8},254 L{x2},260 L{x2-8},266 Z" fill="{INK}"/>')
        out.append(f'<rect x="{cx-PILL_W/2}" y="{PILL_TOP}" width="{PILL_W}" height="{PILL_H}" rx="10" '
                   f'fill="#ffffff" stroke="{INK}" stroke-width="2"/>'
                   f'<rect x="{cx-PILL_W/2+10}" y="{PILL_TOP}" width="{PILL_W-20}" height="3" fill="{GREEN}"/>')
        out.append(text(cx, PILL_TOP+20, a, 12.5, 700, INK, 'middle'))
        out.append(text(cx, PILL_TOP+35, b, 12.5, 700, INK, 'middle'))
        out.append(text(cx, PILL_TOP+50, date, 10.5, 400, MUTED, 'middle'))
    x_end = pill_x(6)+PILL_W/2
    out.append(f'<line x1="{x_end}" y1="260" x2="1066" y2="260" stroke="{INK}" stroke-width="3"/>'
               f'<path d="M1066,254 L1074,260 L1066,266 Z" fill="{INK}"/>'
               f'<rect x="1076" y="234" width="92" height="52" rx="10" fill="{INK}"/>'
               + text(1122, 260, '26/30', 21, 700, '#ffffff', 'middle')
               + text(1122, 277, 'TG-002', 10.5, 400, '#d9d8d2', 'middle'))
    # above the main line
    out.append(branch(40, PILL_TOP, 40, 420, GREY, 'paused', 'Neural SDF inverse (implicit MLP)',
                      '2–24 Sep · paused 11 Sep · long runs stalled at RMS 14.1 / 9.5 mm'))
    out.append(branch(200, PILL_TOP, 98, 665, GREY, 'paused', 'Topology events (TOP-001–025)',
                      '11–17 Sep · births, deaths, splits, merges · 8/12 scenes · separate pipeline'))
    out.append(branch(700, PILL_TOP, 70, 850, BLUE, 'kept', 'Theory radius (TR-001/002)',
                      '3 Oct · damping widens the local radius ~41× · no certified rule'))
    out.append(branch(350, PILL_TOP, 156, 560, ORANGE, 'closed', 'Atlas-forecast controller (SC-041–043)',
                      'failed both superiority gates'))
    out.append(branch(410, PILL_TOP, 204, 560, GREY, 'paused', 'Grid localization (SC-050)',
                      'far starts · 6/6 transfers · retired 4 Oct'))
    out.append(branch(940, PILL_TOP, 156, 1150, ORANGE, 'closed', 'GauGal comparison (GGB, GS, ON-002/3, EW)',
                      '5 Oct · circle start works · shapes fail · speed routes closed', anchor='end',
                      label_ys=(127, 144)))
    out.append(branch(1030, PILL_TOP, 204, 1150, ORANGE, 'closed', 'Four-phase schedule (CS-001)',
                      'lost C c13.3 · 4/8 vs 5/8', anchor='end'))
    # below the main line
    out.append(branch(240, PILL_BOT, 344, None, GREEN, None, 'Derivatives & runtime (BIE, SPD) · 11–30 Sep',
                      'analytic → reciprocal derivatives, GPU, damped grids → merged', merge=660))
    out.append(branch(190, PILL_BOT, 404, None, GREEN, None,
                      'Coefficient-space Müller operators (Laurent) · 16–22 Sep',
                      '→ became the node-free modal physics', merge=816))
    out.append(branch(450, 404, 464, 650, ORANGE, 'closed', 'Modal compression & ROMs (LAU, MC-001)',
                      'no useful compression · closed 22 Sep'))
    out.append(branch(60, PILL_BOT, 464, 160, ORANGE, 'closed', 'Implicit IBIM / QBX', 'closed 1 Sep'))
    out.append(branch(870, PILL_BOT, 464, 1020, BLUE, 'kept', 'Relaxed BIE + start census (FM, RB)',
                      '1–3 Oct · no relaxation gain · starts 7/11'))
    out.append(branch(1030, PILL_BOT, 344, 1150, INK, 'open', 'Open: PS-001 screen, RP-001',
                      'modal response · full TG-002 rerun', anchor='end', dashed=True,
                      label_ys=(362, 378)))
    return '\n'.join(out)


# ---------------------------------------------------------------- failure matrix
SCENES = ['circle', 'kite', 'peanut', 'star', 'asymmetric', 'c_shape', 'hook', 'cross', 'cog', 'aphex_twin']
SHORT = ['circle', 'kite', 'peanut', 'star', 'asym.', 'C', 'hook', 'cross', 'cog', 'Aphex']
CONTRASTS = ['0.5', '4', '13.3']


def outcomes(pattern):
    found = {}
    for f in glob.glob(str(RESULTS/pattern)):
        r = json.load(open(f))
        if 'recovered' in r:
            found[Path(f).parent.name] = bool(r['recovered'])
    return found


def matrix_rows():
    pc002 = {r['id']: bool(r['recovered']) for r in json.load(open(RESULTS/'PC-002/NS/summary.json'))['rows']}
    rows = [('PC-001 N1', 'nodal Kress + certified spectral', outcomes('PC-001/N1/runs/*/result.json')),
            ('PC-002', 'nodal Kress + spline, fair profile', pc002),
            ('PC-001 M1', 'modal, established recipe', outcomes('PC-001/M1/runs/*/result.json')),
            ('ON-001 B', 'modal baseline, 120 s contract', outcomes('ON-001/all_B/runs/*/result.json')),
            ('ON-001 E', 'accuracy exit', outcomes('ON-001/all_E/runs/*/result.json')),
            ('DP-001 E', 'frozen E', outcomes('DP-001/E_*/runs/*/result.json')),
            ('DP-001 F', 'agreement damping + reuse', outcomes('DP-001/F_*/runs/*/result.json')),
            ('RG-001 C', 'control', outcomes('RG-001/all/C/runs/*/result.json')),
            ('RG-001 RG', 'decision-relative gate', outcomes('RG-001/all/RG/runs/*/result.json'))]
    for label, _, values in rows:
        if len(values) != 30:
            raise ValueError(f'{label}: expected 30 cases, found {len(values)}')
    return rows


def matrix_svg():
    rows = matrix_rows()
    col = lambda s, c: 214+s*48+c*14  # noqa: E731
    top, step = 62, 30
    out = []
    failing = sorted({f'{s}__c{c}' for _, _, v in rows for s in SCENES for c in CONTRASTS
                      if not v[f'{s}__c{c}']})
    for key in failing:
        s, c = key.split('__c')
        x = col(SCENES.index(s), CONTRASTS.index(c))
        out.append(f'<rect x="{x-7}" y="{top-16}" width="14" height="{step*len(rows)+4}" rx="4" '
                   f'fill="{ORANGE}" fill-opacity="0.10"/>')
    for s, name in enumerate(SHORT):
        out.append(text(col(s, 1), 22, name, 11.5, 700, INK, 'middle'))
        for c, label in enumerate(CONTRASTS):
            out.append(text(col(s, c), 38, label, 8.5, 400, MUTED, 'middle'))
    for i, (label, method, values) in enumerate(rows):
        y = top+i*step
        if i == 2:
            out.append(f'<line x1="0" y1="{y-15}" x2="742" y2="{y-15}" stroke="{SPINE}" stroke-width="1" '
                       f'stroke-dasharray="3 3"/>')
        out.append(text(0, y-1, label, 12, 700))
        out.append(text(0, y+11, method, 9.8, 400, MUTED))
        for s, scene in enumerate(SCENES):
            for c, contrast in enumerate(CONTRASTS):
                x, ok = col(s, c), values[f'{scene}__c{contrast}']
                if ok:
                    out.append(f'<circle cx="{x}" cy="{y}" r="5.5" fill="{GREEN}"/>')
                else:
                    out.append(f'<circle cx="{x}" cy="{y}" r="5.5" fill="#ffffff" stroke="{ORANGE}" stroke-width="2"/>'
                               f'<path d="M{x-2.6},{y-2.6} L{x+2.6},{y+2.6} M{x-2.6},{y+2.6} L{x+2.6},{y-2.6}" '
                               f'stroke="{ORANGE}" stroke-width="1.8" stroke-linecap="round"/>')
        out.append(text(742, y+4, f'{sum(values.values())}/30', 12, 700, INK, 'end'))
    out.append(text(0, 22, 'campaign arm', 11, 400, MUTED))
    out.append(text(0, 38, 'nodal above the dashed line', 9.5, 400, MUTED))
    y = top+len(rows)*step+4
    out.append(f'<circle cx="6" cy="{y}" r="5.5" fill="{GREEN}"/>' + text(16, y+4, 'recovered', 11, 400, MUTED))
    out.append(f'<circle cx="96" cy="{y}" r="5.5" fill="#ffffff" stroke="{ORANGE}" stroke-width="2"/>'
               f'<path d="M93.4,{y-2.6} L98.6,{y+2.6} M93.4,{y+2.6} L98.6,{y-2.6}" stroke="{ORANGE}" stroke-width="1.8"/>'
               + text(106, y+4, 'failed (shaded columns fail in every row)', 11, 400, MUTED))
    out.append(text(742, y+4, 'columns: scene × contrast 0.5 / 4 / 13.3', 11, 400, MUTED, 'end'))
    return '\n'.join(out)


def main():
    html = (HERE/'template.html').read_text()
    html = (html.replace('{{SCHEDULE_SVG}}', schedule_svg()).replace('{{TREE_SVG}}', tree_svg())
            .replace('{{MATRIX_SVG}}', matrix_svg()))
    page = HERE/'research_map.html'
    page.write_text(html)
    chrome = os.environ.get('CHROME', 'google-chrome')
    subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-pdf-header-footer',
                    '--run-all-compositor-stages-before-draw', '--virtual-time-budget=5000',
                    f'--print-to-pdf={PDF}', page.as_uri()], check=True, capture_output=True)
    print(PDF)


if __name__ == '__main__':
    main()
