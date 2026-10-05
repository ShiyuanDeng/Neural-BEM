"""Frozen E confirmation: contiguous B/E pairs, locked and published per batch."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from time import perf_counter
import numpy as np
from bem_inverse.io import read, write, digest
from bem_inverse.runner import deadline
from . import on001 as O, campaign as c, scenes as S


def git(args):
    return subprocess.check_output(["git", *args], cwd=c.ROOT, text=True, stderr=subprocess.STDOUT).strip()


def publish(label):
    with (O.COORD/"git.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if git(["diff", "--cached", "--name-only"]):
            raise RuntimeError("Preserve another publisher staged changes; retry only after its index is clear")
        owned = [str(O.OUTPUT.relative_to(c.ROOT)), "docs/iterations/cleaned_interfaces/iteration_31"]
        git(["diff", "--check", "--", *owned])
        git(["add", *owned])
        git(["commit", "-q", "-m", label])
        pushed = git(["push"])
        head = git(["rev-parse", "HEAD"])
        branch = git(["branch", "--show-current"])
        remote = git(["config", f"branch.{branch}.remote"])
        ref = git(["config", f"branch.{branch}.merge"])
        remote_head = git(["ls-remote", remote, ref]).split()[0]
        if head != remote_head:
            raise RuntimeError("Remote did not match published HEAD")
        status = git(["status", "--short", "--", *owned])
        if status:
            raise RuntimeError("Owned evidence changed during publication: "+status)
        archive = O.COORD/"on001_publications.json"
        records = read(archive) if archive.exists() else []
        records.append(dict(label=label, commit=head, remote_verified=True, own_tree_clean=True))
        write(archive, records)
        print("PUBLISHED", label, head, flush=True)
        return head


def summarize(prefix):
    rows = []
    for case in S.CASES:
        values = {}
        for arm in ("B", "E"):
            p = O.OUTPUT/f"{prefix}_{arm}"/"runs"/case/"result.json"
            if p.exists():
                r = read(p)
                values[arm] = dict(recovered=r["recovered"], outcome=r["outcome"],
                    seconds=r.get("audited_output_seconds", r.get("total_seconds")),
                    fit_seconds=r.get("fit_and_localization_seconds"), fit_internal_seconds=r.get("total_seconds"),
                    metrics=r.get("metrics"), maximum_residual=r.get("maximum_residual"),
                    audit=r.get("final_audit_passed"))
            else:
                values[arm] = dict(status="unrun")
        rows.append(dict(id=case, **values))
    complete = [r for r in rows if all("recovered" in r[a] for a in ("B", "E"))]
    common = [r for r in complete if r["B"]["recovered"] and r["E"]["recovered"]]
    ratios = [r["B"]["seconds"]/r["E"]["seconds"] for r in common]
    value = dict(prefix=prefix, completed_pairs=len(complete), rows=rows,
        recovered={a: sum(r[a].get("recovered", False) for r in rows) for a in ("B", "E")},
        regressions=[r["id"] for r in complete if r["B"]["recovered"] and not r["E"]["recovered"]],
        additions=[r["id"] for r in complete if not r["B"]["recovered"] and r["E"]["recovered"]],
        paired_speedups={r["id"]: ratio for r, ratio in zip(common, ratios)},
        median_speedup=float(np.median(ratios)) if ratios else None,
        p10_speedup=float(np.percentile(ratios, 10)) if ratios else None,
        total_audited_seconds={a: sum(r[a]["seconds"] for r in complete if r[a]["seconds"] is not None) for a in ("B", "E")},
        timing_boundary="child run_case entry to fit-return after fit_result output; excludes truth scoring and Python imports")
    write(O.OUTPUT/f"{prefix}_paired.json", value)
    lines = [f"# ON-001 {prefix} paired confirmation", "", value["timing_boundary"], "",
             "| Case | B recovered | B seconds | E recovered | E seconds | B/E |", "|---|---|---|---|---|---|"]
    for r in rows:
        b, e = r["B"], r["E"]
        def cell(v):
            return ["unrun", "unrun"] if "status" in v else [str(v["recovered"]), format(v["seconds"] or 0, ".3f")]
        bc, ec = cell(b), cell(e)
        ratio = value["paired_speedups"].get(r["id"])
        ratio_text = "—" if ratio is None else f"{ratio:.3f}"
        lines.append("| "+" | ".join([r["id"], *bc, *ec, ratio_text])+" |")
    (O.OUTPUT/f"{prefix}_table.md").write_text("\n".join(lines)+"\n")
    return value


def run_pair(case, prefix, cases):
    requested = perf_counter()
    with (O.COORD/"compute.lock").open("a") as compute, (O.COORD/"source.lock").open("a") as source:
        # Compute waiting counts against the original ceiling and closeout reserve.
        closeout = datetime(2026, 10, 5, 8, 57, 21, tzinfo=timezone.utc)
        remaining = (closeout-datetime.now(timezone.utc)).total_seconds()
        if remaining < 400:
            raise TimeoutError('No remaining cap for another matched pair before closeout')
        with deadline(remaining-400):
            fcntl.flock(compute, fcntl.LOCK_EX)
            fcntl.flock(source, fcntl.LOCK_SH)
        waiting = perf_counter()-requested
        c.verify(require_inputs=True)
        hashes = O.source_hashes()
        fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
        archives = O.OUTPUT/"source_archives"; archives.mkdir(exist_ok=True)
        archive_path = archives/(fingerprint+".tar.gz")
        if not archive_path.exists():
            with tarfile.open(archive_path, "w:gz") as archive:
                for name in hashes:
                    archive.add(c.ROOT/name, arcname=name, recursive=False)
        pair = dict(case=case, started=datetime.now(timezone.utc).isoformat(), compute_wait_seconds=waiting,
                    source_hashes=hashes, source_fingerprint=fingerprint, process_seconds={}, execution=asdict(O.EXECUTION))
        for arm in ("B", "E"):
            folder = O.OUTPUT/f"{prefix}_{arm}"
            folder.mkdir(exist_ok=True)
            manifest = folder/"manifest.json"
            if not manifest.exists():
                write(manifest, dict(experiment="ON-001 frozen E confirmation", arm=arm, cases=cases,
                    settings=O.ARMS[arm], source_hashes=hashes, archive=str(archive_path.relative_to(c.ROOT)),
                    archive_sha256=digest(archive_path), inputs_sha256=digest(c.INPUTS/"manifest.json"),
                    execution=asdict(O.EXECUTION), workers=1, blas_threads=1,
                    warmup="fresh interpreter each case; no excluded numerical warmup; pairs contiguous",
                    commit=git(["rev-parse", "HEAD"])))
            if read(manifest)["settings"] != O.ARMS[arm]:
                raise ValueError("Frozen confirmation settings changed")
            result = folder/"runs"/case/"result.json"
            if result.exists():
                raise FileExistsError("Preserve prior pair evidence: "+str(result))
            log = O.OUTPUT/"validation"/f"{prefix}_{case}_{arm}.log"
            started = perf_counter()
            with log.open("w") as output:
                subprocess.run([sys.executable, "-m", "experiments.benchmark.on001", "case",
                                "--arm", arm, "--batch", f"{prefix}_{arm}", "--cases", case],
                               stdout=output, stderr=subprocess.STDOUT, check=True)
            pair["process_seconds"][arm] = perf_counter()-started
            r = read(result)
            assert r["case"]["id"] == case and r["arm"] == arm
            if "fit_work" in r and r["fit_work"]:
                assert r["fit_work"]["work_units"] <= 13412
            if "metrics" in r:
                m, residual = r["metrics"], r.get("relative_residual")
                expected = bool(r["final_audit_passed"] and m["rms_mm"] <= 1. and m["hausdorff_upper_mm"] <= 2.
                                and residual is not None and np.all(np.asarray(residual) <= r["residual_limits"]))
                assert r["recovered"] == expected
                assert r["final_curve"] == read(result.parent/"fit_result.json")["final_curve"]
            c.summarize(folder)
        assert hashes == O.source_hashes()
        pair["source_check_passed"] = True
        for arm in ("B", "E"):
            write(O.OUTPUT/f"{prefix}_{arm}"/"pairs"/(case+".json"), pair)
    # Reporting and Git run after releasing earlier resources.
    comparison = summarize(prefix)
    O.report()
    print("PAIR", case, comparison["recovered"], "median", comparison["median_speedup"], flush=True)
    publish(f"Record ON-001 {prefix} matched pair {case}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="all")
    parser.add_argument("--cases", default="all")
    args = parser.parse_args()
    cases = list(S.CASES) if args.cases == "all" else args.cases.split(",")
    if not all(k in S.CASES for k in cases):
        parser.error("TG-002 only")
    frozen = O.OUTPUT/"frozen_finalist.json"
    if not frozen.exists():
        write(frozen, dict(recipe="E", required_accuracy=.003, reach_fraction=0., working_anchors=0,
            solver="modal_muller", geometry_update="certified_spectral", localization="none", cases=list(S.CASES),
            fit_seconds=120., fit_units=13412, audit_aggregate_seconds=30., selected_from="declared screen before all-30"))
    assert read(frozen)["recipe"] == "E"
    for case in cases:
        run_pair(case, args.prefix, cases)


if __name__ == "__main__":
    main()
