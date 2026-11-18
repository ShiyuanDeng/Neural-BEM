# Ten-frequency data record

Updated 2026-11-18T11:30:04Z.

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

## star

State: frozen.

[Checks](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/star/checks.json).

| Old GHz | Generated and final row bytes equal parent | Block SHA-256 |
|---:|---|---|
| 0.5 | True | 4f4ef6c852ebd9207e01667ceeeb24766d1f7beac398779cec1cf9b23ef4cb32 |
| 1 | True | 0715bba6e716969c0e738fdf2866a068fb7e08b756d466050c8767d5f305aac9 |
| 1.5 | True | 276b8ebda2694cf5279bde8f21b7d58f4909ff701667bcc7275065767d9461e6 |
| 2 | True | b8dc78fb772557342e93a185d5bef0d550a82063f24701cefbedb5288d1462cb |
| 2.5 | True | 28c4f442aa2c2f59d0cda76063f43149e4fbd1e3e2a89c17cce4019f9fe2e111 |

Table SHA-256: `996cb443c4a46939e574a6b73702c77209c451395bb98ede7c00923c2047b788`.
[Manifest](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/star/manifest.json).

## kite

State: frozen.

[Checks](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/kite/checks.json).

| Old GHz | Generated and final row bytes equal parent | Block SHA-256 |
|---:|---|---|
| 0.5 | True | e13c9d2b607f91392f4e9b6f56166fdd5463e2aa3f8eba6e83180f7208482362 |
| 1 | True | 632af2c5d7d1c45a56965c9f5f5172759973fd06c3f0fcad3d535cc5ecce9741 |
| 1.5 | True | d83ae327a18c829c86611bab4cc916ce24a580b11864ca53ae61858cadab5779 |
| 2 | True | 234809859eee06a65a108ed798fc3e8dd01f9b21120a3c962a75a41fc840271e |
| 2.5 | True | a7b2aa835fa3f7d29975a0b7af39068ff96b8bbba8fc4c246050aaf403dc66b6 |

Table SHA-256: `25aa94f9b02b2107b2c845aff05af6b768abda2835e43e4216bc738f95acdf09`.
[Manifest](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/kite/manifest.json).

## hook

State: frozen.

[Checks](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/hook/checks.json).

| Old GHz | Generated and final row bytes equal parent | Block SHA-256 |
|---:|---|---|
| 0.5 | True | 2eb403034a2058c2b4a0ca28353211c12707d557122e9a3ab00d6ba69dfce655 |
| 1 | True | 396995b131e1d80be6733b1eb31c57b3754c57178434f258854eec7f6605eef6 |
| 1.5 | True | 8b65b426e4f2625bb3332eb059265a5943821a72d384fada54212a988a213c9c |
| 2 | True | ede6f7ad2bea62eb8be0413ff2ea2b4b8fd53b44bb7947b22c8e3c69478f34c8 |
| 2.5 | True | f46c786e1a2efc958b6c195260adce3164eb13679bf0f84b95379d6ddfc032b4 |

Table SHA-256: `fc8c20a8a9687f6eb5cd685bf51fbca558175e86551d45fa3e7c7f6bba96f6c7`.
[Manifest](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/hook/manifest.json).

## peanut

State: frozen.

[Checks](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/peanut/checks.json).

| Old GHz | Generated and final row bytes equal parent | Block SHA-256 |
|---:|---|---|
| 0.5 | True | c12dae2c24e626b2fba38152ff45139ddbcc87bc7e19013ef8aef636a5ad8da5 |
| 1 | True | c56b646b684e1b82ce0bc957b8565f5f330596ec73aa326462f72dd61a8b3a98 |
| 1.5 | True | 15a9929db2c483918bad505305da53f59f44acb13b1197ec3d391e9a7c42d6f2 |
| 2 | True | bfb93e4e6ef66b7cedbe73038d6e166312c9dc6895004f646b3e30f3ec830a34 |
| 2.5 | True | 2cc420808d16e25d39bfb4791ed06e7a3e2077c82a239b78ae5d899252c2e3e0 |

Table SHA-256: `4486f9f831eba3b59cf8d5e0b400000ef47dd4967849968829bbcc531740daa8`.
[Manifest](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/peanut/manifest.json).

## asymmetric

State: frozen.

[Checks](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/asymmetric/checks.json).

| Old GHz | Generated and final row bytes equal parent | Block SHA-256 |
|---:|---|---|
| 0.5 | True | a838166002bfd98d0313ac0d4bc442fcaa1059edadbfeae2d5059ba25a5efa2d |
| 1 | True | abcdd699d1610b81c0ac7a7654eff6d55dad4526e1ab0f6c6d43f441d504328f |
| 1.5 | True | d448235883ad2255eee4b6ee2ea782add641e0c22365b3a27ad0851ebdbbb91d |
| 2 | True | 394afbe6aeeebc269c90c8ce3c12183f51400866b169c2af28f4308b1763792f |
| 2.5 | True | 8a724759cabf97fa25bcff6a123848bac8f2b32a4a3462368739c717aabb2051 |

Table SHA-256: `e4e902e12e666274fe601aff55fd2279fd9b6458364d62ddc49f594b7570195f`.
[Manifest](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/asymmetric/manifest.json).

