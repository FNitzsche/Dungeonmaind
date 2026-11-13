"""Save and load a session's transcript, timeline and map as JSON files.

A saved session folder holds three files next to group.json, settings.json
and chroma_db:

- ``transcript.json`` — start, end, text and speaker for each segment.
- ``timeline.json`` — the session's timeline events.
- ``map.json`` — the session's resolved map locations and edges.

This module deliberately has no web-framework imports so it can be used and
tested on its own; the router translates :class:`SessionFileError` into an
HTTP response.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from uuid import uuid4

from app.domain.map_edge import MapEdge
from app.domain.map_location import MapLocation
from app.domain.map_store import map_store
from app.domain.models import TimelineEvent
from app.domain.timeline_store import timeline_store
from app.domain.transcript_store import TranscriptSegment, transcript_store

TRANSCRIPT_FILE = 'transcript.json'
TIMELINE_FILE = 'timeline.json'
MAP_FILE = 'map.json'
SESSION_FILES = (TRANSCRIPT_FILE, TIMELINE_FILE, MAP_FILE)

FORMAT_VERSION = 1

# Session key the frontend uses until a campaign and session name are saved.
UNSAVED_SESSION_ID = 'unsaved'


class SessionFileError(Exception):
    """A session file could not be written, read or understood."""


@dataclass
class SessionFiles:
    """Parsed contents of a saved session's transcript, timeline and map.

    Attributes:
        segments: Transcript segments in spoken order.
        events: Timeline events.
        map_generated: Whether a map had been generated when the session was saved.
        locations: Resolved map locations.
        edges: Inferred map edges.
    """

    segments: list[TranscriptSegment] = field(default_factory=list)
    events: list[TimelineEvent] = field(default_factory=list)
    map_generated: bool = False
    locations: list[MapLocation] = field(default_factory=list)
    edges: list[MapEdge] = field(default_factory=list)


def build_session_id(campaign_name: str, session_name: str) -> str:
    """Build the campaign/session key used by the timeline, map and transcript stores.

    Mirrors ``buildSessionId`` in the frontend (``campaignName/sessionName``).
    """
    return f'{campaign_name.strip()}/{session_name.strip()}'


def _write_json(folder_path: str, file_name: str, data: dict) -> None:
    """Write one JSON file, replacing any previous version in a single step."""
    file_path = os.path.join(folder_path, file_name)
    temp_path = f'{file_path}.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(temp_path, file_path)
    except (OSError, TypeError, ValueError) as exc:
        with contextlib.suppress(OSError):
            if os.path.exists(temp_path):
                os.remove(temp_path)
        raise SessionFileError(f'Could not save {file_name}: {exc}') from exc


def _read_json(folder_path: str, file_name: str) -> dict | None:
    """Read one JSON file; returns None when the file does not exist."""
    file_path = os.path.join(folder_path, file_name)
    if not os.path.isfile(file_path):
        return None
    try:
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise SessionFileError(f'Could not read {file_name}: {exc}') from exc
    if not isinstance(data, dict):
        raise SessionFileError(f'{file_name} has an unexpected format')
    return data


def _items(data: dict | None, key: str, file_name: str) -> list[dict]:
    """Return the list stored under ``key``, validating its shape."""
    if data is None:
        return []
    items = data.get(key, [])
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise SessionFileError(f'{file_name} has an unexpected format')
    return items


async def write_session_files(
    folder_path: str, session_id: str, stored_session_id: str | None = None
) -> None:
    """Write transcript.json, timeline.json and map.json for one session.

    Args:
        folder_path: Existing directory the three files are written into.
        session_id: Store key the data is currently held under.
        stored_session_id: Session ID recorded inside the files. Defaults to
            ``session_id``.

    Raises:
        SessionFileError: If any of the three files could not be written.
    """
    stored_id = stored_session_id or session_id
    segments = await transcript_store.get_segments(session_id)
    events = await timeline_store.get_session_events(session_id)
    locations = await map_store.get_locations(session_id)
    edges = await map_store.get_edges(session_id)

    def with_session(item: dict) -> dict:
        return {**item, 'session_id': stored_id}

    _write_json(
        folder_path,
        TRANSCRIPT_FILE,
        {
            'version': FORMAT_VERSION,
            'session_id': stored_id,
            'segments': [segment.to_dict() for segment in segments],
        },
    )
    _write_json(
        folder_path,
        TIMELINE_FILE,
        {
            'version': FORMAT_VERSION,
            'session_id': stored_id,
            'events': [with_session(event.to_dict()) for event in events],
        },
    )
    _write_json(
        folder_path,
        MAP_FILE,
        {
            'version': FORMAT_VERSION,
            'session_id': stored_id,
            'generated': locations is not None,
            'locations': [with_session(location.to_dict()) for location in locations or []],
            'edges': [with_session(edge.to_dict()) for edge in edges or []],
        },
    )


def read_session_files(folder_path: str) -> SessionFiles:
    """Read and validate a saved session's transcript, timeline and map.

    Nothing is changed in the stores, so a caller can validate a folder
    before importing anything from it. A file that does not exist counts as
    empty, which keeps sessions saved before these files existed loadable.

    Args:
        folder_path: The saved session directory.

    Returns:
        The parsed session files.

    Raises:
        SessionFileError: If a file exists but cannot be read or understood.
    """
    transcript_data = _read_json(folder_path, TRANSCRIPT_FILE)
    timeline_data = _read_json(folder_path, TIMELINE_FILE)
    map_data = _read_json(folder_path, MAP_FILE)

    try:
        segments = [
            TranscriptSegment.from_dict(item)
            for item in _items(transcript_data, 'segments', TRANSCRIPT_FILE)
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionFileError(f'{TRANSCRIPT_FILE} has an invalid segment: {exc}') from exc

    try:
        events = [
            TimelineEvent.from_dict({'session_id': '', **item})
            for item in _items(timeline_data, 'events', TIMELINE_FILE)
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionFileError(f'{TIMELINE_FILE} has an invalid event: {exc}') from exc

    try:
        locations = [
            MapLocation.from_dict({'session_id': '', **item})
            for item in _items(map_data, 'locations', MAP_FILE)
        ]
        edges = [
            MapEdge.from_dict({'session_id': '', **item})
            for item in _items(map_data, 'edges', MAP_FILE)
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionFileError(f'{MAP_FILE} has an invalid location or edge: {exc}') from exc

    map_generated = bool(map_data.get('generated', bool(locations))) if map_data else False
    return SessionFiles(
        segments=segments,
        events=events,
        map_generated=map_generated,
        locations=locations,
        edges=edges,
    )


async def apply_session_files(files: SessionFiles, session_id: str) -> None:
    """Load parsed session files into the transcript, timeline and map stores.

    Whatever the stores held for ``session_id`` is replaced.

    Args:
        files: Parsed session files from :func:`read_session_files`.
        session_id: Store key the data is loaded under.
    """
    await transcript_store.replace_session(session_id, files.segments)
    await timeline_store.replace_session(session_id, files.events)
    if files.map_generated:
        for item in (*files.locations, *files.edges):
            item.session_id = session_id
        await map_store.save_map(session_id, files.locations, files.edges)
    else:
        await map_store.clear_session(session_id)


async def load_session_files(folder_path: str, session_id: str) -> SessionFiles:
    """Read a saved session's files and load them into the stores.

    Args:
        folder_path: The saved session directory.
        session_id: Store key the data is loaded under.

    Returns:
        The parsed session files that were loaded.

    Raises:
        SessionFileError: If a file cannot be read; the stores are untouched.
    """
    files = read_session_files(folder_path)
    await apply_session_files(files, session_id)
    return files


async def rekey_session(old_session_id: str, new_session_id: str) -> None:
    """Move a session's transcript, timeline and map to a new session ID."""
    await transcript_store.rename_session(old_session_id, new_session_id)
    await timeline_store.rename_session(old_session_id, new_session_id)
    await map_store.rename_session(old_session_id, new_session_id)


