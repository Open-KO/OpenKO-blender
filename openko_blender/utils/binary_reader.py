"""
Low-level binary reading utilities.

BinaryReader wraps a bytes buffer with a position cursor and typed read methods.
All values are little-endian, matching the KnightOnline binary format.
"""

from __future__ import annotations

import struct
from pathlib import Path


class BinaryReader:
    """Stateful reader over a bytes buffer with a position cursor."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    # ── Factory ───────────────────────────────────────────────────────────

    @classmethod
    def from_file(cls, path: Path | str) -> "BinaryReader":
        with open(path, "rb") as f:
            return cls(f.read())

    # ── Position ──────────────────────────────────────────────────────────

    @property
    def pos(self) -> int:
        return self._pos

    @property
    def remaining(self) -> int:
        return len(self._data) - self._pos

    def skip(self, n: int) -> None:
        self._pos += n

    def seek(self, pos: int) -> None:
        self._pos = pos

    # ── Primitives ────────────────────────────────────────────────────────

    def read_bool(self) -> bool:
        (v,) = struct.unpack_from("<?", self._data, self._pos)
        self._pos += 1
        return v

    def read_int8(self) -> int:
        (v,) = struct.unpack_from("<b", self._data, self._pos)
        self._pos += 1
        return v

    def read_uint8(self) -> int:
        (v,) = struct.unpack_from("<B", self._data, self._pos)
        self._pos += 1
        return v

    def read_int16(self) -> int:
        (v,) = struct.unpack_from("<h", self._data, self._pos)
        self._pos += 2
        return v

    def read_uint16(self) -> int:
        (v,) = struct.unpack_from("<H", self._data, self._pos)
        self._pos += 2
        return v

    def read_int32(self) -> int:
        (v,) = struct.unpack_from("<i", self._data, self._pos)
        self._pos += 4
        return v

    def read_uint32(self) -> int:
        (v,) = struct.unpack_from("<I", self._data, self._pos)
        self._pos += 4
        return v

    def read_float(self) -> float:
        (v,) = struct.unpack_from("<f", self._data, self._pos)
        self._pos += 4
        return v

    def read_bytes(self, n: int) -> bytes:
        v = self._data[self._pos : self._pos + n]
        self._pos += n
        return v

    def read_string(self) -> str:
        """Length-prefixed UTF-8 string: int32 byte-count then raw chars.

        Returns empty string when length is zero or negative.
        """
        length = self.read_int32()
        if length <= 0:
            return ""
        raw = self._data[self._pos : self._pos + length]
        self._pos += length
        return raw.decode("utf-8", errors="replace")

    # ── Composite types ───────────────────────────────────────────────────

    def read_vector3(self) -> tuple[float, float, float]:
        """Read x, y, z as three consecutive float32s (12 bytes)."""
        x, y, z = struct.unpack_from("<3f", self._data, self._pos)
        self._pos += 12
        return (x, y, z)

    def read_quaternion(self) -> tuple[float, float, float, float]:
        """Read x, y, z, w as four consecutive float32s (16 bytes)."""
        x, y, z, w = struct.unpack_from("<4f", self._data, self._pos)
        self._pos += 16
        return (x, y, z, w)

    def read_matrix44(self) -> tuple[tuple[float, ...], ...]:
        """Read a 4x4 row-major float matrix (64 bytes)."""
        vals = struct.unpack_from("<16f", self._data, self._pos)
        self._pos += 64
        return tuple(vals[i * 4 : (i + 1) * 4] for i in range(4))

    def read_uv(self) -> tuple[float, float]:
        """Read a UV coordinate pair.

        KO binary format stores UVs as (tu, tv) — standard order per the C++
        __VertexT1 struct and CN3IMesh::UVSet().  The V component is flipped
        (1 - v) to convert from DirectX UV space (v=0 top) to Blender (v=0 bottom).

        Returns: (u, v) in Blender convention.
        """
        u, v_raw = struct.unpack_from("<2f", self._data, self._pos)
        self._pos += 8
        return (u, 1.0 - v_raw)

    def read_vertex(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Read a position+normal vertex (24 bytes).

        Returns: (pos, normal) each as (x, y, z).
        """
        vals = struct.unpack_from("<6f", self._data, self._pos)
        self._pos += 24
        return (vals[0:3], vals[3:6])

    def read_vertex_with_uv(
        self,
    ) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float]]:
        """Read a VertexWithUV (32 bytes): position + normal + (tu, tv).

        UV is stored as (tu, tv) per C++ __VertexT1 struct.
        Returns (u, 1-v) in Blender convention.

        Returns: (pos, normal, uv) where pos and normal are (x,y,z) and uv is (u,v).
        """
        vals = struct.unpack_from("<8f", self._data, self._pos)
        self._pos += 32
        pos = vals[0:3]
        normal = vals[3:6]
        u = vals[6]
        v_raw = vals[7]
        return (pos, normal, (u, 1.0 - v_raw))
