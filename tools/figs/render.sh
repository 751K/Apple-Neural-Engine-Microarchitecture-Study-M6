#!/bin/zsh
# 用 Chrome 无头模式把 SVG 导出为 2 倍分辨率的 PNG。
# 用法：tools/figs/render.sh figs/fig5-2_td_format.svg [...]
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for svg in "$@"; do
  abs=$(cd "$(dirname "$svg")" && pwd)/$(basename "$svg")
  vb=($(grep -o 'viewBox="[^"]*"' "$abs" | head -1 | tr -d '"' | sed 's/viewBox=//'))
  w=${vb[3]}; h=${vb[4]}
  tmp=$(mktemp -t figrender).html
  print "<html><body style=\"margin:0\"><img src=\"file://$abs\" style=\"width:${w}px;height:${h}px;display:block\"></body></html>" > $tmp
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
    --window-size=$w,$h --screenshot="${abs%.svg}.png" --allow-file-access-from-files "file://$tmp" 2>/dev/null
  rm -f $tmp
  echo "${abs%.svg}.png"
done
