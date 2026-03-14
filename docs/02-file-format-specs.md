# KnightOnline File Format Specifications

All formats are **little-endian binary**. All files share a common versioned base header via `CN3BaseFileAccess`.

---

## Common Base Header

Every KO asset file begins with a format version (read by `CN3BaseFileAccess::Load`):

```
uint16_t iFileFormatVersion    // 1098, 1264, or 1298
```

**Known versions:**
| Value | Constant | Notes |
|-------|----------|-------|
| 1098 | `N3FORMAT_VER_1098` | Oldest supported |
| 1264 | `N3FORMAT_VER_1264` | Intermediate |
| 1298 | `N3FORMAT_VER_1298` | Current default |

---

## Shared Primitive Types

All primitive types are little-endian.

| Type | Size | Notes |
|------|------|-------|
| `int8` / `bool` | 1 byte | |
| `int16` / `uint16` | 2 bytes | |
| `int32` / `uint32` | 4 bytes | |
| `float32` | 4 bytes | IEEE 754 |
| `string` | 4 + N bytes | int32 length prefix, then UTF-8 chars |

### Vector3
```
float x, y, z      // 12 bytes
```

### Quaternion
```
float x, y, z, w   // 16 bytes
```

### Matrix44
```
float m[4][4]       // 64 bytes (row-major)
```

### UVVector
```
float u, v          // 8 bytes — V is flipped (1.0 - v) during import
```

### Material (`__Material`)
```
D3DCOLORVALUE diffuse    // 16 bytes (r, g, b, a as float)
D3DCOLORVALUE ambient    // 16 bytes
D3DCOLORVALUE specular   // 16 bytes
D3DCOLORVALUE emissive   // 16 bytes
float         power      //  4 bytes (specular shininess)
uint32        dwColorOp  //  4 bytes
uint32        dwColorArg1//  4 bytes
uint32        dwColorArg2//  4 bytes
uint32        nRenderFlags// 4 bytes (see render flags below)
uint32        dwSrcBlend //  4 bytes (D3DBLEND)
uint32        dwDestBlend//  4 bytes (D3DBLEND)
               TOTAL: 88 bytes
```

**Render Flags (`nRenderFlags`):**
| Bit | Name | Meaning |
|-----|------|---------|
| 0x001 | RF_ALPHABLENDING | Use alpha blending |
| 0x002 | RF_NOTUSEFOG | Disable fog |
| 0x004 | RF_DOUBLESIDED | Two-sided (no backface cull) |
| 0x008 | RF_BOARD_Y | Y-axis billboard |
| 0x010 | RF_POINTSAMPLING | Point texture sampling |
| 0x020 | RF_WINDY | Wind swaying |
| 0x040 | RF_NOTUSELIGHT | Disable lighting |
| 0x080 | RF_DIFFUSEALPHA | Use diffuse alpha channel |
| 0x100 | RF_NOTZWRITE | Disable depth write |
| 0x200 | RF_UV_CLAMP | Clamp UV coordinates |
| 0x400 | RF_NOTZBUFFER | Disable depth test |

---

## Vertex Structures

### `Vertex` (used in skins)
```
Vector3 position    // 12 bytes
Vector3 normal      // 12 bytes
            TOTAL: 24 bytes
```

### `VertexWithUV` (used in progressive meshes)
```
Vector3 position    // 12 bytes
Vector3 normal      // 12 bytes
float   u, v        // 8 bytes
            TOTAL: 32 bytes
```

### `VertexSkinned` (per-vertex bone influence data)
```
Vector3 vOrigin     // 12 bytes — base position
int32   nAffect     //  4 bytes — number of affecting bones (0–4+)
// followed by nAffect entries:
int32[] pnJoints    //  4 bytes each — bone index
float[] pfWeights   //  4 bytes each — blend weight (0.0–1.0)
```

---

## `.n3pmesh` — Progressive Mesh

**C++ class:** `CN3PMesh`

```
uint16  iFileFormatVersion           // base header
int32   m_iNumCollapses              // edge collapse operations
int32   m_iTotalIndexChanges         // total remapping entries
int32   m_iMaxNumVertices            // vertex count at highest LOD
int32   m_iMaxNumIndices             // index count at highest LOD
int32   m_iMinNumVertices            // vertex count at lowest LOD
int32   m_iMinNumIndices             // index count at lowest LOD

VertexWithUV[m_iMaxNumVertices]      // vertex array
uint16[m_iMaxNumIndices]             // triangle indices (3 per face)

// LOD collapse data (may be empty / not used by importer)
__EdgeCollapse[m_iNumCollapses]
int32[m_iTotalIndexChanges]

// LOD control thresholds
int32   m_iLODCtrlValueCount
__LODCtrlValue[m_iLODCtrlValueCount]
  float fDist        // camera distance
  int32 iNumVertices // vertices to use at this distance
```

**Import strategy:** Load `m_iMaxNumVertices` and `m_iMaxNumIndices` (full LOD). Ignore collapse data.

