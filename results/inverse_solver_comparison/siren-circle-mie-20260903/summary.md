# Solver-neutral implicit-initialization inverse comparison

A `siren_neural_implicit` field initialized with `network.network.0.linear.weight[0,0]=0.143894, network.network.0.linear.weight[0,1]=0.127155, network.network.0.linear.weight[1,0]=-0.209602, network.network.0.linear.weight[1,1]=-0.9464, network.network.0.linear.weight[2,0]=1.33858, network.network.0.linear.weight[2,1]=-0.245667, network.network.0.linear.weight[3,0]=-0.158356, network.network.0.linear.weight[3,1]=-0.11013, network.network.0.linear.weight[4,0]=-1.26098, network.network.0.linear.weight[4,1]=-0.213627, network.network.0.linear.weight[5,0]=-0.868509, network.network.0.linear.weight[5,1]=-0.552306, network.network.0.linear.weight[6,0]=-0.185205, network.network.0.linear.weight[6,1]=0.691966, network.network.0.linear.weight[7,0]=-0.647939, network.network.0.linear.weight[7,1]=0.662822, network.network.0.linear.weight[8,0]=-0.265915, network.network.0.linear.weight[8,1]=0.156948, network.network.0.linear.weight[9,0]=1.04537, network.network.0.linear.weight[9,1]=-0.776259, network.network.0.linear.weight[10,0]=-8.90511e-10, network.network.0.linear.weight[10,1]=-8.56685e-10, network.network.0.linear.weight[11,0]=0.0495341, network.network.0.linear.weight[11,1]=0.108609, network.network.0.linear.weight[12,0]=-0.0332765, network.network.0.linear.weight[12,1]=0.0230464, network.network.0.linear.weight[13,0]=-0.396201, network.network.0.linear.weight[13,1]=0.27322, network.network.0.linear.weight[14,0]=-0.257572, network.network.0.linear.weight[14,1]=-1.42505, network.network.0.linear.weight[15,0]=0.025418, network.network.0.linear.weight[15,1]=-0.165922, network.network.0.linear.weight[16,0]=0.0468235, network.network.0.linear.weight[16,1]=-0.157432, network.network.0.linear.weight[17,0]=-1.64557e-16, network.network.0.linear.weight[17,1]=1.51326e-16, network.network.0.linear.weight[18,0]=-0.452123, network.network.0.linear.weight[18,1]=-0.398654, network.network.0.linear.weight[19,0]=0.241884, network.network.0.linear.weight[19,1]=0.0217443, network.network.0.linear.weight[20,0]=0.850457, network.network.0.linear.weight[20,1]=-0.26976, network.network.0.linear.weight[21,0]=-0.0196691, network.network.0.linear.weight[21,1]=0.166701, network.network.0.linear.weight[22,0]=0.740265, network.network.0.linear.weight[22,1]=0.119303, network.network.0.linear.weight[23,0]=0.331397, network.network.0.linear.weight[23,1]=0.0567164, network.network.0.linear.weight[24,0]=-0.100532, network.network.0.linear.weight[24,1]=-0.470356, network.network.0.linear.weight[25,0]=0.178253, network.network.0.linear.weight[25,1]=-0.0885693, network.network.0.linear.weight[26,0]=0.250857, network.network.0.linear.weight[26,1]=-1.19089, network.network.0.linear.weight[27,0]=-1.26086, network.network.0.linear.weight[27,1]=-0.734988, network.network.0.linear.weight[28,0]=-0.112642, network.network.0.linear.weight[28,1]=0.187234, network.network.0.linear.weight[29,0]=0.161628, network.network.0.linear.weight[29,1]=-0.0903692, network.network.0.linear.weight[30,0]=0.0155247, network.network.0.linear.weight[30,1]=-0.246447, network.network.0.linear.weight[31,0]=-0.115151, network.network.0.linear.weight[31,1]=-0.466058, network.network.0.linear.bias[0]=-0.142101, network.network.0.linear.bias[1]=-0.0891789, network.network.0.linear.bias[2]=-0.330952, network.network.0.linear.bias[3]=-0.456557, network.network.0.linear.bias[4]=-0.23979, network.network.0.linear.bias[5]=-0.191196, network.network.0.linear.bias[6]=-0.55207, network.network.0.linear.bias[7]=0.037744, network.network.0.linear.bias[8]=-0.485037, network.network.0.linear.bias[9]=-0.00161173, network.network.0.linear.bias[10]=0.471239, network.network.0.linear.bias[11]=-0.175994, network.network.0.linear.bias[12]=0.496896, network.network.0.linear.bias[13]=0.0963085, network.network.0.linear.bias[14]=-0.368329, network.network.0.linear.bias[15]=0.47131, network.network.0.linear.bias[16]=-0.125444, network.network.0.linear.bias[17]=-0.15708, network.network.0.linear.bias[18]=0.464183, network.network.0.linear.bias[19]=-0.453412, network.network.0.linear.bias[20]=-0.0546715, network.network.0.linear.bias[21]=-0.156728, network.network.0.linear.bias[22]=0.208439, network.network.0.linear.bias[23]=0.0889785, network.network.0.linear.bias[24]=0.0723343, network.network.0.linear.bias[25]=0.0961728, network.network.0.linear.bias[26]=-0.346411, network.network.0.linear.bias[27]=-0.206319, network.network.0.linear.bias[28]=-0.500997, network.network.0.linear.bias[29]=0.260196, network.network.0.linear.bias[30]=0.410146, network.network.0.linear.bias[31]=0.23095, network.network.1.weight[0,0]=0.112801, network.network.1.weight[0,1]=0.0100055, network.network.1.weight[0,2]=-0.00329433, network.network.1.weight[0,3]=-0.0957421, network.network.1.weight[0,4]=0.00331844, network.network.1.weight[0,5]=0.00750149, network.network.1.weight[0,6]=-0.0164007, network.network.1.weight[0,7]=-0.00699505, network.network.1.weight[0,8]=0.025679, network.network.1.weight[0,9]=0.00313565, network.network.1.weight[0,10]=-0.262399, network.network.1.weight[0,11]=0.0669632, network.network.1.weight[0,12]=-0.216886, network.network.1.weight[0,13]=-0.0441159, network.network.1.weight[0,14]=-0.00377578, network.network.1.weight[0,15]=0.119748, network.network.1.weight[0,16]=0.119524, network.network.1.weight[0,17]=-0.278962, network.network.1.weight[0,18]=0.0202593, network.network.1.weight[0,19]=-0.228516, network.network.1.weight[0,20]=0.00942166, network.network.1.weight[0,21]=0.135066, network.network.1.weight[0,22]=-0.0164256, network.network.1.weight[0,23]=0.00810354, network.network.1.weight[0,24]=-0.0151375, network.network.1.weight[0,25]=-0.0743428, network.network.1.weight[0,26]=-0.00401147, network.network.1.weight[0,27]=0.00308859, network.network.1.weight[0,28]=-0.115892, network.network.1.weight[0,29]=-0.0617626, network.network.1.weight[0,30]=-0.0158485, network.network.1.weight[0,31]=-0.0355305, network.network.1.bias=0.224169` was fit to independent analytic Mie scattered-field data for the true `(0.50, 0.50) m`, radius `0.050 m` cylinder.

