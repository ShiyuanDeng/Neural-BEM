"""C12. Accepted-step damping; state commitment and callbacks stay in fit_stage."""
import numpy as np
from . import checks


def scheduled_damping(used, decrease):
    """Default C12 rule: reduce accepted damping, retaining the positive floor."""
    return max(used * decrease, np.finfo(float).tiny)

def accepted_damping(used, floor, fraction, gain_ratio, config):
    if checks.severely_shortened(fraction):
        factor, reason = config.damping_increase, 'severely_shortened'
    elif checks.poor_model_agreement(gain_ratio):
        factor, reason = config.damping_increase, 'poor_model_agreement'
    elif checks.shortened_or_marginal(fraction, gain_ratio):
        factor, reason = 1., 'retain_after_shortening_or_marginal_agreement'
    else:
        factor, reason = config.damping_decrease, 'full_step_good_agreement'
    return max(float(used)*factor, floor), reason
