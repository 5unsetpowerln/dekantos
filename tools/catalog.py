#!/usr/bin/env python3
"""Build a security catalog (.cat) that lets Wine's builtin DLLs pass signature verification.

To match what Wine's wintrust reads, each member gets two attributes, CAT_MEMBERINFO and
SPC_INDIRECT_DATA, and the Digest of the latter holds the Authenticode hash of the DLL.
The catalog is signed with a code signing certificate chained to the CA (CN=Microsoft Windows by default).

Usage:
  catalog.py --ca-dir <dir> --out <cat> --name "Microsoft Windows" <dll> [<dll> ...]
  <ca-dir> must contain ca.key / ca.der created by gen_ca.py.
"""
import argparse
import datetime
import hashlib
import pathlib
import struct

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from asn1crypto import core, cms, algos

# --- OID ---
OID_CTL = "1.3.6.1.4.1.311.10.1"
OID_CATALOG_LIST = "1.3.6.1.4.1.311.12.1.1"
OID_CAT_MEMBERINFO = "1.3.6.1.4.1.311.12.2.2"
OID_SPC_INDIRECT_DATA = "1.3.6.1.4.1.311.2.1.4"
OID_SPC_PE_IMAGE_DATA = "1.3.6.1.4.1.311.2.1.15"
OID_SHA1 = "1.3.14.3.2.26"
MEMBER_GUID = "{C689AAB8-8E78-11D0-8C47-00C04FC295EE}"


# --- Authenticode hash (same computation as Wine's pe_image_hash) ---
def authenticode_sha1(path):
    data = bytearray(pathlib.Path(path).read_bytes())
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe:pe + 4] == b"PE\0\0", "not a PE"
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    checksum_off = opt + 64
    datadir = opt + (96 if magic == 0x10B else 112)
    sec_entry = datadir + 4 * 8  # DataDirectory[IMAGE_DIRECTORY_ENTRY_SECURITY]
    sig_pos = struct.unpack_from("<I", data, sec_entry)[0]

    h = hashlib.sha1()
    h.update(data[0:checksum_off])
    h.update(data[checksum_off + 4:sec_entry])
    start = sec_entry + 8
    end = sig_pos if sig_pos else len(data)
    h.update(data[start:end])
    if not sig_pos:
        rem = len(data) % 8
        if rem:
            h.update(b"\x00" * (8 - rem))
    return h.digest()


# --- ASN.1 structures of the CTL ---
class AlgId(core.Sequence):
    _fields = [("algorithm", core.ObjectIdentifier), ("parameters", core.Any, {"optional": True})]


class DigestInfo(core.Sequence):
    _fields = [("digestAlgorithm", AlgId), ("digest", core.OctetString)]


class SpcAttrTypeAndValue(core.Sequence):
    _fields = [("type", core.ObjectIdentifier), ("value", core.Any, {"optional": True})]


class SpcIndirectData(core.Sequence):
    _fields = [("data", SpcAttrTypeAndValue), ("messageDigest", DigestInfo)]


class CatMemberInfo(core.Sequence):
    _fields = [("subjGuid", core.BMPString), ("certVersion", core.Integer)]


class SetOfAny(core.SetOf):
    _child_spec = core.Any


class CtlAttribute(core.Sequence):
    _fields = [("type", core.ObjectIdentifier), ("values", SetOfAny)]


class CtlAttributes(core.SetOf):
    _child_spec = CtlAttribute


class CtlEntry(core.Sequence):
    _fields = [("subjectIdentifier", core.OctetString), ("attributes", CtlAttributes)]


class CtlEntries(core.SequenceOf):
    _child_spec = CtlEntry


class CtlUsage(core.SequenceOf):
    _child_spec = core.ObjectIdentifier


class Ctl(core.Sequence):
    _fields = [
        ("subjectUsage", CtlUsage),
        ("thisUpdate", core.UTCTime),
        ("subjectAlgorithm", AlgId),
        ("entries", CtlEntries),
    ]


def null():
    return core.Any(core.Null())


def build_entry(dll):
    digest = authenticode_sha1(dll)
    mi = CatMemberInfo({"subjGuid": MEMBER_GUID, "certVersion": 0x200})
    spc = SpcIndirectData({
        "data": SpcAttrTypeAndValue({
            "type": OID_SPC_PE_IMAGE_DATA,
            "value": core.Any.load(b"\x30\x00"),  # empty SpcPeImageData (Wine does not look inside)
        }),
        "messageDigest": DigestInfo({
            "digestAlgorithm": AlgId({"algorithm": OID_SHA1, "parameters": null()}),
            "digest": digest,
        }),
    })
    return CtlEntry({
        "subjectIdentifier": digest,
        "attributes": CtlAttributes([
            CtlAttribute({"type": OID_CAT_MEMBERINFO, "values": SetOfAny([core.Any.load(mi.dump())])}),
            CtlAttribute({"type": OID_SPC_INDIRECT_DATA, "values": SetOfAny([core.Any.load(spc.dump())])}),
        ]),
    })


