"""Tests for the .dxt texture parser."""

import struct
import tempfile
from pathlib import Path

import pytest
from openko_blender.formats import dxt_texture
from openko_blender.formats.dxt_texture import DxtFormat


# ── Synthetic file helpers ─────────────────────────────────────────────────────


def _make_dxt1_file(width: int, height: int, dxt1_blocks: bytes, has_mipmap: bool = False) -> Path:
    """Write a minimal synthetic .dxt (NTF3) file and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".dxt", delete=False)

    # CN3BaseFileAccess name string: int32 length = 0 (empty)
    tmp.write(struct.pack("<i", 0))
    # DXT header: szID(4) + width(4) + height(4) + format(4) + bMipMap BOOL(4)
    tmp.write(b"NTF3")
    tmp.write(struct.pack("<i", width))
    tmp.write(struct.pack("<i", height))
    tmp.write(struct.pack("<i", DxtFormat.DXT1))
    tmp.write(struct.pack("<i", int(has_mipmap)))  # Win32 BOOL = 4 bytes
    # DXT1 pixel data
    tmp.write(dxt1_blocks)
    # Fallback padding expected after DXT1 data (width*height//4 bytes)
    tmp.write(b"\x00" * (width * height // 4))
    tmp.close()
    return Path(tmp.name)


def _solid_dxt1_block(r: int, g: int, b: int) -> bytes:
    """Return an 8-byte DXT1 block where all 16 pixels are the given RGB colour.

    Encodes the colour as color0 in RGB565, sets color1 = 0, and fills the
    lookup table with all-zero codes (all pixels = color0).
    """
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    color0 = (r5 << 11) | (g6 << 5) | b5
    color1 = 0x0000  # must be < color0 so code=3 is transparent; unused here
    ctable = 0x00000000  # all 16 pixels → code 0 → color0
    return struct.pack("<HHI", color0, color1, ctable)


def test_load_parses_without_error(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert tex is not None


def test_dimensions_are_positive(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert tex.width > 0
    assert tex.height > 0


def test_dimensions_are_power_of_two(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert (tex.width & (tex.width - 1)) == 0, f"Width {tex.width} is not a power of 2"
    assert (tex.height & (tex.height - 1)) == 0, f"Height {tex.height} is not a power of 2"


def test_format_is_recognized(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert isinstance(tex.fmt, DxtFormat)


def test_has_mip_data(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert len(tex.mip_data) > 0
    assert len(tex.mip_data[0]) > 0


def test_header_id_is_bytes(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert isinstance(tex.header_id, bytes)
    assert len(tex.header_id) == 4


def test_decompress_returns_correct_size(dxt_file):
    tex = dxt_texture.load(dxt_file)
    if tex.fmt not in (DxtFormat.DXT1, DxtFormat.DXT5):
        pytest.skip(f"Decompression not implemented for {tex.fmt.name}")
    raw = dxt_texture.decompress_to_rgba(tex, mip_level=0)
    expected = tex.width * tex.height * 4
    assert len(raw) == expected


def test_decompress_rgba_values_in_range(dxt_file):
    tex = dxt_texture.load(dxt_file)
    if tex.fmt not in (DxtFormat.DXT1, DxtFormat.DXT5):
        pytest.skip(f"Decompression not implemented for {tex.fmt.name}")
    raw = dxt_texture.decompress_to_rgba(tex, mip_level=0)
    assert all(0 <= b <= 255 for b in raw)


# ── Synthetic DXT1 decompression tests ────────────────────────────────────────
# These use hand-crafted minimal .dxt files so the expected pixel values are
# known exactly.  They would catch:
#   • Wrong bMipMap field size (1 byte read instead of 4 → 3-byte misalignment)
#   • Wrong block iteration order (column-major vs row-major)
#   • Transposed color-table index within each block


def test_synthetic_dxt1_solid_red():
    """A 4×4 DXT1 texture made of a single all-red block decompresses correctly."""
    block = _solid_dxt1_block(255, 0, 0)
    path = _make_dxt1_file(4, 4, block)
    try:
        tex = dxt_texture.load(path)
        raw = dxt_texture.decompress_to_rgba(tex, mip_level=0)
    finally:
        path.unlink()

    assert len(raw) == 4 * 4 * 4
    # Every pixel should be red (with minor RGB565 rounding: 255→248 after encode/decode)
    for i in range(16):
        idx = i * 4
        r, g, b, a = raw[idx], raw[idx + 1], raw[idx + 2], raw[idx + 3]
        assert g == 0,   f"Pixel {i}: expected G=0, got {g}"
        assert b == 0,   f"Pixel {i}: expected B=0, got {b}"
        assert r > 200,  f"Pixel {i}: expected R≈255, got {r}"
        assert a == 255, f"Pixel {i}: expected A=255, got {a}"


def test_synthetic_dxt1_block_positions():
    """An 8×4 texture with two distinct blocks verifies row-major block ordering.

    Block layout (file order = row-major):
      block0 (bx=0, by=0) → pixels x=0..3, y=0..3  — solid red
      block1 (bx=1, by=0) → pixels x=4..7, y=0..3  — solid blue

    If blocks were placed column-major the colours would be transposed.
    """
    red_block  = _solid_dxt1_block(255, 0, 0)
    blue_block = _solid_dxt1_block(0, 0, 255)
    path = _make_dxt1_file(8, 4, red_block + blue_block)
    try:
        tex = dxt_texture.load(path)
        raw = dxt_texture.decompress_to_rgba(tex, mip_level=0)
    finally:
        path.unlink()

    def pixel(x, y):
        idx = (y * 8 + x) * 4
        return raw[idx], raw[idx + 1], raw[idx + 2], raw[idx + 3]

    # Left half (x=0..3) should be red
    r, g, b, _ = pixel(0, 0)
    assert r > 200 and g == 0 and b == 0, f"Expected red at (0,0), got ({r},{g},{b})"
    r, g, b, _ = pixel(3, 0)
    assert r > 200 and g == 0 and b == 0, f"Expected red at (3,0), got ({r},{g},{b})"

    # Right half (x=4..7) should be blue
    r, g, b, _ = pixel(4, 0)
    assert r == 0 and g == 0 and b > 200, f"Expected blue at (4,0), got ({r},{g},{b})"
    r, g, b, _ = pixel(7, 0)
    assert r == 0 and g == 0 and b > 200, f"Expected blue at (7,0), got ({r},{g},{b})"


def test_synthetic_dxt1_mip_data_size():
    """Mip data[0] must be exactly width*height//2 bytes for DXT1.

    If bMipMap were read as 1 byte instead of 4 (Win32 BOOL), the file cursor
    would be 3 bytes ahead of the real pixel data, producing garbage or a
    wrong-sized read.
    """
    w, h = 8, 8
    blocks = _solid_dxt1_block(128, 64, 32) * 4  # 2×2 blocks = 4 blocks
    path = _make_dxt1_file(w, h, blocks)
    try:
        tex = dxt_texture.load(path)
    finally:
        path.unlink()

    expected = (w * h) // 2   # DXT1: 4 bits per pixel
    assert len(tex.mip_data[0]) == expected, (
        f"mip_data[0] is {len(tex.mip_data[0])} bytes; expected {expected}. "
        "Likely caused by reading bMipMap as 1 byte instead of 4 (Win32 BOOL)."
    )
