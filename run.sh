#!/usr/bin/env bash
# 指定したWindowsの実行ファイルを、このパッケージのprefixで実行する。
#   ./run.sh <実行ファイル (Unixのパス、またはC:\...)> [引数...]
# prefixはWINEPREFIX (未指定ならこのディレクトリのprefix/)。実行ファイルが行った変更はprefixに残る。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WINEPREFIX="${WINEPREFIX:-$HERE/prefix}"
EXE="${1:?usage: run.sh <実行ファイル> [引数...]}"
shift

# 読み込むシステムDLLの署名を検証するアプリ (例: LINE)のために、自作ルートCAと、
# Wine内蔵DLLのAuthenticodeハッシュを載せたカタログを入れ、内蔵DLLを署名済みのOSファイルに見せる。
setup_prefix() {
  local ca="$WINEPREFIX/.windows-execution-ca"
  local guid='{127d0a1d-4ef2-11d1-8608-00c04fc295ee}' # wintrustがcatroot以下で探す既定のGUID
  local dir files cats=()
  wineboot -u
  wineserver -w
  if [[ ! -d "$ca" ]]; then
    python3 "$HERE/tools/gen_ca.py" "$ca" >/dev/null
    wine regedit "$ca/root.reg"
    wineserver -w
  fi
  for dir in syswow64 system32; do
    mapfile -t files < <(find "$WINEPREFIX/drive_c/windows/$dir" -maxdepth 1 -type f \
      \( -iname '*.dll' -o -iname '*.exe' \))
    python3 "$HERE/tools/catalog.py" --ca-dir "$ca" --out "$ca/$dir.cat" "${files[@]}"
    cats+=("$ca/$dir.cat")
  done
  # 32bitプロセスはsyswow64の、64bitプロセスはsystem32のcatrootを探すので、両方に両方を置く
  for dir in syswow64 system32; do
    mkdir -p "$WINEPREFIX/drive_c/windows/$dir/catroot/$guid"
    cp "${cats[@]}" "$WINEPREFIX/drive_c/windows/$dir/catroot/$guid/"
  done
}

# カタログはDLLの中身のハッシュなので、Wineの版が変わったら作り直す
stamp="$WINEPREFIX/.windows-execution-wine"
version="$(wine --version)"
if [[ ! -f "$stamp" || "$(<"$stamp")" != "$version" ]]; then
  setup_prefix
  echo "$version" >"$stamp"
fi

exec wine "$EXE" "$@"