---

## `.n3joint` — Joint / Skeleton Node (Recursive Tree)

**C++ class:** `CN3Joint`

Each joint is loaded recursively:
```
uint16  iFileFormatVersion           // base header (root joint only)

// CN3Transform base:
Vector3    m_vPos                    // local position
Quaternion m_qRot                   // local rotation
Vector3    m_vScale                  // local scale

// Joint-specific:
Quaternion m_qOrient                // orientation offset

// Animation keys (CN3AnimKey) — 4 sets:
// m_KeyPos, m_KeyRot, m_KeyScale, m_KeyOrient each:
  int32   m_nCount                  // number of keyframes (0 = no animation)
  uint32  m_eType                   // 0 = KEY_VECTOR3, 1 = KEY_QUATERNION
  float   m_fSamplingRate           // FPS (typically 30.0)
  // if m_nCount > 0:
  Vector3[] or Quaternion[]         // m_nCount keyframe values

// Children:
int32  nChildCount
[recursive CN3Joint for each child]
```

---

## `.n3anim` — Animation Control

**C++ class:** `CN3AnimControl`

```
uint16  iFileFormatVersion

int32   nAnimCount
// for each animation:
  string szName                     // animation name (length-prefixed)
  float  fFrmStart, fFrmEnd         // frame range
  float  fFrmSound0, fFrmSound1     // sound event frames
  float  fFrmStrike0, fFrmStrike1   // hit timing frames
  float  fTimeBlend                 // blend duration (seconds)
  int32  nFlag                      // loop flag and other bits
```

---

## `.n3cpart` — Character Part

**C++ class:** `CN3CPart`

A character body part references external `.n3cskins` and `.n3tex` files:
```
uint16  iFileFormatVersion
uint32  m_dwReserved                // reserved (ignore)
Material m_MtlOrg                  // material (88 bytes)
string  szTexFilename               // texture file (.dxt/.dxt)
string  szSkinsFilename             // skins file (.n3cskins)
```

The `.n3cskins` file contains up to 4 LOD meshes:
```
// for each LOD level (0–3):
  int32  nVertexCount
  int32  nFaceCount
  int32  nUVCount

  Vertex[nVertexCount]              // position + normal (24 bytes each)
  uint16[nFaceCount * 3]            // face indices
  UVVector[nUVCount]                // UV coords
  uint16[nFaceCount * 3]            // UV indices per face corner

  // Skinning data:
  VertexSkinned[nVertexCount]       // per-vertex bone weights
```

---

## `.n3cplug` — Equipment / Weapon Attachment

**C++ class:** `CN3CPlug`

```
uint16  iFileFormatVersion
uint32  m_ePlugType                 // PLUGTYPE_NORMAL=0, PLUGTYPE_CLOAK=1, etc.
bool    m_bVisible                  // visibility flag
int32   m_nJointIndex               // which joint to attach to
Vector3 m_vPosition                 // local offset from joint
Matrix44 m_MtxRot                  // rotation matrix
Vector3 m_vScale                    // scale
Material m_Mtl                     // material
string  szPMeshFilename             // .n3pmesh file reference
string  szTexFilename               // texture file reference
```

---

## `.n3chr` — Complete Character

**C++ class:** `CN3Chr`

The top-level character file that ties everything together:
```
uint16  iFileFormatVersion

// CN3TransformCollision base (position, rotation, scale, bounds):
Vector3     m_vPos
Quaternion  m_qRot
Vector3     m_vScale
float       m_fRadius               // bounding sphere
Vector3     m_vMin, m_vMax          // AABB

// Collision data (if present — raises error in prototype):
bool        bHasCollision

// Skeleton:
string      szJointFilename         // .n3joint file
// (loaded externally, then cross-referenced)

// Animation:
string      szAnimFilename          // .n3anim file

// Parts (body segments):
int32       nPartCount
for each part:
  string    szPartFilename          // .n3cpart file

// Plugs (equipment):
int32       nPlugCount
for each plug:
  string    szPlugFilename          // .n3cplug file
```

---

## `.dxt` / DXT — Texture Format

**C++ class:** `CN3Texture`

KnightOnline uses a custom texture container called **NTF (Noah Texture File)**:

```
char[4]  szID                       // "NTF" + version byte (e.g., "NTF3")
int32    nWidth                     // texture width (pixels)
int32    nHeight                    // texture height
int32    Format                     // compression type (see below)
bool     bMipMap                    // has mipmap chain
// followed by raw DXT block data (+ mipmap levels if bMipMap)
```

**Format values:**
| Value | Name | Description |
|-------|------|-------------|
| 0 | Uncompressed | Raw RGBA |
| 827611204 | D3DFMT_DXT1 | No alpha, 4 bpp |
| (DXT3) | D3DFMT_DXT3 | Explicit alpha |
| 894720068 | D3DFMT_DXT5 | Interpolated alpha |

