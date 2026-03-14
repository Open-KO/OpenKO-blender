"""
Build bpy mesh objects from parsed KO data structures.

Handles both static progressive meshes (N3PMesh / .n3pmesh, .n3cplug) and
skinned character-part meshes (Skin / .n3cpart .n3cskins).

Coordinate conversion is applied in-place on the mesh data via
mesh.transform(MAP_MTX) immediately after from_pydata, so all vertex
positions end up in Blender space.

UV coordinates are already corrected by the BinaryReader (v = 1 - v_raw),
so they are assigned directly to uv_layer loops.
"""

from __future__ import annotations

import bpy
import mathutils

from .coords import MAP_MTX
from ..formats.n3cpart import Skin
from ..formats.n3pmesh import N3PMesh


# ---------------------------------------------------------------------------
# Static mesh (N3PMesh)
# ---------------------------------------------------------------------------


def build_static_mesh(pmesh: N3PMesh, name: str) -> bpy.types.Object:
    """Build a Blender mesh object from an N3PMesh (progressive mesh).

    Vertices, face indices, and UVs are taken from the highest LOD
    (max_num_vertices / max_num_indices).  Coordinate system is converted
    from DirectX to Blender via MAP_MTX.
    """
    mesh = bpy.data.meshes.new(f"{name}-mesh")

    verts = [[v.pos.x, v.pos.y, v.pos.z] for v in pmesh.vertices]
    # Reverse winding (swap indices 1 & 2) to compensate for MAP_MTX's negative
    # determinant, which flips face orientation during the DX→Blender transform.
    faces = [
        [pmesh.indices[i], pmesh.indices[i + 2], pmesh.indices[i + 1]]
        for i in range(0, len(pmesh.indices), 3)
    ]

    mesh.from_pydata(verts, [], faces)
    mesh.transform(MAP_MTX)
    mesh.update(calc_edges=True)

    _apply_pmesh_uvs(mesh, pmesh)

    obj = bpy.data.objects.new(name, mesh)
    return obj


# ---------------------------------------------------------------------------
# Skinned mesh (Skin / CN3Skin)
# ---------------------------------------------------------------------------


def build_skinned_mesh(skin: Skin, name: str) -> bpy.types.Object:
    """Build a Blender mesh object from a skinned character part.

    Vertex positions come from SkinVertex.origin (the bind-pose position used
    for skinning).  Faces use the skin's face_indices.  Coordinate conversion
    is applied via MAP_MTX.
    """
    mesh = bpy.data.meshes.new(f"{name}-mesh")

    verts = [[sv.origin.x, sv.origin.y, sv.origin.z] for sv in skin.skin_vertices]
    # Reverse winding (swap indices 1 & 2) — same MAP_MTX compensation as static meshes.
    faces = [
        [skin.face_indices[i], skin.face_indices[i + 2], skin.face_indices[i + 1]]
        for i in range(0, 3 * skin.face_count, 3)
    ]

    mesh.from_pydata(verts, [], faces)
    mesh.transform(MAP_MTX)
    mesh.update(calc_edges=True)

    # Build UV indices with the same winding swap (corners 1 & 2 exchanged per tri)
    swapped_uv_indices = []
    for i in range(0, 3 * skin.face_count, 3):
        swapped_uv_indices.append(skin.uv_indices[i])
        swapped_uv_indices.append(skin.uv_indices[i + 2])
        swapped_uv_indices.append(skin.uv_indices[i + 1])

    _apply_skin_uvs(mesh, skin, swapped_uv_indices)

    obj = bpy.data.objects.new(name, mesh)
    return obj


# ---------------------------------------------------------------------------
# Skinning helpers
# ---------------------------------------------------------------------------


def apply_skin_weights(
    obj: bpy.types.Object,
    skin: Skin,
    all_joints_by_idx: list[str],
) -> None:
    """Add vertex groups and blend weights to *obj* from skinning data.

    *all_joints_by_idx* maps integer joint indices (as stored in the file)
    to the actual Blender bone names that were created during armature build
    (Blender may append .001 suffixes for duplicate joint names).
    """
    for vert_idx, sv in enumerate(skin.skin_vertices):
        if sv.n_affect == 1:
            bone_name = all_joints_by_idx[sv.joint_indices[0]]
            vg = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
            vg.add([vert_idx], 1.0, 'REPLACE')
        elif sv.n_affect > 1:
            for idx, weight in zip(sv.joint_indices, sv.weights):
                bone_name = all_joints_by_idx[idx]
                vg = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
                vg.add([vert_idx], weight, 'ADD')


def add_armature_modifier(obj: bpy.types.Object, rig: bpy.types.Object) -> None:
    """Attach an Armature modifier to *obj* pointing at *rig*."""
    mod = obj.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = rig
    mod.use_vertex_groups = True


# ---------------------------------------------------------------------------
# Private UV helpers
# ---------------------------------------------------------------------------


def _apply_pmesh_uvs(mesh: bpy.types.Mesh, pmesh: N3PMesh) -> None:
    """Assign per-loop UVs from N3PMesh (one UV per vertex, indexed by face loop).

    Uses mesh.loops[].vertex_index rather than the original pmesh.indices so
    UVs stay correct after the winding-order swap in build_static_mesh().
    """
    uvlayer = mesh.uv_layers.new(name="UVMap")
    for face in mesh.polygons:
        for loop_idx in range(face.loop_start, face.loop_start + face.loop_total):
            vert_idx = mesh.loops[loop_idx].vertex_index
            uv = pmesh.vertices[vert_idx].uv
            uvlayer.data[loop_idx].uv = (uv.u, uv.v)


def _apply_skin_uvs(mesh: bpy.types.Mesh, skin: Skin, uv_indices: list[int]) -> None:
    """Assign per-loop UVs from a Skin using the (possibly winding-swapped) *uv_indices*."""
    if skin.uv_count <= 0:
        return
    uvlayer = mesh.uv_layers.new(name="UVMap")
    for face in mesh.polygons:
        for loop_idx in range(face.loop_start, face.loop_start + face.loop_total):
            uv_idx = uv_indices[loop_idx]
            uv = skin.uvs[uv_idx]
            uvlayer.data[loop_idx].uv = (uv.u, uv.v)