#!/usr/bin/env bash
# 新規のWINEPREFIXを、Windowsソフトを実機に近く動かせる状態に整える。
#
# いまの中身: Windowsのシステムコンポーネントを模した自作のルートCAと、
# Wine内蔵のシステムDLLのAuthenticodeハッシュを載せたセキュリティカタログを導入する。
# これにより、起動時に自身が読み込むシステムDLLの署名を検証するアプリ (例: LINE)が、
# Wineの内蔵DLLを「署名済みのOSファイル」として受け入れて起動できるようになる。
#
# 使い方: build-prefix.sh <WINEPREFIXのパス>
set -euo pipefail

PREFIX="${1:?usage: build-prefix.sh <WINEPREFIX>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 署名カタログの既定のシステムGUID (wintrustがcatroot以下で探すサブディレクトリ)
GUID='{127d0a1d-4ef2-11d1-8608-00c04fc295ee}'

export WINEPREFIX="$PREFIX"
export WINEDEBUG="${WINEDEBUG:--all}"

echo "[1/3] prefixを初期化: $PREFIX"
wineboot -i
wineserver -w

echo "[2/3] 自作ルートCAを生成し、Rootストアに導入"
CADIR="$PREFIX/.windows-execution-ca"
python3 "$HERE/tools/gen_ca.py" "$CADIR" >/dev/null
wine regedit "$CADIR/root.reg"
wineserver -w

echo "[3/3] syswow64/system32のカタログを作成し、catrootに設置"
# 32bitプロセスはsyswow64を、64bitプロセスはsystem32を検証するので、両方のカタログを作る。
# EnumCatalogFromHashはcatroot内の全*.catを探すため、両方を両catrootに置いて取りこぼしを防ぐ。
declare -A CATS=( [syswow64]="sys32-wow.cat" [system32]="sys32-64.cat" )
for srcdir in syswow64 system32; do
  out="$PREFIX/.${CATS[$srcdir]}"
  mapfile -t FILES < <(find "$PREFIX/drive_c/windows/$srcdir" -maxdepth 1 -type f \
    \( -iname '*.dll' -o -iname '*.exe' \))
  python3 "$HERE/tools/catalog.py" --ca-dir "$CADIR" --name "Microsoft Windows" \
    --out "$out" "${FILES[@]}"
done
for catroot in syswow64 system32; do
  d="$PREFIX/drive_c/windows/$catroot/catroot/$GUID"
  mkdir -p "$d"
  cp "$PREFIX/.${CATS[syswow64]}" "$d/"
  cp "$PREFIX/.${CATS[system32]}" "$d/"
done

echo "完了: $PREFIX は署名検証を通せる状態になった"
