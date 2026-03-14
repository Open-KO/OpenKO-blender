"""Tests for the .dxt texture parser."""

import pytest
from openko_blender.formats import dxt_texture
from openko_blender.formats.dxt_texture import DxtFormat


def test_load_parses_without_error(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert tex is not None


def test_dimensions_are_positive(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert tex.width > 0
    assert tex.height > 0


def test_dimensions_are_power_of_two(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert (tex.width & (tex.width - 1)) == 0, f"Width {tex.width} is not a power of 2"
    assert (tex.height & (tex.height - 1)) == 0, f"Height {tex.height} is not a power of 2"


def test_format_is_recognized(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert isinstance(tex.fmt, DxtFormat)


def test_has_mip_data(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert len(tex.mip_data) > 0
    assert len(tex.mip_data[0]) > 0


def test_header_id_is_bytes(dxt_file):
    tex = dxt_texture.load(dxt_file)
    assert isinstance(tex.header_id, bytes)
    assert len(tex.header_id) == 4


def test_decompress_returns_correct_size(dxt_file):
    tex = dxt_texture.load(dxt_file)
    if tex.fmt not in (DxtFormat.DXT1, DxtFormat.DXT5):
        pytest.skip(f"Decompression not implemented for {tex.fmt.name}")
    raw = dxt_texture.decompress_to_rgba(tex, mip_level=0)
    expected = tex.width * tex.height * 4
    assert len(raw) == expected


def test_decompress_rgba_values_in_range(dxt_file):
    tex = dxt_texture.load(dxt_file)
    if tex.fmt not in (DxtFormat.DXT1, DxtFormat.DXT5):
        pytest.skip(f"Decompression not implemented for {tex.fmt.name}")
    raw = dxt_texture.decompress_to_rgba(tex, mip_level=0)
    assert all(0 <= b <= 255 for b in raw)
