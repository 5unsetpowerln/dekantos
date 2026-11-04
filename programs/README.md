# programs

Wineで動かすWindowsのプログラム本体 (インストーラーや実行ファイル)を置く場所。
ここに置いたファイルは配布物なので、READMEを除いてgitでは追跡しない (`../.gitignore`)。

- LINEを導入するには、配布元のインストーラーをこのディレクトリに `LineInst.exe` という名前で置く。
  `../run-line.sh <prefix> install` がこのファイルを実行する。
