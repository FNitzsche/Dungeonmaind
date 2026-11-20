import unittest
from types import SimpleNamespace

from app.domain.models import TimelineEvent
from app.functions.geo.place_resolver import (
    normalize_place_name,
    resolve_location_entities,
    resolve_locations,
    resolve_map_locations,
)


def _event(event_id: str, places: list[str], order: int, session_id: str = 'sess-1'):
    return SimpleNamespace(
        id=event_id, session_id=session_id, order=order, location_entities=places
    )


class PlaceResolverTests(unittest.TestCase):
    def test_normalize_place_name_collapses_whitespace(self) -> None:
        self.assertEqual(normalize_place_name('  Silver   Lake  '), 'Silver Lake')

    def test_resolve_location_entities_dedupes_case_insensitive(self) -> None:
        raw = ['  Silver Lake ', 'silver lake', 'Silver Lake', 'Berlin', ' berlin ']
        self.assertEqual(resolve_location_entities(raw), ['Silver Lake', 'Berlin'])

    def test_resolve_location_entities_preserves_first_seen_order(self) -> None:
        raw = ['Berlin', 'Silver Lake', 'berlin', 'Oakwood Village']
        self.assertEqual(
            resolve_location_entities(raw), ['Berlin', 'Silver Lake', 'Oakwood Village']
        )

    def test_resolve_location_entities_skips_empty_values(self) -> None:
        self.assertEqual(resolve_location_entities(['', '   ', 'Berlin']), ['Berlin'])

    def test_resolve_location_entities_collapses_the_tavern_into_ye_olde_tavern(self) -> None:
        self.assertEqual(
            resolve_location_entities(['Ye Olde Tavern', 'the tavern']), ['Ye Olde Tavern']
        )

    def test_resolve_location_entities_normalizes_casing_and_whitespace_before_dedupe(self) -> None:
        self.assertEqual(
            resolve_location_entities(
                ['  Ye   Olde Tavern ', 'ye olde tavern', '  THE   tavern  ']
            ),
            ['Ye Olde Tavern'],
        )

    def test_resolve_location_entities_keeps_longer_name_when_short_name_comes_first(self) -> None:
        self.assertEqual(
            resolve_location_entities(['the tavern', 'Ye Olde Tavern']), ['Ye Olde Tavern']
        )

    def test_resolve_location_entities_does_not_merge_ambiguous_short_names(self) -> None:
        self.assertEqual(
            resolve_location_entities(['Castle Black', 'White Castle', 'the castle']),
            ['Castle Black', 'White Castle', 'the castle'],
        )

    def test_resolve_location_entities_does_not_merge_inn_into_inner_sanctum(self) -> None:
        self.assertEqual(
            resolve_location_entities(['the inn', 'Inner Sanctum']), ['the inn', 'Inner Sanctum']
        )

    def test_resolve_location_entities_merges_unlisted_place_names(self) -> None:
        self.assertEqual(
            resolve_location_entities(['Black Gloomhold', 'the gloomhold']), ['Black Gloomhold']
        )

    def test_resolve_location_entities_does_not_merge_ambiguous_unlisted_names(self) -> None:
        self.assertEqual(
            resolve_location_entities(['Black Gloomhold', 'Red Gloomhold', 'the gloomhold']),
            ['Black Gloomhold', 'Red Gloomhold', 'the gloomhold'],
        )


