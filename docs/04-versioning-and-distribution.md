# Versioning and Distribution

---

## Versioning Strategy

This project uses **Semantic Versioning** (`MAJOR.MINOR.PATCH`), consistent with Blender's official version number guidelines.

| Component | Meaning | Example trigger |
|-----------|---------|----------------|
| MAJOR | Breaking changes, major rewrites | Dropping support for a file format, removing import options |
| MINOR | New features, backward-compatible | Adding a new supported file type, new import option |
| PATCH | Bug fixes, minor improvements | Fixing incorrect UV mapping, correcting bone transforms |

**Examples:**
- `1.0.0` — Initial release
- `1.1.0` — Added `.n3s` scene file support
- `1.1.1` — Fixed DXT5 decompression edge case
- `2.0.0` — Rewritten with export support and new UI

---

## Branches and Release Flow

```
main         — stable, production-ready code, tagged with version numbers
dev          — active development
feature/*    — individual feature branches, merged into dev
hotfix/*     — critical fixes, merged directly to main + dev
```

**Release flow:**
1. Merge `dev` into `main`
2. Bump version in `blender_manifest.toml` (and keep in sync with git tag)
3. Create git tag: `git tag v1.2.0`
4. CI builds the release ZIP and attaches it to the GitHub Release

---

## Package Structure (ZIP)

The release ZIP must contain exactly the addon package directory:

```
openko_blender.zip
└── openko_blender/
    ├── blender_manifest.toml
    ├── __init__.py
    ├── operators/
    ├── formats/
    ├── blender/
    ├── ui/
    ├── utils/
    └── wheels/
        └── *.whl
```

**Important:** The ZIP root must be the package directory, not the repo root. Blender expects to unzip to `extensions/user_default/openko_blender/`.

**Exclude from ZIP:**
- `.git/`
- `__pycache__/`
- `*.pyc`
- `docs/`
- `tests/`
- `.github/`
- Development config files

---

## GitHub Actions CI/CD

Create `.github/workflows/release.yml`:

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install blender-extension-builder
        run: pip install blender-extension-builder

      - name: Download Pillow wheels
        run: |
          pip download pillow \
            --dest openko_blender/wheels \
            --only-binary :all: \
            --python-version 311 \
            --platform win_amd64 \
            --platform manylinux1_x86_64 \
            --platform macosx_12_0_arm64

      - name: Build extension ZIP
        run: blender-extension-builder build openko_blender

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: openko_blender-*.zip
          generate_release_notes: true
```

---

## Distribution Channels

### 1. GitHub Releases (Primary)

- Tag every release: `v1.0.0`, `v1.1.0`, etc.
- Attach the built `.zip` to the GitHub Release
- Users install via Blender: **Edit > Preferences > Extensions > Install from Disk**
- Include a CHANGELOG entry for every release

### 2. Blender Extensions Platform (Target for v2.x)

Submit the addon to [extensions.blender.org](https://extensions.blender.org) for discoverability and one-click install/update from within Blender's UI.

**Requirements for submission:**
- GPL-2.0-or-later license (or compatible)
- No runtime pip installs (all deps bundled as wheels)
- No obfuscated code
- `blender_manifest.toml` with all required fields
- Passes Blender's automated validation (`blender --command extension validate`)

**Once published**, users can install and update directly from Blender's Extensions panel without ever visiting GitHub.

### 3. Manual ZIP (Always Supported)

The GitHub Release ZIP can always be installed manually. This is important for:
- Offline environments
- Pinning a specific version
- Testing pre-release builds

---

## Installing for Development

```bash
# Clone the repo
git clone https://github.com/your-org/openko-blender.git
cd openko-blender

# Option A: Symlink into Blender's extension directory (recommended)
# Windows (PowerShell as admin):
New-Item -ItemType SymbolicLink `
  -Path "$env:APPDATA\Blender Foundation\Blender\4.2\extensions\user_default\openko_blender" `
  -Target "$PWD\openko_blender"

# Linux/macOS:
ln -s "$(pwd)/openko_blender" \
  ~/.config/blender/4.2/extensions/user_default/openko_blender

# Option B: Install from ZIP each time
blender-extension-builder build openko_blender
# Then install the .zip via Blender Preferences
```

After symlinking, enable the extension in **Edit > Preferences > Extensions**, then search for "OpenKO".

---

## CHANGELOG Format

Maintain a `CHANGELOG.md` in the repo root using [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
# Changelog

## [Unreleased]

## [1.1.0] — 2025-04-01
### Added
- Support for `.n3s` shape files

### Fixed
- DXT5 alpha decompression edge case with a0 < a1

## [1.0.0] — 2025-03-01
### Added
- Initial release with support for .n3chr, .n3cpart, .n3cplug, .n3joint, .n3anim, .n3pmesh
```

---

## Version Tracking in Code

The single source of truth for the version is `blender_manifest.toml`:
```toml
version = "1.0.0"
```

Do not hardcode the version string elsewhere. Read it at runtime if needed:
```python
import importlib.metadata
# Or access via bl_info / manifest — use bpy.context.preferences.addons
```

---

## Compatibility Matrix

| Plugin Version | Blender Min | Blender Max | Notes |
|---------------|-------------|-------------|-------|
| 1.x | 4.2 LTS | — | Extensions format |
| (future 2.x) | 4.2 LTS | — | TBD |

We do **not** plan to support Blender < 4.2 because:
1. Legacy pip install pattern is fragile and officially discouraged
2. Extensions platform provides a much better user experience
3. 4.2 LTS has broad adoption and long support window