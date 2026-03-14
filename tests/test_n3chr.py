"""Tests for the .n3chr parser."""

import pytest
from openko_blender.formats import n3chr


def test_load_parses_without_error(n3chr_file):
    char = n3chr.load(n3chr_file)
    assert char is not None


def test_name_is_string(n3chr_file):
    char = n3chr.load(n3chr_file)
    assert isinstance(char.name, str)


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


def test_scale_is_finite(n3chr_file):
    import math
    char = n3chr.load(n3chr_file)
    assert math.isfinite(char.scale.x)
    assert math.isfinite(char.scale.y)
    assert math.isfinite(char.scale.z)
