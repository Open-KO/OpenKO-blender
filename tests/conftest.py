"""
Shared pytest fixtures pointing to real KnightOnline asset files.

All paths are absolute so tests can be run from any working directory.
"""

from pathlib import Path

import pytest

ASSETS = Path(r"C:\Users\srmeier\Projects\KnightOnline\assets\Client")
CHR = ASSETS / "Chr"
CHR_SELECT = ASSETS / "ChrSelect"
MISC = ASSETS / "Misc"
OBJECT = ASSETS / "Object"
ITEM = ASSETS / "Item"


def _require(path: Path) -> Path:
    """Return path; skip the test if the file does not exist."""
    if not path.exists():
        pytest.skip(f"Asset not found: {path}")
    return path


# ── Per-format fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def n3pmesh_file() -> Path:
    return _require(CHR_SELECT / "a14042000.n3pmesh")


@pytest.fixture
def n3pmesh_file_bow() -> Path:
    return _require(CHR_SELECT / "bow_el_rm.n3pmesh")


@pytest.fixture
def n3joint_file() -> Path:
    return _require(CHR / "el_dong_gold.n3joint")


@pytest.fixture
def n3anim_file() -> Path:
    return _require(CHR / "el_dong_gold.n3anim")


@pytest.fixture
def n3anim_file_canon() -> Path:
    return _require(CHR / "canon.n3anim")


@pytest.fixture
def n3chr_file() -> Path:
    return _require(CHR / "el_dong_gold.n3chr")


@pytest.fixture
def n3cpart_file() -> Path:
    return _require(CHR_SELECT / "upc_el_rf_hair.n3cpart")


@pytest.fixture
def n3cplug_file() -> Path:
    return _require(CHR_SELECT / "long_sword0.n3cplug")


@pytest.fixture
def n3shape_file() -> Path:
    return _require(CHR_SELECT / "bow_el_rm.n3shape")


@pytest.fixture
def n3shape_file_chairs() -> Path:
    return _require(CHR_SELECT / "el_chairs.n3shape")


@pytest.fixture
def dxt_file() -> Path:
    # Find first available .dxt file in ChrSelect
    for name in ("b.dxt", "back05m.dxt", "bb.dxt"):
        p = CHR_SELECT / name
        if p.exists():
            return p
    pytest.skip("No .dxt texture file found in ChrSelect")
