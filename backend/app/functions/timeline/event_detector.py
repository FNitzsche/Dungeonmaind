"""Semantic filtering for campaign timeline events.

This module deliberately avoids a fixed keyword list for deciding whether a
transcript chunk belongs on the timeline.  It compares the chunk against
positive "story changed" concepts and negative out-of-character/chatter
concepts using the project's existing SentenceTransformer model.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings


# These are semantic prototypes, not trigger words.  A paraphrase can match even
# when none of the words below occur in the transcript.
TIMELINE_EVENT_CONCEPTS = [
    "An important event happens in the game world and changes the adventure.",
    "The party travels to, arrives at, enters, leaves, or escapes a meaningful location.",
    "A combat encounter starts, changes significantly, or ends.",
    "A dangerous creature, enemy, trap, or hazard confronts the party.",
    "The party discovers a secret, clue, hidden place, important fact, or important evidence.",
    "The party receives, accepts, advances, fails, changes, or completes a quest or objective.",
    "The party obtains, loses, gives away, destroys, identifies, or uses an important item.",
    "The party makes an important decision that changes what they will do next.",
    "An NPC reveals important information, gives a warning, makes a threat, or offers an agreement.",
    "A relationship, alliance, betrayal, faction, reputation, or political situation changes.",
    "A player character or important NPC is injured, healed, captured, rescued, transformed, or killed.",
    "A player character gains an important ability, level, condition, curse, blessing, or status change.",
    "The party solves or fails a puzzle, riddle, lock, mechanism, or important challenge.",
    "The party rests, camps, sleeps, recovers, or ends a meaningful phase of the journey.",
    "A major magical, environmental, supernatural, or world-state change occurs.",
    "A meaningful purchase, trade, payment, reward, theft, or resource change affects the adventure.",
    "The party learns important lore, history, identity, motivation, or background information.",
    "A plan is actually committed to or acted upon and becomes part of the adventure.",
]

NON_EVENT_CONCEPTS = [
    "Casual conversation or small talk that does not change the game story.",
    "Players joke, laugh, tease each other, or make humorous comments.",
    "Out-of-character conversation unrelated to events in the game world.",
    "Players talk about food, drinks, phones, work, school, real life, or another unrelated topic.",
    "Players discuss dice, character sheets, application controls, microphones, audio, or technical problems.",
    "Players only discuss rules or mechanics and no in-world consequence happens.",
    "A player proposes a possibility or hypothetical idea but the party does not act on it.",
    "Repeated chatter, filler, acknowledgements, greetings, or conversational noise.",
    "A joke or fictional exaggeration is said but nothing actually happens in the campaign.",
    "Someone repeats or rephrases an event that has already happened without a new development.",
    "The group argues about wording, scheduling, breaks, or table administration.",
    "Someone asks a trivial question and receives a trivial answer.",
    "Pure role-play banter that reveals no important information and changes nothing.",
    "A description contains atmosphere or flavor only and no meaningful story change occurs.",
]

STORY_STATE_CONCEPTS = [
    "The location of the party changes.",
    "The quest or objective state changes.",
    "Combat or danger state changes.",
    "The party's knowledge changes because important information is learned.",
    "An important item or resource changes ownership or state.",
    "A character's health, condition, identity, ability, relationship, or status changes.",
    "The world, environment, faction, or political state changes.",
    "The party commits to an important decision or course of action.",
]


@dataclass(frozen=True)
class SemanticEventDecision:
    keep: bool
    event_score: float
    non_event_score: float
    state_change_score: float
    margin: float


@lru_cache(maxsize=1)
def _get_detector_data() -> tuple[SentenceTransformer, np.ndarray, np.ndarray, np.ndarray]:
    model = SentenceTransformer(settings.embedding_model)

    event_embeddings = model.encode(
        TIMELINE_EVENT_CONCEPTS,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    non_event_embeddings = model.encode(
        NON_EVENT_CONCEPTS,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    state_embeddings = model.encode(
        STORY_STATE_CONCEPTS,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return model, event_embeddings, non_event_embeddings, state_embeddings


def semantic_event_decision(text: str) -> SemanticEventDecision:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return SemanticEventDecision(False, 0.0, 1.0, 0.0, -1.0)

    model, event_embeddings, non_event_embeddings, state_embeddings = _get_detector_data()
    embedding = model.encode(
        [cleaned],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]

    event_score = float(np.max(event_embeddings @ embedding))
    non_event_score = float(np.max(non_event_embeddings @ embedding))
    state_change_score = float(np.max(state_embeddings @ embedding))
    margin = event_score - non_event_score

    # Deliberately permissive here: the local LLM performs the final decision
    # when available.  These thresholds mainly prevent obvious chatter from
    # wasting LLM calls and give a useful fallback when Ollama is unavailable.
    obvious_non_event = non_event_score >= 0.60 and margin < -0.06
    enough_story_signal = event_score >= 0.34 or state_change_score >= 0.36
    clearly_story_like = event_score >= 0.46 and margin >= -0.08

    keep = (enough_story_signal or clearly_story_like) and not obvious_non_event

    return SemanticEventDecision(
        keep=keep,
        event_score=event_score,
        non_event_score=non_event_score,
        state_change_score=state_change_score,
        margin=margin,
    )
