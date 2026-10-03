#!/bin/zsh
# kshape 第 4 轮补充：8×32 的 2、3 层，以及 4×32 的 4–24 层（找单 ANE 区间）
K=(1x1 1x2 1x3 1x4 1x5 1x6 1x7 1x8 1x9 1x10 1x11 1x12 1x13 1x14 1x15 3x1 5x1 7x1 9x1 11x1 13x1 15x1 3x3 5x5)
for k in $K; do for L in 2 3; do echo k${k}_c256_h8w32_L$L; done; done
for k in $K; do for L in 4 8 16 24; do echo k${k}_c256_h4w32_L$L; done; done
