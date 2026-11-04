# Dekantos

*Glass that wakes the sleeping wine, and opens what was sealed.*

An environment for running Windows applications on Linux with Wine, as close to a real Windows machine as possible and without manual setup.

## Usage

```sh
./run.sh <executable> [args...]
```

- The executable can be given as a Unix path or as a `C:\...` path.
- The prefix is `WINEPREFIX`. If it is not set, `prefix/` in this directory is used.
- Changes made by the executable (such as an installation) stay in the prefix and are available to later runs.
- On the first run, and whenever Wine or the setup of this package (`run.sh`, `tools/`) changes, the prefix is prepared before the executable runs (this takes about 30 seconds).

Example: LINE

```sh
# Install it (agree to the terms of use and continue)
./run.sh ~/Downloads/LineInst.exe

# Start the installed LINE
./run.sh prefix/drive_c/users/$USER/AppData/Local/LINE/bin/LineLauncher.exe
```

The entry point of LINE is `LineLauncher.exe`, which LINE registers in the registry.
Running `LINE.exe` directly makes it exit, because it is started without a launch token.

## Requirements

- `wine` (64-bit WoW64 setup, tested with wine-11.17)
- `python3` with the `cryptography` and `asn1crypto` packages
- A Vulkan driver for the GPU, including the 32-bit one for 32-bit applications (tested with Mesa's ANV on Intel Iris Xe)
- `curl`, and network access on the first run to download DXVK

## How it works

### Direct3D on Vulkan (DXVK)

Direct3D 9, 10 and 11 run on Vulkan through [DXVK](https://github.com/doitsujin/dxvk), the way Proton runs them.
When `run.sh` prepares the prefix, it downloads the DXVK release pinned in `run.sh` (3.1.1, checked against its sha256 and cached in `.cache/`), copies `d3d11`, `d3d10core`, `d3d9` and `dxgi` into `system32` (64-bit) and `syswow64` (32-bit), and overrides them to native in `HKCU\Software\Wine\DllOverrides`.
These are the DLLs Proton replaces with DXVK by default; `d3d8` stays Wine's builtin.
Wine does not use native DLLs in the system directories without an override, so both steps are needed.

### Font smoothing (ClearType)

Windows smooths text with ClearType by default.
Wine takes the antialiasing mode of every font from fontconfig, ahead of the ClearType setting in the registry, and hosts commonly enable antialiasing without a subpixel order.
Wine then uses grayscale, and the gasp table of UI fonts such as Tahoma turns grayscale off at small sizes, so the text is drawn in two colors.
`run.sh` passes `fonts.conf` to Wine through `FONTCONFIG_FILE`. It includes the host setup and asks for RGB subpixel rendering, which Wine draws without consulting gasp, like ClearType.
`run.sh` also sets the ClearType defaults of Windows in `HKCU\Control Panel\Desktop`, which applications can query.

### Signature verification of system DLLs

Some applications, such as `LineInst.exe` and LINE itself, verify the Authenticode signatures of the system DLLs they load (`gdiplus.dll`, `crypt32.dll`, and so on) with `WinVerifyTrust`.
Wine's builtin DLLs have neither embedded signatures nor catalog signatures, so these applications stop with "Security verification failed (NO_SIGNATURE)".

To let this verification pass the same way it does on Windows, `run.sh` does the following when it prepares the prefix:

1. Generate a root CA that imitates the Windows system components, and add it to the Root store of the prefix.
2. For all system DLLs in `syswow64` (32-bit) and `system32` (64-bit) of the prefix, build security catalogs (`.cat`) holding their Authenticode hashes, and sign them with SHA1 using a code signing certificate chained to that CA.
3. Put both catalogs in `catroot\{127d0a1d-...}`.

The catalogs are built after DXVK is installed, so they also cover the DXVK DLLs.

The catalog hashes depend on the contents of the DLLs, so `run.sh` records the Wine version and a hash of its setup (`run.sh`, `tools/*.py`) it prepared the prefix with, and prepares the prefix again when either changes.

`programs/` is a directory, not tracked by git, for keeping installers and other programs locally.
