"""Digitize the published Figure 1 error curves and compare them with SC-013.

Reads only the local PDF and the saved bundles. No forward or inverse solves.
The two error panels are semilog scatter plots; calibration uses the rendered
y tick labels (whose spacing is checked for uniformity) and an x axis assumed
to span exactly [0, 10], which the recovered k values then confirm.
"""
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from PIL import Image
from scipy import ndimage


directory = Path(__file__).resolve().parent
repo = directory.parents[3]
PDF = repo / "docs/reference/papers/borges_rachh_greengard_2210.11607v1.pdf"
PAGE, DPI = 13, 600
# Panel frame columns, and the exponents printed beside each panel.
PANELS = {"0.33": dict(folder="run-contrast-0.33", leaf="contrast_0.33", exponents=(0., -1., -2.)),
          "10": dict(folder="run-contrast-10", leaf="contrast_10", exponents=(0., -2., -4.))}


def render():
    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "page"
        subprocess.run(["pdftoppm", "-f", str(PAGE), "-l", str(PAGE), "-r", str(DPI),
                        "-png", str(PDF), str(stem)], check=True)
        return np.array(Image.open(next(Path(tmp).glob("page*.png"))).convert("L"))


def frames(dark):
    """Axis frames are the long straight dark runs bounding the error panels."""
    rows = np.where(dark.sum(1) > .15 * dark.shape[1])[0]
    cols = np.where(dark.sum(0) > .5 * dark.shape[0])[0]
    split = lambda a: [g.mean() for g in np.split(a, np.where(np.diff(a) > 5)[0] + 1)]
    row, col = split(rows), split(cols)
    assert len(row) == 2 and len(col) == 4, (row, col)
    return int(row[0]), int(row[1]), [(int(col[0]), int(col[1])), (int(col[2]), int(col[3]))]


def calibrate(dark, left, exponents):
    """Row of each printed y tick label; their spacing must be uniform."""
    label = dark[:, left - 150:left - 15]
    rows = np.where(label.sum(1) > 0)[0]
    centres = [g.mean() for g in np.split(rows, np.where(np.diff(rows) > 12)[0] + 1) if len(g) > 8]
    assert len(centres) == len(exponents), centres
    steps = np.diff(centres) / np.abs(np.diff(exponents))
    assert steps.std() / steps.mean() < .02, steps      # uniform decades
    return centres[0], float(steps.mean())


def scatter(dark, top, bottom, left, right, y_zero, per_decade):
    interior = dark[top + 6:bottom - 6, left + 6:right - 6]
    labelled, count = ndimage.label(interior)
    sizes = ndimage.sum(interior, labelled, range(1, count + 1))
    centres = ndimage.center_of_mass(interior, labelled, range(1, count + 1))
    points = sorted((left + 6 + cx, top + 6 + cy)
                    for (cy, cx), size in zip(centres, sizes) if size > 30)
    k = np.array([(x - left) / (right - left) * 10 for x, _ in points])
    error = np.array([10 ** (-(y - y_zero) / per_decade) for _, y in points])
    snapped = np.round(k * 4) / 4                        # the paper's 0.25 grid
    return snapped, k, error


page = render()
height = page.shape[0]
dark = page[int(.29 * height):int(.42 * height), :] < 128
top, bottom, columns = frames(dark)

report = {}
for (name, spec), (left, right) in zip(PANELS.items(), columns):
    y_zero, per_decade = calibrate(dark, left, spec["exponents"])
    snapped, raw, error = scatter(dark, top, bottom, left, right, y_zero, per_decade)
    published = dict(zip(snapped.tolist(), error.tolist()))
    case = directory / spec["folder"] / spec["leaf"] / "summary.json"
    mine = {d["decision"]["stage"]["wavenumber"]:
            d["area_error"]["relative_symmetric_difference"]
            for d in json.loads(case.read_text())["decisions"]}
    shared = sorted(set(published) & set(mine))
    report[name] = dict(
        detected_points=len(snapped), expected_points=37,
        maximum_k_snap_error=float(np.abs(raw - snapped).max()),
        pixels_per_decade=per_decade,
        published=published, ours=mine,
        ratio={k: published[k] / mine[k] for k in shared})

(directory / "figure1_comparison.json").write_text(json.dumps(report, indent=2) + "\n")
for name, data in report.items():
    print(f"\n=== eta = {name} "
          f"({data['detected_points']}/{data['expected_points']} published points read) ===")
    print(f"{'k':>5} | {'published':>10} | {'SC-013':>10} | {'ratio':>7}")
    for k in sorted(data["ratio"]):
        print(f"{k:5g} | {data['published'][k]:10.4g} | {data['ours'][k]:10.4g} |"
              f" {data['ratio'][k]:6.1f}x")
