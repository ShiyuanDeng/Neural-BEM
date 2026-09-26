"""Post-fit policy geometry diagnostics; no policy decisions or PDE calls."""
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('policy_regularity_source',
    HERE.parent/'SC-042-state-strategies/regularity.py')
regularity=importlib.util.module_from_spec(spec)
spec.loader.exec_module(regularity)
c=regularity.r


def main():
    c.verify()
    rows=[]
    for case in c.CASES:
        target=c.ast.curve_from(c.sc.read(c.ast.source_folder(case)/'truth.json'))
        rows.append(dict(case=case,policy='truth',**regularity.measure(target,target,case=case)))
        for policy in ('fixed','stagnation','atlas'):
            path=HERE/'runs'/case/policy/'result.json'
            if path.exists():
                result=c.sc.read(path)
                rows.append(dict(case=case,policy=policy,**regularity.measure(
                    c.ast.curve_from(result['curve']),target,case=case)))
    c.write(HERE/'regularity.json',dict(rows=rows,count=16384,
        interpretation='Post-fit descriptive measurements, excluded from policy choices and frozen gates. '
        'Curvature spectrum uses uniform arclength; stored-coefficient energy is parameterization-dependent. '
        'Nearest-truth localization is sampled, not a certified distance. Neither statistic tests observability.'))
    print({'rows':len(rows)})


if __name__=='__main__':main()