def build_ctl(dlls):
    now = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    entries, seen = [], set()
    for d in dlls:
        try:
            e = build_entry(d)
        except (AssertionError, struct.error, OSError):
            continue  # skip files that are not PE images
        tag = bytes(e["subjectIdentifier"].native)
        if tag in seen:  # add DLLs with the same hash (same content) only once
            continue
        seen.add(tag)
        entries.append(e)
    ctl = Ctl({
        "subjectUsage": CtlUsage([OID_CATALOG_LIST]),
        "thisUpdate": now,
        "subjectAlgorithm": AlgId({"algorithm": OID_SHA1, "parameters": null()}),
        "entries": CtlEntries(entries),
    })
    return ctl.dump(), len(entries)


def make_codesign_cert(ca_key, ca_cert, name):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1))
        .not_valid_after(datetime.datetime(2040, 1, 1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CODE_SIGNING]), critical=False)
        .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
            key_encipherment=False, data_encipherment=False, key_agreement=False,
            key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False),
            critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    return key, cert


def build_catalog(ctl_der, sign_key, sign_cert, ca_cert):
    # MS catalog convention: encapContentInfo = SEQUENCE { OID, [0] EXPLICIT { CTL-SEQUENCE } }
    # (the CTL goes directly inside [0], not in an OCTET STRING; asn1crypto's Any omits [0], so build it by hand)
    def der_len(n):
        if n < 0x80:
            return bytes([n])
        b = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return bytes([0x80 | len(b)]) + b

    oid_tlv = core.ObjectIdentifier(OID_CTL).dump()
    a0 = b"\xa0" + der_len(len(ctl_der)) + ctl_der          # [0] EXPLICIT { CTL }
    body = oid_tlv + a0
    eci_der = b"\x30" + der_len(len(body)) + body
    econtent = cms.ContentInfo.load(eci_der)

    # CryptCATAdminEnumCatalogFromHash opens catalogs with the MS Base Provider (PROV_RSA_FULL, SHA1 only),
    # and CryptMsgUpdate fails on SHA256, so sign the CMS with SHA1.
    digest = hashlib.sha1(ctl_der).digest()
    signed_attrs = cms.CMSAttributes([
        cms.CMSAttribute({"type": "content_type", "values": [OID_CTL]}),
        cms.CMSAttribute({"type": "message_digest", "values": [digest]}),
    ])
    signature = sign_key.sign(signed_attrs.dump(), padding.PKCS1v15(), hashes.SHA1())

    sign_cert_a = cms.Certificate.load(sign_cert.public_bytes(serialization.Encoding.DER))
    ca_cert_a = cms.Certificate.load(ca_cert.public_bytes(serialization.Encoding.DER))

    signer = cms.SignerInfo({
        "version": "v1",
        "sid": cms.SignerIdentifier({"issuer_and_serial_number": cms.IssuerAndSerialNumber({
            "issuer": sign_cert_a.issuer,
            "serial_number": sign_cert.serial_number,
        })}),
        "digest_algorithm": algos.DigestAlgorithm({"algorithm": "sha1"}),
        "signed_attrs": signed_attrs,
        "signature_algorithm": algos.SignedDigestAlgorithm({"algorithm": "rsassa_pkcs1v15"}),
        "signature": signature,
    })
    signed = cms.SignedData({
        "version": "v1",
        "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha1"})],
        "encap_content_info": econtent,
        "certificates": [sign_cert_a, ca_cert_a],
        "signer_infos": [signer],
    })
    return cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ca-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="Microsoft Windows")
    ap.add_argument("dlls", nargs="+")
    a = ap.parse_args()

    ca_dir = pathlib.Path(a.ca_dir)
    ca_key = serialization.load_pem_private_key((ca_dir / "ca.key").read_bytes(), None)
    ca_cert = x509.load_der_x509_certificate((ca_dir / "ca.der").read_bytes())

    sign_key, sign_cert = make_codesign_cert(ca_key, ca_cert, a.name)
    ctl_der, count = build_ctl(a.dlls)
    cat = build_catalog(ctl_der, sign_key, sign_cert, ca_cert)
    pathlib.Path(a.out).write_bytes(cat)
    print(f"wrote {a.out}: {count} members, {len(cat)} bytes")


if __name__ == "__main__":
    main()
