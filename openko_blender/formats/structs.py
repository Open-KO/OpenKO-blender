"""
Shared data structures for KnightOnline file formats.

All structs are plain Python dataclasses or NamedTuples — no bpy/mathutils dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import NamedTuple


# ── Geometric primitives ──────────────────────────────────────────────────────


class Vector3(NamedTuple):
    x: float
    y: float
    z: float

    def lerp(self, other: "Vector3", t: float) -> "Vector3":
        return Vector3(
            self.x + t * (other.x - self.x),
            self.y + t * (other.y - self.y),
            self.z + t * (other.z - self.z),
        )


class Quaternion(NamedTuple):
    x: float
    y: float
    z: float
    w: float

    def slerp(self, other: "Quaternion", t: float) -> "Quaternion":
        dot = self.x * other.x + self.y * other.y + self.z * other.z + self.w * other.w
        dot = max(-1.0, min(1.0, dot))

        q2 = other
        if dot < 0.0:
            q2 = Quaternion(-other.x, -other.y, -other.z, -other.w)
            dot = -dot

        if dot > 0.9995:
            # Quaternions nearly parallel — safe to lerp
            result = Quaternion(
                self.x + t * (q2.x - self.x),
                self.y + t * (q2.y - self.y),
                self.z + t * (q2.z - self.z),
                self.w + t * (q2.w - self.w),
            )
            mag = math.sqrt(result.x**2 + result.y**2 + result.z**2 + result.w**2)
            if mag == 0.0:
                return result
            return Quaternion(result.x / mag, result.y / mag, result.z / mag, result.w / mag)

        theta_0 = math.acos(dot)
        theta = theta_0 * t
        sin_theta = math.sin(theta)
        sin_theta_0 = math.sin(theta_0)

        s1 = math.cos(theta) - dot * sin_theta / sin_theta_0
        s2 = sin_theta / sin_theta_0

        return Quaternion(
            s1 * self.x + s2 * q2.x,
            s1 * self.y + s2 * q2.y,
            s1 * self.z + s2 * q2.z,
            s1 * self.w + s2 * q2.w,
        )


class UV(NamedTuple):
    u: float
    v: float


class D3DColor(NamedTuple):
    r: float
    g: float
    b: float
    a: float


# ── Material ──────────────────────────────────────────────────────────────────


class RenderFlag(IntFlag):
    ALPHA_BLENDING = 0x001
    NO_FOG = 0x002
    DOUBLE_SIDED = 0x004
    BILLBOARD_Y = 0x008
    POINT_SAMPLING = 0x010
    WINDY = 0x020
    NO_LIGHT = 0x040
    DIFFUSE_ALPHA = 0x080
    NO_Z_WRITE = 0x100
    UV_CLAMP = 0x200
    NO_Z_BUFFER = 0x400


@dataclass
class Material:
    """Binary size: 92 bytes (4×D3DColor@16 + float + 5×uint32 + 2×uint32)."""

    diffuse: D3DColor
    ambient: D3DColor
    specular: D3DColor
    emissive: D3DColor
    power: float
    color_op: int
    color_arg1: int
    color_arg2: int
    render_flags: int  # RenderFlag bitmask (uint32, NOT bool — fixes prototype bug)
    src_blend: int
    dest_blend: int


# ── Animation keys ────────────────────────────────────────────────────────────


class AnimKeyType(IntEnum):
    VECTOR3 = 0
    QUATERNION = 1


@dataclass
class AnimKey:
    """Stores keyframe data for a single channel (position, rotation, or scale).

    Data is a list of Vector3 (for VECTOR3 type) or Quaternion (for QUATERNION type).
    The last element is duplicated for safe out-of-range access during interpolation.
    """

    count: int = 0
    key_type: AnimKeyType = AnimKeyType.VECTOR3
    sampling_rate: float = 30.0
    data: list = field(default_factory=list)

    def get_value(self, frame: float, default):
        """Interpolate the key at the given frame number (30 fps base).

        Falls back to ``default`` when count is 0.
        """
        if self.count <= 0:
            return default

        # Map from 30-fps timeline to key index
        index = int(frame * (self.sampling_rate / 30.0))
        if index < 0 or index > self.count:
            return default

        delta = 0.0
        if index >= self.count:
            index = self.count - 1
        else:
            fD = 30.0 / self.sampling_rate
            delta = (frame - index * fD) / fD

        if delta != 0.0 and (index + 1) < len(self.data):
            d0 = self.data[index]
            d1 = self.data[index + 1]
            if self.key_type == AnimKeyType.VECTOR3:
                return d0.lerp(d1, delta)
            else:
                return d0.slerp(d1, delta)
        else:
            return self.data[index]


# ── Enum types ────────────────────────────────────────────────────────────────


class PlugType(IntEnum):
    NORMAL = 0
    CLOAK = 1
    MAX = 10
    UNDEFINED = 0xFFFFFFFF


# ── LOD ───────────────────────────────────────────────────────────────────────


@dataclass
class LODCtrlValue:
    dist: float
    num_vertices: int
