"""Tests for the .n3chr parser.

Sample files cover two format versions:
  - intro.n3chr (615 bytes) — predates the FX plug field added 2002-10-10;
    loading it is a regression guard for the buffer-overrun fix.
  - mob_goblin, el_dong_gold, npc_dong_gold — newer files that include the
    FX plug field at the end and vary in complexity (parts, plugs, anims).
"""

import math
from pathlib import Path

import pytest

from openko_blender.formats import n3chr

import os as _os
_ASSETS = Path(_os.environ.get("KO_ASSETS", "ko_assets/Client"))

# Four files that span old/new format and low/high complexity.
_SAMPLES = [
    _ASSETS / "Intro" / "intro.n3chr",        # old format — no FX plug
    _ASSETS / "Chr"   / "mob_goblin.n3chr",   # small mob, newer format
    _ASSETS / "Chr"   / "el_dong_gold.n3chr", # NPC with parts, plugs, anim
    _ASSETS / "Chr"   / "npc_dong_gold.n3chr",# large NPC with multiple plugs
]


@pytest.fixture(params=_SAMPLES, ids=[p.name for p in _SAMPLES])
def any_n3chr_file(request):
    path = request.param
    if not path.exists():
        pytest.skip(f"Asset not found: {path}")
    return path


# ── Tests that run against every sample file ──────────────────────────────────


def test_load_parses_without_error(any_n3chr_file):
    char = n3chr.load(any_n3chr_file)
    assert char is not None


def test_name_is_string(any_n3chr_file):
    char = n3chr.load(any_n3chr_file)
    assert isinstance(char.name, str)


def test_pos_is_finite(any_n3chr_file):
    char = n3chr.load(any_n3chr_file)
    assert math.isfinite(char.pos.x)
    assert math.isfinite(char.pos.y)
    assert math.isfinite(char.pos.z)


def test_scale_is_finite(any_n3chr_file):
    char = n3chr.load(any_n3chr_file)
    assert math.isfinite(char.scale.x)
    assert math.isfinite(char.scale.y)
    assert math.isfinite(char.scale.z)


# ── Tests specific to full character files ────────────────────────────────────


def test_has_joint(n3chr_file):
    char = n3chr.load(n3chr_file)
    assert char.joint is not None, "Character should have a loaded skeleton"


def test_joint_has_children(n3chr_file):
    char = n3chr.load(n3chr_file)
    assert len(char.joint.flat_list()) > 1


def test_has_parts(n3chr_file):
    char = n3chr.load(n3chr_file)
    assert len(char.parts) > 0, "Character should have at least one body part"


def test_parts_have_skins(n3chr_file):
    char = n3chr.load(n3chr_file)
    for part in char.parts:
        assert part.skins[0] is not None, "Each part should have LOD 0 skin data"


def test_anim_control_loaded(n3chr_file):
    char = n3chr.load(n3chr_file)
    assert char.anim_control is not None, "Character should have animation data"
    assert len(char.anim_control.animations) > 0


def test_anim_frame_ranges_are_valid(n3chr_file):
    """Animation frame ranges must be non-negative, and at least one must be non-zero.

    Zero-length stubs (frm_start == frm_end) are allowed — the engine uses them as
    placeholder slots.  But frm_end must never be less than frm_start, and at least
    one real clip must exist so the import operator can set a meaningful frame_end.
    """
    char = n3chr.load(n3chr_file)
    for anim in char.anim_control.animations:
        assert anim.frm_end >= anim.frm_start, (
            f"Animation {anim.name!r}: frm_end ({anim.frm_end}) "
            f"must not be less than frm_start ({anim.frm_start})"
        )
    real_anims = [a for a in char.anim_control.animations if a.frm_end > a.frm_start]
    assert real_anims, "Expected at least one animation with a non-zero frame range"