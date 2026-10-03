"""Render saved endpoints only; never called by the fitting algorithm."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from experiments.cleaned_interface import benchmark as b
from experiments.cleaned_interface.fm002 import CASES, OUTPUT
from experiments.cleaned_interface.io import read, curve_from, digest, write


def main():
    arms = ('D0','D1','R0','R1')
    titles = ('Damping, ordinary loss', 'Damping + relaxation',
              'Real prefix, ordinary loss', 'Real prefix + relaxation')
    fig, axes = plt.subplots(len(CASES), len(arms), figsize=(14, 10), constrained_layout=True)
    receipts = {}
    for row_index, case in enumerate(CASES):
        row = next(r for r in b.descriptors() if r['id']==case)
        target = b.ROOT/row['truth']
        truth = curve_from(read(target)).values(2048)*50
        results = [OUTPUT/'runs'/case/arm/'result.json' for arm in arms]
        curves = [curve_from(read(p)['final_curve']).values(2048)*50 for p in results]
        all_points = np.concatenate([truth, *curves])
        xmid = (all_points.real.min()+all_points.real.max())/2
        ymid = (all_points.imag.min()+all_points.imag.max())/2
        half = .56*max(np.ptp(all_points.real),np.ptp(all_points.imag))
        receipts[str(target.relative_to(b.ROOT))] = digest(target)
        for column, (arm, path, curve) in enumerate(zip(arms, results, curves)):
            d = read(path)
            receipts[str(path.relative_to(b.ROOT))] = digest(path)
            ax = axes[row_index,column]
            ax.plot(truth.real,truth.imag,color='#1c2635',lw=2)
            ax.plot(curve.real,curve.imag,color='#148567' if d['recovered'] else '#c74936',lw=1.7,ls='--')
            ax.set_aspect('equal')
            ax.set_xlim(xmid-half,xmid+half)
            ax.set_ylim(ymid-half,ymid+half)
            ax.grid(alpha=.2)
            if row_index==0:
                ax.set_title(titles[column],fontsize=11)
            if column==0:
                ax.set_ylabel(case.removeprefix('modal__').replace('__',' / ')+'\ny (mm)',fontsize=10)
            ax.set_xlabel(f"RMS {d['metrics']['rms_mm']:.4g} mm · {'recovered' if d['recovered'] else 'not recovered'}\nx (mm)",fontsize=9)
    fig.suptitle('Corrected relaxed-BIE comparison — three cases, four fixed arms',fontsize=15)
    fig.legend(handles=[Line2D([0],[0],color='#1c2635',lw=2,label='True boundary'),
        Line2D([0],[0],color='#148567',ls='--',label='Recovered endpoint'),
        Line2D([0],[0],color='#c74936',ls='--',label='Unrecovered endpoint')],
        loc='outside lower center',ncol=3,frameon=False)
    path=OUTPUT/'endpoints.png'
    fig.savefig(path,dpi=160)
    plt.close(fig)
    write(OUTPUT/'plot_receipt.json',dict(inputs=receipts,plot_sha256=digest(path),
        script_sha256=digest(Path(__file__)), units='mm relative to shared physical origin; same limits within each row'))


if __name__=='__main__':
    main()
