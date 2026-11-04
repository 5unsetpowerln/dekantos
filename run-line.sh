#!/usr/bin/env bash
# 整えたprefixでLINEを動かす。
#   run-line.sh <WINEPREFIX> install   … LineInst.exe を実行してLINEを導入する
#   run-line.sh <WINEPREFIX> launch    … 導入済みのLINEを LineLauncher.exe で起動する
set -euo pipefail

PREFIX="${1:?usage: run-line.sh <WINEPREFIX> install|launch}"
ACTION="${2:-install}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WINEPREFIX="$PREFIX"
export WINEDEBUG="${WINEDEBUG:--all}"

case "$ACTION" in
  install)
    exec wine "$HERE/programs/LineInst.exe"
    ;;
  launch)
    # LINEの正しい起動口は LauncherPath に登録される LineLauncher.exe。
    # LINE.exe を直接起動すると起動トークンがなく終了する。
    LAUNCHER="$PREFIX/drive_c/users/$USER/AppData/Local/LINE/bin/LineLauncher.exe"
    exec wine "$LAUNCHER"
    ;;
  *)
    echo "unknown action: $ACTION (install|launch)" >&2; exit 2
    ;;
esac
