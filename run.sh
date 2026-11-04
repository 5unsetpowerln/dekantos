#!/usr/bin/env bash
# Run the given Windows executable in this package's prefix.
#   ./run.sh <executable (Unix path or C:\...)> [args...]
# The prefix is WINEPREFIX, or prefix/ next to this script. Changes made by the executable stay in it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WINEPREFIX="${WINEPREFIX:-$HERE/prefix}"
EXE="${1:?usage: run.sh <executable> [args...]}"
shift

DXVK_VERSION=3.1.1
DXVK_SHA256=40565b4a724aadc4433fa4e010b4b23916d9b1f1baeee64e17186db94f54e608
# The DLLs Proton replaces with DXVK by default (d3d8 stays builtin)
DXVK_DLLS=(d3d11 d3d10core d3d9 dxgi)

# Run Direct3D 9-11 on Vulkan the way Proton does: put the DXVK DLLs in system32 (64-bit) and
# syswow64 (32-bit), and override them to native, since Wine ignores native DLLs there otherwise.
install_dxvk() {
  local archive="$HERE/.cache/dxvk-$DXVK_VERSION.tar.gz"
  local tmp dll
  if [[ ! -f "$archive" ]]; then
    mkdir -p "$HERE/.cache"
    curl -fL -o "$archive.part" "https://github.com/doitsujin/dxvk/releases/download/v$DXVK_VERSION/dxvk-$DXVK_VERSION.tar.gz"
    mv "$archive.part" "$archive"
  fi
  echo "$DXVK_SHA256  $archive" | sha256sum -c --quiet
  tmp="$(mktemp -d)"
  tar -xzf "$archive" -C "$tmp"
  printf 'REGEDIT4\n\n[HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides]\n' >"$tmp/dxvk.reg"
  for dll in "${DXVK_DLLS[@]}"; do
    cp "$tmp/dxvk-$DXVK_VERSION/x64/$dll.dll" "$WINEPREFIX/drive_c/windows/system32/"
    cp "$tmp/dxvk-$DXVK_VERSION/x32/$dll.dll" "$WINEPREFIX/drive_c/windows/syswow64/"
    printf '"%s"="native"\n' "$dll" >>"$tmp/dxvk.reg"
  done
  wine regedit "$tmp/dxvk.reg"
  wineserver -w
  rm -rf "$tmp"
}

# Some applications (e.g. LINE) verify the signatures of the system DLLs they load. Install our own
# root CA and catalogs holding the Authenticode hashes of the DLLs in system32 and syswow64, so they
# look like signed OS files. The catalogs are built after DXVK is installed, so they cover its DLLs.
setup_prefix() {
  local ca="$WINEPREFIX/.windows-execution-ca"
  local guid='{127d0a1d-4ef2-11d1-8608-00c04fc295ee}' # default GUID that wintrust searches under catroot
  local dir files cats=()
  wineboot -u
  wineserver -w
  install_dxvk
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

# Prepare the prefix again when Wine or this setup (run.sh, tools) changes. This also keeps the
# catalogs in sync with the DLLs they hash.
stamp="$WINEPREFIX/.windows-execution-setup"
version="$(wine --version) $(cat "$HERE/run.sh" "$HERE"/tools/*.py | sha256sum | cut -d' ' -f1)"
if [[ ! -f "$stamp" || "$(<"$stamp")" != "$version" ]]; then
  setup_prefix
  echo "$version" >"$stamp"
fi

exec wine "$EXE" "$@"
