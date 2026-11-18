"""Ten-frequency settings and thin calls into the unchanged CSI wrappers."""
from csi_runtime import ROOT, provenance
import argparse
import json
import sys
import traceback

import csi_data as D
import csi_fit as F
import csi_forward_check as C
import csi_policy_dry_check as P

FREQUENCIES = tuple(i/4 for i in range(1, 11))
RESULTS = ROOT/'results/bem/baseline_data/csi_ten_frequency/2026-11-18'


def configure():
    D.SIMULATED = 'results/csi/tg002/2026-11-18_ten_frequency_data/{shape}/forward/synthetic_input.txt'
    F.DATASETS['simulated'] = dict(frequencies_ghz=FREQUENCIES)
    F.LADDER_QUOTAS[10] = (1000, *([375]*8), 4000)
    F.RESULTS = RESULTS
    C.CASES['circle__c4']['path'] = F.case_input('circle__c4')


def main():
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    check = sub.add_parser('check')
    check.add_argument('--cases', nargs='+', required=True)
    sub.add_parser('plan')
    fit = sub.add_parser('fit')
    fit.add_argument('--case', required=True)
    fit.add_argument('--device', choices=['cuda'], required=True)
    args = parser.parse_args()
    configure()
    if args.action == 'check':
        sys.argv = [sys.argv[0], '--out', str(RESULTS/'adapter_checks'), '--cases', *args.cases]
        C.main()
    elif args.action == 'plan':
        RESULTS.mkdir(parents=True, exist_ok=True)
        record = dict(provenance=provenance(), frequencies_ghz=FREQUENCIES,
                      ladder_quotas=F.LADDER_QUOTAS[10])
        try:
            plan, stages = P.plan(F.case_input('circle__c4'), FREQUENCIES, 1.5)
            record.update(state='passed', plan=plan, stages=stages)
            P.show('Ten-frequency dry plan', stages)
        except Exception:
            record.update(state='refused', detail=traceback.format_exc())
        (RESULTS/'policy_dry_check.json').write_text(json.dumps(record, indent=2, default=str)+'\n')
        if record['state'] != 'passed':
            raise SystemExit(record['detail'])
    else:
        sys.argv = [sys.argv[0], '--case', args.case, '--device', args.device,
                    '--out', str(RESULTS), '--checks', str(RESULTS/'adapter_checks')]
        F.main()


if __name__ == '__main__':
    main()
