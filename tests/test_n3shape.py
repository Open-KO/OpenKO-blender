"""Tests for the .n3shape parser."""

import pytest
from openko_blender.formats import n3shape


def test_load_parses_without_error(n3shape_file):
    shape = n3shape.load(n3shape_file)
    assert shape is not None


def test_name_is_string(n3shape_file):
    shape = n3shape.load(n3shape_file)
    assert isinstance(shape.name, str)


def test_has_parts(n3shape_file):
    shape = n3shape.load(n3shape_file)
    assert len(shape.parts) > 0


def test_parts_have_pivot(n3shape_file):
    import math
    shape = n3shape.load(n3shape_file)
    for part in shape.parts:
        assert math.isfinite(part.pivot.x)
        assert math.isfinite(part.pivot.y)
        assert math.isfinite(part.pivot.z)


def test_parts_have_mesh_filename(n3shape_file):
    shape = n3shape.load(n3shape_file)
    for part in shape.parts:
        assert isinstance(part.mesh_filename, str)


def test_parts_have_pmesh_loaded(n3shape_file):
    shape = n3shape.load(n3shape_file)
    for part in shape.parts:
        assert part.pmesh is not None, (
            f"Part '{part.mesh_filename}' should have a loaded progressive mesh"
        )
        assert part.pmesh.vertex_count > 0


def test_second_shape_file(n3shape_file_chairs):
    shape = n3shape.load(n3shape_file_chairs)
    assert len(shape.parts) > 0
