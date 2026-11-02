"""Describe saved stopping and recovery evidence without rerunning a solver."""
import json
import math


LIMITS = {'rms_mm': 1., 'hausdorff_upper_mm': 2., 'maximum_residual': .003}
NAMES = {'rms_mm': 'RMS (mm)', 'hausdorff_upper_mm': 'Hausdorff upper bound (mm)',
         'maximum_residual': 'maximum field residual'}


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def number(value):
    return f'{value:.4g}' if finite(value) else 'unavailable'


def limit_failures(row):
    return [f'{NAMES[key]} {number(row.get(key))} > {limit:g}'
            if finite(row.get(key)) else f'{NAMES[key]} unavailable'
            for key, limit in LIMITS.items()
            if not finite(row.get(key)) or row[key] > limit]


def contrast_errors(row, truth):
    value = row.get('contrast')
    return dict(contrast_true=truth,
                contrast_absolute_error=abs(value-truth) if finite(value) else None,
                contrast_relative_error=(value-truth)/truth if finite(value) else None)


def bem_evidence(data, path, row, truth, frequencies, repo):
    """Keep the triggering trial refusal separate from checks on the accepted curve."""
    check_path = path.parent/'final_audit.json'
    checks = json.loads(check_path.read_text()) if check_path.exists() else {}
    stages = data.get('stages', [])
    last = stages[-1] if stages else {}
    failures = [dict(stage=s['stage'], message=f.get('message'), category=f.get('category'))
                for s in stages for f in s.get('physics_failures', [])]
    messages = list(dict.fromkeys(f"{f['stage']}: {f['message']}" for f in failures))
    fields = checks.get('field_relative', [])
    field_failed = [dict(frequency_hz=float(f), relative_error=e,
                         limit=1e-5 if f <= .5e9 else 1e-7)
                    for f, e in zip(frequencies, fields)
                    if not finite(e) or e > (1e-5 if f <= .5e9 else 1e-7)]
    jacobian = max(checks.get('jacobian_relative', []), default=None)
    fd = checks.get('full_trial_fd_relative')
    check_reasons = []
    if field_failed:
        worst = max(field_failed, key=lambda x: x['relative_error']/x['limit'])
        check_reasons.append(f"field refinement discrepancy at {len(field_failed)} frequencies; "
                             f"worst tolerance ratio {number(worst['relative_error']/worst['limit'])} "
                             f"at {worst['frequency_hz']/1e9:g} GHz")
    if finite(jacobian) and jacobian > .001:
        check_reasons.append(f'Jacobian discrepancy {number(jacobian)} > 0.001')
    if finite(fd) and fd > .001:
        check_reasons.append(f'full-trial finite-difference discrepancy {number(fd)} > 0.001')
    if check_path.exists() and not checks.get('passed') and not check_reasons:
        check_reasons.append('final numerical check did not pass; see saved check file')
    stop = f"{data['outcome']}; {last.get('stage', 'no stage')}: " + str(
        last.get('stop') or last.get('detail') or last.get('outcome', 'unavailable'))
    reasons = messages+check_reasons+limit_failures(row)
    path_values = [s['contrast'] for s in stages if finite(s.get('contrast'))]
    start = data.get('initial_contrast')
    if not data['recovered'] and finite(row['contrast']):
        if finite(start):
            reasons.append(f"contrast start {number(start)}, warm-up end "
                           f"{number(stages[0].get('contrast') if stages else None)}, "
                           f"final {number(row['contrast'])}; truth {truth:g}")
    return dict(**contrast_errors(row, truth), stop_reason=stop,
                recovery_status='recovered' if data['recovered'] else 'not recovered',
                failure_reason='None: all TG-002 recovery checks passed.' if data['recovered']
                else '; '.join(reasons) or stop,
                evidence=[str(p.relative_to(repo)) for p in (path, check_path) if p.exists()],
                final_checks_passed=checks.get('passed'),
                final_field_discrepancy=max(fields, default=None),
                final_field_failed_frequencies=field_failed,
                final_jacobian_discrepancy=jacobian, final_trial_fd_discrepancy=fd,
                numerical_refusals=failures, initial_contrast=start,
                stage_contrasts=path_values,
                fit_seconds=data.get('fit_and_localization_seconds'),
                final_check_seconds=data.get('audit_seconds'))


def gaugal_evidence(data, path, row, truth, repo):
    stop = data.get('stop_reason', 'unavailable')
    iterations = data.get('iterations', 0)
    descriptions = {
        'iteration_limit': f'reached the declared {iterations}-iteration budget; convergence not established',
        'time_limit': f'reached the optimization time allowance after {iterations} iterations',
        'outer_time_limit': f"outer process limit ({data.get('outer_limit_seconds', 'unknown')} s); "
                            f'last saved checkpoint at iteration {iterations}',
        'nonfinite_gradient': 'stopped after a nonfinite loss or gradient',
        'nonfinite_update': 'stopped after a nonfinite image update',
    }
    reasons = [descriptions.get(stop, str(data.get('failure') or stop))]
    reasons += limit_failures(row)
    traced = data.get('traced', {})
    if traced.get('traces') == 0:
        reasons.append('no closed half-peak contour; boundary scores and traced mean contrast unavailable')
    elif traced.get('traces', 0) > 1:
        reasons.append(f"{traced['traces']} closed half-peak contours; the longest supplies the boundary")
    if finite(row.get('contrast')):
        reasons.append(f"traced mean contrast {number(row['contrast'])}; truth {truth:g}")
    history = data.get('history', [])
    first = history[0].get('weighted_misfit') if history else None
    last = history[-1].get('weighted_misfit') if history else None
    # History is evaluated at extrapolated iterates; final residual is separately recomputed.
    nfreq = len(data.get('frequencies_hz', []))
    if finite(first) and finite(last) and nfreq:
        reasons.append(f'logged mean squared relative misfit {number(first/nfreq)} → {number(last/nfreq)}')
    solves = data.get('linear_solves')
    calls = sum(s['calls'] for s in solves) if solves else None
    unconverged = sum(s['unconverged'] for s in solves) if solves else None
    largest = max((s['max_final_relative'] for s in solves), default=None) if solves else None
    if calls:
        reasons.append(f'{unconverged}/{calls} inner solves missed their convergence tolerance '
                       f'(largest logged inner residual {number(largest)})')
    else:
        reasons.append('inner-solve summary unavailable for this partial output')
    return dict(**contrast_errors(row, truth),
                recovered=None,
                recovery_status=('shared limits met; not numerically qualified' if row['meets_shared_limits']
                                 else 'shared limits not met'),
                failure_reason='; '.join(reasons), evidence=[str(path.relative_to(repo))],
                inner_solve_calls=calls, inner_solves_unconverged=unconverged,
                inner_solve_max_relative=largest, logged_misfit_first=first,
                logged_misfit_last=last, build_seconds=data.get('build_seconds'),
                optimize_seconds=data.get('optimize_seconds'),
                process_returncode=data.get('process_returncode'),
                closed_contours=traced.get('traces'), peak_susceptibility=traced.get('peak'))


def json_safe(value):
    """Strict JSON uses null for unavailable/nonfinite scores, never NaN/Infinity."""
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
