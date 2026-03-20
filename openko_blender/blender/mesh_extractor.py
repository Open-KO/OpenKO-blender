"""
Extract KO data structures from Blender mesh objects for export.

Reverses the coordinate transforms and winding-order swaps applied during
import (see mesh_builder.py), producing data structures ready for the
format save() functions.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
import mathutils

from .coords import MAP_MTX, MAP_MTX_INV
from ..formats.n3pmesh import MeshVertex, N3PMesh
from ..formats.n3cpart import Skin, SkinVertex
from ..formats.structs import UV, Vector3


def extract_static_mesh(obj: bpy.types.Object, name: str = "") -> N3PMesh:
    """Extract an N3PMesh from a Blender mesh object.

    Reverses:
      - MAP_MTX coordinate transform (Blender → DX)
      - Winding-order swap (undo the index 1↔2 swap per triangle)
    """
    mesh = obj.data
    if not name:
        name = obj.name

    # Use the base mesh directly (no evaluated mesh — avoids modifier deformation).
    # Transform positions and normals manually via MAP_MTX_INV 3x3 to avoid
    # mesh.update() recalculating normals with swapped face winding.
    mesh = obj.data
    uv_layer = mesh.uv_layers.active
    mtx3 = MAP_MTX_INV.to_3x3()

    # Build per-vertex data.  N3PMesh stores one UV per vertex (not per-loop),
    # so we take the UV from the first loop that references each vertex.
    vertex_uvs: dict[int, tuple[float, float]] = {}

    for poly in mesh.polygons:
        for loop_idx in range(poly.loop_start, poly.loop_start + poly.loop_total):
            vi = mesh.loops[loop_idx].vertex_index
            if vi not in vertex_uvs and uv_layer is not None:
                uv = uv_layer.data[loop_idx].uv
                vertex_uvs[vi] = (uv[0], uv[1])

    vertices: list[MeshVertex] = []
    for i, vert in enumerate(mesh.vertices):
        dx_pos = mtx3 @ vert.co
        dx_nrm = mtx3 @ vert.normal
        uv = vertex_uvs.get(i, (0.0, 0.0))
        vertices.append(MeshVertex(
            pos=Vector3(dx_pos.x, dx_pos.y, dx_pos.z),
            normal=Vector3(dx_nrm.x, dx_nrm.y, dx_nrm.z),
            uv=UV(*uv),
        ))

    # Triangulate and reverse winding (undo the import swap of indices 1↔2)
    indices: list[int] = []
    for poly in mesh.polygons:
        if poly.loop_total == 3:
            loops = [mesh.loops[poly.loop_start + j].vertex_index for j in range(3)]
            indices.extend([loops[0], loops[2], loops[1]])
        elif poly.loop_total == 4:
            loops = [mesh.loops[poly.loop_start + j].vertex_index for j in range(4)]
            indices.extend([loops[0], loops[2], loops[1]])
            indices.extend([loops[0], loops[3], loops[2]])

    return N3PMesh(
        name=name,
        vertices=vertices,
        indices=indices,
        min_num_vertices=len(vertices),
        min_num_indices=len(indices),
    )


def extract_material_struct(
    mat: bpy.types.Material,
) -> "from ..formats.structs import Material":
    """Rebuild a KO __Material struct from a Blender material.

    Reads custom properties (Ambient, dwColorOp, etc.) that were stored
    during import.  Falls back to extracting values from the Principled BSDF
    node if custom properties are missing.
    """
    from ..formats.structs import D3DColor, Material, RenderFlag

    # Defaults — alpha 0.0 for specular/emissive matches KO convention
    diffuse = D3DColor(1.0, 1.0, 1.0, 1.0)
    ambient = D3DColor(0.5, 0.5, 0.5, 1.0)
    specular = D3DColor(0.0, 0.0, 0.0, 0.0)
    emissive = D3DColor(0.0, 0.0, 0.0, 0.0)
    power = 10.0
    color_op = 1  # D3DTOP_MODULATE
    color_arg1 = 2
    color_arg2 = 0
    render_flags = 0
    src_blend = 5
    dest_blend = 6

    if mat is None:
        return Material(diffuse, ambient, specular, emissive, power,
                        color_op, color_arg1, color_arg2, render_flags, src_blend, dest_blend)

    # Try to read from Principled BSDF
    if mat.use_nodes:
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                bc = node.inputs["Base Color"].default_value
                diffuse = D3DColor(bc[0], bc[1], bc[2], bc[3])

                roughness = node.inputs["Roughness"].default_value
                # Reverse: roughness = sqrt(2/(power+2)) → power = 2/roughness² - 2
                if roughness > 0.001:
                    power = max(0.0, 2.0 / (roughness * roughness) - 2.0)

                spec_ior = node.inputs["Specular IOR Level"].default_value
                specular = D3DColor(spec_ior, spec_ior, spec_ior, 0.0)

                ec = node.inputs["Emission Color"].default_value
                es = node.inputs["Emission Strength"].default_value
                if es > 0.0:
                    emissive = D3DColor(ec[0], ec[1], ec[2], 0.0)
                break

    # Render flags from Blender material properties
    if not mat.use_backface_culling:
        render_flags |= RenderFlag.DOUBLE_SIDED
    if hasattr(mat, 'blend_method') and mat.blend_method == 'BLEND':
        render_flags |= RenderFlag.ALPHA_BLENDING

    # Override with stored custom properties (they take precedence)
    if "Ambient" in mat:
        a = mat["Ambient"]
        ambient = D3DColor(a[0], a[1], a[2], a[3] if len(a) > 3 else 1.0)
    if "dwColorOp" in mat:
        color_op = int(mat["dwColorOp"])
    if "dwColorArg1" in mat:
        color_arg1 = int(mat["dwColorArg1"])
    if "dwColorArg2" in mat:
        color_arg2 = int(mat["dwColorArg2"])
    if "nRenderFlags" in mat:
        render_flags = int(mat["nRenderFlags"])
    if "dwSrcBlend" in mat:
        src_blend = int(mat["dwSrcBlend"])
    if "dwDestBlend" in mat:
        dest_blend = int(mat["dwDestBlend"])

    return Material(diffuse, ambient, specular, emissive, power,
                    color_op, color_arg1, color_arg2, render_flags, src_blend, dest_blend)


def extract_skinned_mesh(
    obj: bpy.types.Object,
    bone_names: list[str],
    name: str = "",
) -> Skin:
    """Extract a Skin from a Blender skinned mesh object.

    Uses obj.data (the base/bind-pose mesh), NOT the evaluated mesh — the
    evaluated mesh includes armature deformation which would give posed
    positions instead of bind-pose positions.

    Reverses the import transforms:
      - MAP_MTX coordinate transform (Blender -> DX)
      - Winding-order swap (undo the index 1<->2 swap per triangle)

    *bone_names* is an ordered list of bone names matching the joint index
    order in the skeleton.  Vertex group names are mapped to indices in this
    list to produce the skinning joint_indices.
    """
    if not name:
        name = obj.name

    # Build a map from vertex group name -> joint index
    bone_to_idx = {bname: i for i, bname in enumerate(bone_names)}

    # Work on the base mesh (not evaluated — no armature deformation).
    # This gives us the bind-pose geometry that was set during import.
    mesh = obj.data
    uv_layer = mesh.uv_layers.active

    # MAP_MTX_INV 3x3 for transforming positions and normals to DX space.
    # We transform manually rather than using mesh.transform() because
    # mesh.update() would recalculate normals from swapped-winding faces,
    # producing flipped normals.
    mtx3 = MAP_MTX_INV.to_3x3()

    # Build vertices (position + normal) and skin vertices (origin + weights)
    vertices: list[tuple] = []
    skin_vertices: list[SkinVertex] = []

    for i, vert in enumerate(mesh.vertices):
        dx_pos = mtx3 @ vert.co
        dx_nrm = mtx3 @ vert.normal
        v_pos = Vector3(dx_pos.x, dx_pos.y, dx_pos.z)
        normal = Vector3(dx_nrm.x, dx_nrm.y, dx_nrm.z)
        vertices.append((v_pos, normal))

        # Extract skinning weights from vertex groups.
        # Sort by joint index to ensure deterministic order.
        raw_weights: list[tuple[int, float]] = []
        for vg in obj.vertex_groups:
            try:
                weight = vg.weight(i)
            except RuntimeError:
                continue
            if weight > 0.0:
                idx = bone_to_idx.get(vg.name)
                if idx is not None:
                    raw_weights.append((idx, weight))
        raw_weights.sort(key=lambda x: x[0])

        skin_vertices.append(SkinVertex(
            origin=v_pos,
            joint_indices=[jw[0] for jw in raw_weights],
            weights=[jw[1] for jw in raw_weights],
        ))

    # Build face indices with reversed winding.
    # Import swapped indices 1<->2 per triangle; we swap them back.
    face_indices: list[int] = []
    face_count = 0
    for poly in mesh.polygons:
        if poly.loop_total == 3:
            loops = [mesh.loops[poly.loop_start + j].vertex_index for j in range(3)]
            face_indices.extend([loops[0], loops[2], loops[1]])
            face_count += 1
        elif poly.loop_total == 4:
            loops = [mesh.loops[poly.loop_start + j].vertex_index for j in range(4)]
            face_indices.extend([loops[0], loops[2], loops[1]])
            face_indices.extend([loops[0], loops[3], loops[2]])
            face_count += 2

    # Build UVs — .n3cskins uses a separate UV array with per-face-corner indices.
    # During import, UVs were assigned per-loop via _apply_skin_uvs which set
    # uvlayer.data[loop_idx].uv = skin.uvs[swapped_uv_indices[loop_idx]].
    # We read them back per-loop, deduplicate to build a UV array, and construct
    # UV indices with the same winding reversal as face indices.
    uvs: list[UV] = []
    uv_indices: list[int] = []

    if uv_layer is not None:
        # Build per-loop UV index with dedup by exact float value
        uv_map: dict[tuple[float, float], int] = {}
        loop_uv_idx: list[int] = []
        for li in range(len(mesh.loops)):
            raw_uv = uv_layer.data[li].uv
            key = (raw_uv[0], raw_uv[1])
            if key not in uv_map:
                uv_map[key] = len(uvs)
                uvs.append(UV(raw_uv[0], raw_uv[1]))
            loop_uv_idx.append(uv_map[key])

        # Build uv_indices with reversed winding to match face_indices
        for poly in mesh.polygons:
            if poly.loop_total == 3:
                li0, li1, li2 = [poly.loop_start + j for j in range(3)]
                uv_indices.extend([loop_uv_idx[li0], loop_uv_idx[li2], loop_uv_idx[li1]])
            elif poly.loop_total == 4:
                li0, li1, li2, li3 = [poly.loop_start + j for j in range(4)]
                uv_indices.extend([loop_uv_idx[li0], loop_uv_idx[li2], loop_uv_idx[li1]])
                uv_indices.extend([loop_uv_idx[li0], loop_uv_idx[li3], loop_uv_idx[li2]])

    return Skin(
        name=name,
        face_count=face_count,
        vertex_count=len(vertices),
        uv_count=len(uvs),
        vertices=vertices,
        face_indices=face_indices,
        uvs=uvs,
        uv_indices=uv_indices,
        skin_vertices=skin_vertices,
    )


def generate_lod_skins(
    obj: bpy.types.Object,
    bone_names: list[str],
    name: str = "",
    ratios: tuple[float, ...] = (1.0, 0.7, 0.5, 0.25),
) -> list["Skin | None"]:
    """Generate 4 LOD levels of a skinned mesh using Blender's Decimate modifier.

    LOD 0 is the original mesh (ratio 1.0).  LODs 1-3 use progressively lower
    ratios applied via a temporary Decimate modifier in COLLAPSE mode.

    Returns a list of 4 Skin objects (or None for empty LODs).
    """
    if not name:
        name = obj.name

    skins: list[Skin | None] = []

    for i, ratio in enumerate(ratios):
        if ratio >= 1.0:
            # LOD 0: extract directly from the base mesh
            skins.append(extract_skinned_mesh(obj, bone_names, name))
            continue

        # Add a temporary Decimate modifier
        mod = obj.modifiers.new(name="_lod_decimate", type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio

        # Get the decimated mesh via the depsgraph
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()

        # Build a temporary object with the decimated mesh to extract from
        temp_mesh = eval_mesh.copy()
        eval_obj.to_mesh_clear()

        temp_obj = bpy.data.objects.new(f"_lod_{i}", temp_mesh)
        # Copy vertex groups from original
        for vg in obj.vertex_groups:
            temp_obj.vertex_groups.new(name=vg.name)
        # Copy weights - the evaluated mesh preserves vertex groups
        # but we need to re-extract from eval
        # Actually, use a simpler approach: extract from the eval_obj directly

        # Clean up temp approach - let's use a different method
        bpy.data.objects.remove(temp_obj)
        bpy.data.meshes.remove(temp_mesh)

        # Better approach: extract directly from the evaluated (decimated) object
        # We need to read the base mesh of the evaluated object
        eval_mesh2 = eval_obj.to_mesh()
        mtx3 = MAP_MTX_INV.to_3x3()

        vertices = []
        skin_vertices = []
        bone_to_idx = {bname: idx for idx, bname in enumerate(bone_names)}

        for vi, vert in enumerate(eval_mesh2.vertices):
            dx_pos = mtx3 @ vert.co
            dx_nrm = mtx3 @ vert.normal
            v_pos = Vector3(dx_pos.x, dx_pos.y, dx_pos.z)
            normal = Vector3(dx_nrm.x, dx_nrm.y, dx_nrm.z)
            vertices.append((v_pos, normal))

            # Extract weights from the evaluated vertex groups
            joint_indices = []
            weights = []
            for g in eval_mesh2.vertices[vi].groups:
                vg_name = obj.vertex_groups[g.group].name
                idx = bone_to_idx.get(vg_name)
                if idx is not None and g.weight > 0.0:
                    joint_indices.append(idx)
                    weights.append(g.weight)
            # Sort by joint index
            pairs = sorted(zip(joint_indices, weights))
            skin_vertices.append(SkinVertex(
                origin=v_pos,
                joint_indices=[p[0] for p in pairs],
                weights=[p[1] for p in pairs],
            ))

        face_indices = []
        face_count = 0
        for poly in eval_mesh2.polygons:
            if poly.loop_total == 3:
                loops = [eval_mesh2.loops[poly.loop_start + j].vertex_index for j in range(3)]
                face_indices.extend([loops[0], loops[2], loops[1]])
                face_count += 1

        uv_layer = eval_mesh2.uv_layers.active
        uvs = []
        uv_indices = []
        if uv_layer:
            uv_map = {}
            loop_uv_idx = []
            for li in range(len(eval_mesh2.loops)):
                raw_uv = uv_layer.data[li].uv
                key = (raw_uv[0], raw_uv[1])
                if key not in uv_map:
                    uv_map[key] = len(uvs)
                    uvs.append(UV(raw_uv[0], raw_uv[1]))
                loop_uv_idx.append(uv_map[key])

            for poly in eval_mesh2.polygons:
                if poly.loop_total == 3:
                    li0, li1, li2 = [poly.loop_start + j for j in range(3)]
                    uv_indices.extend([loop_uv_idx[li0], loop_uv_idx[li2], loop_uv_idx[li1]])

        eval_obj.to_mesh_clear()

        skins.append(Skin(
            name=name,
            face_count=face_count,
            vertex_count=len(vertices),
            uv_count=len(uvs),
            vertices=vertices,
            face_indices=face_indices,
            uvs=uvs,
            uv_indices=uv_indices,
            skin_vertices=skin_vertices,
        ))

        # Remove the temporary modifier
        obj.modifiers.remove(mod)

    return skins


def extract_texture_filename(mat: bpy.types.Material) -> str:
    """Extract the texture filename from a material's image texture node.

    Returns empty string if no texture node is found.
    """
    if mat is None or not mat.use_nodes:
        return ""

    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image is not None:
            # The image name was set during import to the object name;
            # try to find the original filename from the image filepath
            # or fall back to the image name
            if node.image.filepath:
                return Path(node.image.filepath).name
            return node.image.name

    return ""


def extract_plug_transform(
    obj: bpy.types.Object,
) -> tuple[Vector3, tuple, Vector3]:
    """Recover the DX-space position, rotation matrix, and scale from a
    bone-parented plug object.

    Reverses the import math from _attach_plug_to_bone():
      Import: plug_local_bl = dx_to_blender(plug_local_dx)
              obj.matrix_basis = plug_local_bl

      Export: plug_local_dx = blender_to_dx(obj.matrix_basis)
              Decompose into position, rot_matrix, scale

    Returns: (position, rot_matrix_4x4, scale)
    """
    basis = obj.matrix_basis.copy()

    # Reverse: blender_to_dx = MAP_MTX_INV @ bl_mtx @ MAP_MTX
    plug_local_dx = MAP_MTX_INV @ basis @ MAP_MTX

    # Decompose the DX-space local matrix
    # C++ builds it as: rot_bl = MtxRot^T, then M = rot_bl @ Scale
    # With pos set as position * scale in column 3
    #
    # Extract scale from column magnitudes
    sx = mathutils.Vector(plug_local_dx.col[0][:3]).length
    sy = mathutils.Vector(plug_local_dx.col[1][:3]).length
    sz = mathutils.Vector(plug_local_dx.col[2][:3]).length

    scale = Vector3(sx if sx > 1e-8 else 1.0, sy if sy > 1e-8 else 1.0, sz if sz > 1e-8 else 1.0)

    # Extract rotation matrix (normalize columns to remove scale)
    rot = plug_local_dx.copy()
    for c in range(3):
        col_len = mathutils.Vector(rot.col[c][:3]).length
        if col_len > 1e-8:
            for r in range(3):
                rot[r][c] /= col_len

    # C++ stores rot_matrix as the TRANSPOSE of what we computed
    # (import did: rot_bl = Matrix(plug.rot_matrix).transposed())
    rot_matrix = tuple(
        tuple(rot[r][c] for c in range(4))
        for r in range(4)
    )

    # Extract position: import set col3 = position * scale
    # So position = col3 / scale
    px = plug_local_dx[0][3] / scale.x if scale.x > 1e-8 else 0.0
    py = plug_local_dx[1][3] / scale.y if scale.y > 1e-8 else 0.0
    pz = plug_local_dx[2][3] / scale.z if scale.z > 1e-8 else 0.0
    position = Vector3(px, py, pz)

    return position, rot_matrix, scale
