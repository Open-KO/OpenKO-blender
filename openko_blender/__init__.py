"""
OpenKO Blender — Import KnightOnline game assets into Blender 4.2+.

Supported formats:
  .n3chr    — Full character (skeleton + skinned parts + plugs + animations)
  .n3shape  — Static shape / prop
  .n3cpart  — Character part (skinned mesh)
  .n3cplug  — Equipment / weapon plug mesh
  .n3joint  — Skeleton hierarchy only
  .n3anim   — Animation metadata (produces a text summary)
  .n3pmesh  — Progressive mesh (static geometry)

Entry point: File ▸ Import ▸ KnightOnline Assets
"""

from __future__ import annotations

# Maps object name → last-seen action name.  Used by the action-sync handler
# to avoid updating the scene frame range on every single depsgraph tick.
_last_action: dict[str, str | None] = {}


def _sync_frame_range_to_action(scene, depsgraph) -> None:  # noqa: ARG001
    """depsgraph_update_post handler — syncs scene frame range when the active
    action on any armature changes."""
    import bpy

    for obj in scene.objects:
        if obj.type != 'ARMATURE':
            continue
        anim = obj.animation_data
        action = anim.action if anim else None
        action_name = action.name if action else None

        if _last_action.get(obj.name) == action_name:
            continue  # no change for this armature

        _last_action[obj.name] = action_name

        if action is None:
            continue

        # Stop playback before changing the frame range so the new end frame
        # takes effect immediately rather than being clamped to the old range.
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)

        start, end = action.frame_range
        scene.frame_start = int(start)
        scene.frame_end = int(end)
        scene.frame_current = scene.frame_start


def register() -> None:
    # Imports are deferred so that the openko_blender package can be imported
    # in a plain Python environment (e.g. pytest) without bpy being present.
    import bpy
    from .operators.import_ops import IMPORT_OT_ko_asset, menu_func_import

    bpy.utils.register_class(IMPORT_OT_ko_asset)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.app.handlers.depsgraph_update_post.append(_sync_frame_range_to_action)


def unregister() -> None:
    import bpy
    from .operators.import_ops import IMPORT_OT_ko_asset, menu_func_import

    if _sync_frame_range_to_action in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_sync_frame_range_to_action)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_OT_ko_asset)
