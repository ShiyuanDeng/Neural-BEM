"""Feedback for the opt-in LM agreement controller, in scaled coordinates."""
import numpy as np


def damping_floor(normal, metric, relative):
    factor = np.linalg.cholesky(metric)
    scaled = np.linalg.solve(factor, normal)
    scaled = np.linalg.solve(factor, scaled.T).T
    # Infinity norm bounds the curvature spectrum without an eigensolve.
    curvature = max(float(np.linalg.norm(scaled, ord=np.inf)), np.finfo(float).eps)
    return max(relative * curvature, np.finfo(float).eps)


def accepted_damping(used, floor, fraction, gain_ratio, config):
    if fraction <= .25:
        factor, reason = config.damping_increase, 'severely_shortened'
    elif gain_ratio is None or not np.isfinite(gain_ratio) or gain_ratio < .25:
        factor, reason = config.damping_increase, 'poor_model_agreement'
    elif fraction < .75 or gain_ratio < .75:
        factor, reason = 1., 'retain_after_shortening_or_marginal_agreement'
    else:
        factor, reason = config.damping_decrease, 'full_step_good_agreement'
    return max(float(used)*factor, floor), reason


def shortened_stagnation(history, window, minimum_progress):
    if len(history) <= window:
        return False
    start, end = history[-window-1]['loss'], history[-1]['loss']
    shortened = sum(row.get('accepted_fraction', 1.) <= .25 for row in history[-window:])
    return (shortened >= (window+1)//2 and
            (start-end)/max(abs(start), np.finfo(float).tiny) < minimum_progress)
