"""Tests for the .n3pmesh parser against real asset files."""

import pytest
from openko_blender.formats import n3pmesh


def test_load_parses_without_error(n3pmesh_file):
    mesh = n3pmesh.load(n3pmesh_file)
    assert mesh is not None


def test_has_vertices(n3pmesh_file):
    mesh = n3pmesh.load(n3pmesh_file)
    assert mesh.vertex_count > 0


def test_has_faces(n3pmesh_file):
    mesh = n3pmesh.load(n3pmesh_file)
    assert mesh.face_count > 0


def test_indices_multiple_of_three(n3pmesh_file):
    mesh = n3pmesh.load(n3pmesh_file)
    assert len(mesh.indices) % 3 == 0


def test_vertex_positions_are_finite(n3pmesh_file):
    import math
    mesh = n3pmesh.load(n3pmesh_file)
    for v in mesh.vertices:
        assert math.isfinite(v.pos.x)
        assert math.isfinite(v.pos.y)
        assert math.isfinite(v.pos.z)


def test_uv_coords_in_valid_range(n3pmesh_file):
    mesh = n3pmesh.load(n3pmesh_file)
    for v in mesh.vertices:
        # UV coords won't always be [0,1] (tiling) but should be finite
        import math
        assert math.isfinite(v.uv.u)
        assert math.isfinite(v.uv.v)


def test_name_is_string(n3pmesh_file):
    mesh = n3pmesh.load(n3pmesh_file)
    assert isinstance(mesh.name, str)


def test_min_vertex_count_lte_max(n3pmesh_file):
    mesh = n3pmesh.load(n3pmesh_file)
    assert mesh.min_num_vertices <= mesh.vertex_count


def test_second_mesh(n3pmesh_file_bow):
    """Verify a second mesh file also parses cleanly."""
    mesh = n3pmesh.load(n3pmesh_file_bow)
    assert mesh.vertex_count > 0
    assert mesh.face_count > 0
