"""
Parser for .n3pmesh (CN3PMesh) — progressive mesh format.

Binary layout (all little-endian):
  string          name            (CN3BaseFileAccess base)
  int32           num_collapses
  int32           total_index_changes
  int32           max_num_vertices
  int32           max_num_indices
  int32           min_num_vertices
  int32           min_num_indices
  VertexWithUV × max_num_vertices
  uint16       × max_num_indices
  [EdgeCollapse data — skipped when num_collapses > 0]
  [Index change data — skipped when total_index_changes > 0]
  int32           lod_ctrl_value_count
  LODCtrlValue × lod_ctrl_value_count

We always import at the highest LOD (max_num_vertices / max_num_indices).
Edge collapse and index change data is read and discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from openko_blender.formats._base import read_name
from openko_blender.formats.structs import LODCtrlValue, UV, Vector3
from openko_blender.utils.binary_reader import BinaryReader


@dataclass
class MeshVertex:
    pos: Vector3
    normal: Vector3
    uv: UV


@dataclass
class N3PMesh:
    name: str
    vertices: list[MeshVertex] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)   # flat triangle indices (3 per face)
    lod_ctrl_values: list[LODCtrlValue] = field(default_factory=list)
    min_num_vertices: int = 0
    min_num_indices: int = 0

    @property
    def face_count(self) -> int:
        return len(self.indices) // 3

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)


def load(path: Path | str) -> N3PMesh:
    """Parse a .n3pmesh file and return an N3PMesh."""
    r = BinaryReader.from_file(path)

    name = read_name(r)
    num_collapses = r.read_int32()
    total_index_changes = r.read_int32()
    max_num_vertices = r.read_int32()
    max_num_indices = r.read_int32()
    min_num_vertices = r.read_int32()
    min_num_indices = r.read_int32()

    vertices: list[MeshVertex] = []
    for _ in range(max_num_vertices):
        pos, normal, uv = r.read_vertex_with_uv()
        vertices.append(MeshVertex(Vector3(*pos), Vector3(*normal), UV(*uv)))

    indices: list[int] = []
    for _ in range(max_num_indices):
        indices.append(r.read_int16())

    # Skip LOD collapse data — not used for import
    if num_collapses > 0:
        # Each __EdgeCollapse: 5 × int32 + 1 × bool (padded to 24 bytes)
        r.skip(num_collapses * 24)

    if total_index_changes > 0:
        r.skip(total_index_changes * 4)

    lod_ctrl_values: list[LODCtrlValue] = []
    lod_count = r.read_int32()
    for _ in range(lod_count):
        dist = r.read_float()
        nv = r.read_int32()
        lod_ctrl_values.append(LODCtrlValue(dist, nv))

    return N3PMesh(
        name=name,
        vertices=vertices,
        indices=indices,
        lod_ctrl_values=lod_ctrl_values,
        min_num_vertices=min_num_vertices,
        min_num_indices=min_num_indices,
    )
