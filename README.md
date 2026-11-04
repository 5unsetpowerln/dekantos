# windows-execution (Wine環境パッケージ)

WindowsアプリをLinux上のWineで、追加の手設定なしに実機に近く動かすための環境を用意する。

## いま対応しているもの

- **LINE (Windows版)**: 配布版インストーラー `LineInst.exe` を実行するだけで、
  本体のダウンロード・インストール・起動までが通る。

## 前提

- `wine` (64bit WoW64構成, wine-11.17 で確認)
- `python3` と `cryptography` / `asn1crypto` パッケージ
  (`pip install cryptography asn1crypto`)
- `i686-w64-mingw32-gcc` / `x86_64-w64-mingw32-gcc` は不要 (カタログ生成はPythonのみ)

## 使い方

```sh
# 0. LINEのインストーラーを programs/LineInst.exe として置く (配布物なのでgit管理外)

# 1. 新規prefixを、署名検証を通せる状態に整える
./build-prefix.sh /path/to/prefix

# 2. LINEをインストールする (利用規約に同意して進める)
./run-line.sh /path/to/prefix install

# 3. 以降、インストール済みのLINEを起動する
./run-line.sh /path/to/prefix launch
```

## 仕組み (なぜこれが要るか)

`LineInst.exe` やLINE本体は、起動時に自分が読み込むシステムDLL
(`gdiplus.dll`, `crypt32.dll` など)のAuthenticode署名を `WinVerifyTrust` で検証し、
署名が無いと「Security verification failed (NO_SIGNATURE)」で停止する。
Wineの内蔵DLLは埋め込み署名もカタログ署名も持たないため、そのままでは止まる。

`build-prefix.sh` は、この検証を実機と同じ形で通すために次を行う:

1. Windowsのシステムコンポーネントを模した自作ルートCAを生成し、prefixのRootストアに導入する。
2. prefix内の `syswow64` (32bit)と `system32` (64bit)の全システムDLLについて、
   Authenticodeハッシュを載せたセキュリティカタログ (`.cat`)を作り、そのCAに連なる
   コード署名証明書でSHA1署名する。
3. 両カタログを `catroot\{127d0a1d-...}` に置く。

これにより、32bitプロセス (インストーラー)も64bitプロセス (LINE本体)も、Wineの内蔵DLLを
「署名済みのOSファイル」として受け入れ、検証を通過して起動できる。

> カタログのハッシュはWineのDLLの中身に依存するため、**Wineを更新したら
> `build-prefix.sh` を実行し直して** prefixを作り直すこと。
