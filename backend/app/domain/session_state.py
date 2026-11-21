"""Identity of the game session the backend is currently running.

The backend hosts one group of players at a time, so it also owns the
identity of the one *active session*. Every new game gets its own key, which
is what keeps one game's transcript, timeline and map apart from another's.

Two identifiers exist per session:

- the **session key** (``session_id`` everywhere else in the code) is what the
  frontend sends and what the in-memory stores are keyed by. It is
  ``draft-<random>`` until the session is saved and ``campaign/session``
  afterwards.
- the **session uid** never changes, not even when the session is saved or
  renamed. Transcript chunks in the vector database are tagged with it, so
  they stay attached to their session without ever being rewritten.
"""

from __future__ import annotations

from uuid import uuid4

DRAFT_PREFIX = 'draft-'

# Keys older frontends send for "the game that has not been saved yet". They
# are treated as "the active session" so they can never address a shared bucket.
_ACTIVE_ALIASES = frozenset({'', 'unsaved'})

# Tag carried by transcript chunks stored before sessions had identities.
LEGACY_TRANSCRIPT_UID = 'none'


class SessionRegistry:
    """Tracks the active session and the permanent uid behind every session key."""

    def __init__(self) -> None:
        self._uids: dict[str, str] = {}
        self._active_session_id = ''
        self.start_new()

    @property
    def active_session_id(self) -> str:
        """Key of the session the backend is currently running."""
        return self._active_session_id

    def start_new(self) -> str:
        """Begin a brand-new, empty session and make it the active one.

        Returns:
            The key of the new session.
        """
        uid = uuid4().hex
        session_id = f'{DRAFT_PREFIX}{uid[:12]}'
        self._uids[session_id] = uid
        self._active_session_id = session_id
        return session_id

    def activate(self, session_id: str, uid: str | None = None) -> str:
        """Make ``session_id`` the active session (used when a saved session is loaded).

        Args:
            session_id: Key of the session to activate.
            uid: The session's permanent uid if it is known (read from its
                saved files). A new one is created otherwise.

        Returns:
            The uid the session now has.
        """
        resolved_uid = uid or self._uids.get(session_id) or uuid4().hex
        self._uids[session_id] = resolved_uid
        self._active_session_id = session_id
        return resolved_uid

    def resolve(self, session_id: str | None) -> str:
        """Translate a key received from a client into a real session key.

        A missing key and the legacy ``unsaved`` key both mean "the active
        session". Any other key is returned unchanged.
        """
        if session_id is None or session_id.strip() in _ACTIVE_ALIASES:
            return self._active_session_id
        return session_id

    def uid_for(self, session_id: str) -> str:
        """Return the permanent uid of a session.

        A key that was never registered is its own uid, so data stored under
        an arbitrary key still stays separate from every other key.
        """
        return self._uids.get(session_id, session_id)

    def rename(self, old_session_id: str, new_session_id: str) -> None:
        """Give a session a new key (it was saved or renamed); its uid is kept."""
        if old_session_id == new_session_id:
            return
        self._uids[new_session_id] = self._uids.pop(old_session_id, old_session_id)
        if self._active_session_id == old_session_id:
            self._active_session_id = new_session_id

    @staticmethod
    def is_draft(session_id: str) -> bool:
        """Return whether a key belongs to a session that has not been saved yet."""
        return session_id.startswith(DRAFT_PREFIX)


session_registry = SessionRegistry()
