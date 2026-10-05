"""ON-001 F complete-map qualification on predeclared screen baseline states."""
import fcntl
import tarfile
from pathlib import Path
from time import perf_counter
import traceback
from types import SimpleNamespace
import numpy as np
from bem_inverse.io import read, write, curve_from, digest
from bem_inverse.geometry import resize
from bem_inverse.geometry_selection import make_update
from bem_inverse.gaussian_displacement import GaussianDisplacement
from bem_inverse.policy import CumulativePolicy
from bem_inverse.runner import deadline
from . import on001 as O, campaign as c


def qualify(width_factor=2., batch="qualification_F"):
    folder = O.OUTPUT/batch
    with (O.COORD/"compute.lock").open("a") as compute, (O.COORD/"source.lock").open("a") as source:
        fcntl.flock(compute, fcntl.LOCK_EX)
        fcntl.flock(source, fcntl.LOCK_SH)
        folder.mkdir(exist_ok=False)
        hashes = O.source_hashes()
        hashes[str(Path(__file__).resolve().relative_to(c.ROOT))] = digest(Path(__file__))
        with tarfile.open(folder/"sources.tar.gz", "w:gz") as archive:
            for name in hashes:
                archive.add(c.ROOT/name, arcname=name, recursive=False)
        write(folder/"manifest.json", dict(width_factor=width_factor, cases=O.SCREEN, source_hashes=hashes,
            states="original start M1 K4 and recorded baseline endpoint with actual last M/storage",
            frequencies="highest real initial frequency; highest active recorded endpoint frequency; both catalogs",
            limits=dict(field_low=1e-5, field_high=1e-7, column_jacobian=1e-3, complete_fd=1e-3),
            fd_step_m=1e-7, seed=1001, inputs_sha256=digest(c.INPUTS/"manifest.json")))
        rows = []
        for case in O.SCREEN:
            p = c.problem(case)
            baseline = read(O.OUTPUT/"screen_B"/"runs"/case/"result.json")
            physics = c._physics("modal_muller", O.EXECUTION)
            last = baseline["stages"][-1]
            ops = list(CumulativePolicy().operations(p, physics))
            ops += list(CumulativePolicy().tail(p, physics, last["M"]))
            actual = next(op.stage for op in ops if op.label == last["stage"])
            max_frequency = max(o.frequency_hz for o in actual.observations)
            states = (("initial", resize(p.initial, 4), 1, max(o.frequency_hz for o in p.real)),
                      ("accepted_endpoint", curve_from(baseline["final_curve"]), last["M"], max_frequency))
            for name, curve, M, frequency in states:
                started = perf_counter()
                row = dict(case=case, state=name, M=M, K=curve.band, frequency_hz=frequency, checks=[])
                update = GaussianDisplacement(p.length_unit_m, device="cuda", width_factor=width_factor)
                try:
                    with deadline(120.):
                        space = update.prepare(curve, M, curve.band)
                        row.update(condition=space.condition, width=space.width, controls=len(space.centres))
                        rng = np.random.default_rng(1001)
                        direction = rng.normal(size=2*M+1); direction /= np.linalg.norm(direction)
                        tangent = rng.normal(size=2*M+1); tangent /= np.linalg.norm(tangent)
                        C = np.exp(-.5)*sum(abs(space.weights@direction))/space.width
                        finite = direction*(1.6/C) if C > 0 else direction*.001
                        for label, a in (("zero", direction*0), ("active", finite)):
                            current, receipt = update.trial(space, a)
                            hp, h = 5e-8, 1e-7
                            plus, plus_receipt = update.trial(space, a+h*tangent)
                            minus, minus_receipt = update.trial(space, a-h*tangent)
                            if label == "zero":
                                delta = space.derivatives@tangent
                            else:
                                delta = update.tangent_at(space, a, tangent)
                            directional = SimpleNamespace(curve=current, derivatives=delta[:, None])
                            profile = physics.resolution_profile(current.band)
                            for catalog, observations in (("real", p.real), ("damped", p.damped)):
                                observation = next(o for o in observations if o.frequency_hz == frequency)
                                coarse = physics.evaluate(current, observation, p.contrast, profile["production"])
                                fine = physics.evaluate(current, observation, p.contrast, profile["refined"])
                                field = float(np.linalg.norm(coarse.prediction-fine.prediction)/np.linalg.norm(fine.prediction))
                                # At zero qualify every model column, plus the independent full finite trial.
                                checked_space = space if label == "zero" else directional
                                ja = physics.derivative(coarse, update, checked_space)
                                jb = physics.derivative(fine, update, checked_space)
                                column = float(max(np.linalg.norm(ja-jb, axis=0)/np.maximum(np.linalg.norm(jb, axis=0), 1e-30)))
                                derivative = jb@tangent if label == "zero" else jb[:, 0]
                                fd = (physics.evaluate(plus, observation, p.contrast, profile["refined"]).prediction-
                                      physics.evaluate(minus, observation, p.contrast, profile["refined"]).prediction)/(2*h)
                                error = float(np.linalg.norm(fd-derivative)/max(np.linalg.norm(fd), 1e-30))
                                passed = field <= (1e-5 if frequency <= .5e9 else 1e-7) and column <= 1e-3 and error <= 1e-3
                                row["checks"].append(dict(label=label, catalog=catalog, field_relative=field,
                                    column_relative=column, full_trial_fd_relative=error, passed=bool(passed),
                                    gaussian=receipt, plus_alpha=plus_receipt["gaussian_alpha"],
                                    minus_alpha=minus_receipt["gaussian_alpha"],
                                    nominal_zero_model_ratio=None if label != "zero" else (1/plus_receipt["gaussian_alpha"]-1)))
                                print(case, name, label, catalog, "field", field, "column", column, "FD", error,
                                      "passed", passed, flush=True)
                    row["passed"] = all(r["passed"] for r in row["checks"])
                except Exception as exc:
                    row.update(passed=False, refusal_reason=getattr(exc, "reason", None),
                               error=str(exc), traceback=traceback.format_exc())
                    print(case, name, "REFUSED", str(exc), flush=True)
                row.update(seconds=perf_counter()-started, geometry=update.counts, physics=physics.receipt())
                rows.append(row)
                write(folder/"qualification.json", dict(passed=all(r["passed"] for r in rows), rows=rows,
                                                       complete=len(rows) == 16))
        final = O.source_hashes()
        final[str(Path(__file__).resolve().relative_to(c.ROOT))] = digest(Path(__file__))
        write(folder/"source_check.json", dict(passed=hashes == final))
        assert hashes == final
        return all(r["passed"] for r in rows)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width-factor", type=float, choices=(1., 2.), default=2.)
    parser.add_argument("--batch", default="qualification_F")
    args = parser.parse_args()
    print("QUALIFIED", qualify(args.width_factor, args.batch), flush=True)
