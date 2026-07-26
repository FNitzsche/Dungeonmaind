import unittest
from unittest.mock import patch

from app.functions.embedding.entity_extractor import (
    ExtractedEntities,
    extract_entities,
    extract_entities_hybrid,
)

DOCX_CASES = [
    {
        'text': (
            'On Monday morning, the adventurers gathered in Oakwood Village before beginning their journey. '
            'At 9:00 AM, they left the village and followed the eastern road toward Green Forest. '
            'Around noon, they stopped beside Silver Lake to rest and eat lunch. Later that afternoon, '
            'they crossed the Old Stone Bridge and continued toward Riverstone Town. Before sunset, '
            'they reached a small campsite near Dragon Hill and decided to stay there for the night.'
        ),
        'temporal': [
            'Monday morning',
            '9:00 AM',
            'Around noon',
            'Later that afternoon',
            'Before sunset',
            'Night',
        ],
        'location': [
            'Oakwood Village',
            'Green Forest',
            'Silver Lake',
            'Old Stone Bridge',
            'Riverstone Town',
            'Dragon Hill',
        ],
    },
    {
        'text': (
            'Early on Tuesday morning, the group departed from Riverstone Town and headed south toward Moon Temple. '
            'After traveling for three hours, they entered Crystal Forest and discovered a hidden trail. '
            'By midday, they reached Whispering Lake and found an abandoned watchtower overlooking the water. '
            'During the evening, they followed an old map that pointed toward Shadow Cave. Shortly before midnight, '
            'they arrived at the cave entrance and established a temporary camp nearby.'
        ),
        'temporal': [
            'Tuesday morning',
            'After traveling for three hours',
            'By midday',
            'During the evening',
            'Shortly before midnight',
        ],
        'location': [
            'Riverstone Town',
            'Moon Temple',
            'Crystal Forest',
            'Whispering Lake',
            'Watchtower',
            'Shadow Cave',
        ],
    },
    {
        'text': (
            'Two days after leaving Oakwood Village, the expedition reached the northern edge of Frostwind Valley. '
            'At approximately 14:30, the scouts reported unusual activity near Raven Peak. Later that evening, '
            'a messenger arrived from Silver Harbor carrying a letter addressed to the governor of Ironkeep City. '
            'The letter instructed the group to travel to Sunfall Fortress before dawn on Thursday. '
            'During the following night, the party crossed the Black River and entered the western region of Emerald Plains.'
        ),
        'temporal': [
            'Two days after leaving',
            '14:30',
            'Later that evening',
            'Before dawn on Thursday',
            'During the following night',
        ],
        'location': [
            'Oakwood Village',
            'Frostwind Valley',
            'Raven Peak',
            'Silver Harbor',
            'Ironkeep City',
            'Sunfall Fortress',
            'Black River',
            'Emerald Plains',
        ],
    },
    {
        'text': (
            'Three weeks after the events at Dragon Hill, the council convened in the Grand Hall of Aethergate. '
            'On the morning of March 17, 2025, representatives from Northwatch, Eastmere, and the Kingdom of Valoria '
            'met to discuss increasing monster activity near the Shattered Coast. At approximately 07:45 AM, '
            'reports arrived describing sightings near the Ruins of Eldermoor, while additional messages referenced '
            'incidents occurring between sunset and midnight around the Obsidian Cliffs. By the end of the month, '
            'investigators were expected to travel through Frostmere Pass, continue toward the Citadel of Arcanis, '
            'and eventually reach the Isle of Storms before the beginning of the next year.'
        ),
        'temporal': [
            'Three weeks after',
            'Morning of March 17, 2025',
            '07:45 AM',
            'Between sunset and midnight',
            'By the end of the month',
            'Before the beginning of the next year',
        ],
        'location': [
            'Dragon Hill',
            'Aethergate',
            'Northwatch',
            'Eastmere',
            'Kingdom of Valoria',
            'Shattered Coast',
            'Ruins of Eldermoor',
            'Obsidian Cliffs',
            'Frostmere Pass',
            'Citadel of Arcanis',
            'Isle of Storms',
        ],
    },
]


def casefold_list(values: list[str]) -> list[str]:
    return [value.casefold() for value in values]


