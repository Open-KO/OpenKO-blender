"""
Low-level binary writing utilities.

BinaryWriter mirrors BinaryReader — it builds a bytes buffer with typed write
methods.  All values are little-endian, matching the KnightOnline binary format.
"""

from __future__ import annotations

import struct
from pathlib import Path


class BinaryWriter:
    """Stateful writer that accumulates bytes into an internal buffer."""

    def __init__(self) -> None:
        self._parts: list[bytes] = []

    # ── Output ─────────────────────────────────────────────────────────

    def to_bytes(self) -> bytes:
        return b"".join(self._parts)

    def to_file(self, path: Path | str) -> None:
        Path(path).write_bytes(self.to_bytes())

    # ── Primitives ─────────────────────────────────────────────────────

    def write_bool(self, v: bool) -> None:
        self._parts.append(struct.pack("<?", v))

    def write_int8(self, v: int) -> None:
        self._parts.append(struct.pack("<b", v))

    def write_uint8(self, v: int) -> None:
        self._parts.append(struct.pack("<B", v))

    def write_int16(self, v: int) -> None:
        self._parts.append(struct.pack("<h", v))

    def write_uint16(self, v: int) -> None:
        self._parts.append(struct.pack("<H", v))

    def write_int32(self, v: int) -> None:
        self._parts.append(struct.pack("<i", v))

    def write_uint32(self, v: int) -> None:
        self._parts.append(struct.pack("<I", v))

    def write_float(self, v: float) -> None:
        self._parts.append(struct.pack("<f", v))

    def write_bytes(self, data: bytes) -> None:
        self._parts.append(data)

    def write_string(self, s: str) -> None:
        """Length-prefixed UTF-8 string: int32 byte-count then raw chars."""
        encoded = s.encode("utf-8") if s else b""
        self.write_int32(len(encoded))
        if encoded:
            self._parts.append(encoded)

    # ── Composite types ────────────────────────────────────────────────

    def write_vector3(self, x: float, y: float, z: float) -> None:
        self._parts.append(struct.pack("<3f", x, y, z))

    def write_quaternion(self, x: float, y: float, z: float, w: float) -> None:
        self._parts.append(struct.pack("<4f", x, y, z, w))

    def write_matrix44(self, rows: tuple[tuple[float, ...], ...]) -> None:
        """Write a 4x4 row-major float matrix (64 bytes)."""
        flat = [v for row in rows for v in row]
        self._parts.append(struct.pack("<16f", *flat))

    def write_uv(self, u: float, v: float) -> None:
        """Write a UV coordinate pair.

        Accepts Blender-convention (v=0 bottom) and converts back to
        DirectX convention (v=0 top) by flipping: v_raw = 1 - v.
        """
        self._parts.append(struct.pack("<2f", u, 1.0 - v))

    def write_vertex(
        self,
        pos: tuple[float, float, float],
        normal: tuple[float, float, float],
    ) -> None:
        """Write a position+normal vertex (24 bytes)."""
        self._parts.append(struct.pack("<6f", *pos, *normal))

    def write_vertex_with_uv(
        self,
        pos: tuple[float, float, float],
        normal: tuple[float, float, float],
        uv: tuple[float, float],
    ) -> None:
        """Write a VertexWithUV (32 bytes): position + normal + (tu, tv).

        UV is converted from Blender convention (v=0 bottom) to DX (v=0 top).
        """
        self._parts.append(struct.pack("<8f", *pos, *normal, uv[0], 1.0 - uv[1]))
