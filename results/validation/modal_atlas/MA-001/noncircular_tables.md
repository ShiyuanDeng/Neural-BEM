# MA-001 part B tables

## Qualification

| State | modal vs nodal (512/1024) | 512 vs 1024 | nodal vs production | truncation bound |
|---|---:|---:|---:|---|
| end/A_hybrid/circle_to_star | 1.2e-14 / 9.1e-15 | 1.9e-14 | 6.0e-16 | holds |
| end/A_hybrid/kite | 2.7e-08 / 3.1e-08 | 1.4e-07 | 6.0e-16 | holds |
| end/E_wider_ladder/circle_to_star | 1.3e-14 / 8.2e-15 | 1.8e-14 | 5.9e-16 | holds |
| end/F_released_m/circle_to_c | 3.3e-09 / 3.3e-09 | 3.2e-09 | 6.0e-16 | holds |
| end/F_released_m/kite | 6.2e-06 / 6.0e-06 | 7.5e-04 | 6.0e-16 | VIOLATED |
| end/G_fixed_m9/kite | 8.3e-09 / 8.3e-09 | 8.1e-10 | 5.8e-16 | holds |
| truth/circle_to_c | 1.2e-14 / 8.8e-15 | 7.7e-15 | 6.0e-16 | holds |
| truth/circle_to_star | 5.4e-11 / 5.4e-11 | 1.7e-14 | 6.1e-16 | holds |
| truth/hook | 1.3e-14 / 9.4e-15 | 1.3e-14 | 6.1e-16 | holds |
| truth/kite | 6.5e-11 / 6.5e-11 | 9.8e-15 | 5.9e-16 | holds |
| truth/peanut | 1.3e-14 / 9.2e-15 | 8.5e-15 | 6.1e-16 | holds |

## Frontier and trace band at 0.25 / 1.25 / 2.5 GHz

Frontier: highest p with column norm >= tau x strongest column. `K_U+K_V(eps)`: combined trace support at relative coefficient level eps. Trace K(1e-6): projected band giving every trace to 1e-6. J K(1e-6): projected band giving column p to 1e-6 of the strongest column.

