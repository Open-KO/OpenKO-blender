"""
Parser for .n3joint (CN3Joint) — skeleton hierarchy format.

CN3Joint extends CN3Transform which extends CN3BaseFileAccess.

Binary layout per joint node (recursive):
  string      name            (CN3BaseFileAccess)
  Vector3     pos             (CN3Transform)
  Quaternion  rot
  Vector3     scale
  AnimKey     key_pos         (CN3Transform — 3 animation keys)
  AnimKey     key_rot
  AnimKey     key_scale
  AnimKey     key_orient      (CN3Joint — additional orient key)
  int32       child_count
  Joint × child_count         (recursive)

The root joint is the entry point of the .n3joint file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from ._base import read_anim_key, read_name
from .structs import AnimKey, Quaternion, Vector3
from ..utils.binary_reader import BinaryReader

# Identity quaternion (no rotation)
_IDENTITY_QUAT = Quaternion(0.0, 0.0, 0.0, 1.0)
_UNIT_SCALE = Vector3(1.0, 1.0, 1.0)


@dataclass
class Joint:
    name: str
    pos: Vector3
    rot: Quaternion
    scale: Vector3
    orient: Quaternion = _IDENTITY_QUAT
    key_pos: AnimKey = field(default_factory=AnimKey)
    key_rot: AnimKey = field(default_factory=AnimKey)
    key_scale: AnimKey = field(default_factory=AnimKey)
    key_orient: AnimKey = field(default_factory=AnimKey)
    children: list["Joint"] = field(default_factory=list)

    def local_matrix_at(self, frame: float) -> tuple[tuple[float, ...], ...]:
        """Compute the local 4×4 transform matrix at the given animation frame.

        Replicates CN3Joint::ReCalcMatrix() exactly:
          1. Resolve animated values (fall back to bind-pose defaults).
          2. rot_final = rot * orient  (if orient keys exist)
          3. Matrix = rotation_from_quaternion(rot_final)
          4. Apply scale (if non-uniform)
          5. Set translation column

        Returns a 4-tuple of 4-tuples (row-major, Blender column-major order).
        """
        pos: Vector3 = self.key_pos.get_value(frame, self.pos)
        rot: Quaternion = self.key_rot.get_value(frame, self.rot)
        scale: Vector3 = self.key_scale.get_value(frame, self.scale)
        orient: Quaternion = (
            self.key_orient.get_value(frame, self.orient)
            if self.key_orient.count > 0
            else self.orient
        )

        # Combine rotation with orientation offset
        rot_final = _quat_mul(rot, orient)

        # Build 4×4 from quaternion
        m = _quat_to_mat4(rot_final)

        # Apply scale
        if scale.x != 1.0 or scale.y != 1.0 or scale.z != 1.0:
            m = _mat4_scale(m, scale)

        # Set translation (column 3)
        m = (
            (m[0][0], m[0][1], m[0][2], pos.x),
            (m[1][0], m[1][1], m[1][2], pos.y),
            (m[2][0], m[2][1], m[2][2], pos.z),
            (m[3][0], m[3][1], m[3][2], m[3][3]),
        )
        return m

    def bind_matrix(self) -> tuple[tuple[float, ...], ...]:
        """Bind-pose local matrix (frame 0)."""
        return self.local_matrix_at(0.0)

    def flat_list(self) -> list["Joint"]:
        """Return this joint and all descendants in depth-first order."""
        result = [self]
        for child in self.children:
            result.extend(child.flat_list())
        return result


def load(path: Path | str) -> Joint:
    """Parse a .n3joint file and return the root Joint."""
    r = BinaryReader.from_file(path)
    return _read_joint(r)


def _read_joint(r: BinaryReader) -> Joint:
    name = read_name(r)
    pos = Vector3(*r.read_vector3())
    rot = Quaternion(*r.read_quaternion())
    scale = Vector3(*r.read_vector3())
    key_pos = read_anim_key(r)
    key_rot = read_anim_key(r)
    key_scale = read_anim_key(r)
    key_orient = read_anim_key(r)

    child_count = r.read_int32()
    children = [_read_joint(r) for _ in range(child_count)]

    return Joint(
        name=name,
        pos=pos,
        rot=rot,
        scale=scale,
        orient=_IDENTITY_QUAT,
        key_pos=key_pos,
        key_rot=key_rot,
        key_scale=key_scale,
        key_orient=key_orient,
        children=children,
    )


# ── Pure-Python matrix math ───────────────────────────────────────────────────


def _quat_mul(q1: Quaternion, q2: Quaternion) -> Quaternion:
    """Hamilton product q1 * q2."""
    return Quaternion(
        q1.w * q2.x + q1.x * q2.w + q1.y * q2.z - q1.z * q2.y,
        q1.w * q2.y - q1.x * q2.z + q1.y * q2.w + q1.z * q2.x,
        q1.w * q2.z + q1.x * q2.y - q1.y * q2.x + q1.z * q2.w,
        q1.w * q2.w - q1.x * q2.x - q1.y * q2.y - q1.z * q2.z,
    )


def _quat_to_mat4(q: Quaternion) -> tuple[tuple[float, ...], ...]:
    """Convert a unit quaternion to a 4×4 rotation matrix (column-major, Blender style)."""
    x, y, z, w = q.x, q.y, q.z, q.w
    x2, y2, z2 = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return (
        (1 - 2 * (y2 + z2), 2 * (xy - wz),     2 * (xz + wy),     0.0),
        (2 * (xy + wz),     1 - 2 * (x2 + z2), 2 * (yz - wx),     0.0),
        (2 * (xz - wy),     2 * (yz + wx),     1 - 2 * (x2 + y2), 0.0),
        (0.0,               0.0,               0.0,               1.0),
    )


def _mat4_scale(m: tuple, s: Vector3) -> tuple[tuple[float, ...], ...]:
    """Right-multiply m by a diagonal scale matrix S = diag(s.x, s.y, s.z, 1)."""
    return (
        (m[0][0] * s.x, m[0][1] * s.y, m[0][2] * s.z, m[0][3]),
        (m[1][0] * s.x, m[1][1] * s.y, m[1][2] * s.z, m[1][3]),
        (m[2][0] * s.x, m[2][1] * s.y, m[2][2] * s.z, m[2][3]),
        (m[3][0] * s.x, m[3][1] * s.y, m[3][2] * s.z, m[3][3]),
    )
