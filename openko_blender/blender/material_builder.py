"""
Build Blender materials and load KO DXT textures.

Textures are decompressed using the pure-Python DXT implementation from
openko_blender.formats.dxt_texture — no Pillow dependency required.

The raw RGBA bytes from decompress_to_rgba() are in top-to-bottom row order.
Blender's image.pixels expects bottom-to-top, so rows are reversed before
assigning to image.pixels.

Material setup reproduces the KnightOnline D3D9 fixed-function pipeline:
  - Principled BSDF with diffuse, specular, emissive from KO __Material
  - Texture blending: D3DTOP_MODULATE → texture × diffuse color
  - Render flags: double-sided, alpha blending, no-light (emission-only)
  - Specular power: D3D power → Blender roughness via sqrt(2 / (power + 2))

When a texture cannot be found or decompressed, a material is still created
(without a texture node) so the object is usable.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

import bpy

if TYPE_CHECKING:
    from ..formats.dxt_texture import DxtTexture
    from ..formats.structs import Material as KOMaterial


# ---------------------------------------------------------------------------
# Material creation
# ---------------------------------------------------------------------------


def create_material(
    name: str,
    image: "bpy.types.Image | None" = None,
    ko_material: "KOMaterial | None" = None,
) -> bpy.types.Material:
    """Create a Principled BSDF material matching KO's D3D9 rendering.

    When *ko_material* is provided, diffuse/specular/emissive colours and render
    flags are applied.  The KO engine uses D3DTOP_MODULATE (texture × diffuse) as
    the default texture blend mode — when diffuse is not pure white, a Multiply
    node is inserted between the texture and the shader.

    Node layout (with texture + non-white diffuse):
      [TexImage] --Color--> [Multiply] --Color--> [Principled BSDF] --> [Output]
                  diffuse ->     ↑

    Node layout (texture only, white diffuse):
      [TexImage] --Color--> [Principled BSDF] --> [Output]
    """
    from ..formats.structs import RenderFlag

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    shader = nodes.new(type="ShaderNodeBsdfPrincipled")
    shader.location = (0, 0)

    mat_out = nodes.new(type="ShaderNodeOutputMaterial")
    mat_out.location = (400, 0)
    links.new(shader.outputs["BSDF"], mat_out.inputs["Surface"])

    # ── Apply KO material properties ─────────────────────────────────────
    diffuse_rgb = (1.0, 1.0, 1.0)
    if ko_material is not None:
        d = ko_material.diffuse
        diffuse_rgb = (d.r, d.g, d.b)

        # Specular: convert D3D power to Blender roughness
        # D3D: higher power = sharper highlight; Blender: lower roughness = sharper
        power = max(ko_material.power, 0.0)
        roughness = math.sqrt(2.0 / (power + 2.0))
        shader.inputs["Roughness"].default_value = roughness

        # Specular intensity (average of specular RGB)
        s = ko_material.specular
        spec_intensity = (s.r + s.g + s.b) / 3.0
        shader.inputs["Specular IOR Level"].default_value = spec_intensity

        # Emissive
        e = ko_material.emissive
        if e.r > 0.0 or e.g > 0.0 or e.b > 0.0:
            shader.inputs["Emission Color"].default_value = (e.r, e.g, e.b, 1.0)
            shader.inputs["Emission Strength"].default_value = 1.0

        # RF_NOTUSELIGHT: object is fully self-lit (treat as emission-only)
        flags = ko_material.render_flags
        if flags & RenderFlag.NO_LIGHT:
            shader.inputs["Emission Strength"].default_value = 1.0
            # Set emission to diffuse if no explicit emissive was set
            if e.r == 0.0 and e.g == 0.0 and e.b == 0.0:
                shader.inputs["Emission Color"].default_value = (*diffuse_rgb, 1.0)

        # RF_DOUBLESIDED: disable backface culling
        if flags & RenderFlag.DOUBLE_SIDED:
            mat.use_backface_culling = False
        else:
            mat.use_backface_culling = True

        # RF_ALPHABLENDING / RF_DIFFUSEALPHA: enable transparency.
        # Blender 4.2+ EEVEE Next removed blend_method; transparency is
        # automatic when the Principled BSDF Alpha input is connected.
        # For older Blender versions, set blend_method if available.
        if flags & (RenderFlag.ALPHA_BLENDING | RenderFlag.DIFFUSE_ALPHA):
            if hasattr(mat, 'blend_method'):
                mat.blend_method = 'BLEND' if flags & RenderFlag.ALPHA_BLENDING else 'CLIP'
                mat.shadow_method = 'CLIP'

    # Set base diffuse colour (used as fallback when no texture)
    shader.inputs["Base Color"].default_value = (*diffuse_rgb, 1.0)

    # ── Texture node ─────────────────────────────────────────────────────
    if image is not None:
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.image = image
        tex_node.location = (-400, 0)

        # KO default: D3DTOP_MODULATE = texture × diffuse
        # If diffuse is white, the multiply is a no-op — wire directly
        is_white = all(c > 0.99 for c in diffuse_rgb)
        if is_white:
            links.new(tex_node.outputs["Color"], shader.inputs["Base Color"])
        else:
            mix = nodes.new("ShaderNodeMix")
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.location = (-150, 0)
            mix.inputs["Factor"].default_value = 1.0
            mix.inputs[6].default_value = (*diffuse_rgb, 1.0)  # B input (color)
            links.new(tex_node.outputs["Color"], mix.inputs[7])  # A input (color)
            links.new(mix.outputs[2], shader.inputs["Base Color"])  # Result (color)

        # Wire texture alpha for transparency
        if ko_material is not None:
            flags = ko_material.render_flags
            if flags & (RenderFlag.ALPHA_BLENDING | RenderFlag.DIFFUSE_ALPHA):
                links.new(tex_node.outputs["Alpha"], shader.inputs["Alpha"])

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