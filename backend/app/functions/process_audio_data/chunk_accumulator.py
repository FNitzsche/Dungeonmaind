from __future__ import annotations
import asyncio
from pathlib import Path
import shutil
import tempfile
import os
from typing import List

class AudioChunkAccumulator:
    def __init__(self, target_ms: int):
        self.target_ms = target_ms
        self.base = Path(tempfile.gettempdir()) / "live_audio_chunks"
        self.base.mkdir(parents=True, exist_ok=True)
        self._durations: dict[str, int] = {}         # session_id -> total ms
        self._locks: dict[str, asyncio.Lock] = {}    # per-session lock
        self._glock = asyncio.Lock()

    async def _lock_for(self, session_id: str) -> asyncio.Lock:
        async with self._glock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
            return self._locks[session_id]

    def _session_dir(self, session_id: str) -> Path:
        p = self.base / session_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    async def add_chunk(
        self,
        *,
        session_id: str,
        chunk_index: int,
        data: bytes,
        filename: str,
        duration_ms: int | None,
    ) -> bool:
        """Save chunk on disk; return True when total duration >= target."""
        lock = await self._lock_for(session_id)
        async with lock:
            ext = Path(filename).suffix or ".webm"
            path = self._session_dir(session_id) / f"{chunk_index:09d}{ext}"
            path.write_bytes(data)

            total = self._durations.get(session_id, 0)
            if duration_ms and duration_ms > 0:
                total += int(duration_ms)
            self._durations[session_id] = total

            # Only trigger when we actually have >= target_ms accumulated.
            return total >= self.target_ms

    async def list_chunks(self, session_id: str) -> List[Path]:
        lock = await self._lock_for(session_id)
        async with lock:
            d = self._session_dir(session_id)
            return sorted([p for p in d.iterdir() if p.is_file()], key=lambda p: p.name)

    async def clear_session(self, session_id: str) -> None:
        lock = await self._lock_for(session_id)
        async with lock:
            d = self._session_dir(session_id)
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
            self._durations.pop(session_id, None)

# Use env to pick 5 or 10 minutes etc.
_target_ms = int(os.getenv("LIVE_TARGET_MS", "300000"))  # default 5 min
accumulator = AudioChunkAccumulator(target_ms=_target_ms)
