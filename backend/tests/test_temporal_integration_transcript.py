import os
import sys
from pathlib import Path


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.functions.entity_extraction.entity_extractor import extract_entities


TRANSCRIPT_PATH = Path(__file__).parent / "data" / "dnd_temporal_integration_transcript.txt"


def temporal_entities(text: str) -> list[tuple[str, str]]:
    entities, _ = extract_entities(text)
    return [(entity.text, entity.entity_type) for entity in entities]


def test_realistic_dnd_transcript_exact_temporal_output() -> None:
    text = TRANSCRIPT_PATH.read_text(encoding="utf-8")

    assert temporal_entities(text) == [
        ("at dawn", "relative_time"),
        ("Three hours later", "relative_time"),
        ("Tomorrow morning", "relative_date"),
        ("In two hours", "relative_time"),
        ("After a short rest", "relative_time"),
        ("Two rounds later", "relative_time"),
        ("for 3 rounds", "duration"),
        ("At the end of your next turn", "relative_time"),
        ("After a long rest", "relative_time"),
        ("Later that evening", "relative_date"),
        ("every other night", "recurrence"),
        ("at 8 PM", "clock_time"),
        ("before midnight", "relative_time"),
        ("once per day", "recurrence"),
        ("On Friday", "weekday"),
        ("at 10:30 am", "clock_time"),
        ("the next morning", "relative_date"),
        ("On the 12th of Eleasis", "calendar_date"),
        ("For the next two hours", "duration"),
        ("Half an hour later", "relative_time"),
        ("within three days", "relative_time"),
        ("before the next night", "relative_time"),
        ("That evening", "relative_date"),
        ("at sunset", "relative_time"),
        ("The following morning", "relative_date"),
    ]


def test_realistic_dnd_transcript_ignores_numeric_and_dialogue_noise() -> None:
    text = TRANSCRIPT_PATH.read_text(encoding="utf-8")
    found = temporal_entities(text)
    found_texts = {entity_text.lower() for entity_text, _ in found}

    forbidden = {
        "25 gold pieces",
        "14 arrows",
        "number 7",
        "18",
        "2 spell slots",
        "31 hit points",
        "12 damage",
        "door 12",
        "50 silver pieces",
        "30 feet",
    }

    for value in forbidden:
        assert value.lower() not in found_texts


def test_realistic_dnd_transcript_is_deterministic() -> None:
    text = TRANSCRIPT_PATH.read_text(encoding="utf-8")
    first = temporal_entities(text)
    second = temporal_entities(text)

    assert first == second
    assert len(first) == 25
