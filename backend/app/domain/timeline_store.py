"""Async-safe in-memory store for timeline events."""

import asyncio
from collections import defaultdict
from uuid import uuid4

from app.domain.models import TimelineEvent


class TimelineStore:
    """Async-safe in-memory store for timeline events, organized by session.

    Attributes:
        _events: Dict mapping event ID to TimelineEvent.
        _by_session: Dict mapping session ID to list of event IDs.
        _lock: Async lock for thread-safe access.
    """

    def __init__(self) -> None:
        self._events: dict[str, TimelineEvent] = {}
        self._by_session: dict[str, list[str]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def _generate_id(self) -> str:
        """Generate a unique event ID.

        Returns:
            A 12-character hex string.
        """
        return uuid4().hex[:12]
        return uuid4().hex[:12]

    async def add_event(self, event: TimelineEvent) -> TimelineEvent:
        """Add a single event to the store.

        If the event has no ID, a new one is generated.

        Args:
            event: The TimelineEvent to add.

        Returns:
            The added TimelineEvent.
        """
        async with self._lock:
            if not event.id:
                event_id = self._generate_id()
                object.__setattr__(event, 'id', event_id)
            else:
                event_id = event.id
            self._events[event_id] = event
            if event.session_id not in self._by_session[event.session_id]:
                self._by_session[event.session_id].append(event_id)
            return event

    async def add_events(self, events: list[TimelineEvent]) -> list[TimelineEvent]:
        """Add multiple events to the store.

        Args:
            events: List of TimelineEvent objects to add.

        Returns:
            List of added TimelineEvent objects.
        """
        async with self._lock:
            added = []
            for event in events:
                if not event.id:
                    event_id = self._generate_id()
                    object.__setattr__(event, 'id', event_id)
                else:
                    event_id = event.id
                self._events[event_id] = event
                self._by_session[event.session_id].append(event_id)
                added.append(event)
            return added

    async def get_event(self, event_id: str) -> TimelineEvent | None:
        """Get an event by its ID.

        Args:
            event_id: The event identifier.

        Returns:
            The TimelineEvent if found, None otherwise.
        """
        async with self._lock:
            return self._events.get(event_id)

    async def get_session_events(self, session_id: str = 'default') -> list[TimelineEvent]:
        """Get all events for a session, sorted by order.

        Args:
            session_id: The session identifier (default 'default').

        Returns:
            List of TimelineEvent objects sorted by order.
        """
        async with self._lock:
            event_ids = list(self._by_session.get(session_id, []))
            events = [self._events[eid] for eid in event_ids if eid in self._events]
            events.sort(key=lambda e: e.order)
            return events

    async def delete_event(self, event_id: str) -> bool:
        """Delete a single event by its ID.

        Args:
            event_id: The event identifier.

        Returns:
            True if the event was found and deleted, False otherwise.
        """
        async with self._lock:
            event = self._events.pop(event_id, None)
            if event is None:
                return False
            session_events = self._by_session.get(event.session_id, [])
            if event_id in session_events:
                session_events.remove(event_id)
            return True

    async def clear_session(self, session_id: str = 'default') -> int:
        """Clear all events for a session.

        Args:
            session_id: The session identifier (default 'default').

        Returns:
            The number of events removed.
        """
        async with self._lock:
            event_ids = list(self._by_session.get(session_id, []))
            count = 0
            for eid in event_ids:
                if eid in self._events:
                    del self._events[eid]
                    count += 1
            self._by_session[session_id] = []
            return count

    async def clear_all(self) -> int:
        """Clear all events from the store.

        Returns:
            The total number of events removed.
        """
        async with self._lock:
            count = len(self._events)
            self._events.clear()
            self._by_session.clear()
            return count


timeline_store = TimelineStore()
