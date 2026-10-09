"""
Regression tests for timeline event detection (issue #13).

"""

import unittest

from app.base_models.timeline_models import TimelineSourceSegment

# timeline_generator imports numpy, sentence-transformers, langchain and
# chromadb at module level. The CI backend job installs only pydantic, so the
# import fails there. Skip with an explanation rather than erroring out, which
# would look like a broken suite instead of an environment it cannot run in.
try:
    from app.functions.timeline.timeline_generator import (
        _detect_category,
        _is_meaningful_group,
        _is_out_of_character,
    )
except ImportError as exc:
    raise unittest.SkipTest(f"requires numpy/sentence-transformers: {exc}")


# ---------------------------------------------------------------------------
# _detect_category(text: str) -> TimelineCategory
# ---------------------------------------------------------------------------

class DetectCategoryTests(unittest.TestCase):

    detect_category_cases = [
        ("combat-rules-talk-not-action",  "Wait, what's my armor class again, and do I need to roll for initiative?", "dialogue", False),
        ("item-fix-may-shift-to-combat",  "I'm thinking of taking Great Weapon Master for my next feat.",             "dialogue", False),
        ("item-real-acquisition",         "I open the chest and pull out an old iron key.",                           "item",     True),
        ("discovery-real",                "We push open the door and discover a hidden passage behind the bookshelf.","discovery",True),
        ("combat-real-action",            "Grog swings his greataxe and lands a critical hit on the goblin.",         "combat",   True),
        ("bug-attacked-double-counts",    "Grog attacked the goblin.",                                                 "combat",   True),
        ("dialogue-hypothetical-travel",  "Wait. I thought we were going to be heading south?",                        "dialogue", False),
        ("item-longsword-feat-also-shifts","Should I pick up Polearm Master instead of another weapon feat?",         "dialogue", False),
    ]

    def test_detect_category(self):
        for case_id, text, expected_category, should_create_event in self.detect_category_cases:
            with self.subTest(case_id=case_id):
                actual = _detect_category(text)
                self.assertEqual(actual, expected_category)


# ---------------------------------------------------------------------------
# _is_out_of_character(text: str) -> bool
# ---------------------------------------------------------------------------

class OutOfCharacterTests(unittest.TestCase):

    ooc_cases = [
        ("ooc-voice-actor-intro",   "My name is Matthew Mercer, voice actor and Dungeon Master for Critical Role.", True),
        ("ooc-audio-bottleneck",    "We're having an audio bottleneck, it'll take about 30 seconds.",               True),
        ("ooc-welcome-back-spared", "Hey guys, welcome back.",                                                        False),
        ("ooc-real-tavern-line",    "I grab the amulet off the table and shove it in my pack.",                       False),
    ]

    def test_is_out_of_character(self):
        for case_id, text, expected in self.ooc_cases:
            with self.subTest(case_id=case_id):
                self.assertEqual(_is_out_of_character(text), expected)


# ---------------------------------------------------------------------------
# _is_meaningful_group(group: list[TimelineSourceSegment]) -> bool
# ---------------------------------------------------------------------------

class MeaningfulGroupTests(unittest.TestCase):

    @staticmethod
    def make_segment(text, start=0.0, end=5.0, speaker="PLAYER"):
        return TimelineSourceSegment(text=text, speaker=speaker, start_time=start, end_time=end)

    meaningful_group_cases = [
        ("reject-too-short-text",     "Ok.",                                                             0.0, 5.0, False),
        ("reject-too-short-duration", "I grab the amulet off the table and put it in my pack.",          0.0, 1.0, False),
        ("reject-too-few-words",      "Hmmmmmmmmmm, okay, no.",                                          0.0, 5.0, False),
        ("accept-real-item-line",     "I grab the amulet off the table and put it in my pack.",          0.0, 5.0, True),
        ("reject-ooc-even-if-long",   "Thanks to our sponsor for making tonight's episode possible, we'll be right back after this break.", 0.0, 6.0, False),
        ("accept-welcome-back-line",  "Hey guys, welcome back, the tavern's still buzzing from last night.", 0.0, 4.0, True),
    ]

    def test_is_meaningful_group(self):
        for case_id, text, start, end, expected in self.meaningful_group_cases:
            with self.subTest(case_id=case_id):
                group = [self.make_segment(text, start=start, end=end)]
                self.assertEqual(_is_meaningful_group(group), expected)


if __name__ == "__main__":
    unittest.main()
