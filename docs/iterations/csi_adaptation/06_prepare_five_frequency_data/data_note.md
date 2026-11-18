# Shared five-frequency frozen observations

Updated 2026-11-18T04:02:34Z.

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

## kite

Path: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_five_frequency_data/kite/forward/synthetic_input.txt`.
SHA-256: `e827e20acc02391b185175ae2b7b2f10e10bf7ee4de493586c0fe60aa91769c7`.
Parent SHA-256: `93128bd3b0b0b36c53338c6f83342d4e330461a4304758ec175a3a359759b509`.
Checks: 8820 finite rows; exact pair order, mask and copied line bytes; maximum native residual 3.0493e-12; maximum reproduction relative L2 0.
Evidence: [manifest](../../../../results/csi/tg002/2026-11-18_five_frequency_data/kite/manifest.json), [checks](../../../../results/csi/tg002/2026-11-18_five_frequency_data/kite/checks.json).

## peanut

Path: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_five_frequency_data/peanut/forward/synthetic_input.txt`.
SHA-256: `debf658e6c4542a5760c42cfd00129851e01c6dd5480ca94a4f3930bad19736d`.
Parent SHA-256: `2bab1e12b87839fe0263428b163e2905b4db8615620a57ee78ee08bc8d07c13c`.
Checks: 8820 finite rows; exact pair order, mask and copied line bytes; maximum native residual 3.75625e-12; maximum reproduction relative L2 0.
Evidence: [manifest](../../../../results/csi/tg002/2026-11-18_five_frequency_data/peanut/manifest.json), [checks](../../../../results/csi/tg002/2026-11-18_five_frequency_data/peanut/checks.json).

## star

Path: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_five_frequency_data/star/forward/synthetic_input.txt`.
SHA-256: `243dc047b84693446216afa9435fa03e2da3cf1611b1e1cddcebbd5f8e64c637`.
Parent SHA-256: `fc14e91b1e8a09b1ef33d7604659703a5ba738b4748a68a1938ea40d60bd0ed4`.
Checks: 8820 finite rows; exact pair order, mask and copied line bytes; maximum native residual 4.24142e-12; maximum reproduction relative L2 0.
Evidence: [manifest](../../../../results/csi/tg002/2026-11-18_five_frequency_data/star/manifest.json), [checks](../../../../results/csi/tg002/2026-11-18_five_frequency_data/star/checks.json).

## asymmetric

Path: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_five_frequency_data/asymmetric/forward/synthetic_input.txt`.
SHA-256: `52c0716dcb16fc7771177074fcde3d468d6b7505e7be920f0dd2edd2c0d6db70`.
Parent SHA-256: `89926a60b42ac003c1090c3f72324533adbc3a021259f16b04fc563bf5e7e37e`.
Checks: 8820 finite rows; exact pair order, mask and copied line bytes; maximum native residual 4.15986e-12; maximum reproduction relative L2 0.
Evidence: [manifest](../../../../results/csi/tg002/2026-11-18_five_frequency_data/asymmetric/manifest.json), [checks](../../../../results/csi/tg002/2026-11-18_five_frequency_data/asymmetric/checks.json).

## c_shape

Path: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_five_frequency_data/c_shape/forward/synthetic_input.txt`.
SHA-256: `b7916978d3f619b1e6553e9e663e2636b721b9d48cac2ec1c846cd0cb1b8594c`.
Parent SHA-256: `d7b81094a097094c74be584ceda7869017e34ba42cb7659ce0c27d8388b7315b`.
Checks: 8820 finite rows; exact pair order, mask and copied line bytes; maximum native residual 3.90935e-12; maximum reproduction relative L2 0.
Evidence: [manifest](../../../../results/csi/tg002/2026-11-18_five_frequency_data/c_shape/manifest.json), [checks](../../../../results/csi/tg002/2026-11-18_five_frequency_data/c_shape/checks.json).

