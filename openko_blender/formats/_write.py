"""
Shared binary writing helpers used by all format writers.

These mirror the read helpers in _base.py and map directly to the
CN3BaseFileAccess, CN3Transform, and CN3TransformCollision class
Save() chains in the C++ source.
"""

from __future__ import annotations

from .structs import AnimKey, AnimKeyType, Material
from ..utils.binary_writer import BinaryWriter


def write_name(w: BinaryWriter, name: str) -> None:
    """CN3BaseFileAccess::Save — writes the object name string."""
    w.write_string(name)


def write_anim_key(w: BinaryWriter, key: AnimKey | None = None) -> None:
    """Write one CN3AnimKey to the buffer.

    If *key* is None or has count == 0, writes a single int32(0) (no keyframes).
    The AnimKey.data list has a duplicated last element for interpolation safety
    — only the first *count* elements are written.
    """
    if key is None or key.count <= 0:
        w.write_int32(0)
        return

    w.write_int32(key.count)
    w.write_int32(key.key_type.value)
    w.write_float(key.sampling_rate)

    for i in range(key.count):
        d = key.data[i]
        if key.key_type == AnimKeyType.VECTOR3:
            w.write_vector3(d.x, d.y, d.z)
        else:
            w.write_quaternion(d.x, d.y, d.z, d.w)


def write_empty_anim_key(w: BinaryWriter) -> None:
    """Write an empty CN3AnimKey (count=0)."""
    w.write_int32(0)


def write_transform(
    w: BinaryWriter,
    name: str,
    pos: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rot: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    key_pos: AnimKey | None = None,
    key_rot: AnimKey | None = None,
    key_scale: AnimKey | None = None,
) -> None:
    """CN3Transform::Save — writes name, pos, rot, scale, and 3 anim keys."""
    write_name(w, name)
    w.write_vector3(*pos)
    w.write_quaternion(*rot)
    w.write_vector3(*scale)
    write_anim_key(w, key_pos)
    write_anim_key(w, key_rot)
    write_anim_key(w, key_scale)


def write_transform_collision(
    w: BinaryWriter,
    name: str,
    pos: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rot: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    key_pos: AnimKey | None = None,
    key_rot: AnimKey | None = None,
    key_scale: AnimKey | None = None,
    collision_mesh_filename: str = "",
    climb_mesh_filename: str = "",
) -> None:
    """CN3TransformCollision::Save — writes transform then two collision filenames."""
    write_transform(w, name, pos, rot, scale, key_pos, key_rot, key_scale)
    w.write_string(collision_mesh_filename)
    w.write_string(climb_mesh_filename)


def write_material(w: BinaryWriter, mat: Material) -> None:
    """Write a __Material struct (92 bytes).

    Layout: 4xD3DColor (16 bytes each) + power(f) + color_op + color_arg1 +
    color_arg2 + render_flags + src_blend + dest_blend (all uint32).
    """
    for color in (mat.diffuse, mat.ambient, mat.specular, mat.emissive):
        w.write_float(color.r)
        w.write_float(color.g)
        w.write_float(color.b)
        w.write_float(color.a)
    w.write_float(mat.power)
    w.write_uint32(mat.color_op)
    w.write_uint32(mat.color_arg1)
    w.write_uint32(mat.color_arg2)
    w.write_uint32(mat.render_flags)
    w.write_uint32(mat.src_blend)
    w.write_uint32(mat.dest_blend)
