#!/usr/bin/env bash
# Pravi ngtree wheel; po želji isti kod kopira u ngfw kao ngfw.tree.
#
#   bash build.sh                 samo napravi dist/ngtree-<verzija>-py3-none-any.whl
#   bash build.sh --ngfw          + kopira ngtree/ u <ngfw>/ngfw/tree/ (zatim tamo: nova verzija
#                                   ngfw u __init__.py + CHANGELOG.md, pa bash build.sh <aplikacije>)
#                                   <ngfw> = $NGFW_DIR, ili putanja upisana u ngfw.local, ili ../ngfw
#   bash build.sh app1 app2 ...   + kopira wheel u <app>/wheels/ i upiše ga u requirements.txt
#                                   (aplikacije koje NE koriste ngfw; za ngfw aplikacije koristite ngfw.tree)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
NGFW="${NGFW_DIR:-$(cat ngfw.local 2>/dev/null || echo ../ngfw)}"
NGFW="${NGFW/#\~/$HOME}"
declare -A APPS=()   # npr. APPS=([nesto]="$HOME/projects/nesto")

VER=$(python3 -c 'import re;print(re.search(r"__version__ = \"(.+?)\"", open("ngtree/__init__.py").read())[1])')
grep -q "^## $VER" CHANGELOG.md || { echo "✘ CHANGELOG.md nema stavku „## $VER”." >&2; exit 1; }

rm -rf dist build ./*.egg-info
python3 -m pip wheel --quiet --no-deps --wheel-dir dist . >/dev/null
WHL=dist/ngtree-$VER-py3-none-any.whl
[[ -f $WHL ]] || { echo "✘ Wheel nije napravljen." >&2; exit 1; }
rm -rf build ./*.egg-info
echo "✔ $WHL"

for arg in "$@"; do
  if [[ $arg == --ngfw ]]; then
    [[ -d $NGFW/ngfw ]] || { echo "✘ Nema $NGFW/ngfw" >&2; exit 1; }
    rm -rf "$NGFW/ngfw/tree"
    mkdir -p "$NGFW/ngfw/tree"
    cp ngtree/*.py "$NGFW/ngfw/tree/"
    echo "✔ ngtree $VER → $NGFW/ngfw/tree/  (povećajte verziju ngfw i dopišite CHANGELOG.md, pa build.sh tamo)"
    continue
  fi
  dir=${APPS[$arg]:-}
  [[ -n $dir && -d $dir ]] || { echo "✘ Nepoznata aplikacija: $arg (dopišite je u APPS u build.sh)" >&2; exit 1; }
  mkdir -p "$dir/wheels"
  find "$dir/wheels" -name 'ngtree-*.whl' ! -name "$(basename "$WHL")" -delete
  cp "$WHL" "$dir/wheels/"
  if grep -q '^\./wheels/ngtree-.*\.whl' "$dir/requirements.txt"; then
    sed -i "s|^\./wheels/ngtree-.*\.whl.*|./wheels/$(basename "$WHL")|" "$dir/requirements.txt"
  else
    printf '\n# ngtree — stablo kao NiceGUI element (ngtree: bash build.sh %s)\n./wheels/%s\n' "$arg" "$(basename "$WHL")" >> "$dir/requirements.txt"
  fi
  echo "✔ $arg: wheels/$(basename "$WHL") + requirements.txt"
done
