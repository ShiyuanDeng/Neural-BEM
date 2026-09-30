"""Run ``python -m experiments.cleaned_interface --help`` from the repository root."""
import argparse
import json
from pathlib import Path
from . import benchmark as b
from .io import portable
from .physics import Execution, make_backend
from .policy import CumulativePolicy, readable_plan


def main():
    parser=argparse.ArgumentParser(description='CI-001 cumulative inverse and all-36 regression campaign')
    parser.add_argument('command',choices=('inventory','prepare','augment','verify','plan','run','report','spd-pairs','compare-execution'))
    parser.add_argument('--output',type=Path,default=b.DEFAULT_OUTPUT)
    parser.add_argument('--solver',default='nodal_kress')
    parser.add_argument('--device',choices=('auto','cpu','cuda'),default='auto')
    parser.add_argument('--acceleration',choices=('reference','spd016'),default='spd016')
    parser.add_argument('--frequency-threads',type=int,default=4)
    parser.add_argument('--workers',type=int,default=1)
    parser.add_argument('--resolution',type=int,default=512)
    parser.add_argument('--cases',nargs='+')
    parser.add_argument('--allow-new-damped-data',action='store_true')
    parser.add_argument('--reuse-from',type=Path,help='reuse exactly the sealed augmented observations of another campaign')
    parser.add_argument('--format',choices=('text','json'),default='text',help='plan output format')
    parser.add_argument('--references',type=Path,nargs='+',help='matched reference campaign directories')
    parser.add_argument('--candidates',type=Path,nargs='+',help='matched candidate campaign directories')
    parser.add_argument('--matched-host-load',action='store_true',help='attest comparable host load during repeated timings')
    args=parser.parse_args()
    execution=Execution(args.device,args.frequency_threads,args.acceleration,resolution=args.resolution)
    if args.command=='inventory':
        rows=b.descriptors()
        value=dict(cases=len(rows),missing_damped=sum('damped' not in r for r in rows),
                   rows=[dict(id=r['id'],contrast=r['contrast'],damped_available='damped' in r) for r in rows])
    elif args.command=='prepare':
        value=b.prepare(args.output)
    elif args.command=='augment':
        value=b.augment(args.output,execution,allow_new_damped_data=args.allow_new_damped_data,reuse_from=args.reuse_from)
    elif args.command=='verify':
        value=dict(verified=True,cases=len(b.verify(args.output)['cases']))
    elif args.command=='plan':
        rows=b.descriptors()
        case=(args.cases or ['modal__c4__development_c'])[0]
        row=next((r for r in rows if r['id']==case),None)
        if row is None:
            parser.error('Unknown case: '+case)
        value=CumulativePolicy().plan(b.fitting_problem(row,args.output),make_backend(args.solver,execution))
        if args.format=='text':
            print(readable_plan(value))
            return
    elif args.command=='run':
        value=b.run(args.output,execution,solver=args.solver,workers=args.workers,cases=args.cases)
    elif args.command=='spd-pairs':
        from .qualification import spd_pairs
        value=spd_pairs(args.output,execution)
    elif args.command=='compare-execution':
        if not args.references or not args.candidates:
            parser.error('compare-execution requires --references and --candidates')
        from .qualification import compare_execution
        value=compare_execution(args.references,args.candidates,matched_host_load=args.matched_host_load)
    else:
        value=b.report(args.output)
    print(json.dumps(portable(value),indent=2))


if __name__=='__main__':
    main()
