"""
Shared binary reading helpers used by all format parsers.

These map directly to the CN3BaseFileAccess, CN3Transform, and
CN3TransformCollision class load() chains in the C++ source.
"""

from __future__ import annotations

from pathlib import Path

from .structs import (
    AnimKey,
    AnimKeyType,
    D3DColor,
    Material,
    Quaternion,
    Vector3,
)
from ..utils.binary_reader import BinaryReader


def read_name(r: BinaryReader) -> str:
    """CN3BaseFileAccess::Load — reads the object name string."""
    return r.read_string()


def read_anim_key(r: BinaryReader) -> AnimKey:
    """Read one CN3AnimKey from the buffer."""
    key = AnimKey()
    key.count = r.read_int32()
    if key.count > 0:
        key.key_type = AnimKeyType(r.read_int32())
        key.sampling_rate = r.read_float()
        if key.key_type == AnimKeyType.VECTOR3:
            for _ in range(key.count):
                x, y, z = r.read_vector3()
                key.data.append(Vector3(x, y, z))
        else:
            for _ in range(key.count):
                x, y, z, w = r.read_quaternion()
                key.data.append(Quaternion(x, y, z, w))
        # Duplicate last element for safe interpolation at end of range
        key.data.append(key.data[-1])
    return key


def read_transform(r: BinaryReader) -> tuple:
    """CN3Transform::Load — reads pos, rot, scale, and 3 anim keys.

    Returns: (name, pos, rot, scale, key_pos, key_rot, key_scale)
    """
    name = read_name(r)
    pos = Vector3(*r.read_vector3())
    rot = Quaternion(*r.read_quaternion())
    scale = Vector3(*r.read_vector3())
    key_pos = read_anim_key(r)
    key_rot = read_anim_key(r)
    key_scale = read_anim_key(r)
    return name, pos, rot, scale, key_pos, key_rot, key_scale


def read_transform_collision(r: BinaryReader) -> tuple:
    """CN3TransformCollision::Load — reads transform then two collision mesh filenames.

    The collision mesh and climb mesh filenames are read and discarded;
    collision geometry is not used for import.

    Returns: same as read_transform()
    """
    result = read_transform(r)
    r.read_string()  # szCollisionMeshFilename
    r.read_string()  # szClimbMeshFilename
    return result


def read_material(r: BinaryReader) -> Material:
    """Read a __Material struct (92 bytes).

    Layout: 4×D3DColor (16 bytes each) + power(f) + color_op + color_arg1 +
    color_arg2 + render_flags + src_blend + dest_blend (all uint32).
    """
    diffuse = D3DColor(*struct_unpack_4f(r))
    ambient = D3DColor(*struct_unpack_4f(r))
    specular = D3DColor(*struct_unpack_4f(r))
    emissive = D3DColor(*struct_unpack_4f(r))
    power = r.read_float()
    color_op = r.read_uint32()
    color_arg1 = r.read_uint32()
    color_arg2 = r.read_uint32()
    render_flags = r.read_uint32()
    src_blend = r.read_uint32()
    dest_blend = r.read_uint32()
    return Material(diffuse, ambient, specular, emissive, power,
                    color_op, color_arg1, color_arg2, render_flags, src_blend, dest_blend)


def resolve_asset_path(base_file: Path, stored_path: str) -> "Path | None":
    """Resolve a file reference stored inside a KO asset file.

    KO files store paths relative to the game's Client root (e.g.
    ``item\\long_sword.n3cpart``), but the base file may live in a
    subdirectory (e.g. ``Chr\\``).

    Resolution order (first existing path wins):
      1. Same directory as base_file — handles flat/ripped asset packs.
      2. Relative to base_file's directory — handles sibling references.
      3. Relative to base_file's parent directory — handles
         ``Chr\\el.n3chr`` → ``Client\\item\\...`` references.
    """
    if not stored_path:
        return None
    # KO stores paths with Windows backslashes; normalise for cross-platform use
    stored = Path(stored_path.replace("\\", "/"))
    candidates = [
        base_file.parent / stored.name,
        base_file.parent / stored,
        base_file.parent.parent / stored,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def struct_unpack_4f(r: BinaryReader) -> tuple[float, float, float, float]:
    """Read four consecutive float32s."""
    import struct
    vals = struct.unpack_from("<4f", r._data, r._pos)
    r._pos += 16
    return vals
