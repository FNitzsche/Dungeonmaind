"""Local-LLM analysis for high-quality timeline events.

The existing Ollama model acts as a second-stage judge after the cheap semantic
filter.  One cached call can decide importance, classify the event, and extract
exact location/temporal spans.  If Ollama is unavailable, callers simply fall
back to the semantic/heuristic pipeline.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache

import requests

from app.core.config import settings


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
TIMELINE_AI_ENABLED = os.getenv("TIMELINE_AI_ENABLED", "true").strip().lower() not in {
    "0", "false", "no", "off"
}
TIMELINE_AI_TIMEOUT = float(os.getenv("TIMELINE_AI_TIMEOUT", "45"))

VALID_CATEGORIES = {
    "travel",
    "combat",
    "dialogue",
    "discovery",
    "rest",
    "quest",
    "item",
    "other",
}


@dataclass(frozen=True)
class TimelineAIAnalysis:
    keep: bool
    importance: float
    category: str
    title: str | None
    locations: tuple[str, ...]
    temporal_entities: tuple[str, ...]
    reason: str | None


def _extract_json_object(value: str) -> dict | None:
    value = value.strip()
    if not value:
        return None

    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Tolerate models wrapping JSON in markdown or a short explanation.
    match = re.search(r"\{.*\}", value, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _exact_spans(values: object, source_text: str) -> tuple[str, ...]:
    """Accept only values that really occur in the transcript.

    This prevents an LLM from inventing a fantasy location or time expression.
    Matching is case-insensitive and the returned text uses the original source
    casing.
    """
    if not isinstance(values, list):
        return ()

    output: list[str] = []
    seen: set[str] = set()
    lower_source = source_text.casefold()

    for raw in values:
        if not isinstance(raw, str):
            continue
        candidate = " ".join(raw.split()).strip(" \t\n\r.,;:!?\"'()[]{}")
        if len(candidate) < 2:
            continue
        start = lower_source.find(candidate.casefold())
        if start < 0:
            continue
        original = source_text[start:start + len(candidate)].strip()
        key = original.casefold()
        if key and key not in seen:
            seen.add(key)
            output.append(original)

    return tuple(output)


def _safe_importance(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


@lru_cache(maxsize=512)
def analyze_timeline_event(text: str, speakers_key: str = "") -> TimelineAIAnalysis | None:
    if not TIMELINE_AI_ENABLED:
        return None

    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return None

    system_prompt = """You are the campaign-event extractor for a Dungeons & Dragons timeline.
Decide whether the supplied transcript describes a MAIN IN-WORLD EVENT worth remembering.

KEEP events that change campaign state, including: travel/arrival/departure; combat start/result; danger/traps; discoveries/clues/secrets/lore; quest acceptance/progress/failure/completion; important items gained/lost/used; important NPC information, promises, threats or deals; major decisions that are committed to; rest/recovery; character injury/death/rescue/status changes; puzzles solved/failed; faction/relationship/world-state changes; important trade/rewards/resources; major magic/environment changes.

REJECT: jokes, laughter, banter, greetings, filler, repeated statements, real-life discussion, food/phone/work talk, technical/audio discussion, pure rules/mechanics talk with no in-world consequence, hypothetical plans not acted upon, trivial dialogue, and ordinary conversation that reveals nothing important.

Dialogue is a timeline event ONLY when the conversation itself creates an important story change or reveals information the party should remember.

Extract locations and temporal expressions automatically from meaning/context. Fantasy names are valid locations. Return ONLY exact text spans that appear in the transcript; never invent a place or time. If none is explicitly stated, use an empty list.

Return JSON only with this schema:
{"keep":true,"importance":0.0,"category":"travel|combat|dialogue|discovery|rest|quest|item|other","title":"short factual title","locations":[],"temporal_entities":[],"reason":"short reason"}

Use importance >= 0.55 only for events that genuinely deserve a timeline entry. If keep is false, title/locations/temporal_entities may be empty."""

    user_prompt = f"Speakers: {speakers_key or 'unknown'}\nTranscript: {cleaned}"

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
        },
    }

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=TIMELINE_AI_TIMEOUT,
        )
        response.raise_for_status()
        response_data = response.json()
        content = response_data.get("message", {}).get("content", "")
        data = _extract_json_object(content)
        if not data:
            return None
    except (requests.RequestException, ValueError, TypeError):
        return None

    keep = bool(data.get("keep", False))
    importance = _safe_importance(data.get("importance"))
    category = str(data.get("category", "other")).strip().lower()
    if category not in VALID_CATEGORIES:
        category = "other"

    # The keep flag and minimum importance jointly prevent chatty output.
    keep = keep and importance >= 0.55

    raw_title = data.get("title")
    title = None
    if isinstance(raw_title, str):
        title = " ".join(raw_title.split()).strip(" \t\n\r.,;:-")[:120] or None

    reason = data.get("reason")
    if isinstance(reason, str):
        reason = " ".join(reason.split()).strip()[:240] or None
    else:
        reason = None

    return TimelineAIAnalysis(
        keep=keep,
        importance=importance,
        category=category,
        title=title,
        locations=_exact_spans(data.get("locations"), cleaned),
        temporal_entities=_exact_spans(data.get("temporal_entities"), cleaned),
        reason=reason,
    )
