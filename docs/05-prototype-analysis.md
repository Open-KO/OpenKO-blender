# Prototype Analysis — ko-assets-blender

This document summarizes the existing working prototype located at `C:\Users\srmeier\Projects\ko-ripping\ko-assets-blender`. The prototype is the primary technical reference for the rewrite.

---

## Overview

- **Single file:** `__init__.py` (1658 lines)
- **Blender version:** 4.0.0 minimum
- **Format:** Legacy addon (`bl_info` dict, no manifest)
- **Dependencies:** Pillow (auto-installed via `pip.main()` at load time — to be replaced with bundled wheels)

---

## What Works Well

The prototype contains correct, validated implementations of:
- Binary parsing for all 6 file formats
- DXT1 and DXT5 decompression (custom Python implementation)
- Coordinate system conversion (DirectX → Blender)
- Armature creation with proper bind-pose matrix calculation
- Vertex skinning with vertex groups
- Animation keyframe interpolation (linear for Vector3, slerp for Quaternion)
- UV mapping (with correct V-flip)
- Principled BSDF material setup with image texture nodes
- Collection-based object organization

---

## What Needs Improvement

| Issue | Current Prototype | Target (Rewrite) |
|-------|------------------|-----------------|
| Code organization | Single 1658-line file | Multi-file package structure |
| Addon format | Legacy `bl_info` | `blender_manifest.toml` (Extension) |
| Dependency install | Runtime `pip.main()` | Bundled Pillow wheels |
| Error reporting | `print()` statements | `self.report()` in operators |
| Error handling | Bare `NotImplementedError` raises | User-facing error messages |
| Progress feedback | None | `wm.progress_begin/update/end()` |
| Import options | None | LOD level, animation toggle, scale |
| DXT3 support | Not implemented | Implement |
| Drag-and-drop | Not supported | Implement FileHandler |
| Module reload | Not set up | Add reload guards in `__init__.py` |

---

## Binary Reader Functions (to reuse in `utils/binary_reader.py`)

These are correct and should be carried forward:

```python
def load_int(data, idx):
    return struct.unpack_from('<i', data, idx)[0], idx + 4

def load_short(data, idx):
    return struct.unpack_from('<h', data, idx)[0], idx + 2

def load_float(data, idx):
    return struct.unpack_from('<f', data, idx)[0], idx + 4

def load_string(data, idx):
    length, idx = load_int(data, idx)
    s = data[idx:idx+length].decode('utf-8')
    return s, idx + length

def load_vector(data, idx):    # returns (x, y, z), new_idx
def load_quaternion(data, idx):# returns (x, y, z, w), new_idx
def load_matrix44(data, idx):  # returns 4x4 tuple, new_idx
def load_material(data, idx):  # returns Material namedtuple, new_idx
def load_uv(data, idx):        # returns (u, 1-v), new_idx  ← V-flip
```

Note: The UV V-flip (`1.0 - v`) is critical and must be preserved.

---

## Coordinate Transformation (to reuse in `utils/`)

```python
from mathutils import Matrix

# DirectX Y-up right-hand → Blender Z-up right-hand
map_mtx = (
    Matrix(((1,0,0,0), (0,0,-1,0), (0,1,0,0), (0,0,0,1)))
    @ Matrix(((-1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1)))
)

# For geometry (vertices, mesh data):
obj.data.transform(map_mtx)

# For bone/joint transforms (similarity transform):
bl_mtx = map_mtx @ dx_mtx @ map_mtx.inverted()
```

---

## Bone Transform Algorithm (to reuse in `blender/armature_builder.py`)

The prototype's `calc_joint_matrix(joint, fFrm)` is correct:

