# Frozen 1–3 GHz data for the BEM side

Prepared read-only before launch; selected files will be written in the new campaign folder.
CSI will load each unchanged full parent table with native fre=1:3.
Select column 3 in {1,2,3}; one-based rows 8*j+f, j=0..1763, f=1,2,3.
There are 5292 selected rows, 1764 per frequency; they are interleaved, not the first 5292 parent rows.
Fields use exp(+j omega t); conjugate once for BEM. The 36-source/49-receiver mask and file pair order stay fixed.
Selected byte hashes below preserve the exact parent line text, with no float reserialization.

## circle

Parent: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-17_campaign/circle/forward/synthetic_input.txt`.
Parent SHA-256: `34ed9276fb6680d01ff6e7a7c26c8d19fb70fe5df4dbe1a81de39e025924cefe`.
Selected path after launch: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band/circle/selected/synthetic_input.txt`.
Expected selected SHA-256: `756379d9063de8b4ea6359785062798ac05a6b85b57b487d686066307728e4a6`.

## kite

Parent: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-17_campaign/kite/forward/synthetic_input.txt`.
Parent SHA-256: `93128bd3b0b0b36c53338c6f83342d4e330461a4304758ec175a3a359759b509`.
Selected path after launch: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band/kite/selected/synthetic_input.txt`.
Expected selected SHA-256: `09728581b51758049cf4546b83d26cb87cd51d1427197bbf023bfc9960c064a9`.

## peanut

Parent: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-17_campaign/peanut/forward/synthetic_input.txt`.
Parent SHA-256: `2bab1e12b87839fe0263428b163e2905b4db8615620a57ee78ee08bc8d07c13c`.
Selected path after launch: `/home/drdeng/Neural_SDF_BEM_AD_organised/results/csi/tg002/2026-11-18_low_band/peanut/selected/synthetic_input.txt`.
Expected selected SHA-256: `27615d07715bd3100ec4dc011395565bcde5fae174d3e2d6b11c165939f877b4`.

