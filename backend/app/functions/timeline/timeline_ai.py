"""Local-LLM analysis for high-quality timeline events.

The existing Ollama model acts as a second-stage judge after the cheap semantic
filter. Bounded batches decide importance, classify events, and extract exact
evidence and location/temporal spans using the same validator as single-event
analysis. If Ollama is unavailable,
callers use semantic filtering with conservative source-derived titles.
"""

from __future__ import annotations

import json
import logging
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
    evidence: str | None = None


def item_event_sentences(text: str) -> list[str]:
    """Return sentences with item-action evidence for AI and offline validation."""
    candidates = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        # Check individual clauses so an unrelated modal/negation does not
        # suppress a completed transfer elsewhere in the sentence.
        clauses = re.split(r"[,;]|\b(?:and|but|so)\b", sentence, flags=re.IGNORECASE)
        for clause in clauses:
            if clause.rstrip().endswith("?") or re.search(
                r"\b(?:going to|gonna|will|would|could|should|might|may|if|"
                r"want(?:s|ed)? to|plan(?:s|ned)? to|intend(?:s|ed)? to|try to|"
                r"not|never|no|didn't|doesn't|don't|wasn't|weren't|can't|cannot|"
                r"attacks?|great weapon master|dice|rolls?|modifier|damage|"
                r"spell slots?|actions?|saving throws?|proficiency bonus|advantage|"
                r"disadvantage|d\d+|rerolls?|ability checks?)\b",
                clause, re.IGNORECASE,
            ):
                continue
            if re.search(
                r"\b(?:obtained|acquired|received|picked up|took|bought|purchased|"
                r"looted|stole|sold|gave|handed|lost|destroyed|used|identified|"
                r"obtain|obtains|acquire|acquires|receive|receives|pick up|picks up|"
                r"take|takes|buy|buys|give|gives|use|uses)\s+\S+",
                clause, re.IGNORECASE,
            ):
                candidates.append(sentence)
                break
    return candidates


def _grounded_evidence(text: str, evidence: object) -> str | None:
    """Match a whole source sentence without removing surrounding qualifiers."""
    if not isinstance(evidence, str) or not evidence.strip():
        return None
    source = " ".join(text.split()).strip()
    candidate = " ".join(evidence.split()).strip()
    return next((sentence for sentence in re.split(r"(?<=[.!?])\s+", source)
                 if sentence.casefold() == candidate.casefold()), None)


def grounded_event_title(text: str, category: str, evidence: object = None) -> str | None:
    """Ground wording, not event semantics; keep/occurred decide AI validity.

    Long evidence stays intact in the analysis. Its title is explicitly marked
    as a transcript excerpt, rather than presenting a truncated assertion as a
    complete sentence. Category selection belongs to the fallback caller.
    """
    sentence = _grounded_evidence(text, evidence if evidence is not None else text)
    if sentence is None:
        return None
    if len(sentence) <= 120:
        return sentence
    prefix = sentence[:107].rsplit(" ", 1)[0]
    return f'Excerpt: “{prefix}…”'


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


SYSTEM_PROMPT = """You are the campaign-event extractor for a Dungeons & Dragons timeline.
Decide whether the supplied transcript describes a MAIN IN-WORLD EVENT worth remembering.

KEEP events that change campaign state, including: travel/arrival/departure; combat start/result; danger/traps; discoveries/clues/secrets/lore; quest acceptance/progress/failure/completion; important items gained/lost/used; important NPC information, promises, threats or deals; major decisions that are committed to; rest/recovery; character injury/death/rescue/status changes; puzzles solved/failed; faction/relationship/world-state changes; important trade/rewards/resources; major magic/environment changes.

REJECT: jokes, laughter, banter, greetings, filler, repeated statements, real-life discussion, food/phone/work talk, technical/audio discussion, pure rules/mechanics talk with no in-world consequence, hypothetical plans not acted upon, trivial dialogue, and ordinary conversation that reveals nothing important.

Dialogue is a timeline event ONLY when the conversation itself creates an important story change or reveals information the party should remember.

Extract locations and temporal expressions automatically from meaning/context. Fantasy names are valid locations. Return ONLY exact text spans that appear in the transcript; never invent a place or time. If none is explicitly stated, use an empty list.

Return JSON only with this schema:
{"keep":true,"occurred":true,"importance":0.0,"category":"travel|combat|dialogue|discovery|rest|quest|item|other","evidence":"complete exact transcript sentence","locations":[],"temporal_entities":[],"reason":"short reason"}

Evidence must describe the actual event, including its subject, action and any qualifiers.
Copy a complete sentence exactly; do not remove negation, conditions or intentions.
Set occurred to true ONLY when the evidence establishes an actual in-world event.
An item mention is not an acquisition. "I am going to take all three attacks at
Great Weapon Master at him" is mechanics/intent, not obtaining an item.
If no suitable evidence exists, set keep and occurred to false. The evidence itself
will supply the title (long evidence is displayed as an excerpt); do not generate
a paraphrase or invented outcome. Evidence length does not determine event validity.

Use importance >= 0.55 only for events that genuinely deserve a timeline entry. If keep is false, evidence/locations/temporal_entities may be empty."""


