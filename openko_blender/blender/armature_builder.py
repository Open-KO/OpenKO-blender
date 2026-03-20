"""
Build Blender armatures from CN3Joint hierarchies and bake KO animations.

The core challenge is that Blender's EditBone orientation (determined by
head/tail/roll) does not match the DirectX bind-pose orientation stored in
the KO files.  The approach, ported directly from the prototype, is:

  1. Build armature bones using bind-pose world positions only (head = world pos,
     tail = head + fixed Y offset, use_connect = False).

  2. Record two sets of matrices per bone:
       dx_bind_bl  — the DX bind-pose world matrix converted to Blender space
                     via dx_to_blender().  This is the "true" orientation.
       bone_rest   — Blender's own bone.matrix_local (from head/tail/roll).
                     This is what the Armature modifier actually uses.

  3. Compute a per-bone correction:
       correction = bone_rest.inv @ dx_bind_bl
     This matrix compensates for the orientation mismatch when setting pose
     bone transforms.

  4. During animation baking, for each frame/fFrm:
       dx_anim_bl  = dx_to_blender(dx_animated_world_matrix)
       desired_pose = dx_anim_bl @ correction.inv
       matrix_basis = bone_rest.inv @ desired_pose          (root bone)
                    = rest_offset.inv @ parent_bl_pose.inv @ desired_pose  (child)
       loc, rot, sca = matrix_basis.decompose()
       → keyframe_insert location / rotation_quaternion / scale

This matches the prototype's set_pose_frame() logic exactly.

All animations in N3AnimControl are imported as separate Blender Actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import bpy
import mathutils

from .coords import MAP_MTX, dx_to_blender, joint_local_matrix
from ..formats.n3anim import N3AnimControl
from ..formats.n3joint import Joint


# ---------------------------------------------------------------------------
# ArmatureData — everything needed for animation baking
# ---------------------------------------------------------------------------


@dataclass
class ArmatureData:
    """Per-armature data produced by build_armature(), consumed by build_animations()."""

    rig: bpy.types.Object = None

    # Ordered list of actual Blender bone names (depth-first, matching skinning indices).
    all_joints_by_idx: list[str] = field(default_factory=list)

    # id(joint_python_object) → actual Blender bone name (handles .001 suffixes).
    joint_id_to_bone_name: dict[int, str] = field(default_factory=dict)

    # bone_name → Blender rest matrix (from head/tail/roll — used by armature modifier).
    bone_rest_matrices: dict[str, mathutils.Matrix] = field(default_factory=dict)

    # bone_name → correction = bone_rest.inv @ dx_bind_bl.
    bone_corrections: dict[str, mathutils.Matrix] = field(default_factory=dict)

    # bone_name → DX bind-pose world matrix converted to Blender space.
    dx_bind_bl: dict[str, mathutils.Matrix] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_armature(
    context: bpy.types.Context,
    root_joint: Joint,
    name: str,
    collection: "bpy.types.Collection | None" = None,
) -> ArmatureData:
    """Build a Blender armature from a CN3Joint hierarchy.

    Bones are positioned using the bind-pose world positions (DX → Blender via
    MAP_MTX position-only conversion, matching the prototype).  All necessary
    correction matrices are computed for later animation baking.

    The armature object is linked to *collection* (or the scene root collection
    if None).
    """
    armature = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, armature)

    target = collection if collection is not None else context.scene.collection
    target.objects.link(rig)

    context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')

    data = ArmatureData(rig=rig)

    # Collect per-bone bind-pose data to store as custom properties after edit mode
    _bind_pose_data: dict[str, dict] = {}

    def _add_bone(
        joint: Joint,
        parent_bone: "bpy.types.EditBone | None",
        parent_world_mtx: "mathutils.Matrix | None",
    ) -> None:
        local_mtx = joint_local_matrix(joint, 0.0)   # bind pose = frame 0
        world_mtx = (
            parent_world_mtx @ local_mtx
            if parent_world_mtx is not None
            else local_mtx.copy()
        )

        bone = armature.edit_bones.new(joint.name)

        # Position: convert DX world position to Blender (MAP_MTX on position only)
        bl_pos = MAP_MTX @ mathutils.Vector(world_mtx.to_translation()).to_4d()
        bone.head = bl_pos.to_3d()
        bone.tail = bone.head + mathutils.Vector([0.0, 0.15, 0.0])
        bone.parent = parent_bone
        bone.use_connect = False

        # Blender may add .001 suffix for duplicate joint names — record the real name
        actual_name = bone.name
        data.all_joints_by_idx.append(actual_name)
        data.joint_id_to_bone_name[id(joint)] = actual_name
        data.dx_bind_bl[actual_name] = dx_to_blender(world_mtx)

        # Save bind-pose local values for export round-trip
        _bind_pose_data[actual_name] = {
            "pos": [joint.pos.x, joint.pos.y, joint.pos.z],
            "rot": [joint.rot.x, joint.rot.y, joint.rot.z, joint.rot.w],
            "scale": [joint.scale.x, joint.scale.y, joint.scale.z],
            "dx_bind_bl": [v for row in dx_to_blender(world_mtx) for v in row],
        }

        for child in joint.children:
            _add_bone(child, bone, world_mtx)

    _add_bone(root_joint, None, None)

    # Second pass: orient bones toward children and connect the chain.
    # This makes the skeleton usable for animation in Blender (bones point
    # along the chain instead of all being Y-up stubs).
    _orient_bones(armature)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Store Blender rest matrices and compute per-bone orientation corrections
    for bone in armature.bones:
        data.bone_rest_matrices[bone.name] = bone.matrix_local.copy()

    for bname, dx_bind in data.dx_bind_bl.items():
        data.bone_corrections[bname] = data.bone_rest_matrices[bname].inverted() @ dx_bind

    # Persist bind-pose and correction data as bone custom properties for export
    for bone in armature.bones:
        bp = _bind_pose_data.get(bone.name)
        if bp:
            bone["bind_pos"] = bp["pos"]
            bone["bind_rot"] = bp["rot"]
            bone["bind_scale"] = bp["scale"]
            bone["dx_bind_bl"] = bp["dx_bind_bl"]

    # Store the key sampling rate on the armature for export.
    # Find the first joint with animation keys and use its rate.
    def _find_sampling_rate(joint: Joint) -> float:
        for key in (joint.key_pos, joint.key_rot, joint.key_scale):
            if key.count > 0:
                return key.sampling_rate
        for child in joint.children:
            rate = _find_sampling_rate(child)
            if rate != 30.0:
                return rate
        return 30.0

    rig["key_sampling_rate"] = _find_sampling_rate(root_joint)

    return data


def build_animations(
    context: bpy.types.Context,
    arm_data: ArmatureData,
    root_joint: Joint,
    anim_control: N3AnimControl,
) -> None:
    """Bake every animation clip in *anim_control* as a separate Blender Action.

    Each AnimData entry produces one Action named after the animation clip.
    Keyframes (location, rotation_quaternion, scale) are inserted at every
    integer source frame from frm_start to frm_end.

    All bones are set to QUATERNION rotation mode before baking.
    """
    rig = arm_data.rig
    context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')

    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'

    if rig.animation_data is None:
        rig.animation_data_create()

    first_action = None
    for i, anim_data in enumerate(anim_control.animations):
        action_name = anim_data.name or f"{rig.name}_{i:03d}"
        action = bpy.data.actions.new(name=action_name)
        rig.animation_data.action = action
        if first_action is None:
            first_action = action

        # Store animation metadata as custom properties on the Action.
        # iAnimIndex preserves the original ordering (the game references by index).
        # szAnimName preserves the original name (Blender may append .001 for dupes).
        action["iAnimIndex"] = i
        action["szAnimName"] = anim_data.name
        action["fFrmStart"] = anim_data.frm_start
        action["fFrmEnd"] = anim_data.frm_end
        action["fFrmPerSec"] = anim_data.frm_per_sec
        action["fFrmPlugTraceStart"] = anim_data.frm_plug_trace_start
        action["fFrmPlugTraceEnd"] = anim_data.frm_plug_trace_end
        action["fFrmSound0"] = anim_data.frm_sound_0
        action["fFrmSound1"] = anim_data.frm_sound_1
        action["fFrmStrike0"] = anim_data.frm_strike_0
        action["fFrmStrike1"] = anim_data.frm_strike_1
        action["fTimeBlend"] = anim_data.time_blend
        action["iBlendFlags"] = anim_data.blend_flags

        frame = 1
        fFrm = anim_data.frm_start
        while fFrm <= anim_data.frm_end:
            _set_pose_frame(rig, root_joint, frame, fFrm, None, None, arm_data)
            fFrm += 1.0
            frame += 1

    if first_action is not None:
        rig.animation_data.action = first_action

    bpy.ops.object.mode_set(mode='OBJECT')


# ---------------------------------------------------------------------------
# Private bone orientation helpers
# ---------------------------------------------------------------------------


def _orient_bones(armature: bpy.types.Armature) -> None:
    """Orient edit bones toward their children and connect chains.

    Must be called while in EDIT mode.  For each bone:
      - If it has one child: point tail at the child's head, connect the child.
      - If it has multiple children: point tail at the average of children's heads.
      - If it's a leaf (no children): extend along the parent→bone direction,
        or keep a small Y offset if there's no parent.

    A minimum bone length is enforced so bones remain selectable.
    """
    MIN_LENGTH = 0.02

    edit_bones = armature.edit_bones

    for bone in edit_bones:
        children = [b for b in edit_bones if b.parent == bone]

        if len(children) == 1:
            # Point directly at the single child and connect it
            child = children[0]
            direction = child.head - bone.head
            if direction.length > MIN_LENGTH:
                bone.tail = child.head
                child.use_connect = True
            else:
                bone.tail = bone.head + mathutils.Vector([0.0, MIN_LENGTH, 0.0])

        elif len(children) > 1:
            # Point toward the average of children's heads (don't connect —
            # multiple children can't all connect to one tail)
            avg = mathutils.Vector((0.0, 0.0, 0.0))
            for child in children:
                avg += child.head
            avg /= len(children)
            direction = avg - bone.head
            if direction.length > MIN_LENGTH:
                bone.tail = bone.head + direction
            else:
                bone.tail = bone.head + mathutils.Vector([0.0, MIN_LENGTH, 0.0])

        else:
            # Leaf bone: extend along parent→bone direction
            if bone.parent is not None:
                direction = bone.head - bone.parent.head
                if direction.length > MIN_LENGTH:
                    bone.tail = bone.head + direction.normalized() * min(direction.length * 0.5, 0.1)
                else:
                    bone.tail = bone.head + mathutils.Vector([0.0, MIN_LENGTH, 0.0])
            else:
                bone.tail = bone.head + mathutils.Vector([0.0, 0.15, 0.0])


# ---------------------------------------------------------------------------
# Private animation helpers
# ---------------------------------------------------------------------------


def _set_pose_frame(
    rig: bpy.types.Object,
    joint: Joint,
    frame: int,
    fFrm: float,
    parent_dx_world: "mathutils.Matrix | None",
    parent_bl_pose: "mathutils.Matrix | None",
    arm_data: ArmatureData,
) -> None:
    """Set pose bone transforms for *joint* at Blender *frame* / source *fFrm*.

    Ported directly from the prototype's set_pose_frame().  The formula:

      desired_pose = dx_to_blender(dx_anim_world) @ correction.inv

      For root bones:
        matrix_basis = bone_rest.inv @ desired_pose

      For child bones (with parent):
        rest_offset  = parent_bone_rest.inv @ bone_rest
        matrix_basis = rest_offset.inv @ parent_bl_pose.inv @ desired_pose

    This compensates for the head/tail orientation mismatch so that the
    armature modifier deforms vertices correctly.
    """
    local_mtx = joint_local_matrix(joint, fFrm)
    world_mtx = (
        parent_dx_world @ local_mtx
        if parent_dx_world is not None
        else local_mtx.copy()
    )

    bone_name = arm_data.joint_id_to_bone_name.get(id(joint))
    if bone_name is None:
        for child in joint.children:
            _set_pose_frame(rig, child, frame, fFrm, world_mtx, parent_bl_pose, arm_data)
        return

    pb = rig.pose.bones.get(bone_name)
    dx_anim_bl = dx_to_blender(world_mtx)
    desired_pose = dx_anim_bl @ arm_data.bone_corrections[bone_name].inverted()

    if pb is not None:
        bone_local = arm_data.bone_rest_matrices[bone_name]

        if pb.parent is not None and parent_bl_pose is not None:
            parent_bone_local = arm_data.bone_rest_matrices[pb.parent.name]
            rest_offset = parent_bone_local.inverted() @ bone_local
            matrix_basis = rest_offset.inverted() @ parent_bl_pose.inverted() @ desired_pose
        else:
            matrix_basis = bone_local.inverted() @ desired_pose

        loc, rot, sca = matrix_basis.decompose()
        pb.location = loc
        pb.rotation_quaternion = rot
        pb.scale = sca

        pb.keyframe_insert(data_path="location", frame=frame)
        pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        pb.keyframe_insert(data_path="scale", frame=frame)

    for child in joint.children:
        _set_pose_frame(rig, child, frame, fFrm, world_mtx, desired_pose, arm_data)
