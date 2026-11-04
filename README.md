# windows-execution (Wine environment package)

An environment for running Windows applications on Linux with Wine, as close to a real Windows machine as possible and without manual setup.

## Usage

```sh
./run.sh <executable> [args...]
```

- The executable can be given as a Unix path or as a `C:\...` path.
- The prefix is `WINEPREFIX`. If it is not set, `prefix/` in this directory is used.
- Changes made by the executable (such as an installation) stay in the prefix and are available to later runs.
- On the first run, and whenever the Wine version changes, the prefix is prepared before the executable runs (this takes about 30 seconds).

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

## How it works

Some applications, such as `LineInst.exe` and LINE itself, verify the Authenticode signatures of the system DLLs they load (`gdiplus.dll`, `crypt32.dll`, and so on) with `WinVerifyTrust`.
Wine's builtin DLLs have neither embedded signatures nor catalog signatures, so these applications stop with "Security verification failed (NO_SIGNATURE)".

To let this verification pass the same way it does on Windows, `run.sh` does the following when it prepares the prefix:

1. Generate a root CA that imitates the Windows system components, and add it to the Root store of the prefix.
2. For all system DLLs in `syswow64` (32-bit) and `system32` (64-bit) of the prefix, build security catalogs (`.cat`) holding their Authenticode hashes, and sign them with SHA1 using a code signing certificate chained to that CA.
3. Put both catalogs in `catroot\{127d0a1d-...}`.

The catalog hashes depend on the contents of Wine's DLLs, so `run.sh` records the Wine version it prepared the prefix with, and updates the prefix and rebuilds the catalogs when the version changes.

`programs/` is a directory, not tracked by git, for keeping installers and other programs locally.
