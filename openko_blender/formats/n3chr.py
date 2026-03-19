"""
Parser for .n3chr (CN3Chr) — complete character format.

CN3Chr extends CN3TransformCollision which extends CN3Transform which extends
CN3BaseFileAccess.

Binary layout:
  string      name                (CN3BaseFileAccess)
  Vector3     pos                 (CN3Transform)
  Quaternion  rot
  Vector3     scale
  AnimKey     key_pos             (CN3Transform — 3 anim keys)
  AnimKey     key_rot
  AnimKey     key_scale
  string      coll_mesh_filename  (CN3TransformCollision — collision mesh; usually empty)
  string      climb_mesh_filename (CN3TransformCollision — climb mesh; usually empty)
  string      joint_filename      (CN3Chr — references .n3joint)
  int32       part_count
  string × part_count             (references .n3cpart files)
  int32       plug_count
  string × plug_count             (references .n3cplug files)
  string      anim_filename       (references .n3anim; may be empty)
  int32 × MAX_CHR_ANI_PART        (joint_part_starts)
  int32 × MAX_CHR_ANI_PART        (joint_part_ends)
  string      fx_plug_filename    (added 2002-10-10; absent in older files)
  string      coll_skin_filename  (added for v1298; absent in older files)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ._base import read_anim_key, read_name, resolve_asset_path
from .structs import Quaternion, Vector3
from . import n3anim as _n3anim
from . import n3cpart as _n3cpart
from . import n3cplug as _n3cplug
from . import n3joint as _n3joint
from ..utils.binary_reader import BinaryReader

MAX_CHR_ANI_PART = 2


@dataclass
class N3Chr:
    name: str
    pos: Vector3
    rot: Quaternion
    scale: Vector3
    joint_filename: str = ""
    joint: "_n3joint.Joint | None" = None
    part_filenames: list[str] = field(default_factory=list)
    parts: "list[_n3cpart.N3CPart]" = field(default_factory=list)
    plug_filenames: list[str] = field(default_factory=list)
    plugs: "list[_n3cplug.N3CPlug]" = field(default_factory=list)
    anim_filename: str = ""
    anim_control: "_n3anim.N3AnimControl | None" = None
    # CN3TransformCollision
    collision_mesh_filename: str = ""
    climb_mesh_filename: str = ""
    # CN3Chr metadata
    joint_part_starts: list[int] = field(default_factory=list)
    joint_part_ends: list[int] = field(default_factory=list)
    fx_plug_name: str = ""
    collision_skin_name: str = ""


def load(path: Path | str) -> N3Chr:
    """Parse a .n3chr file and load all referenced sub-files."""
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
    # CN3TransformCollision::Load() reads two length-prefixed mesh filenames
    # (collision mesh + climb mesh). Both are almost always empty strings.
    coll_mesh = r.read_string()
    climb_mesh = r.read_string()

    # ── CN3Chr ────────────────────────────────────────────────────────────
    joint_filename = r.read_string()
    joint = None
    if joint_filename:
        joint_path = resolve_asset_path(path, joint_filename)
        if joint_path:
            joint = _n3joint.load(joint_path)

    part_count = r.read_int32()
    part_filenames: list[str] = []
    parts: list[_n3cpart.N3CPart] = []
    for _ in range(part_count):
        pf = r.read_string()
        if pf:
            part_path = resolve_asset_path(path, pf)
            if part_path:
                part_filenames.append(pf)
                parts.append(_n3cpart.load(part_path))

    plug_count = r.read_int32()
    plug_filenames: list[str] = []
    plugs: list[_n3cplug.N3CPlug] = []
    for _ in range(plug_count):
        pf = r.read_string()
        if pf:
            plug_path = resolve_asset_path(path, pf)
            if plug_path:
                plug_filenames.append(pf)
                plugs.append(_n3cplug.load(plug_path))

    anim_filename = r.read_string()
    anim_control = None
    if anim_filename:
        anim_path = resolve_asset_path(path, anim_filename)
        if anim_path:
            anim_control = _n3anim.load(anim_path)

    # Joint animation part boundaries — split upper/lower body animation.
    # Non-zero values indicate the character uses per-part animation blending.
    joint_part_starts = [r.read_int32() for _ in range(MAX_CHR_ANI_PART)]
    joint_part_ends = [r.read_int32() for _ in range(MAX_CHR_ANI_PART)]

    # FX plug filename — added 2002-10-10; absent in older files.
    fx_plug_name = ""
    if r.remaining >= 4:
        fx_plug_name = r.read_string()

    # Collision skin filename — added for v1298; absent in older files.
    coll_skin_name = ""
    if r.remaining >= 4:
        coll_skin_name = r.read_string()

    return N3Chr(
        name=name,
        pos=pos,
        rot=rot,
        scale=scale,
        joint_filename=joint_filename,
        joint=joint,
        part_filenames=part_filenames,
        parts=parts,
        plug_filenames=plug_filenames,
        plugs=plugs,
        anim_filename=anim_filename,
        anim_control=anim_control,
        collision_mesh_filename=coll_mesh,
        climb_mesh_filename=climb_mesh,
        joint_part_starts=joint_part_starts,
        joint_part_ends=joint_part_ends,
        fx_plug_name=fx_plug_name,
        collision_skin_name=coll_skin_name,
    )
