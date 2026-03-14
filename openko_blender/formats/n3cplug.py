"""
Parser for .n3cplug (CN3CPlug) — equipment/weapon attachment format.

CN3CPlug extends CN3CPlugBase which extends CN3BaseFileAccess.

Binary layout:
  string      name            (CN3BaseFileAccess)
  int32       plug_type       (e_PlugType enum)
  int32       joint_index
  Vector3     position        (local offset from joint)
  Matrix44    rot_matrix      (64 bytes, rotation only)
  Vector3     scale
  Material    material        (92 bytes)
  string      pmesh_filename  (references .n3pmesh)
  string      tex_filename    (references .dxt)
  int32       trace_step      (CN3CPlug extension — skip data if > 0)
  int32       use_vmesh       (CN3CPlug extension — skip data if != 0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ._base import read_material, read_name, resolve_asset_path
from .structs import Material, PlugType, Vector3
from . import n3pmesh as _n3pmesh
from ..utils.binary_reader import BinaryReader


@dataclass
class N3CPlug:
    name: str
    plug_type: PlugType
    joint_index: int
    position: Vector3
    rot_matrix: tuple       # 4×4 tuple (row-major)
    scale: Vector3
    material: Material
    pmesh_filename: str
    tex_filename: str
    pmesh: "_n3pmesh.N3PMesh | None" = None


def load(path: Path | str) -> N3CPlug:
    """Parse a .n3cplug file.

    The referenced .n3pmesh is resolved relative to the directory of ``path``
    and loaded automatically.  Texture is recorded by filename only (loaded
    during Blender import).
    """
    path = Path(path)
    r = BinaryReader.from_file(path)

    name = read_name(r)

    raw_plug_type = r.read_int32()
    try:
        plug_type = PlugType(raw_plug_type)
        if plug_type.value > PlugType.MAX:
            plug_type = PlugType.NORMAL
    except ValueError:
        plug_type = PlugType.NORMAL

    joint_index = r.read_int32()
    position = Vector3(*r.read_vector3())
    rot_matrix = r.read_matrix44()
    scale = Vector3(*r.read_vector3())
    material = read_material(r)

    pmesh_filename = r.read_string()
    tex_filename = r.read_string()

    # CN3CPlug-specific extensions — these fields are absent in older file versions
    trace_step = 0
    if r.remaining >= 4:
        trace_step = r.read_int32()
        if trace_step > 0:
            # Trace step data not yet supported; skip gracefully
            # Each trace entry is a Vector3 (12 bytes)
            r.skip(trace_step * 12)

    if r.remaining >= 4:
        use_vmesh = r.read_int32()
        if use_vmesh:
            raise ValueError(
                "VirtualMesh (use_vmesh) in .n3cplug is not yet supported."
            )

    # Load the referenced progressive mesh
    pmesh = None
    if pmesh_filename:
        pmesh_path = resolve_asset_path(path, pmesh_filename)
        if pmesh_path:
            pmesh = _n3pmesh.load(pmesh_path)

    return N3CPlug(
        name=name,
        plug_type=plug_type,
        joint_index=joint_index,
        position=position,
        rot_matrix=rot_matrix,
        scale=scale,
        material=material,
        pmesh_filename=pmesh_filename,
        tex_filename=tex_filename,
        pmesh=pmesh,
    )
