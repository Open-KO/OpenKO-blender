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
  int32       coll_vc             (CN3TransformCollision — collision vertex count)
  int32       coll_fc             (CN3TransformCollision — collision face count)
  string      joint_filename      (CN3Chr — references .n3joint)
  int32       part_count
  string × part_count             (references .n3cpart files)
  int32       plug_count
  string × plug_count             (references .n3cplug files)
  string      anim_filename       (references .n3anim; may be empty)
  int32 × MAX_CHR_ANI_PART        (joint_part_starts — must all be 0)
  int32 × MAX_CHR_ANI_PART        (joint_part_ends   — must all be 0)
  string      extra_filename      (must be empty)
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
    joint: "_n3joint.Joint | None" = None
    parts: "list[_n3cpart.N3CPart]" = field(default_factory=list)
    plugs: "list[_n3cplug.N3CPlug]" = field(default_factory=list)
    anim_control: "_n3anim.N3AnimControl | None" = None


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
    coll_vc = r.read_int32()
    coll_fc = r.read_int32()
    if coll_vc > 0 or coll_fc > 0:
        raise ValueError(
            f"Collision mesh in .n3chr ({coll_vc} verts, {coll_fc} faces) is not yet supported."
        )

    # ── CN3Chr ────────────────────────────────────────────────────────────
    joint_filename = r.read_string()
    joint = None
    if joint_filename:
        joint_path = resolve_asset_path(path, joint_filename)
        if joint_path:
            joint = _n3joint.load(joint_path)

    part_count = r.read_int32()
    parts: list[_n3cpart.N3CPart] = []
    for _ in range(part_count):
        part_filename = r.read_string()
        if part_filename:
            part_path = resolve_asset_path(path, part_filename)
            if part_path:
                parts.append(_n3cpart.load(part_path))

    plug_count = r.read_int32()
    plugs: list[_n3cplug.N3CPlug] = []
    for _ in range(plug_count):
        plug_filename = r.read_string()
        if plug_filename:
            plug_path = resolve_asset_path(path, plug_filename)
            if plug_path:
                plugs.append(_n3cplug.load(plug_path))

    anim_filename = r.read_string()
    anim_control = None
    if anim_filename:
        anim_path = resolve_asset_path(path, anim_filename)
        if anim_path:
            anim_control = _n3anim.load(anim_path)

    # Joint animation part boundaries — split upper/lower body animation.
    # Non-zero values indicate the character uses per-part animation blending.
    # We read and discard these; all joints will be animated together.
    for _ in range(MAX_CHR_ANI_PART):
        r.read_int32()
    for _ in range(MAX_CHR_ANI_PART):
        r.read_int32()

    extra = r.read_string()
    if extra:
        raise ValueError(f"Unexpected extra filename in .n3chr: {extra!r}")

    return N3Chr(
        name=name,
        pos=pos,
        rot=rot,
        scale=scale,
        joint=joint,
        parts=parts,
        plugs=plugs,
        anim_control=anim_control,
    )