class EntityExtractorTests(unittest.TestCase):
    def test_extracts_relative_time_clock_time_and_city(self):
        entities = extract_entities('Yesterday we met in Berlin at 8:30 PM')

        self.assertIn('Yesterday', entities.temporal_entities)
        self.assertIn('8:30 PM', entities.temporal_entities)
        self.assertIn('Berlin', entities.location_entities)

    def test_extracts_relative_phrase_and_local_places(self):
        entities = extract_entities('Next week go to Room 204 in Building A')

        self.assertIn('Next week', entities.temporal_entities)
        self.assertIn('Room 204', entities.location_entities)
        self.assertIn('Building A', entities.location_entities)

    def test_extracts_full_date_year_and_country(self):
        entities = extract_entities('On 12 June 2026 we left India')

        self.assertIn('12 June 2026', entities.temporal_entities)
        self.assertIn('India', entities.location_entities)

    def test_extracts_fantasy_geographic_locations(self):
        entities = extract_entities(
            'The party crossed Silver Lake, entered the goblin cave, '
            'and camped near Neverwinter Wood.'
        )

        self.assertIn('Silver Lake', entities.location_entities)
        self.assertIn('the goblin cave', entities.location_entities)
        self.assertIn('Neverwinter Wood', entities.location_entities)

    def test_extracts_lowercase_described_locations(self):
        entities = extract_entities('We searched the old ruins below the black tower.')

        self.assertIn('the old ruins', entities.location_entities)
        self.assertIn('the black tower', entities.location_entities)

    def test_extracts_high_variety_dnd_locations(self):
        entities = extract_entities(
            'Yesterday the party reached Phandalin, crossed Silver Lake, '
            'entered the goblin cave, escaped Castle Ravenloft, and searched '
            'the Shrine of Seven Stars near Barovia at 8:30 PM.'
        )

        self.assertIn('Phandalin', entities.location_entities)
        self.assertIn('Silver Lake', entities.location_entities)
        self.assertIn('the goblin cave', entities.location_entities)
        self.assertIn('Castle Ravenloft', entities.location_entities)
        self.assertIn('Shrine of Seven Stars', entities.location_entities)
        self.assertIn('Barovia', entities.location_entities)
        self.assertNotIn('Castle', entities.location_entities)
        self.assertNotIn('the Shrine', entities.location_entities)

    def test_matches_docx_expected_entities_case_insensitive(self):
        for case in DOCX_CASES:
            with self.subTest(case=case['text'][:40]):
                entities = extract_entities(case['text'])
                self.assertEqual(
                    casefold_list(case['temporal']), casefold_list(entities.temporal_entities)
                )
                self.assertEqual(
                    casefold_list(case['location']), casefold_list(entities.location_entities)
                )

    def test_hybrid_adds_llm_entities_without_replacing_rule_entities(self):
        with patch(
            'app.functions.embedding.entity_extractor._extract_entities_with_local_llm',
            return_value=ExtractedEntities(
                temporal_entities=['after the blood moon'],
                location_entities=['Zarathul', 'Misty Hollow'],
            ),
        ):
            entities = extract_entities_hybrid(
                'Tomorrow, after the blood moon, the party reaches Zarathul near Misty Hollow.',
                use_llm=True,
            )

        self.assertIn('Tomorrow', entities.temporal_entities)
        self.assertIn('after the blood moon', entities.temporal_entities)
        self.assertIn('Zarathul', entities.location_entities)
        self.assertIn('Misty Hollow', entities.location_entities)

    def test_hybrid_rejects_llm_descriptions_and_wrong_categories(self):
        text = (
            'For the past 2 weeks, the party gathered at Yoon Shrine in the Dominion of Arkhenfall '
            'on the Frostpire Peninsula. Between sunrise and noon, they sailed toward the Isle of Silent Tides '
            'after receiving reports from the Kingdom of Elendra.'
        )

        with patch(
            'app.functions.embedding.entity_extractor._extract_entities_with_local_llm',
            return_value=ExtractedEntities(
                temporal_entities=[
                    'Yoon Shrine: A place that has been actively gathering information for the past 2 weeks.',
                    'Representative from Dominion of Arkhenfall',
                    'Before Sunset',
                ],
                location_entities=[
                    'Yoon Shrine: A grand observatory nestled within the Dominion of Arkhenfall.',
                    'Frostpire Peninsula: A remote, icy peninsula.',
                    'Isle of Silent Tides: A small, desolate island.',
                    'Kingdom of Elendra: A maritime kingdom.',
                ],
            ),
        ):
            entities = extract_entities_hybrid(text, use_llm=True)

        self.assertIn('For the past 2 weeks', entities.temporal_entities)
        self.assertIn('Between sunrise and noon', entities.temporal_entities)
        self.assertNotIn('Yoon Shrine', entities.temporal_entities)
        self.assertNotIn('Representative from Dominion of Arkhenfall', entities.temporal_entities)
        self.assertIn('Yoon Shrine', entities.location_entities)
        self.assertIn('Frostpire Peninsula', entities.location_entities)
        self.assertIn('Isle of Silent Tides', entities.location_entities)
        self.assertIn('Kingdom of Elendra', entities.location_entities)
        self.assertFalse(any(':' in entity for entity in entities.location_entities))


if __name__ == '__main__':
    unittest.main()
