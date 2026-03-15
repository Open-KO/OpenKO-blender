"""
Parser for .n3shape (CN3Shape) — static shape/prop format.

CN3Shape extends CN3TransformCollision which extends CN3Transform which
extends CN3BaseFileAccess.

Binary layout:
  string      name                (CN3BaseFileAccess)
  Vector3     pos                 (CN3Transform)
  Quaternion  rot
  Vector3     scale
  AnimKey     key_pos             (CN3Transform — 3 anim keys, typically empty)
  AnimKey     key_rot
  AnimKey     key_scale
  string      coll_mesh_filename  (CN3TransformCollision — skipped)
  string      climb_mesh_filename
  int32       part_count          (CN3Shape)
  [per part (CN3SPart)]:
    Vector3   pivot
    string    mesh_filename       (.n3pmesh)
    Material  material            (92 bytes)
    int32     tex_count
    float32   tex_fps
    string × tex_count            (texture filenames, .dxt)
  int32       belong_id           (game-logic metadata — ignored)
  int32       event_id
  int32       event_type
  int32       npc_id
  int32       npc_status
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ._base import read_anim_key, read_material, read_name, resolve_asset_path
from .structs import Material, Quaternion, Vector3
from . import n3pmesh as _n3pmesh
from ..utils.binary_reader import BinaryReader


@dataclass
class ShapePart:
    pivot: Vector3
    mesh_filename: str
    material: Material
    tex_filenames: list[str] = field(default_factory=list)
    tex_fps: float = 0.0
    pmesh: "_n3pmesh.N3PMesh | None" = None


@dataclass
class N3Shape:
    name: str
    pos: Vector3
    rot: Quaternion
    scale: Vector3
    parts: list[ShapePart] = field(default_factory=list)
    # Game-logic fields (stored but not used for import)
    belong_id: int = 0
    event_id: int = 0
    event_type: int = 0
    npc_id: int = 0
    npc_status: int = 0


def load(path: Path | str) -> N3Shape:
    """Parse a .n3shape file and load all referenced .n3pmesh sub-files."""
    path = Path(path)
    r = BinaryReader.from_file(path)

    # ── CN3BaseFileAccess ──────────────────────────────────────────────────
    name = read_name(r)

    # ── CN3Transform ──────────────────────────────────────────────────────
    pos = Vector3(*r.read_vector3())
    rot = Quaternion(*r.read_quaternion())
    scale = Vector3(*r.read_vector3())
    _key_pos = read_anim_key(r)
    _key_rot = read_anim_key(r)
    _key_scale = read_anim_key(r)

    # ── CN3TransformCollision ──────────────────────────────────────────────
    r.read_string()  # szCollisionMeshFilename — skipped
    r.read_string()  # szClimbMeshFilename — skipped

    # ── CN3Shape ──────────────────────────────────────────────────────────
    part_count = r.read_int32()
    parts: list[ShapePart] = []
    for _ in range(part_count):
        pivot = Vector3(*r.read_vector3())
        mesh_filename = r.read_string()
        material = read_material(r)
        tex_count = r.read_int32()
        tex_fps = r.read_float()
        tex_filenames = [r.read_string() for _ in range(tex_count)]

        pmesh = None
        if mesh_filename:
            pmesh_path = resolve_asset_path(path, mesh_filename)
            if pmesh_path:
                pmesh = _n3pmesh.load(pmesh_path)

        parts.append(ShapePart(
            pivot=pivot,
            mesh_filename=mesh_filename,
            material=material,
            tex_filenames=tex_filenames,
            tex_fps=tex_fps,
            pmesh=pmesh,
        ))

    # Game-logic metadata (read but not used)
    belong_id = r.read_int32()
    event_id = r.read_int32()
    event_type = r.read_int32()
    npc_id = r.read_int32()
    npc_status = r.read_int32()

    return N3Shape(
        name=name,
        pos=pos,
        rot=rot,
        scale=scale,
        parts=parts,
        belong_id=belong_id,
        event_id=event_id,
        event_type=event_type,
        npc_id=npc_id,
        npc_status=npc_status,
    )
