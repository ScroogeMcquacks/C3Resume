"""
c3wire.py - minimal Cossacks 3 lobby wire helpers.
Layout derived by reading Sich v0.2.9 (xpackage.get / xpacket.receive / xpack.read_parser); used by the
simulator in this folder.
"""
import struct
from typing import BinaryIO, Iterator, List, Tuple

HDR = struct.Struct("<IHII")          # payload_len, code, id_from, id_to  (little-endian, 14 bytes)
assert HDR.size == 14

# Codes copied from Sich's xcmd table (subset)
CODES = {
    0x0194: "SERVER_SESSION_MSG", 0x0195: "USER_SESSION_MSG",
    0x01BB: "SERVER_SESSION_PARSER", 0x01BC: "USER_SESSION_PARSER",
    0x01BD: "USER_SESSION_RECREATE", 0x01BE: "USER_SESSION_REJOIN",
    0x01C1: "SERVER_SESSION_REJOIN",
    0x01E4: "SERVER_CHECKSUM", 0x01E5: "USER_CHECKSUM", 0x01E6: "USER_CHECKSUM_FAILED",
    0x0032: "LAN_PARSER", 0x04B0: "LAN_RECORD",
}

def pack_frame(code: int, id_from: int, id_to: int, payload: bytes = b"") -> bytes:
    return HDR.pack(len(payload), code, id_from, id_to) + payload

def read_frames(stream: BinaryIO) -> Iterator[Tuple[int, int, int, bytes]]:
    while True:
        head = stream.read(HDR.size)
        if len(head) < HDR.size:
            return
        n, code, a, b = HDR.unpack(head)
        payload = stream.read(n)
        if len(payload) < n:
            return
        yield code, a, b, payload

# "parser" tree: key(u32 len+bytes) value(u32 len+bytes) child_count(u32) children...
Node = Tuple[str, str, list]

def write_node(key: str, value: str, children: List[Node] = ()) -> bytes:
    k, v = key.encode("latin-1"), value.encode("latin-1")
    out = struct.pack("<I", len(k)) + k + struct.pack("<I", len(v)) + v + struct.pack("<I", len(children))
    for c in children:
        out += write_node(*c)
    return out

def read_node(buf: bytes, pos: int = 0) -> Tuple[Node, int]:
    (kl,) = struct.unpack_from("<I", buf, pos); pos += 4
    key = buf[pos:pos + kl].decode("latin-1"); pos += kl
    (vl,) = struct.unpack_from("<I", buf, pos); pos += 4
    val = buf[pos:pos + vl].decode("latin-1"); pos += vl
    (cnt,) = struct.unpack_from("<I", buf, pos); pos += 4
    kids = []
    for _ in range(cnt):
        kid, pos = read_node(buf, pos)
        kids.append(kid)
    return (key, val, kids), pos
