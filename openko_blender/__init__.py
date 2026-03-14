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


def register() -> None:
    # Imports are deferred so that the openko_blender package can be imported
    # in a plain Python environment (e.g. pytest) without bpy being present.
    import bpy
    from .operators.import_ops import IMPORT_OT_ko_asset, menu_func_import

    bpy.utils.register_class(IMPORT_OT_ko_asset)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister() -> None:
    import bpy
    from .operators.import_ops import IMPORT_OT_ko_asset, menu_func_import

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_OT_ko_asset)
