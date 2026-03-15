"""
Parsers for .n3cpart (CN3CPart) and .n3cskins (CN3CPartSkins / CN3Skin).

.n3cpart binary layout:
  string      name              (CN3BaseFileAccess)
  int32       version           (0 = original; 1 = adds a second texture)
  Material    material          (92 bytes)
  string      tex_filename      (references a .dxt file)
  string      tex_diffuse_filename  (only present when version == 1)
  string      skins_filename    (references a .n3cskins file)

.n3cskins binary layout:
  string      name            (CN3BaseFileAccess)
  [LOD 0 .. LOD 3]:
    CN3Skin (via CN3IMesh):
      string    name
      int32     face_count
      int32     vertex_count
      int32     uv_count
      if face_count > 0 and vertex_count > 0:
        Vertex × vertex_count          (position + normal, 24 bytes each)
        uint16 × face_count * 3        (triangle indices)
      if uv_count > 0:
        UVVector × uv_count            (v then u — 8 bytes, v is flipped)
        uint16   × face_count * 3      (UV indices per face corner)
    CN3Skin (skinning extension):
      for each vertex:
        Vector3  origin        (base position, 12 bytes)
        int32    n_affect       (bone count)
        int32    _ptr_joints    (serialized pointer — ignored)
        int32    _ptr_weights   (serialized pointer — ignored)
        if n_affect > 1:
          int32  × n_affect    (joint indices)
          float  × n_affect    (blend weights)
        elif n_affect == 1:
          int32                (single joint index; weight is implicitly 1.0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ._base import read_material, read_name, resolve_asset_path
from .structs import Material, UV, Vector3
from ..utils.binary_reader import BinaryReader

MAX_CHR_LOD = 4


@dataclass
class SkinVertex:
    """Per-vertex skinning data: origin position and bone influences."""
    origin: Vector3
    joint_indices: list[int] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)

    @property
    def n_affect(self) -> int:
        return len(self.joint_indices)


@dataclass
class Skin:
    """One LOD level of a character part mesh (CN3Skin)."""
    name: str
    face_count: int
    vertex_count: int
    uv_count: int
    vertices: list[tuple]     = field(default_factory=list)  # (pos, normal)
    face_indices: list[int]   = field(default_factory=list)  # flat, 3 per face
    uvs: list[UV]             = field(default_factory=list)
    uv_indices: list[int]     = field(default_factory=list)  # 3 per face corner
    skin_vertices: list[SkinVertex] = field(default_factory=list)


@dataclass
class N3CPart:
    name: str
    material: Material
    tex_filename: str           # relative filename of .dxt texture
    skins_filename: str         # relative filename of .n3cskins
    tex_diffuse_filename: str = ""  # only present when version == 1
    skins: list[Skin | None] = field(default_factory=list)  # 4 LOD levels


def load(path: Path | str) -> N3CPart:
    """Parse a .n3cpart file.

    External files (.dxt, .n3cskins) are resolved relative to the directory of
    ``path`` and loaded automatically.
    """
    path = Path(path)
    r = BinaryReader.from_file(path)

    name = read_name(r)
    version = r.read_int32()
    material = read_material(r)
    tex_filename = r.read_string()
    tex_diffuse_filename = r.read_string() if version == 1 else ""
    skins_filename = r.read_string()

    # Resolve and load the skins file
    skins: list[Skin | None] = []
    if skins_filename:
        skins_path = resolve_asset_path(path, skins_filename)
        if skins_path:
            skins = load_skins(skins_path)

    return N3CPart(
        name=name,
        material=material,
        tex_filename=tex_filename,
        tex_diffuse_filename=tex_diffuse_filename,
        skins_filename=skins_filename,
        skins=skins,
    )


def load_skins(path: Path | str) -> list[Skin | None]:
    """Parse a .n3cskins file and return a list of up to 4 Skin LOD levels.

    Slots with vertex_count == 0 are returned as None.
    """
    path = Path(path)
    r = BinaryReader.from_file(path)

    _name = read_name(r)  # CN3BaseFileAccess base name

    result: list[Skin | None] = []
    for _ in range(MAX_CHR_LOD):
        skin = _read_skin(r)
        result.append(skin if skin.vertex_count > 0 else None)
    return result


def _read_skin(r: BinaryReader) -> Skin:
    """Read one CN3Skin LOD level."""
    name = read_name(r)
    face_count = r.read_int32()
    vertex_count = r.read_int32()
    uv_count = r.read_int32()

    vertices: list[tuple] = []
    face_indices: list[int] = []
    uvs: list[UV] = []
    uv_indices: list[int] = []

    if face_count > 0 and vertex_count > 0:
        for _ in range(vertex_count):
            pos, normal = r.read_vertex()
            vertices.append((Vector3(*pos), Vector3(*normal)))
        for _ in range(3 * face_count):
            face_indices.append(r.read_int16())

    if uv_count > 0:
        for _ in range(uv_count):
            u, v = r.read_uv()
            uvs.append(UV(u, v))
        for _ in range(3 * face_count):
            uv_indices.append(r.read_int16())

    # Skinning data (one entry per vertex)
    skin_vertices: list[SkinVertex] = []
    for _ in range(vertex_count):
        ox, oy, oz = r.read_vector3()
        origin = Vector3(ox, oy, oz)
        n_affect = r.read_int32()
        _ptr_joints = r.read_int32()   # serialized pointer, ignore
        _ptr_weights = r.read_int32()  # serialized pointer, ignore

        joint_indices: list[int] = []
        weights: list[float] = []

        if n_affect > 1:
            for _ in range(n_affect):
                joint_indices.append(r.read_int32())
            for _ in range(n_affect):
                weights.append(r.read_float())
        elif n_affect == 1:
            joint_indices.append(r.read_int32())
            weights.append(1.0)

        skin_vertices.append(SkinVertex(origin=origin, joint_indices=joint_indices, weights=weights))

    return Skin(
        name=name,
        face_count=face_count,
        vertex_count=vertex_count,
        uv_count=uv_count,
        vertices=vertices,
        face_indices=face_indices,
        uvs=uvs,
        uv_indices=uv_indices,
        skin_vertices=skin_vertices,
    )
