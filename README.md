# OpenKO Blender

A Blender 4.2+ extension for importing KnightOnline game assets — meshes, skeletons, animations, textures, and more.

![Blender](https://img.shields.io/badge/Blender-4.2%2B-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## Features

- Import complete characters (`.n3chr`) with skeleton, skinned meshes, equipment, and all animations
- Import static props and environment shapes (`.n3shape`, `.n3pmesh`)
- Import individual character parts and equipment attachments (`.n3cpart`, `.n3cplug`)
- Import skeleton hierarchies (`.n3joint`) and animation metadata (`.n3anim`)
- Automatic DXT1/DXT3/DXT5 texture decompression — no external dependencies required
- Correct DirectX → Blender coordinate system conversion (left-handed Y-up → right-handed Z-up)
- Configurable LOD level, scale, and optional lighting rig that matches KnightOnline defaults
- All animations imported as separate Blender Actions

---

## Requirements

- **Blender 4.2 or later**
- No additional Python packages needed — everything is self-contained

---

## Installation

1. Download the latest `openko_blender.zip` from the [Releases](../../releases) page
2. Open Blender and go to **Edit → Preferences → Extensions**
3. Click **Install from Disk** and select the downloaded ZIP
4. Enable **OpenKO Assets** in the extensions list

> **Note:** Do not unzip the file before installing. Blender expects the ZIP directly.

---

## Usage

1. Go to **File → Import → KnightOnline Assets**
2. Browse to and select a supported asset file
3. Adjust import options in the sidebar of the file browser (see below)
4. Click **Import KnightOnline Asset**

The imported objects will appear in your scene, organized into a collection named after the file.

---

## Import Options

| Option | Default | Description |
|---|---|---|
| **LOD Level** | `0` | Level of detail to import (0 = highest quality, 3 = lowest) |
| **Scale** | `1.0` | Global scale factor applied to all imported objects |
| **Skip Textures** | off | Import geometry only; skip texture loading (useful for fast iteration) |
| **Skip Animations** | off | Import skeleton and mesh without baking animations |
| **Add Lighting** | on | Add a KnightOnline-matching sun light and ambient world color if the scene has no lights |

---

## Supported File Formats

| Extension | Purpose |
|---|---|
| `.n3chr` | Complete character — skeleton, skinned body parts, equipment, and animations |
| `.n3shape` | Static shape or environment prop with one or more mesh parts |
| `.n3cpart` | Single skinned character body part |
| `.n3cplug` | Equipment or weapon attachment (progressive mesh) |
| `.n3joint` | Skeleton hierarchy only |
| `.n3anim` | Animation metadata — frame ranges, FPS, and event markers |
| `.n3pmesh` | Progressive mesh (static geometry with LOD support) |

Textures in `.ntf` / `.dxt` format are loaded automatically when referenced by a mesh — they are not directly importable by the user.

---

## What Gets Imported

**Characters (`.n3chr`)**
- Full armature built from the skeleton hierarchy
- All skinned mesh parts with bone weights
- Equipment and weapon attachments parented to the correct bones
- Every animation baked as a separate Blender Action
- Scene frame range synced to the longest animation

**Static Shapes / Props (`.n3shape`, `.n3pmesh`)**
- Mesh geometry at the selected LOD level
- UV maps
- Materials with textures loaded from referenced asset files

**Skeletons (`.n3joint`)**
- Armature without any mesh geometry
- Useful for rigging validation or re-use with other parts

**Animation Metadata (`.n3anim`)**
- Imported as a Blender text block for reference
- Shows clip names, frame ranges, FPS, and strike/sound event frames

---

## Building from Source

Clone the repository and run the build script to produce an installable ZIP:

```bash
git clone https://github.com/Open-KO/OpenKO-blender.git
cd OpenKO-blender
python build_zip.py
```

The output ZIP will be placed in the project root, ready to install via Blender's extension manager.

### Running Tests

The format parsers have a pure-Python test suite (no Blender required):

```bash
pip install pytest
pytest tests/
```

Tests require real KnightOnline asset files. Download the [test assets](https://stephenmeiernet.wordpress.com/wp-content/uploads/2026/03/ko_assets-4.zip) and extract to `ko_assets/` in the project root, or set the `KO_ASSETS` environment variable to point to your local `Client/` directory.

---

## Project Structure

```
openko_blender/
├── formats/          # Pure-Python binary parsers for each file format
├── blender/          # Blender-specific builders (mesh, armature, material)
├── operators/        # Blender UI operators and file browser integration
└── utils/            # Low-level binary reader utilities

docs/                 # Design documentation and binary format specifications
tests/                # Unit tests for the format parsers
```

The `formats/` package has no Blender dependency and can be used in any Python 3.11+ environment.

---

## Documentation

Detailed design notes and binary format specifications live in [docs/](docs/README.md):

- [Project Overview](docs/01-project-overview.md)
- [File Format Specifications](docs/02-file-format-specs.md)
- [Blender Extension Best Practices](docs/03-blender-addon-best-practices.md)
- [Versioning and Distribution](docs/04-versioning-and-distribution.md)
- [Format Parser Reference](docs/05-format-parser-reference.md)

---

## Support

Join the community on [Discord](https://discord.gg/Uy73SMMjWS) for help, feedback, and discussion.

---

## Contributing

Contributions are welcome. Please open an issue before starting work on a large change so we can discuss the approach first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes and add tests where applicable
4. Open a pull request against `main`

---

## License

MIT — see [LICENSE](LICENSE) for details.