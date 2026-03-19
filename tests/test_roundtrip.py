"""
Round-trip tests: load original file → save to temp → load temp → compare.

These tests verify that our writers produce binary-compatible output that
the loaders can parse back to equivalent data structures.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _approx(a: float, b: float, tol: float = 1e-5) -> bool:
    return abs(a - b) < tol


def _vectors_equal(v1, v2, tol=1e-5) -> bool:
    return all(_approx(a, b, tol) for a, b in zip(v1, v2))


# ── N3PMesh ──────────────────────────────────────────────────────────────────


def test_n3pmesh_roundtrip(n3pmesh_file, tmp_path):
    from openko_blender.formats import n3pmesh
    from openko_blender.formats.n3pmesh import save as n3pmesh_save

    original = n3pmesh.load(n3pmesh_file)
    out_path = tmp_path / "test.n3pmesh"
    n3pmesh_save(original, out_path)

    reloaded = n3pmesh.load(out_path)

    assert reloaded.name == original.name
    assert reloaded.vertex_count == original.vertex_count
    assert reloaded.face_count == original.face_count
    assert len(reloaded.indices) == len(original.indices)

    for v_orig, v_new in zip(original.vertices, reloaded.vertices):
        assert _vectors_equal(v_orig.pos, v_new.pos)
        assert _vectors_equal(v_orig.normal, v_new.normal)
        assert _approx(v_orig.uv.u, v_new.uv.u)
        assert _approx(v_orig.uv.v, v_new.uv.v)

    assert reloaded.indices == original.indices


# ── N3Joint ──────────────────────────────────────────────────────────────────


def _compare_joints(j1, j2):
    """Recursively compare two Joint trees."""
    assert j1.name == j2.name
    assert _vectors_equal(j1.pos, j2.pos)
    assert _vectors_equal(j1.rot, j2.rot)
    assert _vectors_equal(j1.scale, j2.scale)
    assert j1.key_pos.count == j2.key_pos.count
    assert j1.key_rot.count == j2.key_rot.count
    assert j1.key_scale.count == j2.key_scale.count
    assert j1.key_orient.count == j2.key_orient.count
    assert len(j1.children) == len(j2.children)
    for c1, c2 in zip(j1.children, j2.children):
        _compare_joints(c1, c2)


def test_n3joint_roundtrip(n3joint_file, tmp_path):
    from openko_blender.formats import n3joint
    from openko_blender.formats.n3joint import save as n3joint_save

    original = n3joint.load(n3joint_file)
    out_path = tmp_path / "test.n3joint"
    n3joint_save(original, out_path)

    reloaded = n3joint.load(out_path)
    _compare_joints(original, reloaded)


# ── N3Anim ───────────────────────────────────────────────────────────────────


def test_n3anim_roundtrip(n3anim_file, tmp_path):
    from openko_blender.formats import n3anim
    from openko_blender.formats.n3anim import save as n3anim_save

    original = n3anim.load(n3anim_file)
    out_path = tmp_path / "test.n3anim"
    n3anim_save(original, out_path)

    reloaded = n3anim.load(out_path)

    assert len(reloaded.animations) == len(original.animations)
    for a_orig, a_new in zip(original.animations, reloaded.animations):
        assert a_new.name == a_orig.name
        assert _approx(a_new.frm_start, a_orig.frm_start)
        assert _approx(a_new.frm_end, a_orig.frm_end)
        assert _approx(a_new.frm_per_sec, a_orig.frm_per_sec)
        assert _approx(a_new.frm_plug_trace_start, a_orig.frm_plug_trace_start)
        assert _approx(a_new.frm_plug_trace_end, a_orig.frm_plug_trace_end)
        assert _approx(a_new.frm_sound_0, a_orig.frm_sound_0)
        assert _approx(a_new.frm_sound_1, a_orig.frm_sound_1)
        assert _approx(a_new.time_blend, a_orig.time_blend)
        assert a_new.blend_flags == a_orig.blend_flags
        assert _approx(a_new.frm_strike_0, a_orig.frm_strike_0)
        assert _approx(a_new.frm_strike_1, a_orig.frm_strike_1)


# ── N3CPlug ──────────────────────────────────────────────────────────────────


def test_n3cplug_roundtrip(n3cplug_file, tmp_path):
    from openko_blender.formats import n3cplug
    from openko_blender.formats.n3cplug import save as n3cplug_save

    original = n3cplug.load(n3cplug_file)
    out_path = tmp_path / "test.n3cplug"
    n3cplug_save(original, out_path)

    reloaded = n3cplug.load(out_path)

    assert reloaded.name == original.name
    assert reloaded.plug_type == original.plug_type
    assert reloaded.joint_index == original.joint_index
    assert _vectors_equal(reloaded.position, original.position)
    assert _vectors_equal(reloaded.scale, original.scale)
    assert reloaded.mesh_filename == original.mesh_filename
    assert reloaded.tex_filename == original.tex_filename
    assert reloaded.trace_step == original.trace_step
    assert reloaded.trace_color == original.trace_color
    assert _approx(reloaded.trace0, original.trace0)
    assert _approx(reloaded.trace1, original.trace1)


# ── N3Shape ──────────────────────────────────────────────────────────────────


def test_n3shape_roundtrip(n3shape_file, tmp_path):
    from openko_blender.formats import n3shape
    from openko_blender.formats.n3shape import save as n3shape_save

    original = n3shape.load(n3shape_file)

    # Clear loaded pmesh references (save only writes filenames)
    from openko_blender.formats.n3shape import ShapePart
    save_shape = n3shape.N3Shape(
        name=original.name,
        pos=original.pos,
        rot=original.rot,
        scale=original.scale,
        parts=original.parts,
        collision_mesh_filename=original.collision_mesh_filename,
        climb_mesh_filename=original.climb_mesh_filename,
        belong_id=original.belong_id,
        event_id=original.event_id,
        event_type=original.event_type,
        npc_id=original.npc_id,
        npc_status=original.npc_status,
    )

    out_path = tmp_path / "test.n3shape"
    n3shape_save(save_shape, out_path)

    # Re-load won't resolve sub-files (no .n3pmesh in tmp), so we just
    # verify the metadata survives the round trip
    reloaded = n3shape.load(out_path)

    assert reloaded.name == original.name
    assert _vectors_equal(reloaded.pos, original.pos)
    assert _vectors_equal(reloaded.rot, original.rot)
    assert _vectors_equal(reloaded.scale, original.scale)
    assert reloaded.collision_mesh_filename == original.collision_mesh_filename
    assert reloaded.climb_mesh_filename == original.climb_mesh_filename
    assert reloaded.belong_id == original.belong_id
    assert reloaded.event_id == original.event_id
    assert reloaded.event_type == original.event_type
    assert reloaded.npc_id == original.npc_id
    assert reloaded.npc_status == original.npc_status
    assert len(reloaded.parts) == len(original.parts)

    for p_orig, p_new in zip(original.parts, reloaded.parts):
        assert _vectors_equal(p_orig.pivot, p_new.pivot)
        assert p_orig.mesh_filename == p_new.mesh_filename
        assert _approx(p_orig.tex_fps, p_new.tex_fps)
        assert p_orig.tex_filenames == p_new.tex_filenames
