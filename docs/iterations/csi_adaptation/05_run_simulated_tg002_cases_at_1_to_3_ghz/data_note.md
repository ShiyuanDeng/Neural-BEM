# Frozen 1–3 GHz data for the BEM side

Available: 4/10 complete parent tables. Updated 2026-11-18T01:34:55.007239+00:00.
All full parent tables use the unchanged 0.625 mm generator, contrast 4, eight frequencies.
Fixed parent pattern: results/csi/tg002/2026-11-18_low_band_data/{shape}/forward/synthetic_input.txt.
A .sha256 sidecar is beside every parent table. The BEM side reads only.
The main comparison uses column 3 in {1,2,3}: one-based parent rows 8*j+f, j=0..1763, f=1,2,3.
These 5292 rows are interleaved, 1764 per frequency; they are not the first 5292 rows.
Selected files retain exact parent line bytes. Their SHA-256 and parent SHA-256 are recorded below.
Fields use exp(+j omega t); BEM conjugates once. Sources, pair order and 49-per-source mask are unchanged.
CSI will read these full parents with native fre=1:3. It will never regenerate a table.
BEM independently checks every true shape on these exact data; the circle check covers the circle only.

## circle

Parent: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band_data/circle/forward/synthetic_input.txt`.
Parent SHA-256: `34ed9276fb6680d01ff6e7a7c26c8d19fb70fe5df4dbe1a81de39e025924cefe`.
Selected: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band_data/circle/selected/synthetic_input.txt`.
Selected SHA-256: `756379d9063de8b4ea6359785062798ac05a6b85b57b487d686066307728e4a6`.

## kite

Parent: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band_data/kite/forward/synthetic_input.txt`.
Parent SHA-256: `93128bd3b0b0b36c53338c6f83342d4e330461a4304758ec175a3a359759b509`.
Selected: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band_data/kite/selected/synthetic_input.txt`.
Selected SHA-256: `09728581b51758049cf4546b83d26cb87cd51d1427197bbf023bfc9960c064a9`.

## peanut

Parent: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band_data/peanut/forward/synthetic_input.txt`.
Parent SHA-256: `2bab1e12b87839fe0263428b163e2905b4db8615620a57ee78ee08bc8d07c13c`.
Selected: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band_data/peanut/selected/synthetic_input.txt`.
Selected SHA-256: `27615d07715bd3100ec4dc011395565bcde5fae174d3e2d6b11c165939f877b4`.

## star

Parent: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band_data/star/forward/synthetic_input.txt`.
Parent SHA-256: `fc14e91b1e8a09b1ef33d7604659703a5ba738b4748a68a1938ea40d60bd0ed4`.
Selected: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band_data/star/selected/synthetic_input.txt`.
Selected SHA-256: `3c297c7e3b944118ea0daf4fcb556a98b5a1f914fb1e73ce30fa03799434f85e`.

