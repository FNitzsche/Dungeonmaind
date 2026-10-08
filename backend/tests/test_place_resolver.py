import unittest

from app.functions.geo.place_resolver import normalize_place_name, resolve_location_entities


class PlaceResolverTests(unittest.TestCase):
    def test_normalize_place_name_collapses_whitespace(self) -> None:
        self.assertEqual(normalize_place_name('  Silver   Lake  '), 'Silver Lake')

    def test_resolve_location_entities_dedupes_case_insensitive(self) -> None:
        raw = ['  Silver Lake ', 'silver lake', 'Silver Lake', 'Berlin', ' berlin ']
        self.assertEqual(
            resolve_location_entities(raw),
            ['Silver Lake', 'Berlin'],
        )

    def test_resolve_location_entities_preserves_first_seen_order(self) -> None:
        raw = ['Berlin', 'Silver Lake', 'berlin', 'Oakwood Village']
        self.assertEqual(
            resolve_location_entities(raw),
            ['Berlin', 'Silver Lake', 'Oakwood Village'],
        )

    def test_resolve_location_entities_skips_empty_values(self) -> None:
        self.assertEqual(resolve_location_entities(['', '   ', 'Berlin']), ['Berlin'])


if __name__ == '__main__':
    unittest.main()
