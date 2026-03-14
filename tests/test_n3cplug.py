"""Tests for the .n3cplug parser."""

import pytest
from openko_blender.formats import n3cplug
from openko_blender.formats.structs import PlugType


def test_load_parses_without_error(n3cplug_file):
    plug = n3cplug.load(n3cplug_file)
    assert plug is not None


def test_name_is_string(n3cplug_file):
    plug = n3cplug.load(n3cplug_file)
    assert isinstance(plug.name, str)


def test_plug_type_is_valid(n3cplug_file):
    plug = n3cplug.load(n3cplug_file)
    assert isinstance(plug.plug_type, PlugType)


def test_joint_index_is_non_negative(n3cplug_file):
    plug = n3cplug.load(n3cplug_file)
    assert plug.joint_index >= 0


def test_position_is_finite(n3cplug_file):
    import math
    plug = n3cplug.load(n3cplug_file)
    assert math.isfinite(plug.position.x)
    assert math.isfinite(plug.position.y)
    assert math.isfinite(plug.position.z)


def test_rot_matrix_is_4x4(n3cplug_file):
    plug = n3cplug.load(n3cplug_file)
    assert len(plug.rot_matrix) == 4
    assert all(len(row) == 4 for row in plug.rot_matrix)


def test_pmesh_loaded(n3cplug_file):
    plug = n3cplug.load(n3cplug_file)
    assert plug.pmesh is not None, "Progressive mesh should be loaded from referenced file"
    assert plug.pmesh.vertex_count > 0


def test_tex_filename_is_string(n3cplug_file):
    plug = n3cplug.load(n3cplug_file)
    assert isinstance(plug.tex_filename, str)
