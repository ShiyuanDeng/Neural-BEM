# Shared five-frequency frozen observations

Updated 2026-11-18T03:59:55Z.

Column order: source index, receiver index, GHz, total real, total imaginary, incident real, incident imaginary.
1764 source–receiver pairs; 36 sources and 49 receivers per source. Seven columns, %.16e format.
Per pair: 0.5, 1, 1.5, 2, 2.5 GHz, in that order; one-based rows 5*j+i, j=0..1763, i=1..5.
Pair order and mask equal the frozen parent. The 1 and 2 GHz lines are exact parent bytes.
Sign convention: exp(+j omega t); BEM conjugates scattered fields once.
Both methods read these same files by SHA-256. BEM true-shape checks are separate from this data freeze.

## circle

Path: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_five_frequency_data/circle/forward/synthetic_input.txt`.
SHA-256: `43b641d73118c4fcc7a319e20b59be9ce70293252403f8c783a1f670a30f3f80`.
Parent SHA-256: `34ed9276fb6680d01ff6e7a7c26c8d19fb70fe5df4dbe1a81de39e025924cefe`.
Checks: 8820 finite rows; exact pair order, mask and copied line bytes; maximum native residual 4.29283e-12; maximum reproduction relative L2 0.
Evidence: [manifest](../../../../results/csi/tg002/2026-11-18_five_frequency_data/circle/manifest.json), [checks](../../../../results/csi/tg002/2026-11-18_five_frequency_data/circle/checks.json).

| GHz | Error / table (%) | Error / exact (%) |
|---:|---:|---:|
| 0.5 | 0.44203362 | 0.44397601 |
| 1 | 0.17232596 | 0.17237011 |
| 1.5 | 0.13467985 | 0.13462665 |
| 2 | 0.12604902 | 0.12599062 |
| 2.5 | 0.17672086 | 0.17656380 |

