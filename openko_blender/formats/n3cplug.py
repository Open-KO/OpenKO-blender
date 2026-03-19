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
  string      mesh_filename   (references .n3pmesh or .n3mesh)
  string      tex_filename    (references .dxt)
  int32       trace_step      (CN3CPlug extension — trace data present when > 0)
  int32       use_vmesh       (CN3CPlug extension — VirtualMesh data present when != 0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ._base import read_material, read_name, resolve_asset_path
from ._write import write_material, write_name
from .structs import Material, PlugType, Vector3
from . import n3pmesh as _n3pmesh
from ..utils.binary_reader import BinaryReader
from ..utils.binary_writer import BinaryWriter


@dataclass
class N3CPlug:
    name: str
    plug_type: PlugType
    joint_index: int
    position: Vector3
    rot_matrix: tuple       # 4×4 tuple (row-major)
    scale: Vector3
    material: Material
    mesh_filename: str      # .n3pmesh or .n3mesh
    tex_filename: str
    trace_step: int = 0
    trace_color: int = 0      # D3DCOLOR (uint32)
    trace0: float = 0.0
    trace1: float = 0.0
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

    mesh_filename = r.read_string()  # .n3pmesh or .n3mesh
    tex_filename = r.read_string()

    # CN3CPlug-specific extensions — these fields are absent in older file versions
    trace_step = 0
    trace_color = 0
    trace0 = 0.0
    trace1 = 0.0
    if r.remaining >= 4:
        trace_step = r.read_int32()
        if trace_step > 0:
            trace_color = r.read_uint32()  # m_crTrace (D3DCOLOR)
            trace0 = r.read_float()        # m_fTrace0
            trace1 = r.read_float()        # m_fTrace1

    if r.remaining >= 4:
        use_vmesh = r.read_int32()
        if use_vmesh:
            raise ValueError(
                "VirtualMesh (use_vmesh) in .n3cplug is not yet supported."
            )

    # Load the referenced mesh
    pmesh = None
    if mesh_filename:
        pmesh_path = resolve_asset_path(path, mesh_filename)
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
        mesh_filename=mesh_filename,
        tex_filename=tex_filename,
        trace_step=trace_step,
        trace_color=trace_color,
        trace0=trace0,
        trace1=trace1,
        pmesh=pmesh,
    )


# ── Save ─────────────────────────────────────────────────────────────────────


def save(plug: N3CPlug, path: Path | str) -> None:
    """Write an N3CPlug to a .n3cplug file."""
    w = BinaryWriter()

    write_name(w, plug.name)
    w.write_uint32(int(plug.plug_type))
    w.write_int32(plug.joint_index)
    w.write_vector3(plug.position.x, plug.position.y, plug.position.z)
    w.write_matrix44(plug.rot_matrix)
    w.write_vector3(plug.scale.x, plug.scale.y, plug.scale.z)
    write_material(w, plug.material)
    w.write_string(plug.mesh_filename)
    w.write_string(plug.tex_filename)

    # Trace data
    w.write_int32(plug.trace_step)
    if plug.trace_step > 0:
        w.write_uint32(plug.trace_color)
        w.write_float(plug.trace0)
        w.write_float(plug.trace1)

    # VirtualMesh flag — always 0 (not supported)
    w.write_int32(0)

    w.to_file(path)
