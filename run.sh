#!/usr/bin/env bash
# Run the given Windows executable in this package's prefix.
#   ./run.sh <executable (Unix path or C:\...)> [args...]
# The prefix is WINEPREFIX, or prefix/ next to this script. Changes made by the executable stay in it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WINEPREFIX="${WINEPREFIX:-$HERE/prefix}"
EXE="${1:?usage: run.sh <executable> [args...]}"
shift

# Some applications (e.g. LINE) verify the signatures of the system DLLs they load. Install our own
# root CA and catalogs holding the Authenticode hashes of Wine's builtin DLLs, so they look like signed OS files.
setup_prefix() {
  local ca="$WINEPREFIX/.windows-execution-ca"
  local guid='{127d0a1d-4ef2-11d1-8608-00c04fc295ee}' # default GUID that wintrust searches under catroot
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
  # 32-bit processes search the catroot in syswow64 and 64-bit ones the one in system32, so put both in both
  for dir in syswow64 system32; do
    mkdir -p "$WINEPREFIX/drive_c/windows/$dir/catroot/$guid"
    cp "${cats[@]}" "$WINEPREFIX/drive_c/windows/$dir/catroot/$guid/"
  done
}

# The catalogs hold hashes of the DLL contents, so rebuild them when the Wine version changes
stamp="$WINEPREFIX/.windows-execution-wine"
version="$(wine --version)"
if [[ ! -f "$stamp" || "$(<"$stamp")" != "$version" ]]; then
  setup_prefix
  echo "$version" >"$stamp"
fi

exec wine "$EXE" "$@"
