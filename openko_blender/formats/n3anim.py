"""
Parser for .n3anim (CN3AnimControl) — animation metadata format.

CN3AnimControl does NOT extend CN3BaseFileAccess; the file starts directly
with the animation count.

Binary layout:
  int32           anim_count
  AnimData × anim_count:
    int32         _reserved       (read and discarded)
    float32       frm_start
    float32       frm_end
    float32       frm_per_sec
    float32       frm_plug_trace_start
    float32       frm_plug_trace_end
    float32       frm_sound_0
    float32       frm_sound_1
    float32       time_blend
    int32         blend_flags
    float32       frm_strike_0
    float32       frm_strike_1
    string        name            (at end, not beginning)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..utils.binary_reader import BinaryReader


@dataclass
class AnimData:
    name: str = ""
    frm_start: float = 0.0
    frm_end: float = 0.0
    frm_per_sec: float = 30.0
    frm_plug_trace_start: float = 0.0
    frm_plug_trace_end: float = 0.0
    frm_sound_0: float = 0.0
    frm_sound_1: float = 0.0
    time_blend: float = 0.25
    blend_flags: int = 0
    frm_strike_0: float = 0.0
    frm_strike_1: float = 0.0

    @property
    def frame_count(self) -> int:
        return max(0, int(self.frm_end - self.frm_start))


@dataclass
class N3AnimControl:
    animations: list[AnimData] = field(default_factory=list)

    def find(self, name: str) -> AnimData | None:
        for a in self.animations:
            if a.name == name:
                return a
        return None


def load(path: Path | str) -> N3AnimControl:
    """Parse a .n3anim file and return an N3AnimControl."""
    r = BinaryReader.from_file(path)
    count = r.read_int32()

    animations: list[AnimData] = []
    for _ in range(count):
        _reserved = r.read_int32()  # unused field
        frm_start = r.read_float()
        frm_end = r.read_float()
        frm_per_sec = r.read_float()
        frm_plug_trace_start = r.read_float()
        frm_plug_trace_end = r.read_float()
        frm_sound_0 = r.read_float()
        frm_sound_1 = r.read_float()
        time_blend = r.read_float()
        blend_flags = r.read_int32()
        frm_strike_0 = r.read_float()
        frm_strike_1 = r.read_float()
        name = r.read_string()

        animations.append(AnimData(
            name=name,
            frm_start=frm_start,
            frm_end=frm_end,
            frm_per_sec=frm_per_sec,
            frm_plug_trace_start=frm_plug_trace_start,
            frm_plug_trace_end=frm_plug_trace_end,
            frm_sound_0=frm_sound_0,
            frm_sound_1=frm_sound_1,
            time_blend=time_blend,
            blend_flags=blend_flags,
            frm_strike_0=frm_strike_0,
            frm_strike_1=frm_strike_1,
        ))

    return N3AnimControl(animations=animations)
