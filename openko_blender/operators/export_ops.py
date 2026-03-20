"""
Export operators for KnightOnline game assets.

Walks Blender collections looking for ExportFileType custom properties,
extracts mesh/material/metadata back into KO data structures, and writes
binary files using the format save() functions.

Entry point: File > Export > KnightOnline Assets
"""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------


class EXPORT_OT_ko_asset(Operator, ExportHelper):
    """Export KnightOnline game assets from collections"""

    bl_idname = "export_ko.asset"
    bl_label = "KnightOnline Asset"
    bl_options = {'UNDO'}

    filename_ext = ""

    filter_glob: StringProperty(
        default="*.n3chr;*.n3shape;*.n3cpart;*.n3cplug;*.n3joint;*.n3anim;*.n3pmesh",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        export_dir = Path(self.filepath).parent

        # Find the active collection or the first collection with ExportFileType
        col = _find_export_collection(context)
        if col is None:
            self.report({'ERROR'}, "No collection with ExportFileType found. "
                        "Select a collection that was imported from a KO file.")
            return {'CANCELLED'}

        try:
            count = _export_collection(col, export_dir)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {count} file(s) to {export_dir}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Menu entry
# ---------------------------------------------------------------------------


def menu_func_export(self, context):
    self.layout.operator(
        EXPORT_OT_ko_asset.bl_idname,
        text="KnightOnline Assets (.n3chr, .n3shape, ...)",
    )


# ---------------------------------------------------------------------------
# Collection walking
# ---------------------------------------------------------------------------


def _find_export_collection(context) -> "bpy.types.Collection | None":
    """Find the collection to export.

    Prefers the active collection (if it has ExportFileType), then falls back
    to searching all scene collections.
    """
    # Try active collection
    active_col = context.view_layer.active_layer_collection.collection
    if "ExportFileType" in active_col:
        return active_col

    # Fall back: search scene collections
    for col in context.scene.collection.children:
        if "ExportFileType" in col:
            return col

    return None


def _export_collection(col: bpy.types.Collection, export_dir: Path) -> int:
    """Export a collection and its children.  Returns total files written."""
    file_type = col.get("ExportFileType", "")
    if not file_type:
        return 0

    dispatch = {
        '.n3chr':   _export_n3chr,
        '.n3shape': _export_n3shape,
        '.n3cpart': _export_n3cpart,
        '.n3cplug': _export_n3cplug,
        '.n3joint': _export_n3joint,
        '.n3pmesh': _export_n3pmesh,
    }

    fn = dispatch.get(file_type)
    if fn is None:
        raise ValueError(f"Unsupported ExportFileType: {file_type}")

    return fn(col, export_dir)


# ---------------------------------------------------------------------------
# Per-format export functions
# ---------------------------------------------------------------------------


def _export_n3chr(col: bpy.types.Collection, export_dir: Path) -> int:
    """Export a .n3chr collection and all its child sub-file collections.

    Sub-files are written to the correct relative directories based on their
    ExportPath (e.g., ``item\\mob_upper.n3cpart`` goes to ``<root>/item/``).
    The root is inferred as the parent of export_dir (since .n3chr files
    live in subdirectories like ``Chr/`` under the Client root).
    """
    from ..formats.n3chr import N3Chr
    from ..formats import n3chr as _n3chr
    from ..formats.structs import Quaternion, Vector3

    filename = col.get("ExportFilename", col.name)
    chr_path = export_dir / f"{filename}.n3chr"

    # The Client root is one level above the .n3chr directory
    # (e.g., Chr/mob.n3chr → Client root is Chr/..)
    client_root = export_dir.parent

    # Collect child collection references by type
    joint_filename = ""
    part_filenames: list[str] = []
    plug_filenames: list[str] = []
    anim_filename = ""
    count = 0

    for child_col in col.children:
        child_type = child_col.get("ExportFileType", "")
        child_name = child_col.get("ExportFilename", child_col.name)
        # Use the original relative path if available, otherwise reconstruct
        child_path = child_col.get("ExportPath", f"{child_name}{child_type}")

        # Resolve the output directory from the relative path
        child_rel = Path(child_path.replace("\\", "/"))
        child_out_dir = client_root / child_rel.parent
        child_out_dir.mkdir(parents=True, exist_ok=True)

        if child_type == ".n3joint":
            joint_filename = child_path
            anim_filename = child_col.get("szAnimFilename", "")
            count += _export_n3joint(child_col, child_out_dir)

        elif child_type == ".n3cpart":
            part_filenames.append(child_path)
            count += _export_n3cpart(child_col, child_out_dir)

        elif child_type == ".n3cplug":
            plug_filenames.append(child_path)
            count += _export_n3cplug(child_col, child_out_dir)

    # Build N3Chr data from custom properties
    chr_data = N3Chr(
        name=col.get("ExportFilename", col.name),
        pos=Vector3(0.0, 0.0, 0.0),
        rot=Quaternion(0.0, 0.0, 0.0, 1.0),
        scale=Vector3(1.0, 1.0, 1.0),
        joint_filename=joint_filename,
        part_filenames=part_filenames,
        plug_filenames=plug_filenames,
        anim_filename=anim_filename,
        collision_mesh_filename=col.get("szCollisionMeshFilename", ""),
        climb_mesh_filename=col.get("szClimbMeshFilename", ""),
        joint_part_starts=list(col.get("m_nJointPartStarts", [0, 0])),
        joint_part_ends=list(col.get("m_nJointPartEnds", [0, 0])),
        fx_plug_name=col.get("szFXPlugName", ""),
        collision_skin_name=col.get("szCollisionSkinName", ""),
    )

    _n3chr.save(chr_data, chr_path)
    count += 1
    return count


def _export_n3shape(col: bpy.types.Collection, export_dir: Path) -> int:
    """Export a .n3shape collection."""
    from ..formats.n3shape import N3Shape, ShapePart, save
    from ..formats.structs import Quaternion, Vector3
    from ..blender.mesh_extractor import (
        extract_static_mesh, extract_material_struct, extract_texture_filename,
    )
    from ..formats import n3pmesh as _n3pmesh

    filename = col.get("ExportFilename", col.name)
    shape_path = export_dir / f"{filename}.n3shape"
    count = 0

    parts: list[ShapePart] = []
    for obj in col.objects:
        if obj.type != 'MESH':
            continue

        # Extract mesh and save as .n3pmesh
        pmesh = extract_static_mesh(obj, obj.name)
        mesh_filename = f"{obj.name}.n3pmesh"
        _n3pmesh.save(pmesh, export_dir / mesh_filename)
        count += 1

        # Extract material
        bl_mat = obj.data.materials[0] if obj.data.materials else None
        mat_struct = extract_material_struct(bl_mat)

        # Read custom properties
        pivot_raw = obj.get("m_vPivot", [0.0, 0.0, 0.0])
        pivot = Vector3(pivot_raw[0], pivot_raw[1], pivot_raw[2])
        tex_fps = obj.get("m_fTexFPS", 0.0)
        tex_filenames = list(obj.get("m_TexRefs", []))
        # Fall back to extracting from the material node if no stored refs
        if not tex_filenames:
            tex_fn = extract_texture_filename(bl_mat)
            if tex_fn:
                tex_filenames = [tex_fn]

        parts.append(ShapePart(
            pivot=pivot,
            mesh_filename=mesh_filename,
            material=mat_struct,
            tex_filenames=tex_filenames,
            tex_fps=tex_fps,
        ))

    shape = N3Shape(
        name=col.get("ExportFilename", col.name),
        pos=Vector3(0.0, 0.0, 0.0),
        rot=Quaternion(0.0, 0.0, 0.0, 1.0),
        scale=Vector3(1.0, 1.0, 1.0),
        parts=parts,
        collision_mesh_filename=col.get("szCollisionMeshFilename", ""),
        climb_mesh_filename=col.get("szClimbMeshFilename", ""),
        belong_id=col.get("m_iBelong", 0),
        event_id=col.get("m_iEventID", 0),
        event_type=col.get("m_iEventType", 0),
        npc_id=col.get("m_iNPC_ID", 0),
        npc_status=col.get("m_iNPC_Status", 0),
    )

    save(shape, shape_path)
    count += 1
    return count


def _export_n3cpart(col: bpy.types.Collection, export_dir: Path) -> int:
    """Export a .n3cpart collection with full .n3cskins skinning data."""
    from ..formats.n3cpart import N3CPart, save, save_skins
    from ..blender.mesh_extractor import (
        extract_material_struct, extract_texture_filename, generate_lod_skins,
    )

    filename = col.get("ExportFilename", col.name)
    cpart_path = export_dir / f"{filename}.n3cpart"
    count = 0

    mesh_obj = None
    for obj in col.objects:
        if obj.type == 'MESH':
            mesh_obj = obj
            break

    if mesh_obj is None:
        raise ValueError(f"No mesh object found in collection '{col.name}' for .n3cpart export")

    bl_mat = mesh_obj.data.materials[0] if mesh_obj.data.materials else None
    mat_struct = extract_material_struct(bl_mat)
    # Use stored original texture filename, fall back to extraction from node
    tex_filename = mesh_obj.get("szTexFilename", "") or extract_texture_filename(bl_mat)
    version = mesh_obj.get("m_dwReserved", 0)

    # Use stored original skins filename, fall back to plain name
    skins_filename = mesh_obj.get("szSkinsFilename", f"{filename}.n3cskins")

    # Build bone name list from the armature (if skinned)
    bone_names: list[str] = []
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            bone_names = [b.name for b in mod.object.data.bones]
            break

    # Use original part name (preserves casing like "mob_gavolt_Lower")
    part_name = mesh_obj.get("szPartName", filename)

    # Generate all 4 LOD levels (LOD 0 = full detail, LODs 1-3 via Decimate)
    skins = generate_lod_skins(mesh_obj, bone_names, part_name)
    skins_stem = Path(skins_filename.replace("\\", "/")).stem
    save_skins(skins, part_name, export_dir / f"{skins_stem}.n3cskins")
    count += 1

    part = N3CPart(
        name=part_name,
        material=mat_struct,
        tex_filename=tex_filename,
        skins_filename=skins_filename,
        version=version,
    )

    save(part, cpart_path)
    count += 1
    return count


def _export_n3cplug(col: bpy.types.Collection, export_dir: Path) -> int:
    """Export a .n3cplug collection."""
    from ..formats.n3cplug import N3CPlug, save
    from ..formats.structs import PlugType, Vector3
    from ..blender.mesh_extractor import (
        extract_static_mesh, extract_material_struct,
        extract_texture_filename, extract_plug_transform,
    )
    from ..formats import n3pmesh as _n3pmesh

    filename = col.get("ExportFilename", col.name)
    cplug_path = export_dir / f"{filename}.n3cplug"
    count = 0

    # Find the mesh object
    mesh_obj = None
    for obj in col.objects:
        if obj.type == 'MESH':
            mesh_obj = obj
            break

    if mesh_obj is None:
        raise ValueError(f"No mesh object found in collection '{col.name}' for .n3cplug export")

    # Export the mesh as .n3pmesh
    pmesh = extract_static_mesh(mesh_obj, mesh_obj.name)
    mesh_filename = f"{mesh_obj.name}.n3pmesh"
    _n3pmesh.save(pmesh, export_dir / mesh_filename)
    count += 1

    bl_mat = mesh_obj.data.materials[0] if mesh_obj.data.materials else None
    mat_struct = extract_material_struct(bl_mat)
    tex_filename = mesh_obj.get("szTexFilename", "") or extract_texture_filename(bl_mat)

    # Read plug metadata from custom properties
    plug_type_val = mesh_obj.get("m_ePlugType", 0)
    try:
        plug_type = PlugType(plug_type_val)
    except ValueError:
        plug_type = PlugType.NORMAL

    # Reconstruct joint index from bone parenting
    joint_index = 0
    if mesh_obj.parent and mesh_obj.parent_type == 'BONE':
        rig = mesh_obj.parent
        bone_name = mesh_obj.parent_bone
        for i, bone in enumerate(rig.data.bones):
            if bone.name == bone_name:
                joint_index = i
                break

    # Recover DX-space transform from matrix_basis
    position, rot_matrix, scale = extract_plug_transform(mesh_obj)

    plug = N3CPlug(
        name=filename,
        plug_type=plug_type,
        joint_index=joint_index,
        position=position,
        rot_matrix=rot_matrix,
        scale=scale,
        material=mat_struct,
        mesh_filename=mesh_filename,
        tex_filename=tex_filename,
        trace_step=mesh_obj.get("m_nTraceStep", 0),
        trace_color=mesh_obj.get("m_crTrace", 0),
        trace0=mesh_obj.get("m_fTrace0", 0.0),
        trace1=mesh_obj.get("m_fTrace1", 0.0),
    )

    save(plug, cplug_path)
    count += 1
    return count


def _export_n3joint(col: bpy.types.Collection, export_dir: Path) -> int:
    """Export a .n3joint collection.

    Reconstructs the Joint hierarchy from the Blender armature, including
    animation keys re-sampled from Blender Actions.
    """
    from ..formats.n3joint import Joint, save

    filename = col.get("ExportFilename", col.name)
    joint_path = export_dir / f"{filename}.n3joint"
    count = 0

    rig = None
    for obj in col.objects:
        if obj.type == 'ARMATURE':
            rig = obj
            break

    if rig is None:
        raise ValueError(f"No armature found in collection '{col.name}' for .n3joint export")

    root_joint = _armature_to_joints(rig)

    # Re-sample animation keys from Blender Actions into the Joint hierarchy
    _resample_animation_keys(rig, root_joint)

    save(root_joint, joint_path)
    count += 1

    # Export animation metadata
    anim_filename = col.get("szAnimFilename", "")
    if anim_filename and rig.animation_data:
        count += _export_anims_from_armature(rig, anim_filename, export_dir)

    return count


def _armature_to_joints(rig: bpy.types.Object) -> "Joint":
    """Build a Joint hierarchy from Blender armature bones.

    Reads bind-pose values from bone custom properties (stored during import).
    Falls back to computing positions from bone heads if properties are missing.
    """
    import mathutils
    from ..formats.n3joint import Joint
    from ..formats.structs import Quaternion, Vector3
    from ..blender.coords import MAP_MTX_INV

    armature = rig.data

    root_bones = [b for b in armature.bones if b.parent is None]
    if not root_bones:
        raise ValueError("Armature has no root bone")

    def _bone_to_joint(
        bone: bpy.types.Bone,
        parent_dx_world_pos: mathutils.Vector | None,
    ) -> Joint:
        # Try to read stored bind-pose values (set during import)
        if "bind_pos" in bone:
            bp = bone["bind_pos"]
            pos = Vector3(bp[0], bp[1], bp[2])
            br = bone["bind_rot"]
            rot = Quaternion(br[0], br[1], br[2], br[3])
            bs = bone["bind_scale"]
            scale = Vector3(bs[0], bs[1], bs[2])
        else:
            # Fall back: derive position from bone heads
            bl_pos = bone.head_local.to_4d()
            dx_world_pos = MAP_MTX_INV @ bl_pos
            if parent_dx_world_pos is not None:
                local_pos = dx_world_pos - parent_dx_world_pos
            else:
                local_pos = dx_world_pos
            pos = Vector3(local_pos.x, local_pos.y, local_pos.z)
            rot = Quaternion(0.0, 0.0, 0.0, 1.0)
            scale = Vector3(1.0, 1.0, 1.0)

        # Compute DX world pos for children's fallback path
        bl_pos = bone.head_local.to_4d()
        dx_world_pos = MAP_MTX_INV @ bl_pos

        return Joint(
            name=bone.name,
            pos=pos,
            rot=rot,
            scale=scale,
            children=[
                _bone_to_joint(child, dx_world_pos)
                for child in bone.children
            ],
        )

    if len(root_bones) == 1:
        return _bone_to_joint(root_bones[0], None)

    return Joint(
        name="root",
        pos=Vector3(0.0, 0.0, 0.0),
        rot=Quaternion(0.0, 0.0, 0.0, 1.0),
        scale=Vector3(1.0, 1.0, 1.0),
        children=[_bone_to_joint(b, None) for b in root_bones],
    )


def _resample_animation_keys(rig: bpy.types.Object, root_joint: "Joint") -> None:
    """Re-sample Blender Actions back into KO AnimKey arrays on the Joint tree.

    For each Action (animation clip), evaluates the pose at each frame,
    reverses the DX↔Blender correction math, decomposes to local pos/rot/scale,
    and stores the results in the Joint's key_pos/key_rot/key_scale arrays.

    The KO engine indexes keys by source frame number (from fFrmStart to fFrmEnd),
    so the key arrays must cover the full range across all clips.
    """
    import mathutils
    from ..formats.structs import AnimKey, AnimKeyType, Quaternion, Vector3
    from ..blender.coords import MAP_MTX, MAP_MTX_INV

    if rig.animation_data is None:
        return

    actions = [a for a in bpy.data.actions if "fFrmStart" in a]
    if not actions:
        return

    # Determine total frame range across all clips
    max_ko_frame = 0
    for action in actions:
        end = int(action.get("fFrmEnd", 0))
        if end > max_ko_frame:
            max_ko_frame = end

    if max_ko_frame <= 0:
        return

    total_keys = max_ko_frame + 1  # frames 0..max_ko_frame

    # Build flat bone list matching Joint tree (depth-first)
    all_joints = root_joint.flat_list()
    bone_names = [j.name for j in all_joints]

    # Pre-compute correction matrices from stored dx_bind_bl
    armature = rig.data
    corrections: dict[str, mathutils.Matrix] = {}
    for bone in armature.bones:
        if "dx_bind_bl" in bone:
            flat = list(bone["dx_bind_bl"])
            dx_bind_bl = mathutils.Matrix([flat[i:i+4] for i in range(0, 16, 4)])
            corrections[bone.name] = bone.matrix_local.inverted() @ dx_bind_bl

    if not corrections:
        return  # No stored correction data — can't reconstruct keys

    # Initialize per-bone key arrays
    # pos_keys[bone_name][ko_frame] = Vector3
    pos_keys: dict[str, list] = {name: [None] * total_keys for name in bone_names}
    rot_keys: dict[str, list] = {name: [None] * total_keys for name in bone_names}
    scale_keys: dict[str, list] = {name: [None] * total_keys for name in bone_names}

    # Save and restore state
    original_action = rig.animation_data.action
    original_frame = bpy.context.scene.frame_current
    was_hidden = rig.hide_get()

    # Ensure armature is visible and active (required for mode_set)
    if was_hidden:
        rig.hide_set(False)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')

    for action in actions:
        rig.animation_data.action = action
        ko_start = int(action.get("fFrmStart", 0))
        ko_end = int(action.get("fFrmEnd", 0))
        num_frames = ko_end - ko_start

        for frame_offset in range(num_frames + 1):
            bl_frame = frame_offset + 1  # Blender frames start at 1
            ko_frame = ko_start + frame_offset

            if ko_frame >= total_keys:
                break

            bpy.context.scene.frame_set(bl_frame)

            # Collect world-space DX matrices for all bones at this frame
            dx_worlds: dict[str, mathutils.Matrix] = {}

            for pb in rig.pose.bones:
                if pb.name not in corrections:
                    continue

                bone = armature.bones[pb.name]
                bone_rest = bone.matrix_local

                # Reconstruct desired_pose from matrix_basis
                # Import: matrix_basis = bone_rest.inv @ desired_pose (root)
                #         matrix_basis = rest_offset.inv @ parent_bl_pose.inv @ desired_pose (child)
                if pb.parent is not None:
                    parent_bone_rest = armature.bones[pb.parent.name].matrix_local
                    rest_offset = parent_bone_rest.inverted() @ bone_rest
                    parent_bl_pose = pb.parent.matrix @ pb.parent.bone.matrix_local.inverted() @ parent_bone_rest
                    desired_pose = parent_bl_pose @ rest_offset @ pb.matrix_basis
                else:
                    desired_pose = bone_rest @ pb.matrix_basis

                # Reverse correction: dx_anim_bl = desired_pose @ correction
                correction = corrections[pb.name]
                dx_anim_bl = desired_pose @ correction

                # Reverse coordinate conversion: dx_world = MAP_MTX_INV @ dx_anim_bl @ MAP_MTX
                dx_world = MAP_MTX_INV @ dx_anim_bl @ MAP_MTX
                dx_worlds[pb.name] = dx_world

            # Compute local transforms and store in key arrays
            for pb in rig.pose.bones:
                if pb.name not in dx_worlds:
                    continue

                dx_world = dx_worlds[pb.name]

                if pb.parent is not None and pb.parent.name in dx_worlds:
                    parent_dx_world = dx_worlds[pb.parent.name]
                    dx_local = parent_dx_world.inverted() @ dx_world
                else:
                    dx_local = dx_world

                loc = dx_local.to_translation()
                rot_q = dx_local.to_quaternion()
                sca = dx_local.to_scale()

                pos_keys[pb.name][ko_frame] = Vector3(loc.x, loc.y, loc.z)
                # KO quaternion order: x, y, z, w
                rot_keys[pb.name][ko_frame] = Quaternion(rot_q.x, rot_q.y, rot_q.z, rot_q.w)
                scale_keys[pb.name][ko_frame] = Vector3(sca.x, sca.y, sca.z)

    # Restore state
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.animation_data.action = original_action
    bpy.context.scene.frame_set(original_frame)
    if was_hidden:
        rig.hide_set(True)

    # Build AnimKey structures on each Joint
    for joint in all_joints:
        pk = pos_keys.get(joint.name)
        rk = rot_keys.get(joint.name)
        sk = scale_keys.get(joint.name)

        if pk and any(v is not None for v in pk):
            # Fill gaps with bind-pose defaults
            for i in range(total_keys):
                if pk[i] is None:
                    pk[i] = joint.pos
                if rk[i] is None:
                    rk[i] = joint.rot
                if sk[i] is None:
                    sk[i] = joint.scale

            joint.key_pos = AnimKey(
                count=total_keys,
                key_type=AnimKeyType.VECTOR3,
                sampling_rate=30.0,
                data=pk + [pk[-1]],  # duplicate last for interpolation safety
            )
            joint.key_rot = AnimKey(
                count=total_keys,
                key_type=AnimKeyType.QUATERNION,
                sampling_rate=30.0,
                data=rk + [rk[-1]],
            )
            joint.key_scale = AnimKey(
                count=total_keys,
                key_type=AnimKeyType.VECTOR3,
                sampling_rate=30.0,
                data=sk + [sk[-1]],
            )


def _export_anims_from_armature(
    rig: bpy.types.Object, anim_filename: str, export_dir: Path
) -> int:
    """Export animation Actions from an armature as a .n3anim file."""
    from ..formats.n3anim import AnimData, N3AnimControl, save
    from pathlib import PurePosixPath

    # Collect all actions that have been used with this armature
    animations: list[AnimData] = []

    for action in bpy.data.actions:
        # Check if this action has our custom properties (was imported from KO)
        if "fFrmStart" not in action:
            continue

        start, end = action.frame_range
        animations.append(AnimData(
            name=action.name,
            frm_start=action.get("fFrmStart", start),
            frm_end=action.get("fFrmEnd", end),
            frm_per_sec=action.get("fFrmPerSec", 30.0),
            frm_plug_trace_start=action.get("fFrmPlugTraceStart", 0.0),
            frm_plug_trace_end=action.get("fFrmPlugTraceEnd", 0.0),
            frm_sound_0=action.get("fFrmSound0", 0.0),
            frm_sound_1=action.get("fFrmSound1", 0.0),
            time_blend=action.get("fTimeBlend", 0.25),
            blend_flags=action.get("iBlendFlags", 0),
            frm_strike_0=action.get("fFrmStrike0", 0.0),
            frm_strike_1=action.get("fFrmStrike1", 0.0),
        ))

    if not animations:
        return 0

    anim_ctrl = N3AnimControl(animations=animations)

    # Use the stored filename stem for the output
    anim_stem = Path(anim_filename.replace("\\", "/")).stem
    anim_path = export_dir / f"{anim_stem}.n3anim"
    save(anim_ctrl, anim_path)
    return 1


def _export_n3pmesh(col: bpy.types.Collection, export_dir: Path) -> int:
    """Export a standalone .n3pmesh collection."""
    from ..formats import n3pmesh as _n3pmesh
    from ..blender.mesh_extractor import extract_static_mesh

    filename = col.get("ExportFilename", col.name)

    mesh_obj = None
    for obj in col.objects:
        if obj.type == 'MESH':
            mesh_obj = obj
            break

    if mesh_obj is None:
        raise ValueError(f"No mesh object found in collection '{col.name}' for .n3pmesh export")

    pmesh = extract_static_mesh(mesh_obj, filename)
    _n3pmesh.save(pmesh, export_dir / f"{filename}.n3pmesh")
    return 1
