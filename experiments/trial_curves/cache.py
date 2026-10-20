"""Replay one iteration (default: first of stage_3_damped) and cache the rows for the notebook."""
import pickle
import sys

from experiments.benchmark import campaign as c
from experiments.cleaned_interface import benchmark as ci
from experiments.trial_curves.replay import load, replay

case, stage, out = 'aphex_twin__c13.3', sys.argv[1], sys.argv[2]
iterations = load('results/trial_curves/aphex_c13.3.pkl')
number = next(i for i, x in enumerate(iterations) if x['stage'] == stage)
it = iterations[number]
row = next(r for r in c.descriptors() if r['id'] == case)
unit = ci.fitting_problem(row, 'results/trial_curves/aphex_c13.3_run').length_unit_m
lambdas = [0.] if len(sys.argv) > 3 and sys.argv[3] == 'gn' else None
rows = replay(it, unit, lambdas=lambdas)
pickle.dump(dict(case=case, stage=stage, iteration_index=number, length_unit_m=unit, base=it['coefficients'],
                 loss=it['loss'], rows=rows, real_trials=it['real_trials']), open(out, 'wb'))
print('saved', out, len(rows))
