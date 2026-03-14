"""Tests for the .n3joint parser against real asset files."""

import math

import pytest
from openko_blender.formats import n3joint
from openko_blender.formats.structs import Quaternion, Vector3


def test_load_parses_without_error(n3joint_file):
    joint = n3joint.load(n3joint_file)
    assert joint is not None


def test_root_joint_has_name(n3joint_file):
    root = n3joint.load(n3joint_file)
    assert isinstance(root.name, str)
    assert len(root.name) > 0


def test_joint_tree_has_children(n3joint_file):
    root = n3joint.load(n3joint_file)
    assert len(root.flat_list()) > 1, "Expected a skeleton with more than just the root"


def test_all_joint_names_are_strings(n3joint_file):
    root = n3joint.load(n3joint_file)
    for j in root.flat_list():
        assert isinstance(j.name, str)


def test_joint_positions_are_finite(n3joint_file):
    root = n3joint.load(n3joint_file)
    for j in root.flat_list():
        assert math.isfinite(j.pos.x)
        assert math.isfinite(j.pos.y)
        assert math.isfinite(j.pos.z)


def test_bind_matrix_is_4x4(n3joint_file):
    root = n3joint.load(n3joint_file)
    m = root.bind_matrix()
    assert len(m) == 4
    assert all(len(row) == 4 for row in m)


def test_bind_matrix_translation_matches_pos(n3joint_file):
    root = n3joint.load(n3joint_file)
    m = root.bind_matrix()
    # Translation is in column 3 of each row
    assert m[0][3] == pytest.approx(root.pos.x, abs=1e-4)
    assert m[1][3] == pytest.approx(root.pos.y, abs=1e-4)
    assert m[2][3] == pytest.approx(root.pos.z, abs=1e-4)


# ── Pure-math unit tests (no assets needed) ───────────────────────────────────


def test_quat_mul_identity():
    identity = Quaternion(0, 0, 0, 1)
    q = Quaternion(0.5, 0.5, 0.5, 0.5)
    result = n3joint._quat_mul(q, identity)
    assert result == pytest.approx(q, abs=1e-6)


def test_quat_to_mat4_identity():
    identity_q = Quaternion(0, 0, 0, 1)
    m = n3joint._quat_to_mat4(identity_q)
    # Should produce identity rotation matrix
    assert m[0][0] == pytest.approx(1.0, abs=1e-6)
    assert m[1][1] == pytest.approx(1.0, abs=1e-6)
    assert m[2][2] == pytest.approx(1.0, abs=1e-6)
    assert m[0][1] == pytest.approx(0.0, abs=1e-6)


def test_anim_key_get_value_no_keys_returns_default():
    from openko_blender.formats.structs import AnimKey
    key = AnimKey()
    default = Vector3(1.0, 2.0, 3.0)
    assert key.get_value(0.0, default) == default


def test_anim_key_get_value_single_key():
    from openko_blender.formats.structs import AnimKey, AnimKeyType
    key = AnimKey(count=1, key_type=AnimKeyType.VECTOR3, sampling_rate=30.0)
    v = Vector3(5.0, 0.0, 0.0)
    key.data = [v, v]  # duplicate for interpolation safety
    result = key.get_value(0.0, Vector3(0, 0, 0))
    assert result == pytest.approx(v, abs=1e-6)


def test_anim_key_interpolates_vector3():
    from openko_blender.formats.structs import AnimKey, AnimKeyType
    # At sampling_rate=30fps, key[0] is at frame 0 and key[1] is at frame 1.
    # Frame 0.5 is exactly halfway between them.
    key = AnimKey(count=2, key_type=AnimKeyType.VECTOR3, sampling_rate=30.0)
    v0 = Vector3(0.0, 0.0, 0.0)
    v1 = Vector3(30.0, 0.0, 0.0)
    key.data = [v0, v1, v1]
    result = key.get_value(0.5, v0)
    assert result.x == pytest.approx(15.0, abs=1.0)


def test_quaternion_slerp_identity():
    q = Quaternion(0, 0, 0, 1)
    result = q.slerp(q, 0.5)
    assert result.w == pytest.approx(1.0, abs=1e-5)
