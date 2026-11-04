# windows-execution (Wine環境パッケージ)

WindowsアプリをLinux上のWineで、追加の手設定なしに実機に近く動かすための環境を用意する。

## 使い方

```sh
./run.sh <実行ファイル> [引数...]
```

- 実行ファイルは、Unixのパスでも`C:\...`の形のパスでもよい。
- prefixは`WINEPREFIX`で指定する。未指定なら、このディレクトリの`prefix/`を使う。
- 実行ファイルが行った変更 (インストールなど)はprefixに残り、次回以降の実行で使える。
- 初回と、Wineの版が変わったときは、実行の前にprefixを整える (30秒ほどかかる)。

例: LINE

```sh
# インストールする (利用規約に同意して進める)
./run.sh ~/Downloads/LineInst.exe

# インストールしたLINEを起動する
./run.sh prefix/drive_c/users/$USER/AppData/Local/LINE/bin/LineLauncher.exe
```

LINEの起動口は、LINEがレジストリに登録している`LineLauncher.exe`である。
`LINE.exe`を直接実行すると、起動トークンがないため終了する。

## 前提

- `wine` (64bit WoW64構成、wine-11.17で確認)
- `python3`と、`cryptography`、`asn1crypto`パッケージ

## 仕組み

`LineInst.exe`やLINE本体のように、起動時に自分が読み込むシステムDLL (`gdiplus.dll`、`crypt32.dll`など)のAuthenticode署名を`WinVerifyTrust`で検証するアプリがある。
Wineの内蔵DLLは埋め込み署名もカタログ署名も持たないため、こうしたアプリは「Security verification failed (NO_SIGNATURE)」で止まる。

`run.sh`は、この検証を実機と同じ形で通すため、prefixを整えるときに次を行う。

1. Windowsのシステムコンポーネントを模した自作ルートCAを生成し、prefixのRootストアに導入する。
2. prefix内の`syswow64` (32bit)と`system32` (64bit)の全システムDLLについて、Authenticodeハッシュを載せたセキュリティカタログ (`.cat`)を作り、そのCAに連なるコード署名証明書でSHA1署名する。
3. 両カタログを`catroot\{127d0a1d-...}`に置く。

カタログのハッシュはWineのDLLの中身に依存するため、`run.sh`はprefixを整えたときのWineの版を記録し、版が変わったらprefixを更新してカタログを作り直す。

`programs/`は、手元のインストーラーなどを置くための、gitで追跡しないディレクトリである。