| State | GHz | kL/2pi | K_U+K_V (1e-1 / 1e-2) | frontier (1e-2 / 1e-3 / 1e-4) | trace K (1e-3 / 1e-6) | J K(1e-6) at p=0/10/20 | endpoint M |
|---|---:|---:|---|---|---|---|---:|
| end/A_hybrid/circle_to_star | 0.25 | 0.84 | 2 / 14 | 9 / 16 / 29 | 14 / 55 | 14 / 19 / 29 | 9 |
| end/A_hybrid/circle_to_star | 1.25 | 4.20 | 18 / 30 | 20 / 31 / 43 | 23 / 67 | 22 / 28 / 35 | 9 |
| end/A_hybrid/circle_to_star | 2.5 | 8.40 | 28 / 42 | 32 / 41 / 52 | 31 / 74 | 29 / 34 / 40 | 9 |
| end/A_hybrid/kite | 0.25 | 0.50 | 2 / 8 | 7 / 14 / 42 | 19 / 160 | 18 / 23 / 29 | 9 |
| end/A_hybrid/kite | 1.25 | 2.48 | 8 / 22 | 17 / 40 / 80 | 41 / 160 | 42 / 47 / 54 | 9 |
| end/A_hybrid/kite | 2.5 | 4.95 | 16 / 34 | 26 / 57 / 80 | 55 / 160 | 59 / 64 / 69 | 9 |
| end/E_wider_ladder/circle_to_star | 0.25 | 0.84 | 2 / 14 | 9 / 16 / 27 | 14 / 46 | 14 / 19 / 26 | 9 |
| end/E_wider_ladder/circle_to_star | 1.25 | 4.20 | 18 / 30 | 20 / 28 / 40 | 21 / 55 | 21 / 27 / 34 | 9 |
| end/E_wider_ladder/circle_to_star | 2.5 | 8.40 | 28 / 42 | 32 / 41 / 52 | 28 / 63 | 27 / 32 / 39 | 9 |
| end/F_released_m/circle_to_c | 0.25 | 0.86 | 4 / 12 | 8 / 14 / 26 | 11 / 152 | 10 / 18 / 26 | 19 |
| end/F_released_m/circle_to_c | 1.25 | 4.29 | 14 / 26 | 18 / 27 / 58 | 21 / 160 | 21 / 28 / 35 | 19 |
| end/F_released_m/circle_to_c | 2.5 | 8.58 | 24 / 38 | 30 / 41 / 80 | 33 / 160 | 34 / 40 / 46 | 19 |
| end/F_released_m/kite | 0.25 | 0.48 | 2 / 8 | 6 / 19 / 29 | 19 / 160 | None / 20 / 25 | 19 |
| end/F_released_m/kite | 1.25 | 2.39 | 8 / 20 | 17 / 30 / 80 | 59 / 160 | None / None / 80 | 19 |
| end/F_released_m/kite | 2.5 | 4.77 | 14 / 34 | 27 / 43 / 80 | 119 / 160 | None / None / None | 19 |
| end/G_fixed_m9/kite | 0.25 | 0.48 | 2 / 8 | 5 / 13 / 33 | 15 / 157 | 13 / 21 / 27 | 9 |
| end/G_fixed_m9/kite | 1.25 | 2.38 | 8 / 24 | 16 / 33 / 63 | 32 / 160 | 33 / 38 / 45 | 9 |
| end/G_fixed_m9/kite | 2.5 | 4.75 | 14 / 32 | 23 / 46 / 80 | 41 / 160 | 44 / 49 / 54 | 9 |
| truth/circle_to_c | 0.25 | 0.86 | 4 / 12 | 8 / 14 / 21 | 11 / 40 | 10 / 18 / 25 |  |
| truth/circle_to_c | 1.25 | 4.29 | 14 / 26 | 18 / 27 / 36 | 21 / 51 | 21 / 25 / 30 |  |
| truth/circle_to_c | 2.5 | 8.58 | 24 / 38 | 30 / 39 / 49 | 27 / 59 | 27 / 31 / 37 |  |
| truth/circle_to_star | 0.25 | 0.85 | 2 / 14 | 9 / 24 / 49 | 24 / 114 | 24 / 29 / 34 |  |
| truth/circle_to_star | 1.25 | 4.24 | 18 / 30 | 24 / 46 / 76 | 35 / 135 | 38 / 43 / 48 |  |
| truth/circle_to_star | 2.5 | 8.48 | 28 / 52 | 34 / 59 / 80 | 46 / 146 | 51 / 56 / 61 |  |
| truth/hook | 0.25 | 0.83 | 4 / 10 | 8 / 14 / 21 | 13 / 42 | 11 / 18 / 25 |  |
| truth/hook | 1.25 | 4.16 | 14 / 28 | 20 / 28 / 37 | 21 / 51 | 21 / 27 / 32 |  |
| truth/hook | 2.5 | 8.32 | 24 / 40 | 30 / 40 / 50 | 28 / 60 | 28 / 32 / 38 |  |
| truth/kite | 0.25 | 0.48 | 2 / 8 | 6 / 16 / 37 | 18 / 110 | 16 / 22 / 27 |  |
| truth/kite | 1.25 | 2.38 | 8 / 22 | 16 / 35 / 65 | 33 / 138 | 34 / 39 / 44 |  |
| truth/kite | 2.5 | 4.76 | 14 / 34 | 24 / 51 / 80 | 42 / 150 | 43 / 49 / 54 |  |
| truth/peanut | 0.25 | 0.55 | 2 / 6 | 5 / 11 / 21 | 11 / 47 | 11 / 15 / 23 |  |
| truth/peanut | 1.25 | 2.77 | 8 / 16 | 11 / 18 / 30 | 16 / 54 | 15 / 21 / 27 |  |
| truth/peanut | 2.5 | 5.53 | 16 / 24 | 18 / 25 / 37 | 20 / 60 | 20 / 26 / 32 |  |

## Brightness decomposition, p <= frontier(1e-3), all 19 frequencies pooled per state

`log ||J_p|| = log A_p - log kappa_p`. A_p: the norm of summed pair magnitudes; kappa_p: cancellation.

| State | var log column | var log A | var log kappa | corr(log column, log A) | corr(log column, -log kappa) | median kappa | max kappa |
|---|---:|---:|---:|---:|---:|---:|---:|
| end/A_hybrid/circle_to_star | 0.944 | 0.941 | 0.021 | 0.989 | 0.229 | 2.09 | 13.8 |
| end/A_hybrid/kite | 0.903 | 0.804 | 0.009 | 0.996 | 0.617 | 2.53 | 4.4 |
| end/E_wider_ladder/circle_to_star | 0.916 | 0.936 | 0.019 | 0.990 | 0.006 | 2.07 | 14.5 |
| end/F_released_m/circle_to_c | 1.083 | 1.045 | 0.012 | 0.995 | 0.262 | 2.02 | 5.1 |
| end/F_released_m/kite | 0.850 | 0.792 | 0.009 | 0.995 | 0.383 | 2.27 | 4.4 |
| end/G_fixed_m9/kite | 0.957 | 0.868 | 0.011 | 0.996 | 0.554 | 2.54 | 4.4 |
| truth/circle_to_c | 1.040 | 1.043 | 0.012 | 0.994 | 0.059 | 1.90 | 5.1 |
| truth/circle_to_star | 1.103 | 0.936 | 0.028 | 0.990 | 0.550 | 2.70 | 9.1 |
| truth/hook | 0.940 | 1.000 | 0.010 | 0.995 | -0.149 | 1.85 | 5.4 |
| truth/kite | 0.897 | 0.814 | 0.009 | 0.996 | 0.485 | 2.38 | 4.4 |
| truth/peanut | 1.102 | 0.987 | 0.032 | 0.988 | 0.468 | 2.22 | 5.7 |

Brightness entries are medians over the 19 frequencies (max kappa: maximum).