async def save_session_folder(
    campaign_folder_path: str,
    session_name: str,
    source_session_id: str,
    target_session_id: str,
    writers: Sequence[Callable[[str], None]] = (),
) -> str:
    """Save a whole session folder so that it either fully exists or not at all.

    Everything is first written into a hidden staging folder inside the
    campaign folder. Only when every writer and all three session files
    succeeded is the staging folder moved into place (replacing an older
    save of the same name). If anything fails, the staging folder is removed,
    an older save is left as it was, and the error is raised.

    After a successful save the in-memory transcript, timeline and map are
    moved from ``source_session_id`` to ``target_session_id``, so the saved
    session keeps showing them under its new key.

    Args:
        campaign_folder_path: Existing campaign directory.
        session_name: Name of the session folder to create inside it.
        source_session_id: Store key the session data is currently held under.
        target_session_id: Store key of the saved session.
        writers: Functions that each write part of the save (group, settings,
            ChromaDB) into the folder path they are given. They run in a
            worker thread, in order.

    Returns:
        Absolute path of the saved session folder.

    Raises:
        SessionFileError: If a session file or the final move failed.
        Exception: Whatever a writer raised, unchanged.
    """
    session_folder_path = os.path.join(campaign_folder_path, session_name)
    token = uuid4().hex[:8]
    staging_path = os.path.join(campaign_folder_path, f'.{session_name}.saving-{token}')
    backup_path = os.path.join(campaign_folder_path, f'.{session_name}.replaced-{token}')

    try:
        os.makedirs(staging_path)
    except OSError as exc:
        raise SessionFileError(f'Could not create session folder: {exc}') from exc

    try:
        for writer in writers:
            await asyncio.to_thread(writer, staging_path)
        await write_session_files(
            staging_path, source_session_id, stored_session_id=target_session_id
        )
    except BaseException:
        shutil.rmtree(staging_path, ignore_errors=True)
        raise

    had_previous_save = os.path.exists(session_folder_path)
    try:
        if had_previous_save:
            os.rename(session_folder_path, backup_path)
        os.rename(staging_path, session_folder_path)
    except OSError as exc:
        if had_previous_save and not os.path.exists(session_folder_path):
            with contextlib.suppress(OSError):
                os.rename(backup_path, session_folder_path)
        shutil.rmtree(staging_path, ignore_errors=True)
        raise SessionFileError(f'Could not finish saving the session: {exc}') from exc

    if had_previous_save:
        shutil.rmtree(backup_path, ignore_errors=True)

    await rekey_session(source_session_id, target_session_id)
    return session_folder_path
