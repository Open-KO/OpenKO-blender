"""
Parser and decompressor for .dxt texture files (CN3Texture).

CN3Texture extends CN3BaseFileAccess.

Binary layout:
  string      name            (CN3BaseFileAccess)
  char[4]     header_id       (e.g. b"DXT3", b"NTF3")
  int32       width
  int32       height
  int32       format          (D3DFORMAT FOURCC or integer)
  bool(1)     has_mipmap
  [raw DXT block data, possibly multiple mipmap levels]

DXT format FOURCC values (stored as little-endian int32):
  DXT1 = 0x31545844 = 827611204
  DXT3 = 0x33545844 = 861165636
  DXT5 = 0x35545844 = 894720068
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from io import BytesIO
from pathlib import Path

from ._base import read_name
from ..utils.binary_reader import BinaryReader


class DxtFormat(IntEnum):
    DXT1 = 827611204   # 0x31545844
    DXT2 = 844388420   # 0x32545844
    DXT3 = 861165636   # 0x33545844
    DXT4 = 877942852   # 0x34545844
    DXT5 = 894720068   # 0x35545844
    A4R4G4B4 = 26


@dataclass
class DxtTexture:
    name: str
    header_id: bytes   # 4-byte identifier string
    width: int
    height: int
    fmt: DxtFormat
    has_mipmap: bool
    mip_data: list[bytes] = field(default_factory=list)  # raw DXT blocks per mip level


def load(path: Path | str) -> DxtTexture:
    """Parse a .dxt texture file and return a DxtTexture with raw block data."""
    path = Path(path)
    r = BinaryReader.from_file(path)

    name = read_name(r)
    header_id = r.read_bytes(4)
    width = r.read_int32()
    height = r.read_int32()
    raw_format = r.read_int32()
    has_mipmap = r.read_bool()

    try:
        fmt = DxtFormat(raw_format)
    except ValueError:
        raise ValueError(f"Unsupported texture format value: {raw_format} in {path.name!r}")

    mip_data: list[bytes] = []

    if fmt in (DxtFormat.DXT1, DxtFormat.DXT2):
        block_bytes = 8  # 8 bytes per 4×4 block
        base_size = (width * height) // 2

        if has_mipmap:
            # Multiple mip levels at base_size each, then smaller mips
            mip_count = _count_mips(width, height)
            for _ in range(mip_count):
                mip_data.append(r.read_bytes(base_size))
            # Skip remaining smaller mip levels
            w, h = width // 2, height // 2
            while w >= 4 and h >= 4:
                r.skip((w * h) // 2)
                w //= 2
                h //= 2
        else:
            mip_data.append(r.read_bytes(base_size))
            # Skip extra data that follows in single-mip DXT1 files
            r.skip((width * height) // 4)
            if width >= 1024:
                r.skip(256 * 256 * 2)

    elif fmt in (DxtFormat.DXT3, DxtFormat.DXT4, DxtFormat.DXT5):
        base_size = width * height  # 16 bytes per 4×4 block (twice DXT1)

        if has_mipmap:
            mip_count = _count_mips(width, height)
            for _ in range(mip_count):
                mip_data.append(r.read_bytes(base_size))
            w, h = width // 2, height // 2
            while w >= 4 and h >= 4:
                r.skip(w * h)
                w //= 2
                h //= 2
        else:
            mip_data.append(r.read_bytes(base_size))

    else:
        raise ValueError(f"Texture format {fmt.name} decompression is not yet supported.")

    return DxtTexture(
        name=name,
        header_id=header_id,
        width=width,
        height=height,
        fmt=fmt,
        has_mipmap=has_mipmap,
        mip_data=mip_data,
    )


def decompress_to_rgba(tex: DxtTexture, mip_level: int = 0) -> bytes:
    """Decompress a DxtTexture to raw RGBA bytes (width × height × 4).

    Uses a pure-Python DXT1/DXT5 decompressor derived from the prototype.
    """
    if mip_level >= len(tex.mip_data):
        raise ValueError(f"Mip level {mip_level} not available (max {len(tex.mip_data) - 1}).")

    raw = tex.mip_data[mip_level]
    buf = BytesIO(raw)
    w, h = tex.width, tex.height

    if tex.fmt in (DxtFormat.DXT1, DxtFormat.DXT2):
        return _decompress_dxt1(buf, w, h)
    elif tex.fmt in (DxtFormat.DXT3, DxtFormat.DXT4, DxtFormat.DXT5):
        return _decompress_dxt5(buf, w, h)
    else:
        raise ValueError(f"Decompression not implemented for {tex.fmt.name}.")


# ── DXT decompression (ported from prototype) ─────────────────────────────────


def _unpack_rgb565(packed: int) -> tuple[int, int, int, int]:
    r = ((packed >> 11) & 0x1F)
    g = ((packed >> 5) & 0x3F)
    b = ((packed) & 0x1F)
    r = (r << 3) | (r >> 2)
    g = (g << 2) | (g >> 4)
    b = (b << 3) | (b >> 2)
    return (r, g, b, 255)


def _read_u(buf: BytesIO, n: int) -> int:
    SIGNS = {1: "B", 2: "H", 4: "I", 8: "Q"}
    return struct.unpack("<" + SIGNS[n], buf.read(n))[0]


def _decompress_dxt1(buf: BytesIO, width: int, height: int) -> bytes:
    block_x = width // 4
    block_y = height // 4
    pixels = bytearray(width * height * 4)

    for row in range(block_x):
        for col in range(block_y):
            c0 = _read_u(buf, 2)
            c1 = _read_u(buf, 2)
            ctable = _read_u(buf, 4)
            _fill_dxt1_block(pixels, row * 4, col * 4, c0, c1, ctable, width, 255)

    return bytes(pixels)


def _decompress_dxt5(buf: BytesIO, width: int, height: int) -> bytes:
    block_x = width // 4
    block_y = height // 4
    pixels = bytearray(width * height * 4)

    for row in range(block_x):
        for col in range(block_y):
            a0 = _read_u(buf, 1)
            a1 = _read_u(buf, 1)
            atable = buf.read(6)
            acode0 = (atable[2] | (atable[3] << 8) | (atable[4] << 16) | (atable[5] << 24))
            acode1 = (atable[0] | (atable[1] << 8))
            c0 = _read_u(buf, 2)
            c1 = _read_u(buf, 2)
            ctable = _read_u(buf, 4)

            for j in range(4):
                for i in range(4):
                    alpha = _get_alpha(j, i, a0, a1, acode0, acode1)
                    px = row * 4 + i
                    py = col * 4 + j
                    if px < width and py < height:
                        color = _get_dxt1_color(i, j, c0, c1, ctable, alpha)
                        idx = (py * width + px) * 4
                        pixels[idx : idx + 4] = color

    return bytes(pixels)


def _fill_dxt1_block(pixels, bx, by, c0, c1, ctable, width, default_alpha):
    rc0 = _unpack_rgb565(c0)
    rc1 = _unpack_rgb565(c1)
    for j in range(4):
        for i in range(4):
            px = bx + i
            py = by + j
            if px < width:
                color = _get_dxt1_color(i, j, c0, c1, ctable, default_alpha)
                idx = (py * width + px) * 4
                pixels[idx : idx + 4] = color


def _get_dxt1_color(i, j, c0, c1, ctable, alpha) -> bytes:
    code = (ctable >> (2 * (4 * i + j))) & 0x03
    rc0 = _unpack_rgb565(c0)
    rc1 = _unpack_rgb565(c1)
    r0, g0, b0 = rc0[0], rc0[1], rc0[2]
    r1, g1, b1 = rc1[0], rc1[1], rc1[2]
    if code == 0:
        return bytes([r0, g0, b0, alpha])
    if code == 1:
        return bytes([r1, g1, b1, alpha])
    if c0 > c1:
        if code == 2:
            return bytes([(2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3, alpha])
        return bytes([(r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3, alpha])
    else:
        if code == 2:
            return bytes([(r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, alpha])
        return bytes([0, 0, 0, alpha])


def _get_alpha(i, j, a0, a1, acode0, acode1) -> int:
    alpha_index = 3 * (4 * j + i)
    if alpha_index <= 12:
        alpha_code = (acode1 >> alpha_index) & 0x07
    elif alpha_index == 15:
        alpha_code = (acode1 >> 15) | ((acode0 << 1) & 0x06)
    else:
        alpha_code = (acode0 >> (alpha_index - 16)) & 0x07

    if alpha_code == 0:
        return a0
    if alpha_code == 1:
        return a1
    if a0 > a1:
        return ((8 - alpha_code) * a0 + (alpha_code - 1) * a1) // 7
    if alpha_code == 6:
        return 0
    if alpha_code == 7:
        return 255
    alphas = [0, a0, a1,
              (4 * a0 + 1 * a1) // 5,
              (3 * a0 + 2 * a1) // 5,
              (2 * a0 + 3 * a1) // 5,
              (1 * a0 + 4 * a1) // 5,
              0]
    return alphas[alpha_code] if alpha_code < len(alphas) else 0


def _count_mips(width: int, height: int) -> int:
    count = 1
    w, h = width, height
    while w >= 4 and h >= 4:
        count += 1
        w //= 2
        h //= 2
    return count