class MapLocationResolverTests(unittest.TestCase):
    def test_four_event_worked_example_resolves_three_canonical_places(self) -> None:
        events = [
            TimelineEvent(
                id='evt_1',
                session_id='sess-1',
                title='Arrival at Crossing',
                description='The party reaches Velmora Crossing.',
                order=1,
                location_entities=['Velmora Crossing'],
            ),
            TimelineEvent(
                id='evt_2',
                session_id='sess-1',
                title='Camp at the lake',
                description='They camp beside Silver Lake.',
                order=2,
                location_entities=['Silver Lake'],
            ),
            TimelineEvent(
                id='evt_3',
                session_id='sess-1',
                title='Arrival',
                description='The party enters Ye Olde Tavern.',
                order=3,
                location_entities=['Ye Olde Tavern'],
            ),
            TimelineEvent(
                id='evt_4',
                session_id='sess-1',
                title='Asked around',
                description='Rumors at the tavern.',
                order=4,
                location_entities=['the tavern'],
            ),
        ]

        locations = resolve_locations(events)
        by_id = {location.id: location for location in locations}
        canonical_names = [location.canonical_name for location in locations]

        self.assertEqual(len(locations), 3)
        self.assertEqual(len(set(canonical_names)), 3)
        self.assertEqual(list(by_id), ['loc_1', 'loc_2', 'loc_3'])

        self.assertEqual(by_id['loc_1'].canonical_name, 'Velmora Crossing')
        self.assertEqual(by_id['loc_1'].aliases, [])
        self.assertEqual(by_id['loc_1'].event_ids, ['evt_1'])
        self.assertEqual(by_id['loc_1'].mention_count, 1)
        self.assertEqual(by_id['loc_1'].first_order, 0)

        self.assertEqual(by_id['loc_2'].canonical_name, 'Silver Lake')
        self.assertEqual(by_id['loc_2'].aliases, [])
        self.assertEqual(by_id['loc_2'].event_ids, ['evt_2'])
        self.assertEqual(by_id['loc_2'].mention_count, 1)
        self.assertEqual(by_id['loc_2'].first_order, 1)

        self.assertEqual(by_id['loc_3'].canonical_name, 'Ye Olde Tavern')
        self.assertEqual(by_id['loc_3'].aliases, ['the tavern'])
        self.assertEqual(by_id['loc_3'].event_ids, ['evt_3', 'evt_4'])
        self.assertEqual(by_id['loc_3'].mention_count, 2)
        self.assertEqual(by_id['loc_3'].first_order, 2)

    def test_evt3_and_evt4_resolve_to_one_map_location(self) -> None:
        events = [
            _event('evt_3', ['Ye Olde Tavern'], order=3),
            _event('evt_4', ['the tavern'], order=4),
        ]

        locations = resolve_locations(events)

        self.assertEqual(len(locations), 1)
        location = locations[0]
        self.assertEqual(location.canonical_name, 'Ye Olde Tavern')
        self.assertEqual(location.aliases, ['the tavern'])
        self.assertEqual(location.event_ids, ['evt_3', 'evt_4'])
        self.assertEqual(location.mention_count, 2)
        self.assertEqual(location.first_order, 0)
        self.assertEqual(location.session_id, 'sess-1')
        self.assertEqual(location.id, 'loc_1')

    def test_unique_short_name_merges_into_the_only_matching_place(self) -> None:
        events = [
            _event('evt_1', ['Castle Ravenloft'], order=1),
            _event('evt_2', ['the castle'], order=2),
        ]

        locations = resolve_locations(events)

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].canonical_name, 'Castle Ravenloft')
        self.assertEqual(locations[0].aliases, ['the castle'])
        self.assertEqual(locations[0].event_ids, ['evt_1', 'evt_2'])

    def test_ambiguous_short_name_degrades_safely(self) -> None:
        events = [
            _event('evt_1', ['Silver Lake'], order=1),
            _event('evt_2', ['Black Lake'], order=2),
            _event('evt_3', ['the lake'], order=3),
        ]

        locations = resolve_locations(events)
        names = [location.canonical_name for location in locations]

        self.assertEqual(names, ['Silver Lake', 'Black Lake', 'the lake'])
        self.assertEqual(locations[0].event_ids, ['evt_1'])
        self.assertEqual(locations[1].event_ids, ['evt_2'])
        self.assertEqual(locations[2].event_ids, ['evt_3'])

    def test_article_variant_is_exact_match_after_stripping(self) -> None:
        events = [
            _event('evt_1', ['The Silver Lake'], order=1),
            _event('evt_2', ['Silver Lake'], order=2),
        ]

        locations = resolve_locations(events)

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].canonical_name, 'The Silver Lake')
        self.assertEqual(locations[0].aliases, ['Silver Lake'])
        self.assertEqual(locations[0].event_ids, ['evt_1', 'evt_2'])

    def test_resolve_locations_accepts_timeline_events_and_indexes_lookups(self) -> None:
        events = [
            TimelineEvent(
                id='evt_4',
                session_id='sess-1',
                title='Asked around',
                description='Rumors at the tavern.',
                order=4,
                location_entities=['the tavern'],
            ),
            TimelineEvent(
                id='evt_3',
                session_id='sess-1',
                title='Arrival',
                description='The party enters Ye Olde Tavern.',
                order=3,
                location_entities=['Ye Olde Tavern'],
            ),
        ]

        locations = resolve_locations(events)
        by_id = {location.id: location.event_ids for location in locations}

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].first_order, 0)
        self.assertEqual(by_id['loc_1'], ['evt_3', 'evt_4'])

    def test_resolve_locations_records_an_event_once_when_it_mentions_aliases(self) -> None:
        events = [_event('evt_3', ['Ye Olde Tavern', 'the tavern'], order=3)]

        locations = resolve_locations(events)

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].event_ids, ['evt_3'])
        self.assertEqual(locations[0].mention_count, 2)

    def test_resolve_locations_returns_empty_for_events_without_places(self) -> None:
        self.assertEqual(resolve_locations([_event('evt_1', [], order=1)]), [])
        self.assertEqual(resolve_locations([]), [])

    def test_resolve_map_locations_is_an_alias_of_resolve_locations(self) -> None:
        events = [
            _event('evt_3', ['Ye Olde Tavern'], order=3),
            _event('evt_4', ['the tavern'], order=4),
        ]
        self.assertEqual(
            resolve_map_locations(events)[0].event_ids, resolve_locations(events)[0].event_ids
        )

    def test_session_b_reuses_stable_ids_and_allocates_the_next_place(self) -> None:
        session_a = [
            _event('evt_1', ['Velmora Crossing'], order=1, session_id='session_a'),
            _event('evt_2', ['Silver Lake'], order=2, session_id='session_a'),
            _event('evt_3', ['Ye Olde Tavern'], order=3, session_id='session_a'),
            _event('evt_4', ['the tavern'], order=4, session_id='session_a'),
        ]
        existing = resolve_locations(session_a, existing=[])
        before = [
            (location.id, list(location.event_ids), location.mention_count, location.first_order)
            for location in existing
        ]
        session_b = [
            _event('evt_5', ['the tavern', 'Old Watchtower'], order=5, session_id='session_b'),
            _event('evt_6', ['Silver Lake', 'Old Watchtower'], order=6, session_id='session_b'),
        ]

        locations = resolve_locations(session_b, existing=existing)
        by_id = {location.id: location for location in locations}

        self.assertEqual(
            before,
            [
                (
                    location.id,
                    list(location.event_ids),
                    location.mention_count,
                    location.first_order,
                )
                for location in existing
            ],
        )
        self.assertEqual(list(by_id), ['loc_1', 'loc_2', 'loc_3', 'loc_4'])
        self.assertEqual(
            [location.canonical_name for location in locations],
            ['Velmora Crossing', 'Silver Lake', 'Ye Olde Tavern', 'Old Watchtower'],
        )

        self.assertEqual(by_id['loc_1'].event_ids, ['evt_1'])
        self.assertEqual(by_id['loc_1'].mention_count, 1)
        self.assertEqual(by_id['loc_1'].first_order, 0)
        self.assertEqual(by_id['loc_1'].session_id, 'session_a')

        self.assertEqual(by_id['loc_2'].canonical_name, 'Silver Lake')
        self.assertEqual(by_id['loc_2'].event_ids, ['evt_2', 'evt_6'])
        self.assertEqual(by_id['loc_2'].mention_count, 2)
        self.assertEqual(by_id['loc_2'].first_order, 1)

        self.assertEqual(by_id['loc_3'].canonical_name, 'Ye Olde Tavern')
        self.assertEqual(by_id['loc_3'].aliases, ['the tavern'])
        self.assertEqual(by_id['loc_3'].event_ids, ['evt_3', 'evt_4', 'evt_5'])
        self.assertEqual(by_id['loc_3'].mention_count, 3)
        self.assertEqual(by_id['loc_3'].first_order, 2)
        self.assertEqual(by_id['loc_3'].session_id, 'session_a')

        self.assertEqual(by_id['loc_4'].canonical_name, 'Old Watchtower')
        self.assertEqual(by_id['loc_4'].aliases, [])
        self.assertEqual(by_id['loc_4'].event_ids, ['evt_5', 'evt_6'])
        self.assertEqual(by_id['loc_4'].mention_count, 2)
        self.assertEqual(by_id['loc_4'].first_order, 3)
        self.assertEqual(by_id['loc_4'].session_id, 'session_b')

    def test_case_and_whitespace_reuse_an_existing_place_id(self) -> None:
        existing = resolve_locations([_event('evt_2', ['Silver Lake'], order=2)])

        locations = resolve_locations(
            [_event('evt_6', ['  silver   lake '], order=6, session_id='session_b')],
            existing=existing,
        )

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].id, 'loc_1')
        self.assertEqual(locations[0].canonical_name, 'Silver Lake')
        self.assertEqual(locations[0].event_ids, ['evt_2', 'evt_6'])

    def test_new_alias_merges_into_the_existing_place(self) -> None:
        existing = resolve_locations([_event('evt_5', ['Old Watchtower'], order=5)])

        locations = resolve_locations(
            [_event('evt_6', ['the watchtower'], order=6)], existing=existing
        )

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].id, 'loc_1')
        self.assertEqual(locations[0].canonical_name, 'Old Watchtower')
        self.assertEqual(locations[0].aliases, ['the watchtower'])
        self.assertEqual(locations[0].event_ids, ['evt_5', 'evt_6'])

    def test_ambiguous_short_name_still_allocates_a_new_id(self) -> None:
        existing = resolve_locations(
            [_event('evt_1', ['Silver Lake'], order=1), _event('evt_2', ['Black Lake'], order=2)]
        )

        locations = resolve_locations([_event('evt_3', ['the lake'], order=3)], existing=existing)

        self.assertEqual(
            [location.canonical_name for location in locations],
            ['Silver Lake', 'Black Lake', 'the lake'],
        )
        self.assertEqual(locations[2].id, 'loc_3')
        self.assertEqual(locations[2].event_ids, ['evt_3'])

    def test_same_event_is_not_stored_twice_when_it_repeats_a_place(self) -> None:
        existing = resolve_locations([_event('evt_3', ['Ye Olde Tavern'], order=3)])

        locations = resolve_locations(
            [_event('evt_5', ['Ye Olde Tavern', 'the tavern'], order=5)], existing=existing
        )

        self.assertEqual(locations[0].event_ids, ['evt_3', 'evt_5'])
        self.assertEqual(locations[0].mention_count, 3)


if __name__ == '__main__':
    unittest.main()
