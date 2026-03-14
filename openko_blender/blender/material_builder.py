"""
Build Blender materials and load KO DXT textures.

Textures are decompressed using the pure-Python DXT implementation from
openko_blender.formats.dxt_texture — no Pillow dependency required.

The raw RGBA bytes from decompress_to_rgba() are in top-to-bottom row order.
Blender's image.pixels expects bottom-to-top, so rows are reversed before
assigning to image.pixels.

Material setup: Principled BSDF ← BaseColor ← TexImage ← .dxt file.
When a texture cannot be found or decompressed, a material is still created
(without a texture node) so the object is usable.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import bpy

if TYPE_CHECKING:
    from ..formats.dxt_texture import DxtTexture


# ---------------------------------------------------------------------------
# Material creation
# ---------------------------------------------------------------------------


def create_material(
    name: str,
    image: "bpy.types.Image | None" = None,
) -> bpy.types.Material:
    """Create a Principled BSDF material, optionally wired to *image*.

    Node layout:
      [TexImage (-400,0)] --Color--> [Principled BSDF (0,0)] --BSDF--> [Output (400,0)]
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    shader = nodes.new(type="ShaderNodeBsdfPrincipled")
    shader.location = (0, 0)

    mat_out = nodes.new(type="ShaderNodeOutputMaterial")
    mat_out.location = (400, 0)
    mat.node_tree.links.new(shader.outputs["BSDF"], mat_out.inputs["Surface"])

    if image is not None:
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.image = image
        tex_node.location = (-400, 0)
        mat.node_tree.links.new(tex_node.outputs["Color"], shader.inputs["Base Color"])

    return mat


def apply_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    """Assign *mat* to *obj*'s first material slot."""
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


# ---------------------------------------------------------------------------
# Texture loading
# ---------------------------------------------------------------------------


def load_dxt_as_image(tex: "DxtTexture", name: str) -> "bpy.types.Image | None":
    """Decompress *tex* and return a Blender Image, or None on failure.

    Uses the pure-Python DXT decompressor from openko_blender.formats.dxt_texture.
    Rows are flipped vertically so the image appears correctly in Blender
    (DXT = top-to-bottom; Blender image.pixels = bottom-to-top).
    """
    from ..formats.dxt_texture import decompress_to_rgba

    try:
        rgba_bytes = decompress_to_rgba(tex, mip_level=0)
    except Exception:
        return None

    w, h = tex.width, tex.height
    image = bpy.data.images.new(name, width=w, height=h, alpha=True)

    # Convert bytes → floats [0,1], then flip rows for Blender's bottom-to-top order
    floats = [b / 255.0 for b in rgba_bytes]
    row_stride = w * 4
    rows = [floats[i : i + row_stride] for i in range(0, len(floats), row_stride)]
    rows.reverse()
    image.pixels[:] = [v for row in rows for v in row]
    image.update()
    return image


def resolve_and_load_texture(
    tex_filename: str,
    base_path: Path,
    name: str,
) -> "bpy.types.Image | None":
    """Resolve *tex_filename* relative to *base_path*, load and return a Blender Image.

    Uses the same three-candidate resolution strategy as resolve_asset_path():
      1. Same directory as base_path.
      2. Relative to base_path's directory.
      3. Relative to base_path's parent (Client root reference).

    Returns None silently if the file cannot be found or decompressed.
    """
    from ..formats._base import resolve_asset_path
    from ..formats import dxt_texture as _dxt

    if not tex_filename:
        return None

    tex_path = resolve_asset_path(base_path, tex_filename)
    if tex_path is None:
        return None

    try:
        tex = _dxt.load(tex_path)
        return load_dxt_as_image(tex, name)
    except Exception:
        return None
