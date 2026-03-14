"""
Unit tests for BinaryReader using synthetic hand-crafted byte sequences.

These tests have no dependency on real asset files.
"""

import struct

import pytest

from openko_blender.utils.binary_reader import BinaryReader


def make(*args):
    """Pack values into bytes using little-endian struct.pack."""
    return b"".join(args)


# ── Primitives ────────────────────────────────────────────────────────────────


def test_read_bool_true():
    r = BinaryReader(b"\x01")
    assert r.read_bool() is True


def test_read_bool_false():
    r = BinaryReader(b"\x00")
    assert r.read_bool() is False


def test_read_int8_positive():
    r = BinaryReader(b"\x7f")
    assert r.read_int8() == 127


def test_read_int8_negative():
    r = BinaryReader(b"\x80")
    assert r.read_int8() == -128


def test_read_uint8():
    r = BinaryReader(b"\xff")
    assert r.read_uint8() == 255


def test_read_int16():
    r = BinaryReader(struct.pack("<h", -1000))
    assert r.read_int16() == -1000


def test_read_uint16():
    r = BinaryReader(struct.pack("<H", 65535))
    assert r.read_uint16() == 65535


def test_read_int32():
    r = BinaryReader(struct.pack("<i", -100000))
    assert r.read_int32() == -100000


def test_read_uint32():
    r = BinaryReader(struct.pack("<I", 0xDEADBEEF))
    assert r.read_uint32() == 0xDEADBEEF


def test_read_float():
    r = BinaryReader(struct.pack("<f", 3.14))
    assert abs(r.read_float() - 3.14) < 1e-5


def test_read_bytes():
    r = BinaryReader(b"\x01\x02\x03\x04")
    assert r.read_bytes(3) == b"\x01\x02\x03"
    assert r.pos == 3


# ── Position tracking ─────────────────────────────────────────────────────────


def test_pos_advances():
    r = BinaryReader(struct.pack("<4i", 1, 2, 3, 4))
    assert r.pos == 0
    r.read_int32()
    assert r.pos == 4
    r.read_int32()
    assert r.pos == 8


def test_remaining():
    r = BinaryReader(b"\x00" * 10)
    assert r.remaining == 10
    r.skip(3)
    assert r.remaining == 7


def test_skip():
    r = BinaryReader(b"\x00" * 8 + struct.pack("<i", 42))
    r.skip(8)
    assert r.read_int32() == 42


def test_seek():
    data = struct.pack("<3i", 10, 20, 30)
    r = BinaryReader(data)
    r.seek(8)
    assert r.read_int32() == 30


# ── String ────────────────────────────────────────────────────────────────────


def test_read_string_normal():
    text = "hello"
    data = struct.pack("<i", len(text)) + text.encode()
    r = BinaryReader(data)
    assert r.read_string() == "hello"


def test_read_string_empty_length_zero():
    data = struct.pack("<i", 0)
    r = BinaryReader(data)
    assert r.read_string() == ""


def test_read_string_negative_length():
    data = struct.pack("<i", -1)
    r = BinaryReader(data)
    assert r.read_string() == ""


def test_read_string_unicode():
    text = "test_name"
    data = struct.pack("<i", len(text)) + text.encode("utf-8")
    r = BinaryReader(data)
    assert r.read_string() == "test_name"


# ── Composite types ───────────────────────────────────────────────────────────


def test_read_vector3():
    data = struct.pack("<3f", 1.0, 2.0, 3.0)
    r = BinaryReader(data)
    assert r.read_vector3() == pytest.approx((1.0, 2.0, 3.0))


def test_read_quaternion():
    data = struct.pack("<4f", 0.0, 0.0, 0.0, 1.0)
    r = BinaryReader(data)
    assert r.read_quaternion() == pytest.approx((0.0, 0.0, 0.0, 1.0))


def test_read_matrix44_identity():
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    data = struct.pack("<16f", *identity)
    r = BinaryReader(data)
    m = r.read_matrix44()
    assert m[0] == pytest.approx((1.0, 0.0, 0.0, 0.0))
    assert m[3] == pytest.approx((0.0, 0.0, 0.0, 1.0))
    assert r.pos == 64


def test_read_uv_u_is_first_float():
    # File stores (tu, tv) per C++ __VertexT1 / CN3IMesh::UVSet.
    # U is the first float, V is second (and gets flipped).
    u_raw, v_raw = 0.75, 0.25
    data = struct.pack("<2f", u_raw, v_raw)
    r = BinaryReader(data)
    result_u, result_v = r.read_uv()
    assert result_u == pytest.approx(0.75)        # u unchanged
    assert result_v == pytest.approx(0.75)        # 1 - 0.25


def test_read_uv_v_flip_zero():
    # V=0.0 in DX (top of texture) → V=1.0 in Blender (top of texture)
    data = struct.pack("<2f", 0.5, 0.0)           # u=0.5, v_raw=0.0
    r = BinaryReader(data)
    u, v = r.read_uv()
    assert u == pytest.approx(0.5)
    assert v == pytest.approx(1.0)                # 1 - 0.0


def test_read_uv_v_flip_one():
    # V=1.0 in DX (bottom) → V=0.0 in Blender (bottom)
    data = struct.pack("<2f", 0.0, 1.0)           # u=0.0, v_raw=1.0
    r = BinaryReader(data)
    u, v = r.read_uv()
    assert u == pytest.approx(0.0)
    assert v == pytest.approx(0.0)                # 1 - 1.0


def test_read_vertex():
    data = struct.pack("<6f", 1.0, 2.0, 3.0, 0.0, 1.0, 0.0)
    r = BinaryReader(data)
    pos, normal = r.read_vertex()
    assert pos == pytest.approx((1.0, 2.0, 3.0))
    assert normal == pytest.approx((0.0, 1.0, 0.0))
    assert r.pos == 24


def test_read_vertex_with_uv():
    # pos(3f) + normal(3f) + tu(f) + tv(f)  per C++ __VertexT1
    data = struct.pack("<8f", 1.0, 2.0, 3.0, 0.0, 0.0, 1.0, 0.6, 0.3)
    r = BinaryReader(data)
    pos, normal, uv = r.read_vertex_with_uv()
    assert pos == pytest.approx((1.0, 2.0, 3.0))
    assert normal == pytest.approx((0.0, 0.0, 1.0))
    assert uv[0] == pytest.approx(0.6)   # u  (first float, tu)
    assert uv[1] == pytest.approx(0.7)   # 1 - 0.3  (1 - tv)
    assert r.pos == 32


# ── from_file ────────────────────────────────────────────────────────────────


def test_from_file(tmp_path):
    p = tmp_path / "test.bin"
    p.write_bytes(struct.pack("<i", 12345))
    r = BinaryReader.from_file(p)
    assert r.read_int32() == 12345