**DXT block structure (4×4 pixels):**
- **DXT1**: 8 bytes per block — 2× RGB565 color endpoints + 4×4 2-bit color index table
- **DXT3**: 16 bytes per block — 8 bytes explicit 4-bit alpha + 8 bytes DXT1 color
- **DXT5**: 16 bytes per block — 2× 8-bit alpha endpoints + 6 bytes alpha index table + 8 bytes DXT1 color

**Decompression approach:** Use the `Pillow` (PIL) library (or a pure-Python DXT decoder) to decompress to RGBA, save as a temp PNG, then load into Blender via `bpy.data.images.load()`.

---

## Coordinate System

KnightOnline uses the **DirectX right-handed coordinate system** (Y-up). Blender uses **Z-up right-handed**. The conversion matrix used in the prototype:

```python
# Map matrix: DirectX → Blender
map_mtx = Matrix(((1,0,0,0), (0,0,-1,0), (0,1,0,0), (0,0,0,1)))
       @ Matrix(((-1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1)))
```

For bone transforms, the full similarity transform is applied:
```python
bl_mtx = map_mtx @ dx_mtx @ map_mtx.inverted()
```

---

## `.n3shape` — Static Shape / Prop

**C++ class:** `CN3Shape` / `CN3SPart`

> Note: the file extension is `.n3shape`, **not** `.n3s`. Confirmed from C++ source. Files are found under `object\*.n3shape` and `Misc\*.n3shape` in the game data.

A static scene object composed of one or more mesh parts, each with its own material and texture(s). Also contains game-logic metadata (faction affiliation, event type, NPC binding) that is not relevant to mesh import.

```
uint16  iFileFormatVersion

// CN3TransformCollision base:
Vector3     m_vPos                  // world position
Quaternion  m_qRot                  // world rotation
Vector3     m_vScale                // world scale
float       m_fRadius               // bounding sphere radius
Vector3     m_vMin, m_vMax          // AABB

// Parts:
int32   nPartCount
for each part (CN3SPart):
  Vector3  m_vPivot                 // local pivot point (12 bytes)
  string   szMeshFilename           // .n3pmesh file reference
  Material m_Mtl                   // material (88 bytes)
  float    fTexFPS                  // texture animation FPS
  int32    nTextureCount
  for each texture:
    string szTexFilename            // .dxt texture file reference

// Game-logic metadata (import ignores these):
int32   nBelongID                   // faction affiliation
int32   nEventID
int32   nEventType                  // bind point, gate, lever, etc.
int32   nNPCID
int32   nNPCStatus
```

**Import strategy:** For each part, load the referenced `.n3pmesh`, apply the pivot transform, load the texture(s), and create a material. Multiple parts become separate mesh objects parented to an empty at the shape's world transform. Game-logic fields are ignored.

---

---

## Level / Terrain Files (Future Reference — Not v1.0 Scope)

These formats exist in the game data but are complex enough to warrant a separate milestone. Documented here for future reference.

### `.gtd` — Game Terrain Data (heightmap + tile layout)

Loaded by `CN3Terrain`. Contains a full heightmap grid, per-tile texture indices, normals, patch bounding volumes, grass attributes, river/pond data, and LOD control. Map size is always `(4k+1) × (4k+1)` tiles where k is a power of 2.

### `.gtt` — Game Tile Texture

Indexed tile texture atlas used by terrain. Each `.gtd` references one or more `.gtt` files by path pattern `dtex\{name}_{index}.gtt`. Contains DXT-compressed tile textures packed sequentially.

### `.n3scene` — Scene Container

A top-level container referencing cameras, lights, `.n3shape` objects, and `.n3chr` characters by filename. Similar in role to a Blender scene file.

These formats are deferred to a future release. The terrain system alone is a significant undertaking (heightmaps, tile blending, LOD patches) and is out of scope for the initial asset-focused importer.

---

## File Relationship Diagram

```
.n3chr (Character Root)
├── .n3joint  (Skeleton tree, recursive)
├── .n3anim   (Animation metadata)
├── .n3cpart  (Body part × N)
│   ├── .n3cskins  (LOD mesh data, referenced externally)
│   └── .dxt      (Texture, referenced externally)
└── .n3cplug  (Equipment × M)
    ├── .n3pmesh  (Mesh, referenced externally)
    └── .dxt      (Texture, referenced externally)

.n3pmesh (Standalone static mesh)
.n3joint (Standalone skeleton)
.n3anim  (Standalone animation metadata)

.n3shape (Static Shape/Prop)
└── .n3pmesh × N  (one per part, referenced externally)
    └── .dxt × M  (one or more textures per part)

--- Future scope ---
.n3scene (Scene Container)
├── .n3shape × N
└── .n3chr × M

.gtd (Terrain)
└── .gtt × N  (tile texture atlases)
```

All referenced files are expected to reside in the **same directory** as the root file. Paths stored in the file are resolved to filename-only before loading.
