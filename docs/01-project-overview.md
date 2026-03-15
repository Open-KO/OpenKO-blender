# OpenKO Blender Plugin — Project Overview

## What This Is

A professional Blender addon for importing KnightOnline game assets into Blender. It targets the KnightOnline open-source community and serves modders, artists, and developers who want to work with KO assets in a modern 3D environment.

This project is a Blender extension built with emphasis on:
- Professional code structure and maintainability
- Great user experience (helpful error messages, import options, progress feedback)
- Correct versioning and easy distribution
- Full compliance with Blender's current addon best practices (Blender 4.2+ Extensions)

---

## Reference Projects

| Source | Purpose |
|--------|---------|
| [KnightOnline C++ source](https://github.com/Open-KO/KnightOnline) | Authoritative source for binary format structs and field meanings |

---

## Supported Blender Versions

- **Target minimum**: Blender 4.2 LTS (July 2024)
- **Format**: Blender Extension (uses `blender_manifest.toml`, not legacy `bl_info`)
- Blender 4.2 is the correct baseline — it is the first Long-Term Support release in the new Extensions era

---

## Supported File Formats (Import)

| Extension | C++ Class | Description |
|-----------|-----------|-------------|
| `.n3chr` | `CN3Chr` | Complete character — skeleton, body parts, equipment, animations |
| `.n3cpart` | `CN3CPart` | Single character body part with mesh, UVs, bones, and texture |
| `.n3cplug` | `CN3CPlug` | Equipment / weapon attachment with progressive mesh |
| `.n3joint` | `CN3Joint` | Skeleton hierarchy only (bone tree, no mesh) |
| `.n3anim` | `CN3AnimControl` | Animation metadata (frame ranges, FPS, strike/sound markers) |
| `.n3pmesh` | `CN3PMesh` | Static progressive mesh (terrain details, props) |
| `.n3shape` | `CN3Shape` | Static shape/prop with multiple mesh parts and textures |

Texture loading (`.ntf` / DXT-compressed) is handled internally — these are referenced by the above files, not imported directly by the user.

---

## High-Level Feature Goals

### Must Have (v1.0)
- Import all seven file types listed above (including `.n3shape`)
- Correct mesh geometry with normals and UVs
- DXT1/DXT3/DXT5 texture decompression and material assignment
- Graceful fallback when a referenced texture file is missing — import the mesh with a warning, do not abort
- Skeleton (armature) reconstruction with correct bind pose
- Vertex skinning (bone weights per vertex)
- **All animations** imported as separate Blender Actions (not just the first)
- Coordinate system conversion (DirectX right-hand → Blender left-hand)
- LOD level selector (0–3) as an import option
- Scale factor as an import option
- Toggle to skip texture import
- Toggle to skip animation import
- Helpful error messages displayed in Blender's UI (not just console)
- Progress reporting in status bar during long imports

### Nice to Have (v1.x)
- Import all LOD levels as separate mesh objects (optionally)
- Drag-and-drop file support (Blender 4.1+ File Handlers)
- Export support for at least `.n3pmesh`
- Scene/level file support (`.n3d`)

---

## Distribution Plan

1. **GitHub Releases** — ZIP packages attached to tagged releases (e.g., `v1.0.0`)
2. **Blender Extensions Platform** — Submit to [extensions.blender.org](https://extensions.blender.org) for one-click install/update from within Blender
3. License: GPL-2.0-or-later (required by Extensions platform and consistent with Blender ecosystem)

See [04-versioning-and-distribution.md](04-versioning-and-distribution.md) for full details.
