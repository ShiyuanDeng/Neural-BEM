"""Activity 09 thin entry point: change only the table and result paths."""
from csi_runtime import ROOT
import csi_data
import csi_fit

csi_data.SIMULATED = 'results/bem/baseline_data/fresnel_own_forward/2026-11-18/data/{shape}/synthetic_input.txt'
csi_fit.RESULTS = ROOT/'results/bem/baseline_data/fresnel_own_forward/2026-11-18'

if __name__ == '__main__':
    csi_fit.main()
