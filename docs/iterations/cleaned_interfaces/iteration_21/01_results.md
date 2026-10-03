# FM-003 results

Frozen plan: [iteration 20](../iteration_20/03_plan.md). Existing `feature/shape-frequency-continuation` branch; production policy unchanged.

Baseline `b43fa04c2e27b6b1f7fd05eba153436f4f2e7cc0`. One worker, four frequency threads, auto device; single-threaded BLAS.

Phase L gates: **PASS**. Usable lifts: `[{'frequency_hz': 250000000.0, 'N': 2}]`.

| GHz | N | Full truncation floor | Paired residual | Full lift error | Ambiguity | Linear error |
|---|---|---|---|---|---|---|
| 0.25 | 2 | 0.00344 | 0.001371 | 0.006125 | 1.332e-08 | 0.9543 |
| 0.25 | 3 | 0.0001735 | 3.239e-06 | 0.8892 | 2.719 | 0.9804 |
| 0.25 | 4 | 1.797e-05 | 8.65e-09 | 1.757 | 3.093 | 0.998 |
| 0.5 | 2 | 0.2162 | 0.06975 | 1.317 | 1.952e-07 | 0.9823 |
| 0.5 | 3 | 0.02537 | 0.01371 | 1.114 | 1.934 | 0.9604 |
| 0.5 | 4 | 0.0008897 | 7.148e-05 | 1.777 | 2.861 | 0.9729 |
| 0.75 | 2 | 0.3711 | 0.3026 | 0.7244 | 1.608e-07 | 0.9763 |
| 0.75 | 3 | 0.07111 | 0.0522 | 0.9372 | 1.278 | 0.9581 |
| 0.75 | 4 | 0.05531 | 0.0126 | 1.051 | 2.029 | 0.9743 |

Phase 0 strict replay: **PASS**. Checks: `{'accepted_steps': True, 'stop': True, 'loss': True, 'identical_coefficients': True}`. Loss relative difference 0; maximum coefficient difference 0.

## phase1: modal__c13.3__development_c, paired

512/512 starts; 3789.6 s; 56100 units; capped: False. Stop reasons: `{'no_decreasing_step': 447, 'NUMERICAL_FAILURE': 63, 'maximum_iterations': 2}`.

| Event | Hits / n | Share | Wilson 95% interval |
|---|---|---|---|
| lowest_cluster | 1/512 | 0.001953 | [0.0003449, 0.01098] |
| within_5mm | 9/512 | 0.01758 | [0.009275, 0.03307] |
| zero_loss | 0/512 | 0 | [0, 0.007447] |
| z1_cluster | 266/512 | 0.5195 | [0.4763, 0.5625] |

