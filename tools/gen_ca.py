#!/usr/bin/env python3
"""自作のルートCA証明書を生成し、WineのRootストアに入れる.reg を書き出す。
使い方: gen_ca.py <出力ディレクトリ>
  <dir>/ca.key, ca.der, ca.pem, root.reg を作る。"""
import struct
import sys
import hashlib
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pathlib

CERT_CERT_PROP_ID = 32

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, "WINE-LOCAL-CATALOG-ROOT"),
])
now = datetime.datetime(2020, 1, 1)
cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now)
    .not_valid_after(datetime.datetime(2040, 1, 1))
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False,
        key_encipherment=False, data_encipherment=False, key_agreement=False,
        key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False),
        critical=True)
    .sign(key, hashes.SHA256())
)

der = cert.public_bytes(serialization.Encoding.DER)
(out / "ca.key").write_bytes(key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption()))
(out / "ca.der").write_bytes(der)
(out / "ca.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))

thumb = hashlib.sha1(der).hexdigest().upper()
blob = struct.pack("<III", CERT_CERT_PROP_ID, 1, len(der)) + der

# .reg の REG_BINARY は「hex:」にカンマ区切りの16進を、76桁で折り返して書く
hexbytes = ",".join(f"{b:02x}" for b in blob)
lines, cur = [], "\"Blob\"=hex:"
for tok in hexbytes.split(","):
    piece = tok + ","
    if len(cur) + len(piece) > 76:
        lines.append(cur + "\\")
        cur = "  " + piece
    else:
        cur += piece
lines.append(cur.rstrip(","))
blob_reg = "\n".join(lines)

reg = (
    "Windows Registry Editor Version 5.00\r\n\r\n"
    f"[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\SystemCertificates\\Root\\Certificates\\{thumb}]\r\n"
    + blob_reg.replace("\n", "\r\n") + "\r\n"
)
(out / "root.reg").write_text(reg, encoding="utf-16-le")
# UTF-16 BOM を付ける
data = (out / "root.reg").read_bytes()
(out / "root.reg").write_bytes(b"\xff\xfe" + data)
print("thumbprint", thumb)
print("wrote", out)
