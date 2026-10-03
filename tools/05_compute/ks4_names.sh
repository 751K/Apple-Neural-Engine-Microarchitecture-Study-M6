#!/bin/zsh
# 输出 kshape 第 4 轮扫描的模型名
for hw in h8w32 h16w32 h32w32; do
  for k in 1x1 1x2 1x3 1x4 1x5 1x6 1x7 1x8 1x9 1x10 1x11 1x12 1x13 1x14 1x15 3x1 5x1 7x1 9x1 11x1 13x1 15x1 3x3 5x5; do
    for L in 4 8 16 24; do echo k${k}_c256_${hw}_L$L; done
  done
done
