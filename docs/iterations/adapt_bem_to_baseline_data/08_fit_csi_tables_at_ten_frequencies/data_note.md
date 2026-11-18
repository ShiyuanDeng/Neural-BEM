# Ten-frequency data record

Updated 2026-11-18T11:25:42Z.

Same CSI forward, grid, material, source, calibration and receiver code as the frozen five-frequency run.
Only pair-template size and the frequency list differ in the MATLAB driver.
Columns: source, receiver, GHz, total real/imaginary, incident real/imaginary.
17640 rows; 1764 pairs; 36 sources, 49 measured receivers each.
Within each pair: 0.25 to 2.5 GHz in 0.25 GHz steps. Row: i+10*j, i=1..10, j=0..1763.
Sign exp(+j omega t); BEM conjugates once. Old rows are proved equal before copying.

## circle

State: frozen.

[Checks](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/circle/checks.json).

| Old GHz | Generated and final row bytes equal parent | Block SHA-256 |
|---:|---|---|
| 0.5 | True | 418b4351452bd721f419b2f1c6633971566bdaa576d8a7b26c9d5aa556e9d166 |
| 1 | True | 85042bdd14d20609c0e00ad788b42492034c309436db890a067eb0ce05ebcbb7 |
| 1.5 | True | 18985e5f57388a51d54ad2e07061d8db5b4b1382228cbb16158346de8f40e74a |
| 2 | True | 7eb95318e02c253cbeb9a637a5a0569df81ef9d49e06e613cf2c20c454d434eb |
| 2.5 | True | 05430e8545f4bcce6cd03503fe1fd03dc4e08ac7bc416dba293817e4c384a8ba |

| GHz | Error / table (%) | Error / exact (%) |
|---:|---:|---:|
| 0.25 | 0.24550332 | 0.24495693 |
| 0.5 | 0.44203362 | 0.44397601 |
| 0.75 | 0.30516025 | 0.30470577 |
| 1 | 0.17232596 | 0.17237011 |
| 1.25 | 0.18825964 | 0.18800476 |
| 1.5 | 0.13467985 | 0.13462665 |
| 1.75 | 0.19590215 | 0.19577067 |
| 2 | 0.12604902 | 0.12599062 |
| 2.25 | 0.22663147 | 0.22660167 |
| 2.5 | 0.17672086 | 0.17656380 |

Table SHA-256: `c92b8da4a63dfd6bd0a7ec36543ce1476f7f518b10ffa0d28e694e6793b3a037`.
[Manifest](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/circle/manifest.json).