MOD and Kress received the same ordered Method-B boundary at each parameter evaluation and used the same bounded central-FD damped Gauss--Newton inverse. Only the forward solver differed.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Max node-to-boundary (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MOD | 9.232e-01 | 3.657e-01 | 6.489e+00x | 1.142e+00 | 7.302e-02 | 11.4505 | 4.4313 | 22.2987 | 414.80 s |
| KRESS | 9.238e-01 | 3.344e-01 | 7.543e+00x | 1.035e+00 | 8.195e-14 | 8.1859 | 8.5352 | 17.9750 | 271.00 s |

MOD: `maximum_iterations` after 10 accepted updates / 2911 forward evaluations; KRESS: `maximum_iterations` after 10 accepted updates / 2931 forward evaluations.

With MOD at 2911 inverse evaluations and KRESS at 2931 inverse evaluations, MOD/Kress wall time was `1.53x`; the final held-out MOD/Kress error ratio was `1.103e+00x`.

Training frequencies: 0.25 GHz, 0.5 GHz. Holdout frequencies: 1 GHz, 1.5 GHz, 2.5 GHz.

Observations: gpr_bem_ref analytic penetrable-cylinder Mie series.

## Acceptance

- **FAIL** `mod_optimizer_converged`: value `maximum_iterations`, required `converged stop condition`.
- **PASS** `mod_accepted_losses_monotone`: value `True`, required `True`.
- **FAIL** `mod_training_loss_drop`: value `6.488545129036182`, required `>= 100`.
- **FAIL** `mod_boundary_error_within_representation`: value `{'final': 0.022298677548580753, 'floor': 0.0018003087631495093}`, required `<= 2x the same network fitted to the exact target`.
- **FAIL** `mod_boundary_error_improved`: value `{'final': 0.022298677548580753, 'initial': 0.04045005862029351}`, required `<= 0.25x the initial contour error`.
- **FAIL** `mod_holdout_within_representation`: value `{'final': 1.1416698321111165, 'floor': 0.16087513932885797}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `mod_linear_system_residual`: value `7.857041666078413e-15`, required `<= 1e-10`.
- **FAIL** `mod_holdout_relative_l2`: value `1.1416698321111165`, required `<= 0.15`.
- **PASS** `mod_warm_start_is_eikonal`: value `0.1331928414560244`, required `<= 0.25`.
- **FAIL** `kress_optimizer_converged`: value `maximum_iterations`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **FAIL** `kress_training_loss_drop`: value `7.543112315966995`, required `>= 100`.
- **FAIL** `kress_boundary_error_within_representation`: value `{'final': 0.01797497321858174, 'floor': 0.0018003087631495093}`, required `<= 2x the same network fitted to the exact target`.
- **FAIL** `kress_boundary_error_improved`: value `{'final': 0.01797497321858174, 'initial': 0.04045005862029351}`, required `<= 0.25x the initial contour error`.
- **FAIL** `kress_holdout_within_representation`: value `{'final': 1.034855469980506, 'floor': 0.1482692932061453}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_linear_system_residual`: value `6.299380352012257e-15`, required `<= 1e-10`.
- **FAIL** `kress_holdout_relative_l2`: value `1.034855469980506`, required `<= 0.15`.
- **PASS** `kress_warm_start_is_eikonal`: value `0.1331928414560244`, required `<= 0.25`.
- **PASS** `kress_holdout_beats_mod`: value `{'kress': 1.034855469980506, 'mod': 1.1416698321111165}`, required `Kress < MOD`.
- **PASS** `kress_target_geometry_holdout_beats_mod`: value `{'kress': 8.195004317091178e-14, 'mod': 0.07302406119319439}`, required `Kress < MOD on the identical true boundary`.
- **PASS** `common_initial_boundary_identical`: value `0.0`, required `<= 1e-14 m`.
- **PASS** `common_target_boundary_identical`: value `0.0`, required `<= 1e-14 m`.

Overall: **FAIL**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --initial-model siren_circle --max-iterations 10 --output-dir results/inverse_solver_comparison/siren-circle-mie-20260903 --overwrite
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

This establishes an auditable low-dimensional inverse baseline for smooth single-component Torch implicit fields. The field-to-curve seam crosses NumPy and is not autograd-differentiable. A large randomly initialized SIREN therefore needs a topology-valid initialization and derivatives of the actual Kress weighted operators before it is a scalable inverse.
