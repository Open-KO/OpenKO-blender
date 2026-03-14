"""
Import operators for KnightOnline game assets.

Exposes a single IMPORT_OT_ko_asset operator with a filter_glob covering all
seven supported formats.  The operator dispatches to a per-format function
based on the selected file's extension.

Import options (shown in the file-browser sidebar):
  lod_level      — which LOD to import (0 = highest, fallback to first available)
  scale          — global scale factor applied to every imported object
  skip_textures  — skip DXT texture loading (geometry only)
  skip_animations— skip animation baking for .n3chr files
"""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------


class IMPORT_OT_ko_asset(Operator, ImportHelper):
    """Import KnightOnline game assets"""

    bl_idname = "import_ko.asset"
    bl_label = "KnightOnline Asset"
    bl_options = {'UNDO'}

    filename_ext = ""

    filter_glob: StringProperty(
        default="*.n3chr;*.n3shape;*.n3cpart;*.n3cplug;*.n3joint;*.n3anim;*.n3pmesh",
        options={'HIDDEN'},
        maxlen=255,
    )

    lod_level: IntProperty(
        name="LOD Level",
        description="Level of detail to import (0 = highest quality)",
        default=0,
        min=0,
        max=3,
    )
    scale: FloatProperty(
        name="Scale",
        description="Global scale factor applied to the imported asset",
        default=1.0,
        min=0.001,
        soft_max=100.0,
    )
    skip_textures: BoolProperty(
        name="Skip Textures",
        description="Import geometry only, without loading DXT textures",
        default=False,
    )
    skip_animations: BoolProperty(
        name="Skip Animations",
        description="Import skeleton and mesh only, without baking animation keyframes",
        default=False,
    )

    def execute(self, context):
        filepath = Path(self.filepath)
        ext = filepath.suffix.lower()

        kwargs = dict(
            context=context,
            filepath=filepath,
            lod=self.lod_level,
            scale=self.scale,
            skip_textures=self.skip_textures,
            skip_animations=self.skip_animations,
        )

        dispatch = {
            '.n3chr':   _import_n3chr,
            '.n3shape': _import_n3shape,
            '.n3cpart': _import_n3cpart,
            '.n3cplug': _import_n3cplug,
            '.n3joint': _import_n3joint,
            '.n3anim':  _import_n3anim,
            '.n3pmesh': _import_n3pmesh,
        }

        fn = dispatch.get(ext)
        if fn is None:
            self.report({'ERROR'}, f"Unsupported file type: {ext}")
            return {'CANCELLED'}

        try:
            return fn(**kwargs)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "lod_level")
        layout.prop(self, "scale")
        layout.prop(self, "skip_textures")
        layout.prop(self, "skip_animations")


# ---------------------------------------------------------------------------
# Menu entry
# ---------------------------------------------------------------------------


def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_OT_ko_asset.bl_idname,
        text="KnightOnline Assets (.n3chr, .n3shape, ...)",
    )


# ---------------------------------------------------------------------------
# Per-format import functions
# ---------------------------------------------------------------------------


