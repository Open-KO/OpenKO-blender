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

_ASSETS = Path(r"C:\Users\srmeier\Projects\KnightOnline\assets\Client")

# Four files that span old/new format and low/high complexity.
_SAMPLES = [
    _ASSETS / "Intro"  / "intro.n3chr",       # old format — no FX plug
    _ASSETS / "Chr"    / "mob_goblin.n3chr",   # small mob, newer format
    _ASSETS / "Chr"    / "el_dong_gold.n3chr", # NPC with parts, plugs, anim
    _ASSETS / "Chr"    / "npc_dong_gold.n3chr",# large NPC with multiple plugs
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