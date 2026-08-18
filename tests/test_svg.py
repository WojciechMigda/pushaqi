"""Tests for the SVG path -> digit decoder."""

import pusher


def _char_vectors(char):
    return [path for path, c in pusher.CHAR_TEST_VECTORS if c == char]


def test_legacy_character_vectors():
    """The upstream bundled character-recognition vectors still pass."""
    pusher.test_character_recognition()


def test_legacy_number_vectors():
    """The upstream bundled multi-digit recognition vectors still pass."""
    pusher.test_number_recognition()


def test_reduce_simple_path():
    # Numbers adjacent to command letters (e.g. '18.23L', '16.56Z') are kept —
    # the glyph signatures in CHAR_MAP rely on them.
    reduced = pusher.svg_path_reduce('M5.40 18.23L5.40 18.23Q3.13 18.23 1.93 16.56Z')
    assert reduced == 'M* 18.23L* 18.23Q* * * 16.56Z'


def test_to_number_minus_sign():
    for path in _char_vectors('-'):
        assert pusher.svg_path_to_number(path) == '-'


def test_to_number_every_single_glyph():
    # Every glyph in CHAR_MAP must round-trip through the decoder using the
    # real widget paths captured in CHAR_TEST_VECTORS.
    for char in pusher.CHAR_MAP:
        for path in _char_vectors(char):
            assert pusher.svg_path_to_number(path) == char


def test_to_number_digits_concatenated():
    # Adjacent glyphs concatenate into the multi-digit value they render.
    one = _char_vectors('1')[0]
    zero = _char_vectors('0')[0]
    assert pusher.svg_path_to_number(one + zero) == '10'


def test_collate_svg_paths():
    svg = (
        '<svg><path d="M1 2L3 4Z"/><path d="M5 6L7 8Z"/></svg>'
    )
    assert pusher.collate_svg_paths(svg) == 'M1 2L3 4ZM5 6L7 8Z'