def _import_n3chr(context, filepath, lod, scale, skip_textures, skip_animations):
    """Import a full character: armature + skinned parts + plugs + all animations."""
    from ..formats import n3chr as _n3chr
    from ..blender import armature_builder, material_builder, mesh_builder

    chr_data = _n3chr.load(filepath)
    chr_name = chr_data.name or filepath.stem

    # Root collection for this character
    chr_col = bpy.data.collections.new(chr_name)
    context.scene.collection.children.link(chr_col)

    # ── Armature ──────────────────────────────────────────────────────────────
    arm_data = None
    if chr_data.joint is not None:
        arm_data = armature_builder.build_armature(
            context, chr_data.joint, chr_name, chr_col
        )
        if scale != 1.0:
            arm_data.rig.scale = (scale, scale, scale)

    # ── Skinned parts ─────────────────────────────────────────────────────────
    parts_col = bpy.data.collections.new(f"{chr_name} Parts")
    chr_col.children.link(parts_col)

    for part in chr_data.parts:
        skin = _pick_lod(part.skins, lod)
        if skin is None:
            continue

        obj_name = skin.name or part.name or filepath.stem
        obj = mesh_builder.build_skinned_mesh(skin, obj_name)
        if scale != 1.0:
            obj.scale = (scale, scale, scale)

        if arm_data is not None:
            mesh_builder.apply_skin_weights(obj, skin, arm_data.all_joints_by_idx)
            mesh_builder.add_armature_modifier(obj, arm_data.rig)

        parts_col.objects.link(obj)

        if not skip_textures and part.tex_filename:
            image = material_builder.resolve_and_load_texture(
                part.tex_filename, filepath, obj_name
            )
            if image is None and part.tex_filename:
                # Texture not found — report a warning but continue
                pass
            mat = material_builder.create_material(obj_name, image)
            material_builder.apply_material(obj, mat)

    # ── Plugs (static weapon / equipment meshes) ──────────────────────────────
    plugs_col = bpy.data.collections.new(f"{chr_name} Plugs")
    chr_col.children.link(plugs_col)

    for plug in chr_data.plugs:
        if plug.pmesh is None:
            continue

        obj_name = plug.name or filepath.stem
        obj = mesh_builder.build_static_mesh(plug.pmesh, obj_name)
        if scale != 1.0:
            obj.scale = (scale, scale, scale)

        plugs_col.objects.link(obj)

        if not skip_textures and plug.tex_filename:
            image = material_builder.resolve_and_load_texture(
                plug.tex_filename, filepath, obj_name
            )
            mat = material_builder.create_material(obj_name, image)
            material_builder.apply_material(obj, mat)

    # ── Animations ────────────────────────────────────────────────────────────
    if (
        not skip_animations
        and arm_data is not None
        and chr_data.anim_control is not None
        and chr_data.anim_control.animations
    ):
        armature_builder.build_animations(
            context, arm_data, chr_data.joint, chr_data.anim_control
        )

        # Expand the scene frame range to fit the longest imported action.
        # We only ever grow the range so multiple imports accumulate correctly.
        # Skip zero-length stub slots (frm_end == frm_start) that have no data.
        real_anims = [
            a for a in chr_data.anim_control.animations
            if a.frm_end > a.frm_start
        ]
        if not real_anims:
            return {'FINISHED'}
        max_frames = max(int(a.frm_end - a.frm_start) + 1 for a in real_anims)
        context.scene.frame_start = 1
        if max_frames > context.scene.frame_end:
            context.scene.frame_end = max_frames

    return {'FINISHED'}


def _import_n3shape(context, filepath, lod, scale, skip_textures, skip_animations):
    """Import a static shape / prop: one or more N3PMesh parts."""
    from ..formats import n3shape as _n3shape
    from ..blender import material_builder, mesh_builder

    shape = _n3shape.load(filepath)
    shape_name = shape.name or filepath.stem

    shape_col = bpy.data.collections.new(shape_name)
    context.scene.collection.children.link(shape_col)

    for part in shape.parts:
        if part.pmesh is None:
            continue

        obj_name = Path(part.mesh_filename).stem if part.mesh_filename else shape_name
        obj = mesh_builder.build_static_mesh(part.pmesh, obj_name)
        if scale != 1.0:
            obj.scale = (scale, scale, scale)

        shape_col.objects.link(obj)

        if not skip_textures and part.tex_filenames:
            image = material_builder.resolve_and_load_texture(
                part.tex_filenames[0], filepath, obj_name
            )
            mat = material_builder.create_material(obj_name, image)
            material_builder.apply_material(obj, mat)

    return {'FINISHED'}


