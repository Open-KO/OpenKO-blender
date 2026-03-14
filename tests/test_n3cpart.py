"""Tests for the .n3cpart and .n3cskins parsers."""

import pytest
from openko_blender.formats import n3cpart


def test_load_parses_without_error(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    assert part is not None


def test_name_is_string(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    assert isinstance(part.name, str)


def test_has_tex_filename(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    assert isinstance(part.tex_filename, str)


def test_has_skins_filename(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    assert isinstance(part.skins_filename, str)


def test_skins_list_has_4_slots(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    assert len(part.skins) == 4


def test_lod0_skin_is_not_none(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    assert part.skins[0] is not None, "LOD 0 skin should have mesh data"


def test_lod0_skin_has_vertices(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    skin = part.skins[0]
    assert skin.vertex_count > 0


def test_lod0_skin_has_faces(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    skin = part.skins[0]
    assert skin.face_count > 0


def test_lod0_face_indices_multiple_of_3(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    skin = part.skins[0]
    assert len(skin.face_indices) == skin.face_count * 3


def test_lod0_has_uvs(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    skin = part.skins[0]
    assert skin.uv_count > 0
    assert len(skin.uvs) == skin.uv_count


def test_lod0_skin_vertices_count_matches(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    skin = part.skins[0]
    assert len(skin.skin_vertices) == skin.vertex_count


def test_skin_vertex_joint_indices_are_ints(n3cpart_file):
    part = n3cpart.load(n3cpart_file)
    skin = part.skins[0]
    for sv in skin.skin_vertices:
        for ji in sv.joint_indices:
            assert isinstance(ji, int)
            assert ji >= 0


def test_lod_levels_are_decreasing_or_none(n3cpart_file):
    """Higher LOD levels (1, 2, 3) should have fewer or equal vertices than LOD 0."""
    part = n3cpart.load(n3cpart_file)
    lod0 = part.skins[0]
    for lod in part.skins[1:]:
        if lod is not None:
            assert lod.vertex_count <= lod0.vertex_count


def test_lod0_uv_values_in_range(n3cpart_file):
    """All UV coordinates must be in [0, 1] after DX→Blender conversion."""
    part = n3cpart.load(n3cpart_file)
    skin = part.skins[0]
    for i, uv in enumerate(skin.uvs):
        assert 0.0 <= uv.u <= 1.0, f"UV[{i}].u = {uv.u} out of range"
        assert 0.0 <= uv.v <= 1.0, f"UV[{i}].v = {uv.v} out of range"


def test_lod0_uv_indices_in_bounds(n3cpart_file):
    """Every UV index must refer to a valid entry in the UV list."""
    part = n3cpart.load(n3cpart_file)
    skin = part.skins[0]
    for i, idx in enumerate(skin.uv_indices):
        assert 0 <= idx < skin.uv_count, (
            f"uv_indices[{i}] = {idx} is out of bounds (uv_count={skin.uv_count})"
        )


def test_lod0_uv_not_all_zero(n3cpart_file):
    """UV coordinates must not all be zero — would indicate a read-order bug."""
    part = n3cpart.load(n3cpart_file)
    skin = part.skins[0]
    assert any(uv.u != 0.0 or uv.v != 0.0 for uv in skin.uvs), (
        "All UV coordinates are zero — likely a U/V read-order bug"
    )
