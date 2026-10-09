import os
import sys
import unittest


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.functions.entity_extraction.entity_extractor import extract_entities


class TemporalEntityExtractionTests(unittest.TestCase):
    def temporal(self, text: str) -> list[tuple[str, str]]:
        entities, _ = extract_entities(text)
        return [(entity.text, entity.entity_type) for entity in entities]

    def test_realistic_travel_and_rest_transcript(self) -> None:
        text = (
            "The party leaves Waterdeep before dawn. Three hours later they "
            "reach the old bridge, and later that evening they make camp. "
            "The next morning they continue north."
        )

        self.assertEqual(
            self.temporal(text),
            [
                ("before dawn", "relative_time"),
                ("Three hours later", "relative_time"),
                ("later that evening", "relative_date"),
                ("The next morning", "relative_date"),
            ],
        )

    def test_realistic_quest_deadline_and_clock_time(self) -> None:
        text = (
            "The innkeeper says, 'Meet me at 8 PM tomorrow. You have until "
            "sunset, and return in two days if you find the map.'"
        )

        self.assertEqual(
            self.temporal(text),
            [
                ("at 8 PM", "clock_time"),
                ("tomorrow", "relative_date"),
                ("until sunset", "relative_time"),
                ("in two days", "relative_time"),
            ],
        )

    def test_common_tabletop_narration_phrases(self) -> None:
        text = (
            "Tomorrow morning we leave after a long rest. Keep watch for the "
            "next two hours and stay here until the next morning."
        )

        self.assertEqual(
            self.temporal(text),
            [
                ("Tomorrow morning", "relative_date"),
                ("after a long rest", "relative_time"),
                ("for the next two hours", "duration"),
                ("until the next morning", "relative_time"),
            ],
        )

    def test_dnd_round_and_turn_expressions(self) -> None:
        text = (
            "The ward lasts for 3 rounds. At the end of your next turn, the "
            "gate closes. Two rounds later the ritual completes."
        )

        self.assertEqual(
            self.temporal(text),
            [
                ("for 3 rounds", "duration"),
                ("At the end of your next turn", "relative_time"),
                ("Two rounds later", "relative_time"),
            ],
        )

    def test_recurrence_and_fantasy_calendar_date(self) -> None:
        text = (
            "The caravan arrives every other night. The contract expires on "
            "the 12th of Eleasis."
        )

        self.assertEqual(
            self.temporal(text),
            [
                ("every other night", "recurrence"),
                ("on the 12th of Eleasis", "calendar_date"),
            ],
        )

    def test_complete_phrase_wins_over_nested_match(self) -> None:
        entities, _ = extract_entities("The next morning we leave the village.")

        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].text, "The next morning")
        self.assertEqual(entities[0].start_character, 0)
        self.assertEqual(entities[0].end_character, 16)

    def test_existing_supported_expressions_remain_supported(self) -> None:
        text = "Yesterday we waited for two hours, then left at 10:30 am on Friday."

        self.assertEqual(
            self.temporal(text),
            [
                ("Yesterday", "relative_date"),
                ("for two hours", "duration"),
                ("at 10:30 am", "clock_time"),
                ("on Friday", "weekday"),
            ],
        )

    def test_non_temporal_numbers_are_not_extracted(self) -> None:
        text = "I rolled 18 damage, found 50 gold, and opened door 3."

        self.assertEqual(self.temporal(text), [])

    def test_unrelated_dialogue_is_ignored(self) -> None:
        text = (
            "I rolled 18 damage, spent 50 gold, bought 20 arrows, have AC 17, "
            "and the locked door is room 12. The sword deals 2d6 damage."
        )

        self.assertEqual(self.temporal(text), [])

    def test_mixed_dialogue_returns_only_real_temporal_entity(self) -> None:
        text = (
            "I rolled 18, lost 12 hit points, bought 5 torches, and found "
            "door 3. Tomorrow morning we leave for Waterdeep."
        )

        self.assertEqual(
            self.temporal(text),
            [("Tomorrow morning", "relative_date")],
        )

    def test_distances_levels_and_dice_are_not_temporal(self) -> None:
        text = (
            "Move 30 feet, cast the level 3 spell, roll 1d20 plus 5, and "
            "use 2 spell slots."
        )

        self.assertEqual(self.temporal(text), [])

    def test_arbitrary_fantasy_name_is_not_calendar_month(self) -> None:
        text = "Meet the envoy at the 12th of Waterdeep delegation."

        self.assertEqual(self.temporal(text), [])

    def test_known_fantasy_month_still_extracts(self) -> None:
        text = "The treaty expires on the 12th of Eleasis."

        self.assertEqual(
            self.temporal(text),
            [("on the 12th of Eleasis", "calendar_date")],
        )

    def test_non_time_use_of_round_is_ignored_without_temporal_marker(self) -> None:
        text = "The ranger buys 20 rounds of ammunition and three mugs of ale."

        self.assertEqual(self.temporal(text), [])

    def test_temporal_extraction_report(self) -> None:
        test_cases = [
            "I'll kill you in three days.",
            "The party will leave tomorrow morning.",
            "We found 50 gold pieces in the chest.",
            "The fighter took 18 damage.",
            "After a long rest, we travel north.",
            "Meet me at 8 PM.",
            "The wizard has 2 spell slots remaining.",
            "Two rounds later, the dragon attacks.",
            "The door is 30 feet away.",
            "The ritual happens every other night.",
            "That was the funniest goblin I've ever seen.",
            "On the 12th of Eleasis, the army arrives.",
        ]

        print("\n")
        print("=" * 80)
        print("D&D TEMPORAL ENTITY EXTRACTION REPORT")
        print("=" * 80)

        for sentence in test_cases:
            temporal = self.temporal(sentence)

            print(f"\nINPUT:")
            print(f'  "{sentence}"')

            if temporal:
                print("TEMPORAL ENTITY:")
                for entity_text, entity_type in temporal:
                    print(f"  Text : {entity_text}")
                    print(f"  Type : {entity_type}")
            else:
                print("TEMPORAL ENTITY:")
                print("  None")

            print("-" * 80)


if __name__ == "__main__":
    unittest.main()