def _import_n3cpart(context, filepath, lod, scale, skip_textures, skip_animations):
    """Import a standalone character part (skinned mesh, no skeleton)."""
    from ..formats import n3cpart as _n3cpart
    from ..blender import material_builder, mesh_builder

    part = _n3cpart.load(filepath)
    skin = _pick_lod(part.skins, lod)
    if skin is None:
        return {'CANCELLED'}

    name = skin.name or part.name or filepath.stem
    obj = mesh_builder.build_skinned_mesh(skin, name)
    if scale != 1.0:
        obj.scale = (scale, scale, scale)

    context.scene.collection.objects.link(obj)

    if not skip_textures and part.tex_filename:
        image = material_builder.resolve_and_load_texture(
            part.tex_filename, filepath, name
        )
        mat = material_builder.create_material(name, image)
        material_builder.apply_material(obj, mat)

    return {'FINISHED'}


def _import_n3cplug(context, filepath, lod, scale, skip_textures, skip_animations):
    """Import a standalone plug/weapon mesh."""
    from ..formats import n3cplug as _n3cplug
    from ..blender import material_builder, mesh_builder

    plug = _n3cplug.load(filepath)
    if plug.pmesh is None:
        return {'CANCELLED'}

    name = plug.name or filepath.stem
    obj = mesh_builder.build_static_mesh(plug.pmesh, name)
    if scale != 1.0:
        obj.scale = (scale, scale, scale)

    context.scene.collection.objects.link(obj)

    if not skip_textures and plug.tex_filename:
        image = material_builder.resolve_and_load_texture(
            plug.tex_filename, filepath, name
        )
        mat = material_builder.create_material(name, image)
        material_builder.apply_material(obj, mat)

    return {'FINISHED'}


def _import_n3joint(context, filepath, lod, scale, skip_textures, skip_animations):
    """Import a standalone skeleton hierarchy."""
    from ..formats import n3joint as _n3joint
    from ..blender import armature_builder

    root_joint = _n3joint.load(filepath)
    name = root_joint.name or filepath.stem
    arm_data = armature_builder.build_armature(context, root_joint, name)
    if scale != 1.0:
        arm_data.rig.scale = (scale, scale, scale)

    return {'FINISHED'}


def _import_n3anim(context, filepath, lod, scale, skip_textures, skip_animations):
    """Import animation metadata as a text block (no geometry to display)."""
    from ..formats import n3anim as _n3anim

    anim_ctrl = _n3anim.load(filepath)
    name = filepath.stem
    text = bpy.data.texts.new(f"{name}_animations")
    text.write(f"Animation file: {filepath.name}\n")
    text.write(f"Total animations: {len(anim_ctrl.animations)}\n\n")

    for i, anim in enumerate(anim_ctrl.animations):
        frames = anim.frm_end - anim.frm_start
        text.write(f"[{i}] {anim.name}\n")
        text.write(f"    Frames:     {anim.frm_start} – {anim.frm_end}  ({frames:.0f} frames)\n")
        text.write(f"    FPS:        {anim.frm_per_sec}\n")
        text.write(f"    Blend time: {anim.time_blend}\n")
        if anim.frm_strike_0 or anim.frm_strike_1:
            text.write(f"    Strike:     {anim.frm_strike_0}, {anim.frm_strike_1}\n")
        if anim.frm_sound_0 or anim.frm_sound_1:
            text.write(f"    Sound:      {anim.frm_sound_0}, {anim.frm_sound_1}\n")
        text.write("\n")

    return {'FINISHED'}


def _import_n3pmesh(context, filepath, lod, scale, skip_textures, skip_animations):
    """Import a standalone progressive mesh (no texture)."""
    from ..formats import n3pmesh as _n3pmesh
    from ..blender import mesh_builder

    pmesh = _n3pmesh.load(filepath)
    name = pmesh.name or filepath.stem
    obj = mesh_builder.build_static_mesh(pmesh, name)
    if scale != 1.0:
        obj.scale = (scale, scale, scale)

    context.scene.collection.objects.link(obj)
    return {'FINISHED'}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _pick_lod(skins, lod: int):
    """Return the requested LOD level, falling back to the first available."""
    if not skins:
        return None
    if lod < len(skins) and skins[lod] is not None:
        return skins[lod]
    return next((s for s in skins if s is not None), None)
