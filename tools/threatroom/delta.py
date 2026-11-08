#!/usr/bin/env python3
"""MMSD deltas: rebuild a file from another one with copy and insert operations (the MMS Registry's threatroom.c
applies them).

    format: "MMSD" u32 version(1) | u32 src_size, sha1[20] | u32 dst_size, sha1[20] | u32 nops |
            ops: u8 0 (copy) u32 src_offset u32 length  /  u8 1 (insert) u32 length bytes
"""
import hashlib
import struct

BLOCK = 16


def make(src, dst):
    index = {}
    for i in range(0, len(src) - BLOCK + 1):
        lst = index.setdefault(src[i:i + BLOCK], [])
        if len(lst) < 64:
            lst.append(i)
    ops, lit = [], bytearray()
    t = 0
    while t < len(dst):
        best_len, best_off = 0, 0
        for s in index.get(dst[t:t + BLOCK], ()):
            n = BLOCK
            while t + n < len(dst) and s + n < len(src) and dst[t + n] == src[s + n]:
                n += 1
            if n > best_len:
                best_len, best_off = n, s
        if best_len >= BLOCK:
            if lit:
                ops.append((1, bytes(lit)))
                lit = bytearray()
            ops.append((0, best_off, best_len))
            t += best_len
        else:
            lit.append(dst[t])
            t += 1
    if lit:
        ops.append((1, bytes(lit)))
    out = bytearray(b"MMSD" + struct.pack("<I", 1))
    out += struct.pack("<I", len(src)) + hashlib.sha1(src).digest()
    out += struct.pack("<I", len(dst)) + hashlib.sha1(dst).digest()
    out += struct.pack("<I", len(ops))
    for op in ops:
        if op[0] == 0:
            out += struct.pack("<BII", 0, op[1], op[2])
        else:
            out += struct.pack("<BI", 1, len(op[1])) + op[1]
    return bytes(out)


def apply(delta, src):
    assert delta[:4] == b"MMSD" and struct.unpack_from("<I", delta, 4)[0] == 1
    ssize, = struct.unpack_from("<I", delta, 8)
    ssha = delta[12:32]
    dsize, = struct.unpack_from("<I", delta, 32)
    dsha = delta[36:56]
    nops, = struct.unpack_from("<I", delta, 56)
    if len(src) != ssize or hashlib.sha1(src).digest() != ssha:
        raise ValueError("source does not match")
    at, out = 60, bytearray()
    for _ in range(nops):
        t = delta[at]
        if t == 0:
            off, n = struct.unpack_from("<II", delta, at + 1)
            out += src[off:off + n]
            at += 9
        else:
            n, = struct.unpack_from("<I", delta, at + 1)
            out += delta[at + 5:at + 5 + n]
            at += 5 + n
    if len(out) != dsize or hashlib.sha1(out).digest() != dsha:
        raise ValueError("result does not match")
    return bytes(out)


def c_array(name, data):
    lines = [f"static const unsigned char {name}[{len(data)}] = {{"]
    for i in range(0, len(data), 24):
        lines.append("    " + ",".join(str(b) for b in data[i:i + 24]) + ",")
    lines.append("};")
    return "\n".join(lines)
