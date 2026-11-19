"""Extract saved measured-cylinder stage receipts without running a fit."""
from csi_runtime import ROOT
import json
from collections import Counter
import csi_cylinder_loss_map as L


def main():
    folder=L.BASE/'first_fit/dielTM_dec8f/cuda/attempt_01'
    fit=json.loads((folder/'fit.json').read_text())
    ops=json.loads((folder/'manifest.json').read_text())['settings']['policy']['operations']
    stages={p['stage']:p for p in L.paths()['saved']}
    rows=[]
    for s in fit['stages']:
        receipt=json.loads((folder/'local'/f"{s['stage']}.json").read_text())
        trials=receipt['trials'];status=Counter(t['status'] for t in trials)
        op=next(o for o in ops if o['label']==s['stage'])
        rows.append(dict(stage=s['stage'],frequencies_ghz=[f/1e9 for f in op['stage']['frequencies_hz']],
                         update_band=s['M'],accepted_steps=s['accepted_steps'],stop=s['stop'],
                         loss_in=s['initial_loss'],loss_out=s['final_loss'],
                         permittivity_in=s['entry_contrast'],permittivity_out=s['contrast'],
                         radius_mm=stages[s['stage']]['radius_mm'],centre_mm=stages[s['stage']]['centre_mm'],
                         area_repaired=stages[s['stage']]['area_repaired'],proposals=s['geometry_proposals'],
                         recorded_trials=len(trials),refused=len(trials)-status['accepted'],trial_status=dict(status),work_units=s['work']['work_units']))
    out=L.OUT;out.mkdir(parents=True,exist_ok=True)
    (out/'saved_stage_table.json').write_text(json.dumps(dict(rows=rows,used=fit['fit_and_localization_units'],cap=13412),indent=2)+'\n')
    lines=['| Stage | GHz | Band | Steps | Stop | Loss in → out | ε in → out | Radius mm | Centre mm | Trials / refused | Cumulative units |',
           '|---|---|---:|---:|---|---|---|---:|---|---:|---:|']
    for r in rows:
        c=r['centre_mm'];fs=r['frequencies_ghz'];freq='1' if len(fs)==1 else f'1–{int(fs[-1])}'
        lines.append(f"| {r['stage']} | {freq} | {r['update_band']} | {r['accepted_steps']} | {r['stop']} | {r['loss_in']:.6f} → {r['loss_out']:.6f} | {r['permittivity_in']:.4f} → {r['permittivity_out']:.4f} | {r['radius_mm']:.3f} | ({c[0]:.3f}, {c[1]:.3f}) | {r['recorded_trials']} / {r['refused']} | {r['work_units']} |")
    (out/'saved_stage_table.md').write_text('\n'.join(lines)+'\n')
    print(f"Saved stage table: {fit['fit_and_localization_units']} / 13412 units")

if __name__=='__main__':main()
