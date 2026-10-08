"""Normalize and deduplicate place names from timeline location entities."""

from __future__ import annotations


def normalize_place_name(value: str) -> str:
    """Normalize whitespace in a place name string.

    Args:
        value: Raw place name from location_entities.

    Returns:
        Place name with leading/trailing whitespace removed and internal
        whitespace collapsed to single spaces.
    """
    return ' '.join(value.strip().split())


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    """Remove duplicate strings while preserving original order.

    Comparison is case-insensitive; the first occurrence's casing is kept.

    Args:
        values: List of normalized place name strings.

    Returns:
        Deduplicated list preserving first occurrence order.
    """
    seen = set()
    result = []
    for value in values:
        normalized = normalize_place_name(value)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def resolve_location_entities(location_entities: list[str]) -> list[str]:
    """Normalize casing/whitespace and dedupe exact place-name matches.

    Args:
        location_entities: Raw location entity strings from one or more events.

    Returns:
        Normalized, deduplicated place names in first-seen order.
    """
    return _dedupe_preserving_order(location_entities)
