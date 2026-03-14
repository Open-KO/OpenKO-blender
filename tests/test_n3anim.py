"""Tests for the .n3anim parser against real asset files."""

import pytest
from openko_blender.formats import n3anim


def test_load_parses_without_error(n3anim_file):
    ctrl = n3anim.load(n3anim_file)
    assert ctrl is not None


def test_has_animations(n3anim_file):
    ctrl = n3anim.load(n3anim_file)
    assert len(ctrl.animations) > 0


def test_animation_names_are_strings(n3anim_file):
    ctrl = n3anim.load(n3anim_file)
    for a in ctrl.animations:
        assert isinstance(a.name, str)


def test_frame_ranges_are_valid(n3anim_file):
    ctrl = n3anim.load(n3anim_file)
    for a in ctrl.animations:
        assert a.frm_end >= a.frm_start


def test_fps_is_positive(n3anim_file):
    ctrl = n3anim.load(n3anim_file)
    for a in ctrl.animations:
        assert a.frm_per_sec > 0.0


def test_find_returns_animation_by_name(n3anim_file):
    ctrl = n3anim.load(n3anim_file)
    if ctrl.animations:
        first_name = ctrl.animations[0].name
        found = ctrl.find(first_name)
        assert found is not None
        assert found.name == first_name


def test_find_returns_none_for_missing(n3anim_file):
    ctrl = n3anim.load(n3anim_file)
    assert ctrl.find("__nonexistent__") is None


def test_second_anim_file(n3anim_file_canon):
    ctrl = n3anim.load(n3anim_file_canon)
    assert len(ctrl.animations) > 0
