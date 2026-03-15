# Blender Addon Best Practices (2024–2025)

This document summarizes current best practices for Blender addon/extension development, as applicable to this project. Sources include the official Blender Developer Documentation, Extensions Platform guidelines, and community experience.

---

## Extensions vs. Legacy Addons

As of **Blender 4.2 LTS (July 2024)**, the addon system was replaced by the **Extensions Platform**:

| Feature | Legacy Addon | Extension (4.2+) |
|---------|-------------|-----------------|
| Metadata | `bl_info` dict in `__init__.py` | `blender_manifest.toml` |
| Module namespace | `import my_addon` | `import bl_ext.{repo}.my_addon` |
| Dependency install | Runtime pip (fragile) | Bundled `.whl` wheels |
| Distribution | Manual ZIP, Blender Market | extensions.blender.org + manual ZIP |
| In-Blender updates | No | Yes |

**This project targets Blender 4.2+ and uses the Extensions format.**

Legacy addons still install via "Install legacy Add-on" in Preferences — so old plugins are not broken. But new projects should use the Extension format.

---

## `blender_manifest.toml`

The manifest file replaces `bl_info`. Required fields:

```toml
schema_version = "1.0.0"
id = "openko_blender"
version = "1.0.0"
name = "OpenKO Assets"
tagline = "Import KnightOnline game assets"
maintainer = "Your Name <email@example.com>"
type = "add-on"
blender_version_min = "4.2.0"
license = ["SPDX:GPL-2.0-or-later"]
tags = ["Import-Export", "Game Engine"]
website = "https://github.com/Open-KO/openko-blender"
```

**Rules:**
- All listed fields must be present and non-empty — **no empty strings, no empty lists**
- Entirely omit optional fields rather than setting them to empty
- `license` must use an SPDX identifier

---

## Project Structure

Multi-file structure (recommended for any non-trivial addon):

```
openko_blender/
├── blender_manifest.toml
├── __init__.py              # register/unregister entry point
├── operators/
│   ├── __init__.py
│   └── import_ops.py        # ImportHelper-based operator classes
├── formats/
│   ├── __init__.py
│   ├── n3pmesh.py           # CN3PMesh parser
│   ├── n3joint.py           # CN3Joint parser
│   ├── n3anim.py            # CN3AnimControl parser
│   ├── n3cpart.py           # CN3CPart parser
│   ├── n3cplug.py           # CN3CPlug parser
│   ├── n3chr.py             # CN3Chr parser
│   └── ntf_texture.py       # NTF/DXT decompression
├── blender/
│   ├── __init__.py
│   ├── mesh_builder.py      # bpy mesh/object creation helpers
│   ├── armature_builder.py  # bpy armature/bone helpers
│   ├── material_builder.py  # bpy material/node helpers
│   └── animation_builder.py # bpy keyframe/action helpers
├── ui/
│   ├── __init__.py
│   └── panels.py            # Sidebar panels, preferences
├── utils/
│   ├── __init__.py
│   └── binary_reader.py     # Low-level binary reading helpers
└── wheels/                  # Bundled Python wheels (e.g., Pillow)
    └── Pillow-*.whl
```

Every folder needs an `__init__.py` for Python to treat it as a package.

---

## Class Naming Conventions (Strictly Enforced by Blender)

| Type | Pattern | Example |
|------|---------|---------|
| Operator | `UPPER_OT_lower` | `IMPORT_OT_ko_asset` |
| Panel | `UPPER_PT_lower` | `VIEW3D_PT_openko` |
| Menu | `UPPER_MT_lower` | `TOPBAR_MT_openko` |
| Property Group | `UPPER_PG_lower` | `SCENE_PG_openko_props` |
| Preferences | `UPPER_AP_lower` | Not applicable here |

---

## Registering Classes

```python
# Collect all classes in a tuple
classes = (
    IMPORT_OT_ko_asset,
    SCENE_PG_openko_props,
    VIEW3D_PT_openko,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.openko_props = bpy.props.PointerProperty(
        type=SCENE_PG_openko_props
    )
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    del bpy.types.Scene.openko_props
    for cls in reversed(classes):       # reversed order is important
        bpy.utils.unregister_class(cls)
```

**Key rule:** Always unregister in reverse registration order to handle class dependencies correctly.

---

## Import Operator Pattern

```python
from bpy_extras.io_utils import ImportHelper

class IMPORT_OT_ko_asset(bpy.types.Operator, ImportHelper):
    bl_idname = "import_ko.asset"
    bl_label = "Import KO Asset"
    bl_description = "Import a KnightOnline game asset"
    bl_options = {'REGISTER', 'UNDO'}

    # File filter shown in the file browser
    filter_glob: bpy.props.StringProperty(
        default="*.n3chr;*.n3cpart;*.n3cplug;*.n3joint;*.n3anim;*.n3pmesh",
        options={'HIDDEN'},
    )

    # Import options shown in the file browser side panel
    import_animations: bpy.props.BoolProperty(
        name="Import Animations",
        description="Import animation keyframes",
        default=True,
    )
    lod_level: bpy.props.EnumProperty(
        name="LOD Level",
        description="Which level of detail to import",
        items=[("0", "LOD 0 (Highest)", ""), ("1", "LOD 1", ""),
               ("2", "LOD 2", ""), ("3", "LOD 3 (Lowest)", "")],
        default="0",
    )

    def execute(self, context):
        from pathlib import Path
        ext = Path(self.filepath).suffix.lower()
        try:
            return self._dispatch(context, ext)
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}

    def _dispatch(self, context, ext):
        # delegate to per-format importers
        ...
```

