#!/bin/zsh
# 重新生成报告的全部图：figs/<语言>/<主题>/，语言为 zh、en，主题为 light、dark。
#   1. 各生成脚本输出中文浅色 SVG（figs/zh/light/）；图 4-1、图 4-2 为手写 SVG，直接放在该目录。
#   2. translate.py 按 tools/figs/i18n/*.en.json 生成英文浅色 SVG（figs/en/light/）。
#   3. darken.py 由两种语言的浅色版生成深色版（figs/*/dark/）。
#   4. render.sh 把全部 SVG 导出为 PNG。
#   5. 图 8-2、图 8-3 由 tools/06_numerics/lut_plot.py 直接输出四种 PNG。
# 用法：tools/figs/build_all.sh（在仓库任意位置运行均可）
set -e
cd "$(dirname "$0")/../.."
for f in tools/figs/fig*.py; do python3 $f > /dev/null; done
python3 tools/figs/translate.py > /dev/null
python3 tools/figs/darken.py > /dev/null
tools/figs/render.sh figs/*/*/*.svg > /dev/null
python3 tools/06_numerics/lut_plot.py data/06_numerics/lut_m6 figs > /dev/null 2>&1
echo "figs/: $(ls figs/*/*/*.png | wc -l | tr -d ' ') 张 PNG"
