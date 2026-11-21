"""Async-safe in-memory store for a session's transcript segments."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class TranscriptSegment:
    """One transcribed stretch of speech in a session recording.

    Attributes:
        start: Start time of the segment in seconds.
        end: End time of the segment in seconds.
        text: Transcribed text of the segment.
        speaker: Speaker label or player name assigned to the segment.
    """

    start: float
    end: float
    text: str
    speaker: str = 'unknown'

    def to_dict(self) -> dict:
        """Serialize this segment for transcript.json."""
        return {'start': self.start, 'end': self.end, 'text': self.text, 'speaker': self.speaker}

    @classmethod
    def from_dict(cls, data: dict) -> TranscriptSegment:
        """Deserialize a segment written by export."""
        return cls(
            start=float(data['start']),
            end=float(data['end']),
            text=str(data['text']),
            speaker=str(data.get('speaker') or 'unknown'),
        )


class TranscriptStore:
    """Async-safe in-memory store for transcript segments, per session.

    Attributes:
        _segments: Dict mapping session ID to its segments in arrival order.
        _lock: Async lock for thread-safe access.
    """

    def __init__(self) -> None:
        self._segments: dict[str, list[TranscriptSegment]] = {}
        self._lock = asyncio.Lock()

    async def add_segments(self, session_id: str, segments: list[TranscriptSegment]) -> None:
        """Append segments to a session's transcript.

        Args:
            session_id: The session identifier.
            segments: Segments to append, in spoken order.
        """
        async with self._lock:
            self._segments.setdefault(session_id, []).extend(segments)

    async def get_segments(self, session_id: str) -> list[TranscriptSegment]:
        """Get a copy of a session's transcript segments.

        Args:
            session_id: The session identifier.

        Returns:
            The session's segments in arrival order (empty if none).
        """
        async with self._lock:
            return list(self._segments.get(session_id, []))

    async def replace_session(self, session_id: str, segments: list[TranscriptSegment]) -> None:
        """Replace every segment for one session with the given list.

        Args:
            session_id: The session identifier.
            segments: Segments that should exist for this session after the call.
        """
        async with self._lock:
            self._segments[session_id] = list(segments)

    async def rename_session(self, old_session_id: str, new_session_id: str) -> None:
        """Move a session's transcript to a new session ID.

        Any transcript already stored under the new ID is replaced. Does
        nothing when both IDs are equal.

        Args:
            old_session_id: The session identifier the segments are stored under.
            new_session_id: The session identifier they should be stored under.
        """
        if old_session_id == new_session_id:
            return
        async with self._lock:
            self._segments[new_session_id] = self._segments.pop(old_session_id, [])

    async def clear_session(self, session_id: str) -> int:
        """Clear a session's transcript.

        Args:
            session_id: The session identifier.

        Returns:
            The number of segments removed.
        """
        async with self._lock:
            return len(self._segments.pop(session_id, []))


transcript_store = TranscriptStore()