@lru_cache(maxsize=512)
def analyze_timeline_event(text: str, speakers_key: str = "") -> TimelineAIAnalysis | None:
    if not TIMELINE_AI_ENABLED:
        return None

    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return None

    user_prompt = f"Speakers: {speakers_key or 'unknown'}\nTranscript: {cleaned}"

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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

    return _validate_analysis(cleaned, data)


def _validate_analysis(cleaned: str, data: dict) -> TimelineAIAnalysis:
    keep = data.get("keep") is True and data.get("occurred") is True
    importance = _safe_importance(data.get("importance"))
    category = str(data.get("category", "other")).strip().lower()
    if category not in VALID_CATEGORIES:
        category = "other"

    # The keep flag and minimum importance jointly prevent chatty output.
    keep = keep and importance >= 0.55

    raw_evidence = data.get("evidence")
    evidence = _grounded_evidence(cleaned, raw_evidence)
    title = grounded_event_title(cleaned, category, evidence) if evidence else None
    keep = keep and evidence is not None
    # Exact quotation alone cannot turn mechanics or an item mention into
    # an item event, even if the model incorrectly confirms occurrence.
    if keep and category == "item":
        keep = bool(item_event_sentences(evidence))

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
        evidence=evidence,
    )


logger = logging.getLogger(__name__)
TIMELINE_AI_BATCH_SIZE = 8
TIMELINE_AI_BATCH_CHARS = 12000


def analyze_timeline_events(
    candidates: list[tuple[str, str]],
) -> list[TimelineAIAnalysis | None]:
    """Validate bounded batches against each candidate's own source.

    None selects local fallback. Missing/duplicate IDs never shift results.
    Transport failures stop AI work for this run. Oversized candidates use
    local fallback rather than truncating evidence.
    """
    results: list[TimelineAIAnalysis | None] = [None] * len(candidates)
    if not TIMELINE_AI_ENABLED:
        return results
    batches: list[list[dict]] = []
    batch: list[dict] = []
    size = 0
    for index, (text, speakers) in enumerate(candidates):
        cleaned = " ".join(text.split()).strip()
        item = dict(id=index, transcript=cleaned, speakers=speakers)
        item_size = len(json.dumps(item))
        if not cleaned or item_size > TIMELINE_AI_BATCH_CHARS:
            continue
        if batch and (len(batch) >= TIMELINE_AI_BATCH_SIZE
                      or size + item_size > TIMELINE_AI_BATCH_CHARS):
            batches.append(batch)
            batch, size = [], 0
        batch.append(item)
        size += item_size
    if batch:
        batches.append(batch)

    for number, batch in enumerate(batches, 1):
        logger.info("Timeline AI batch %d/%d (%d candidates)", number, len(batches), len(batch))
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT +
                         '\nAnalyze each candidate independently. Return {"results": [...]} '
                         'with one object using the schema above plus the exact integer id '
                         'for each candidate. Never borrow evidence or entities from another candidate.'},
                        {"role": "user", "content": json.dumps(batch)},
                    ],
                    "stream": False, "format": "json",
                    "options": {"temperature": 0.0},
                },
                timeout=TIMELINE_AI_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("Timeline AI unavailable; using local fallback for remaining candidates: %s", error)
            break
        try:
            content = response.json()["message"]["content"]
            data = _extract_json_object(content) if isinstance(content, str) else None
            rows = data.get("results") if data else None
            if not isinstance(rows, list):
                raise ValueError("missing results list")
        except (ValueError, TypeError, KeyError):
            logger.warning("Timeline AI batch %d malformed; using local fallback", number)
            continue
        by_id: dict[int, list[dict]] = {}
        for row in rows:
            if isinstance(row, dict) and type(row.get("id")) is int:
                by_id.setdefault(row["id"], []).append(row)
        for item in batch:
            matches = by_id.get(item["id"], [])
            if len(matches) == 1:
                results[item["id"]] = _validate_analysis(item["transcript"], matches[0])
    return results