```python
def calc_joint_matrix(joint, fFrm):
    """Returns the local 4x4 transform matrix for a joint at a given frame."""
    # 1. Get base values
    pos = joint.m_vPos
    rot = joint.m_qRot
    scale = joint.m_vScale
    orient = joint.m_qOrient  # default identity

    # 2. Apply animation keys if present
    if joint.m_KeyPos.m_nCount > 0:
        pos = joint.m_KeyPos.get_data(fFrm, pos)
    if joint.m_KeyRot.m_nCount > 0:
        rot = joint.m_KeyRot.get_data(fFrm, rot)
    if joint.m_KeyScale.m_nCount > 0:
        scale = joint.m_KeyScale.get_data(fFrm, scale)
    if joint.m_KeyOrient.m_nCount > 0:
        orient = joint.m_KeyOrient.get_data(fFrm, orient)

    # 3. Combine rot and orient
    combined_rot = rot @ orient

    # 4. Build matrix: R * S, then set translation column
    rot_matrix = combined_rot.to_matrix().to_4x4()
    if scale != Vector((1, 1, 1)):
        scale_matrix = Matrix.Diagonal((*scale, 1))
        mtx = rot_matrix @ scale_matrix
    else:
        mtx = rot_matrix

    mtx[0][3] = pos.x
    mtx[1][3] = pos.y
    mtx[2][3] = pos.z
    return mtx
```

Key implementation detail: quaternion multiplication is `rot @ orient` (not the reverse).

---

## Animation Keyframe Interpolation (CN3AnimKey.get_data)

The interpolation logic in the prototype is correct:

```python
def get_data(self, fFrm, in_val):
    if self.m_nCount == 0:
        return in_val
    if self.m_nCount == 1:
        return self.m_pDatas[0]

    # Clamp to valid range
    fFrm = max(0, min(fFrm, self.m_nCount - 1))

    idx = int(fFrm)
    t = fFrm - idx

    if idx >= self.m_nCount - 1:
        return self.m_pDatas[-1]

    d0 = self.m_pDatas[idx]
    d1 = self.m_pDatas[idx + 1]

    if self.m_eType == KEY_VECTOR3:
        return d0.lerp(d1, t)           # linear interpolation
    elif self.m_eType == KEY_QUATERNION:
        return d0.slerp(d1, t)          # spherical linear interpolation
```

---

## File Parser Classes (to refactor into `formats/`)

Each format's parsing is entirely correct in the prototype and can be extracted into separate module files:

| Prototype class | Target module |
|----------------|--------------|
| `CN3PMesh` | `formats/n3pmesh.py` |
| `CN3Shape`, `CN3SPart` | `formats/n3shape.py` (new — not in prototype) |
| `CN3Joint` | `formats/n3joint.py` |
| `CN3AnimKey` | `formats/n3joint.py` (helper) |
| `CN3AnimControl`, `AnimData` | `formats/n3anim.py` |
| `CN3CPart`, `CN3CPartSkins`, `CN3Skin` | `formats/n3cpart.py` |
| `CN3CPlug` | `formats/n3cplug.py` |
| `CN3Chr` | `formats/n3chr.py` |
| `CN3Texture`, `DXTBuffer` | `formats/ntf_texture.py` |
| All ctypes structs | `formats/structs.py` |
| `load_*` functions | `utils/binary_reader.py` |

---

## Blender Builder Functions (to refactor into `blender/`)

| Prototype function | Target module |
|-------------------|--------------|
| `build_mesh_from_skin()` | `blender/mesh_builder.py` |
| `apply_skin_uvs()` | `blender/mesh_builder.py` |
| `build_mesh_from_pmesh()` | `blender/mesh_builder.py` |
| `apply_pmesh_uvs()` | `blender/mesh_builder.py` |
| `build_armature_from_joint()` | `blender/armature_builder.py` |
| `calc_joint_matrix()` | `blender/armature_builder.py` |
| `dx_to_blender()` | `blender/armature_builder.py` |
| `set_pose_frame()` | `blender/animation_builder.py` |
| `create_material()` | `blender/material_builder.py` |
| `apply_material()` | `blender/material_builder.py` |
| `decompress_texture()` | `formats/ntf_texture.py` |

---

## Known Limitations in Prototype (to address in rewrite)

1. **DXT3 not implemented** — raises `NotImplementedError`
2. **Collision mesh not imported** — raises `NotImplementedError`
3. **CN3Chr joint animation parts** — raises `NotImplementedError` when `MAX_CHR_ANI_PART > 0`
4. **CN3CPlug trace steps / VirtualMesh** — raises `NotImplementedError`
5. **Progressive mesh LOD collapses** — stored but not used (raises error if present in some files)
6. **Only first animation imported** — all animations must be imported as separate Blender Actions
7. **No import options** — always imports at LOD 0 with all defaults
8. **No progress reporting** — UI freezes during large character imports

These limitations are acceptable for v1.0 as long as they produce clear error messages to the user rather than silent crashes.