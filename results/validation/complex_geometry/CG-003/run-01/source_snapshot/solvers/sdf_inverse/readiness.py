"""Pure training-only decision: no solver, scene, truth or evaluation imports."""
import numpy as np

FIT_TOLERANCE = 1e-5
DISCREPANCY_TOLERANCES = (1e-5, 1e-7, 1e-7, 1e-7)


def training_readiness(observed, production, refined):
    arrays = [np.asarray(x, dtype=np.complex128) for x in (observed, production, refined)]
    if (arrays[0].ndim != 2 or arrays[0].shape[0] == 0 or arrays[0].shape[1] != 4
            or any(x.shape != arrays[0].shape for x in arrays)):
        raise ValueError("Exactly four matching training-frequency columns are required.")
    if any(not np.all(np.isfinite(x)) for x in arrays):
        raise ValueError("Readiness inputs must be finite.")
    observed, production, refined = arrays
    norm = np.linalg.norm(observed, axis=0)
    floor = 1e-12 * max(1., float(np.max(norm)), float(np.linalg.norm(observed))/2)
    if np.any(norm <= floor) or np.any(np.linalg.norm(refined, axis=0) <= floor):
        raise ValueError("Readiness requires usable observation and prediction norms.")
    errors = [np.linalg.norm(x-observed, axis=0)/norm for x in (production, refined)]
    discrepancy = np.linalg.norm(production-refined, axis=0)/np.linalg.norm(refined, axis=0)
    finite = bool(np.all(np.isfinite(np.concatenate(errors+[discrepancy]))))
    fits = finite and all(np.all(x <= FIT_TOLERANCE) for x in errors)
    numerical = finite and bool(np.all(discrepancy <= DISCREPANCY_TOLERANCES))
    return dict(ready=bool(fits and numerical), training_fit_pass=bool(fits),
                numerical_pass=numerical, production_errors=errors[0].tolist(),
                refined_errors=errors[1].tolist(), discrepancy=discrepancy.tolist(),
                fit_tolerance=FIT_TOLERANCE,
                discrepancy_tolerances=list(DISCREPANCY_TOLERANCES),
                decision_inputs="four training frequencies and two numerical resolutions only")
