"""Tests for AQI classification and value parsing helpers."""

import pytest

import pusher


@pytest.mark.parametrize("pm25,expected", [
    # Regression: the Moderate band upper bound is 35.4 (EPA 24-hour PM2.5
    # table), not 25.4 — values like 30 µg/m³ are Moderate, not "Unhealthy
    # for Sensitive Groups".
    (25.5, 'Moderate'),
    (30.0, 'Moderate'),
    (35.4, 'Moderate'),
    # Exact breakpoints and just-above values for every band.
    (0.0, 'Good'),
    (12.0, 'Good'),
    (12.1, 'Moderate'),
    (35.5, 'Unhealthy for Sensitive Groups'),
    (55.4, 'Unhealthy for Sensitive Groups'),
    (55.5, 'Unhealthy'),
    (150.4, 'Unhealthy'),
    (150.5, 'Very Unhealthy'),
    (250.4, 'Very Unhealthy'),
    (250.5, 'Hazardous'),
    (500.4, 'Hazardous'),
])
def test_aqi_by_pm25_breakpoints(pm25, expected):
    assert pusher.aqi_by_pm25(pm25) == expected


def test_all_levels_have_posting_data():
    for name, level in pusher.AQI_PM25_LEVELS.items():
        assert 'hi' in level and 'img' in level
        assert name in ('Good', 'Moderate', 'Unhealthy for Sensitive Groups',
                        'Unhealthy', 'Very Unhealthy', 'Hazardous')


@pytest.mark.parametrize("value,expected", [
    ('25', 25.0),
    ('18.5', 18.5),
    ('-1', -1.0),
    (' 12 ', 12.0),
    (3, 3.0),
    (2.5, 2.5),
    (None, None),
    ('', None),
    # SVG decode can leave undecodable glyph junk behind (e.g. a decimal
    # point has no CHAR_MAP signature) — must not crash float parsing.
    ('12M* *L* *Z5', None),
    ('abc', None),
])
def test_to_float(value, expected):
    assert pusher.to_float(value) == expected


def test_coerce_former_aqi_keeps_none_sentinel():
    # None = "state unknown" must survive coercion, otherwise the first-run
    # posting branch is dead code.
    assert pusher.coerce_former_aqi(None) is None
    assert pusher.coerce_former_aqi(0) is False
    assert pusher.coerce_former_aqi(1) is True
    assert pusher.coerce_former_aqi(False) is False
    assert pusher.coerce_former_aqi(True) is True