---

## Error Handling and User Feedback

### Operator Reports (primary mechanism)

```python
# In execute():
self.report({'ERROR'}, "File not found: check that all referenced files are in the same folder.")
return {'CANCELLED'}

self.report({'WARNING'}, "Collision mesh skipped (not yet supported).")

self.report({'INFO'}, "Import complete.")
return {'FINISHED'}
```

**Report types:**
- `'ERROR'` — shown as red popup, blocks further operation
- `'WARNING'` — shown in info area
- `'INFO'` — shown in status bar

### Inline Panel Warnings

For non-blocking warnings in operator draw():
```python
def draw(self, context):
    layout = self.layout
    if not some_condition:
        row = layout.row()
        row.alert = True  # makes the row red
        row.label(text="Missing dependency!", icon='ERROR')
```

### Avoid

- `print()` to console — users never see this
- `raise Exception()` without catching — crashes silently in Blender
- Modal dialogs for non-destructive warnings

---

## Dependency Management (Pillow)

**The correct approach for Blender 4.2 Extensions:**

1. Download the correct `Pillow` wheel for the target platforms:
   - `Pillow-10.x.x-cp311-cp311-win_amd64.whl`
   - `Pillow-10.x.x-cp311-cp311-manylinux1_x86_64.whl`
   - `Pillow-10.x.x-cp311-cp311-macosx_arm64.whl`

2. Place wheels in `./wheels/` inside the addon directory.

3. Declare them in `blender_manifest.toml`:
   ```toml
   wheels = [
     "./wheels/Pillow-10.4.0-cp311-cp311-win_amd64.whl",
     "./wheels/Pillow-10.4.0-cp311-cp311-manylinux1_x86_64.whl",
     "./wheels/Pillow-10.4.0-cp311-cp311-macosx_arm64.whl",
   ]
   ```

4. Blender installs wheels automatically when the user installs the extension from a `.zip` or from the Extensions Platform.

**Do not use runtime pip installs.** The official Extensions Platform policy explicitly forbids `pip install` at addon load time.

As a fallback for development (non-zipped install), gracefully detect if Pillow is unavailable and report an error to the user rather than crashing.

---

## Progress Reporting

### Status bar (simple operations)
```python
wm = context.window_manager
wm.progress_begin(0, total)
for i, item in enumerate(items):
    wm.progress_update(i)
    process(item)
wm.progress_end()
```

### Header text (during modal operators)
```python
context.workspace.status_text_set(f"Importing... {i}/{total}")
# Remember to clear it when done:
context.workspace.status_text_set(None)
```

### Modal operator (for truly long non-blocking operations)

Use a modal operator with a timer when an operation would otherwise freeze Blender's UI for >1 second. See `bpy.types.Operator` modal pattern in official docs.

---

## Python Code Style

Per Blender's official Python Style Guide:
- Max line width: **120 characters**
- Prefer `str.format()` with type specifiers
- **Delay heavy imports** to function bodies (faster Blender startup)
- Prefix unused variables with `_`
- Use descriptive names: `mesh` not `me`, `armature` not `arm`

---

## Module Reloading During Development

Add this to `__init__.py` to enable in-place reload without restarting Blender:

```python
if "bpy" in locals():
    import importlib
    importlib.reload(formats.n3pmesh)
    importlib.reload(formats.n3chr)
    importlib.reload(blender.mesh_builder)
    # ... etc
```

Use the **Blender Development** VS Code extension (by Jacques Lucke) for auto-reload on save.

---

## Development Setup

```bash
# Option 1: Symlink your repo into Blender's addon directory
# Windows (run as admin):
mklink /D "%APPDATA%\Blender Foundation\Blender\4.2\extensions\user_default\openko_blender" "C:\path\to\OpenKO-blender\openko_blender"

# Option 2: Install as ZIP, re-zip and reinstall after changes
# Use blender-extension-builder to automate this
pip install blender-extension-builder
```

For IDE type hints without running Blender:
```bash
pip install fake-bpy-module-4.2
```

---

## Useful References

- [Blender Extensions Platform Docs](https://docs.blender.org/manual/en/latest/advanced/extensions/)
- [How to Create Extensions](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html)
- [Blender Python Style Guide](https://developer.blender.org/docs/handbook/guidelines/python/)
- [Blender HIG — Layouts](https://developer.blender.org/docs/features/interface/human_interface_guidelines/layouts/)
- [Blender HIG — Dialogs](https://developer.blender.org/docs/features/interface/human_interface_guidelines/dialogs/)
- [Compatibility Changes by Release](https://developer.blender.org/docs/release_notes/compatibility/)
- [Version Number Guidelines](https://docs.blender.org/manual/en/latest/advanced/extensions/version_number_guidelines.html)
- [fake-bpy-module on PyPI](https://pypi.org/project/fake-bpy-module-4.2/)
- [blender-extension-builder on PyPI](https://pypi.org/project/blender-extension-builder/)