| Cluster | Size | Loss | Representative | Truth distance (mm) | Stops |
|---|---|---|---|---|---|
| 0 | 1 | 0.00118292425 | 289 | 2.4153 | `{'no_decreasing_step': 1}` |
| 1 | 1 | 0.0014791569 | 82 | 2.6979 | `{'no_decreasing_step': 1}` |
| 2 | 1 | 0.00190725923 | 399 | 18.588 | `{'no_decreasing_step': 1}` |
| 3 | 1 | 0.00193725415 | 142 | 3.6659 | `{'no_decreasing_step': 1}` |
| 4 | 1 | 0.00270789226 | 139 | 4.2341 | `{'no_decreasing_step': 1}` |
| 5 | 1 | 0.00275457792 | 431 | 4.5327 | `{'no_decreasing_step': 1}` |
| 6 | 1 | 0.00288773942 | 30 | 3.6743 | `{'no_decreasing_step': 1}` |
| 7 | 1 | 0.00318074195 | 383 | 4.6225 | `{'no_decreasing_step': 1}` |
| 8 | 1 | 0.00348034017 | 443 | 4.695 | `{'no_decreasing_step': 1}` |
| 9 | 1 | 0.00369271678 | 262 | 4.3188 | `{'no_decreasing_step': 1}` |
| 10 | 1 | 0.00383471876 | 479 | 5.2197 | `{'no_decreasing_step': 1}` |
| 11 | 1 | 0.00437762589 | 155 | 19.335 | `{'no_decreasing_step': 1}` |
| 12 | 1 | 0.00440893726 | 323 | 18.347 | `{'no_decreasing_step': 1}` |
| 13 | 1 | 0.00443176509 | 225 | 17.6 | `{'no_decreasing_step': 1}` |
| 14 | 1 | 0.00443589079 | 485 | 18.83 | `{'no_decreasing_step': 1}` |
| 15 | 1 | 0.00444786333 | 186 | 17.705 | `{'no_decreasing_step': 1}` |
| 16 | 1 | 0.00445164567 | 477 | 18.461 | `{'no_decreasing_step': 1}` |
| 17 | 1 | 0.00445227605 | 278 | 18.27 | `{'no_decreasing_step': 1}` |
| 18 | 1 | 0.00445631138 | 451 | 17.287 | `{'no_decreasing_step': 1}` |
| 19 | 1 | 0.00447056203 | 213 | 18.802 | `{'no_decreasing_step': 1}` |
| 20 | 1 | 0.00447409329 | 444 | 18.668 | `{'no_decreasing_step': 1}` |
| 21 | 1 | 0.00447972317 | 366 | 23.582 | `{'no_decreasing_step': 1}` |
| 22 | 1 | 0.00448906236 | 333 | 17.777 | `{'no_decreasing_step': 1}` |
| 23 | 1 | 0.00449039812 | 317 | 19.123 | `{'no_decreasing_step': 1}` |
| 24 | 1 | 0.00449087619 | 458 | 16.992 | `{'no_decreasing_step': 1}` |
| 25 | 1 | 0.00449122057 | 358 | 17.271 | `{'no_decreasing_step': 1}` |
| 26 | 1 | 0.0044960853 | 70 | 18.571 | `{'no_decreasing_step': 1}` |
| 27 | 1 | 0.00449901509 | 110 | 19.259 | `{'no_decreasing_step': 1}` |
| 28 | 1 | 0.0044996681 | 90 | 17.201 | `{'no_decreasing_step': 1}` |
| 29 | 1 | 0.0045011777 | 207 | 18.733 | `{'no_decreasing_step': 1}` |
| 30 | 1 | 0.00450261711 | 166 | 13.195 | `{'no_decreasing_step': 1}` |
| 31 | 1 | 0.00450359145 | 195 | 19.414 | `{'no_decreasing_step': 1}` |
| 32 | 1 | 0.00450855341 | 438 | 17.267 | `{'no_decreasing_step': 1}` |
| 33 | 2 | 0.00451197602 | 265 | 17.954 | `{'no_decreasing_step': 2}` |
| 34 | 1 | 0.00451401316 | 390 | 19.085 | `{'no_decreasing_step': 1}` |
| 35 | 1 | 0.004518165 | 460 | 18.945 | `{'no_decreasing_step': 1}` |
| 36 | 1 | 0.00452040133 | 258 | 18.017 | `{'no_decreasing_step': 1}` |
| 37 | 1 | 0.00452061763 | 125 | 19.064 | `{'no_decreasing_step': 1}` |
| 38 | 1 | 0.00452076641 | 382 | 18.894 | `{'no_decreasing_step': 1}` |
| 39 | 266 | 0.00452090165 | 194 | 18.913 | `{'no_decreasing_step': 266}` |
| 40 | 1 | 0.00452374543 | 391 | 18.821 | `{'no_decreasing_step': 1}` |
| 41 | 1 | 0.00452520052 | 405 | 20.946 | `{'no_decreasing_step': 1}` |
| 42 | 1 | 0.00452850198 | 198 | 19.099 | `{'no_decreasing_step': 1}` |
| 43 | 1 | 0.00452891476 | 10 | 17.368 | `{'no_decreasing_step': 1}` |
| 44 | 1 | 0.00452920541 | 251 | 19.412 | `{'no_decreasing_step': 1}` |
| 45 | 1 | 0.00452977875 | 406 | 19.477 | `{'no_decreasing_step': 1}` |
| 46 | 1 | 0.00453136727 | 445 | 18.981 | `{'no_decreasing_step': 1}` |
| 47 | 1 | 0.00453183946 | 355 | 18.051 | `{'no_decreasing_step': 1}` |
| 48 | 1 | 0.00453248967 | 66 | 18.015 | `{'no_decreasing_step': 1}` |
| 49 | 1 | 0.00453552289 | 459 | 18.217 | `{'no_decreasing_step': 1}` |
| 50 | 1 | 0.00453646772 | 425 | 15.782 | `{'no_decreasing_step': 1}` |
| 51 | 1 | 0.00453892603 | 190 | 19.267 | `{'no_decreasing_step': 1}` |
| 52 | 1 | 0.00454016957 | 156 | 19.153 | `{'no_decreasing_step': 1}` |
| 53 | 1 | 0.00454070622 | 347 | 18.859 | `{'no_decreasing_step': 1}` |
| 54 | 1 | 0.00454684895 | 483 | 18.316 | `{'no_decreasing_step': 1}` |
| 55 | 1 | 0.00454848419 | 121 | 18.277 | `{'no_decreasing_step': 1}` |
| 56 | 1 | 0.00455048462 | 221 | 19.173 | `{'no_decreasing_step': 1}` |
| 57 | 1 | 0.00455230803 | 122 | 17.676 | `{'no_decreasing_step': 1}` |
| 58 | 1 | 0.00455872422 | 158 | 17.176 | `{'no_decreasing_step': 1}` |
| 59 | 1 | 0.00456296035 | 50 | 18.66 | `{'no_decreasing_step': 1}` |
| 60 | 1 | 0.00456451379 | 46 | 18.006 | `{'no_decreasing_step': 1}` |
| 61 | 1 | 0.00456608521 | 334 | 18.651 | `{'no_decreasing_step': 1}` |
| 62 | 1 | 0.00457013023 | 157 | 18.136 | `{'no_decreasing_step': 1}` |
| 63 | 1 | 0.00457557789 | 501 | 19.592 | `{'no_decreasing_step': 1}` |
| 64 | 1 | 0.00457645226 | 62 | 19.035 | `{'no_decreasing_step': 1}` |
| 65 | 1 | 0.00458003248 | 509 | 19.309 | `{'no_decreasing_step': 1}` |
| 66 | 1 | 0.00458185377 | 219 | 17.35 | `{'no_decreasing_step': 1}` |
| 67 | 1 | 0.00458287677 | 75 | 17.179 | `{'no_decreasing_step': 1}` |
| 68 | 1 | 0.00458485803 | 282 | 19.374 | `{'no_decreasing_step': 1}` |
| 69 | 1 | 0.00458793358 | 117 | 19.449 | `{'no_decreasing_step': 1}` |
| 70 | 1 | 0.00459265084 | 55 | 18.981 | `{'no_decreasing_step': 1}` |
| 71 | 1 | 0.00459378878 | 118 | 17.17 | `{'no_decreasing_step': 1}` |
| 72 | 1 | 0.00459448256 | 313 | 16.645 | `{'no_decreasing_step': 1}` |
| 73 | 1 | 0.00459535397 | 379 | 19.861 | `{'no_decreasing_step': 1}` |
| 74 | 1 | 0.00459645942 | 339 | 19.488 | `{'no_decreasing_step': 1}` |
| 75 | 1 | 0.0045985767 | 434 | 18.89 | `{'no_decreasing_step': 1}` |
| 76 | 1 | 0.0046000947 | 273 | 17.909 | `{'no_decreasing_step': 1}` |
| 77 | 1 | 0.00460075258 | 179 | 19.69 | `{'no_decreasing_step': 1}` |
| 78 | 1 | 0.00460198301 | 205 | 22.964 | `{'no_decreasing_step': 1}` |
| 79 | 1 | 0.00460298651 | 222 | 20.489 | `{'no_decreasing_step': 1}` |
| 80 | 1 | 0.00460324725 | 453 | 19.51 | `{'no_decreasing_step': 1}` |
| 81 | 1 | 0.00461081029 | 134 | 19.324 | `{'no_decreasing_step': 1}` |
| 82 | 1 | 0.00461109494 | 7 | 20.293 | `{'no_decreasing_step': 1}` |
| 83 | 1 | 0.00461239203 | 310 | 18.76 | `{'no_decreasing_step': 1}` |
| 84 | 1 | 0.00461520669 | 231 | 19.889 | `{'no_decreasing_step': 1}` |
| 85 | 1 | 0.00461574021 | 69 | 19.984 | `{'no_decreasing_step': 1}` |
| 86 | 1 | 0.00461850824 | 146 | 16.887 | `{'no_decreasing_step': 1}` |
| 87 | 1 | 0.00462451887 | 381 | 19.79 | `{'no_decreasing_step': 1}` |
| 88 | 1 | 0.00462986376 | 135 | 19.446 | `{'no_decreasing_step': 1}` |
| 89 | 1 | 0.00463031686 | 6 | 19.732 | `{'no_decreasing_step': 1}` |
| 90 | 1 | 0.00463388498 | 83 | 19.544 | `{'no_decreasing_step': 1}` |
| 91 | 1 | 0.00463963498 | 93 | 19.673 | `{'no_decreasing_step': 1}` |
| 92 | 1 | 0.004641826 | 474 | 19.126 | `{'no_decreasing_step': 1}` |
| 93 | 1 | 0.00464420175 | 54 | 19.694 | `{'no_decreasing_step': 1}` |
| 94 | 1 | 0.004644344 | 446 | 9.8566 | `{'no_decreasing_step': 1}` |
| 95 | 1 | 0.00464492465 | 162 | 18.347 | `{'no_decreasing_step': 1}` |
| 96 | 1 | 0.00464709322 | 286 | 19.894 | `{'no_decreasing_step': 1}` |
| 97 | 1 | 0.00465145425 | 266 | 19.566 | `{'no_decreasing_step': 1}` |
| 98 | 1 | 0.00465341214 | 422 | 20.005 | `{'no_decreasing_step': 1}` |
| 99 | 1 | 0.0046539297 | 187 | 19.314 | `{'no_decreasing_step': 1}` |
| 100 | 1 | 0.0046574521 | 302 | 19.833 | `{'no_decreasing_step': 1}` |
| 101 | 1 | 0.00465900257 | 103 | 20.561 | `{'no_decreasing_step': 1}` |
| 102 | 1 | 0.00465968179 | 17 | 18.964 | `{'no_decreasing_step': 1}` |
| 103 | 2 | 0.00466255821 | 316 | 20.032 | `{'no_decreasing_step': 2}` |
| 104 | 1 | 0.00466770095 | 407 | 20.298 | `{'no_decreasing_step': 1}` |
| 105 | 1 | 0.00466794034 | 419 | 20.446 | `{'no_decreasing_step': 1}` |
| 106 | 1 | 0.00466902132 | 373 | 18.99 | `{'no_decreasing_step': 1}` |
| 107 | 1 | 0.00468254477 | 182 | 19.794 | `{'no_decreasing_step': 1}` |
| 108 | 1 | 0.00468360212 | 370 | 19.836 | `{'no_decreasing_step': 1}` |
| 109 | 1 | 0.00468745165 | 261 | 19.967 | `{'no_decreasing_step': 1}` |
| 110 | 1 | 0.00469017926 | 242 | 19.986 | `{'no_decreasing_step': 1}` |
| 111 | 1 | 0.00469110369 | 450 | 19.831 | `{'no_decreasing_step': 1}` |
| 112 | 1 | 0.00470051958 | 290 | 19.89 | `{'no_decreasing_step': 1}` |
| 113 | 2 | 0.00470086703 | 437 | 20.321 | `{'no_decreasing_step': 2}` |
| 114 | 1 | 0.00470698111 | 130 | 19.975 | `{'no_decreasing_step': 1}` |
| 115 | 1 | 0.00471117067 | 178 | 20.378 | `{'no_decreasing_step': 1}` |
| 116 | 1 | 0.00471538448 | 301 | 19.101 | `{'no_decreasing_step': 1}` |
| 117 | 1 | 0.00472483962 | 461 | 20.156 | `{'no_decreasing_step': 1}` |
| 118 | 1 | 0.00473389086 | 78 | 19.753 | `{'no_decreasing_step': 1}` |
| 119 | 1 | 0.00474451355 | 167 | 20.503 | `{'no_decreasing_step': 1}` |
| 120 | 1 | 0.00474553668 | 123 | 18.376 | `{'no_decreasing_step': 1}` |
| 121 | 1 | 0.00474634564 | 402 | 19.332 | `{'no_decreasing_step': 1}` |
| 122 | 1 | 0.00474738389 | 230 | 20.097 | `{'no_decreasing_step': 1}` |
| 123 | 1 | 0.0047483973 | 455 | 20.863 | `{'no_decreasing_step': 1}` |
| 124 | 1 | 0.00475597733 | 486 | 19.796 | `{'no_decreasing_step': 1}` |
| 125 | 1 | 0.00475604105 | 430 | 19.459 | `{'no_decreasing_step': 1}` |
| 126 | 1 | 0.00476015132 | 270 | 20.73 | `{'no_decreasing_step': 1}` |
| 127 | 1 | 0.00476698101 | 98 | 20.405 | `{'no_decreasing_step': 1}` |
| 128 | 1 | 0.00478126217 | 447 | 20.715 | `{'no_decreasing_step': 1}` |
| 129 | 1 | 0.00478485268 | 206 | 19.096 | `{'no_decreasing_step': 1}` |
| 130 | 1 | 0.0047878412 | 375 | 20.394 | `{'no_decreasing_step': 1}` |
| 131 | 1 | 0.00479705623 | 114 | 20.461 | `{'no_decreasing_step': 1}` |
| 132 | 1 | 0.00480938362 | 111 | 20.337 | `{'no_decreasing_step': 1}` |
| 133 | 1 | 0.00481419874 | 189 | 20.101 | `{'no_decreasing_step': 1}` |
| 134 | 1 | 0.00481805256 | 218 | 20.527 | `{'no_decreasing_step': 1}` |
| 135 | 1 | 0.00482474936 | 259 | 20.275 | `{'maximum_iterations': 1}` |
| 136 | 1 | 0.00482779548 | 271 | 21.518 | `{'no_decreasing_step': 1}` |
| 137 | 1 | 0.00484373586 | 349 | 19.85 | `{'no_decreasing_step': 1}` |
| 138 | 1 | 0.00484762191 | 411 | 20.127 | `{'no_decreasing_step': 1}` |
| 139 | 1 | 0.00485818892 | 246 | 21.195 | `{'no_decreasing_step': 1}` |
| 140 | 1 | 0.00487535603 | 15 | 20.48 | `{'no_decreasing_step': 1}` |
| 141 | 1 | 0.00489580035 | 363 | 21.277 | `{'no_decreasing_step': 1}` |
| 142 | 1 | 0.00490959317 | 318 | 20.439 | `{'no_decreasing_step': 1}` |
| 143 | 1 | 0.00492002264 | 503 | 21.016 | `{'no_decreasing_step': 1}` |
| 144 | 1 | 0.00492240936 | 395 | 20.068 | `{'no_decreasing_step': 1}` |
| 145 | 1 | 0.00492572513 | 151 | 20.892 | `{'no_decreasing_step': 1}` |
| 146 | 1 | 0.00493336641 | 214 | 18.773 | `{'no_decreasing_step': 1}` |
| 147 | 1 | 0.00493674407 | 350 | 14.361 | `{'NUMERICAL_FAILURE': 1}` |
| 148 | 1 | 0.00493768812 | 11 | 20.769 | `{'no_decreasing_step': 1}` |
| 149 | 1 | 0.00493910812 | 499 | 21.488 | `{'maximum_iterations': 1}` |
| 150 | 1 | 0.00494025403 | 463 | 19.804 | `{'NUMERICAL_FAILURE': 1}` |
| 151 | 1 | 0.00495849903 | 107 | 20.878 | `{'no_decreasing_step': 1}` |
| 152 | 1 | 0.00495987426 | 250 | 21.372 | `{'no_decreasing_step': 1}` |
| 153 | 1 | 0.00498377795 | 279 | 21.071 | `{'no_decreasing_step': 1}` |
| 154 | 1 | 0.00500594623 | 467 | 19.211 | `{'no_decreasing_step': 1}` |
| 155 | 1 | 0.00501167162 | 287 | 20.175 | `{'no_decreasing_step': 1}` |
| 156 | 1 | 0.00501827124 | 418 | 20.757 | `{'no_decreasing_step': 1}` |
| 157 | 1 | 0.00503116086 | 174 | 20.583 | `{'NUMERICAL_FAILURE': 1}` |
| 158 | 1 | 0.00507996541 | 171 | 20.296 | `{'no_decreasing_step': 1}` |
| 159 | 1 | 0.00512292711 | 478 | 18.541 | `{'no_decreasing_step': 1}` |
| 160 | 1 | 0.00521461521 | 126 | 20.381 | `{'no_decreasing_step': 1}` |
| 161 | 1 | 0.00526184202 | 211 | 21.859 | `{'no_decreasing_step': 1}` |
| 162 | 1 | 0.00527283992 | 199 | 20.162 | `{'no_decreasing_step': 1}` |
| 163 | 1 | 0.00528293176 | 330 | 20.145 | `{'no_decreasing_step': 1}` |
| 164 | 1 | 0.00534913253 | 371 | 21.096 | `{'no_decreasing_step': 1}` |
| 165 | 1 | 0.00546531454 | 462 | 20.988 | `{'no_decreasing_step': 1}` |
| 166 | 1 | 0.0055238421 | 163 | 21.641 | `{'no_decreasing_step': 1}` |
| 167 | 1 | 0.00580184557 | 79 | 23.137 | `{'NUMERICAL_FAILURE': 1}` |
| 168 | 1 | 0.006034439 | 495 | 21.119 | `{'no_decreasing_step': 1}` |
| 169 | 1 | 0.00631274485 | 326 | 23.756 | `{'no_decreasing_step': 1}` |
| 170 | 1 | 0.00632341082 | 299 | 11.138 | `{'NUMERICAL_FAILURE': 1}` |
| 171 | 1 | 0.00639959827 | 435 | 21.004 | `{'NUMERICAL_FAILURE': 1}` |
| 172 | 1 | 0.00648733283 | 14 | 21.628 | `{'NUMERICAL_FAILURE': 1}` |
| 173 | 1 | 0.00656352633 | 91 | 23.226 | `{'no_decreasing_step': 1}` |
| 174 | 1 | 0.00743528846 | 374 | 21.431 | `{'NUMERICAL_FAILURE': 1}` |
| 175 | 1 | 0.00789982449 | 502 | 21.559 | `{'NUMERICAL_FAILURE': 1}` |
| 176 | 1 | 0.00917845719 | 143 | 23.119 | `{'NUMERICAL_FAILURE': 1}` |
| 177 | 1 | 0.00931199613 | 291 | 5.9125 | `{'no_decreasing_step': 1}` |
| 178 | 1 | 0.00950448592 | 359 | 21.132 | `{'no_decreasing_step': 1}` |
| 179 | 1 | 0.00965863161 | 303 | 21.452 | `{'NUMERICAL_FAILURE': 1}` |
| 180 | 1 | 0.0109531438 | 415 | 24.294 | `{'NUMERICAL_FAILURE': 1}` |
| 181 | 1 | 0.0121259422 | 507 | 22.46 | `{'no_decreasing_step': 1}` |
| 182 | 1 | 0.0123797963 | 331 | 9.1497 | `{'no_decreasing_step': 1}` |
| 183 | 1 | 0.0124508776 | 38 | 24.103 | `{'no_decreasing_step': 1}` |
| 184 | 1 | 0.0128973204 | 175 | 23.622 | `{'NUMERICAL_FAILURE': 1}` |
| 185 | 1 | 0.0134346398 | 346 | 25.953 | `{'no_decreasing_step': 1}` |
| 186 | 1 | 0.0136769308 | 403 | 44.083 | `{'NUMERICAL_FAILURE': 1}` |
| 187 | 1 | 0.0137855605 | 267 | 23.569 | `{'NUMERICAL_FAILURE': 1}` |
| 188 | 1 | 0.0148141757 | 294 | 25.425 | `{'NUMERICAL_FAILURE': 1}` |
| 189 | 1 | 0.0165730532 | 191 | 24.612 | `{'NUMERICAL_FAILURE': 1}` |
| 190 | 1 | 0.017248365 | 127 | 38.021 | `{'NUMERICAL_FAILURE': 1}` |
| 191 | 1 | 0.0174552734 | 327 | 22.119 | `{'NUMERICAL_FAILURE': 1}` |
| 192 | 1 | 0.0180407453 | 23 | 27.498 | `{'no_decreasing_step': 1}` |
| 193 | 1 | 0.0181714861 | 351 | 43.94 | `{'NUMERICAL_FAILURE': 1}` |
| 194 | 1 | 0.0201516302 | 295 | 15.368 | `{'NUMERICAL_FAILURE': 1}` |
| 195 | 1 | 0.0210211233 | 367 | 25.953 | `{'NUMERICAL_FAILURE': 1}` |
| 196 | 1 | 0.022986029 | 243 | 31.203 | `{'NUMERICAL_FAILURE': 1}` |
| 197 | 1 | 0.0232268098 | 487 | 24.042 | `{'NUMERICAL_FAILURE': 1}` |
| 198 | 1 | 0.0232605918 | 235 | 25.604 | `{'NUMERICAL_FAILURE': 1}` |
| 199 | 1 | 0.0235222315 | 3 | 22.725 | `{'NUMERICAL_FAILURE': 1}` |
| 200 | 1 | 0.0251297377 | 307 | 22.904 | `{'no_decreasing_step': 1}` |
| 201 | 1 | 0.0256137772 | 283 | 24.98 | `{'NUMERICAL_FAILURE': 1}` |
| 202 | 1 | 0.0269339239 | 159 | 35.488 | `{'NUMERICAL_FAILURE': 1}` |
| 203 | 1 | 0.0276058895 | 275 | 27.291 | `{'no_decreasing_step': 1}` |
| 204 | 1 | 0.0302522355 | 471 | 31.56 | `{'NUMERICAL_FAILURE': 1}` |
| 205 | 1 | 0.0331013723 | 115 | 25.92 | `{'NUMERICAL_FAILURE': 1}` |
| 206 | 1 | 0.0346233394 | 47 | 27.55 | `{'NUMERICAL_FAILURE': 1}` |
| 207 | 1 | 0.0348535064 | 427 | 26.773 | `{'no_decreasing_step': 1}` |
| 208 | 1 | 0.0375446691 | 387 | 25.382 | `{'NUMERICAL_FAILURE': 1}` |
| 209 | 1 | 0.0388468196 | 51 | 25.644 | `{'NUMERICAL_FAILURE': 1}` |
| 210 | 1 | 0.0391532728 | 311 | 27.425 | `{'NUMERICAL_FAILURE': 1}` |
| 211 | 1 | 0.0391923186 | 255 | 29.859 | `{'NUMERICAL_FAILURE': 1}` |
| 212 | 1 | 0.040237768 | 43 | 32.03 | `{'NUMERICAL_FAILURE': 1}` |
| 213 | 1 | 0.0408594664 | 239 | 33.032 | `{'NUMERICAL_FAILURE': 1}` |
| 214 | 1 | 0.0465909387 | 315 | 22.576 | `{'no_decreasing_step': 1}` |
| 215 | 1 | 0.0504217518 | 87 | 28.727 | `{'NUMERICAL_FAILURE': 1}` |
| 216 | 1 | 0.0529836131 | 414 | 34.583 | `{'no_decreasing_step': 1}` |
| 217 | 1 | 0.0544548688 | 63 | 32.139 | `{'NUMERICAL_FAILURE': 1}` |
| 218 | 1 | 0.0548779727 | 247 | 33.947 | `{'NUMERICAL_FAILURE': 1}` |
| 219 | 1 | 0.0559701862 | 439 | 25.368 | `{'NUMERICAL_FAILURE': 1}` |
| 220 | 1 | 0.0570310947 | 27 | 24.826 | `{'NUMERICAL_FAILURE': 1}` |
| 221 | 1 | 0.0586554209 | 35 | 33.014 | `{'NUMERICAL_FAILURE': 1}` |
| 222 | 1 | 0.0603613204 | 202 | 32.125 | `{'NUMERICAL_FAILURE': 1}` |
| 223 | 1 | 0.0659117624 | 343 | 25.628 | `{'NUMERICAL_FAILURE': 1}` |
| 224 | 1 | 0.0679784986 | 223 | 35.606 | `{'NUMERICAL_FAILURE': 1}` |
| 225 | 1 | 0.0702463719 | 319 | 33.298 | `{'NUMERICAL_FAILURE': 1}` |
| 226 | 1 | 0.0857211013 | 131 | 35.256 | `{'NUMERICAL_FAILURE': 1}` |
| 227 | 1 | 0.0937833772 | 263 | 38.865 | `{'NUMERICAL_FAILURE': 1}` |
| 228 | 1 | 0.132682774 | 59 | 33.117 | `{'NUMERICAL_FAILURE': 1}` |
| 229 | 1 | 0.231361384 | 31 | 33.6 | `{'NUMERICAL_FAILURE': 1}` |
| 230 | 1 | 0.339082227 | 227 | 32.159 | `{'NUMERICAL_FAILURE': 1}` |
| 231 | 1 | 0.402642005 | 183 | 36.045 | `{'NUMERICAL_FAILURE': 1}` |
| 232 | 1 | 0.423506927 | 335 | 39.257 | `{'NUMERICAL_FAILURE': 1}` |
| 233 | 1 | 0.452926872 | 39 | 43.628 | `{'NUMERICAL_FAILURE': 1}` |
| 234 | 1 | 0.548052118 | 19 | 41.459 | `{'NUMERICAL_FAILURE': 1}` |
| 235 | 1 | 0.579759635 | 99 | 32.58 | `{'no_decreasing_step': 1}` |
| 236 | 1 | 0.760063007 | 423 | 38.612 | `{'NUMERICAL_FAILURE': 1}` |
| 237 | 1 | 0.778370683 | 71 | 45.39 | `{'NUMERICAL_FAILURE': 1}` |
| 238 | 1 | 0.793916699 | 511 | 41.664 | `{'NUMERICAL_FAILURE': 1}` |
| 239 | 1 | 1.2812914 | 95 | 40.844 | `{'NUMERICAL_FAILURE': 1}` |
| 240 | 1 | 1.70722638 | 475 | 43.541 | `{'NUMERICAL_FAILURE': 1}` |
| 241 | 1 | 1.73466742 | 119 | 48.684 | `{'no_decreasing_step': 1}` |
| 242 | 1 | 1.96937412 | 215 | 54.04 | `{'NUMERICAL_FAILURE': 1}` |
| 243 | 1 | 4.14886046 | 147 | 53.399 | `{'NUMERICAL_FAILURE': 1}` |

G1: **True**. Winner chosen by stage-2 loss before truth scoring.

All start draws, refusals, optimizer trials, timeouts and source/input seals are in `results/validation/cleaned_interfaces/FM-003/`. Damped synthetic catalogs support no realism claim.
