"""Truth-assisted atlas diagnostic, with ray-quality and actual-frequency controls.

Not used by the already frozen inverse comparison. No physical solves.
"""
from pathlib import Path
import numpy as np
from experiments.shape_continuation import atlas_dataset as ad
from experiments.shape_continuation import spd_cases as sc
from experiments.shape_continuation.atlas_survey import rms_weights


def main():
    source=ad.BASE/"SC-026-atlas-dataset"
    w=rms_weights(48)
    sets={"original_four":(.5e9,.75e9,1e9,1.25e9),
          "extended_nine":tuple(np.arange(.5e9,2.5e9+1,.25e9))}
    rows=[]
    for case in ad.INPUTS:
        with np.load(source/"cells"/f"{case}.npz") as a,np.load(source/"evaluation"/f"{case}_EVALUATION_ONLY.npz") as e:
            good=(e["normal_ray_coverage"]>=.99)&(e["normal_ray_misaligned"]<=.05)
            J=a["jacobian"]
            for i in np.flatnonzero(good):
                error=e["normal_ray"][i]*np.sqrt(w)
                total=error@error+e["normal_ray_beyond_m"][i]**2
                row=dict(case=case,key=str(a["state_key"][i]),rms_mm=float(e["symmetric_rms_m"][i]*1000))
                for name,frequencies in sets.items():
                    ids=[list(a["frequencies_hz"]).index(f) for f in frequencies]
                    matrix=(J[i,ids]/np.sqrt(w)).reshape(-1,97)
                    mu,V=np.linalg.eigh(matrix.T@matrix)
                    projected=V.T@error
                    for label,move in (("strict",.0001),("lenient",.001)):
                        keep=mu>=(.001*np.sqrt(48*len(ids))/move)**2
                        row[f"{name}_{label}_share"]=float(np.sum(projected[keep]**2)/total)
                rows.append(row)
    report=dict(qualification="normal-ray coverage >=0.99 and misaligned fraction <=0.05",
        retained_states=len(rows),component_noise_standard_deviation=.001,
        note="Exploratory, truth-assisted projection under a declared normalized-component noise model; not a recoverability bound.",
        frequency_sets_hz=sets,by_case={},by_distance={})
    fields=[f"{s}_{m}_share" for s in sets for m in ("strict","lenient")]
    def summarize(part):
        return dict(states=len(part),median={f:float(np.median([r[f] for r in part])) for f in fields} if part else {})
    for case in ad.INPUTS:
        report["by_case"][case]=summarize([r for r in rows if r["case"]==case])
    for lo,hi in ((0,.1),(.1,1),(1,5),(5,15),(15,100)):
        report["by_distance"][f"{lo}-{hi} mm"]=summarize([r for r in rows if lo<=r["rms_mm"]<hi])
    sc.write(Path(__file__).with_name("sensitivity.json"),report)
    print(report)


if __name__=="__main__":
    main()
