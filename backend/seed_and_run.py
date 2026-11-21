"""Seed the in-memory timeline with the worked example, then run the API.

Lets you exercise the map endpoints (locations + edges) end-to-end over
real HTTP without the audio/LLM pipeline. Run: ../.venv/bin/python seed_and_run.py
"""

import asyncio

import uvicorn

from app.domain.models import TimelineEvent
from app.domain.timeline_store import timeline_store
from app.main import app

SESSION_ID = 'default'

EVENTS = [
    TimelineEvent(
        id='evt_1',
        session_id=SESSION_ID,
        title='evt_1',
        description='',
        order=1,
        timestamp='1',
        location_entities=['Velmora Crossing'],
    ),
    TimelineEvent(
        id='evt_2',
        session_id=SESSION_ID,
        title='evt_2',
        description='',
        order=2,
        timestamp='2',
        location_entities=['Silver Lake'],
    ),
    TimelineEvent(
        id='evt_3',
        session_id=SESSION_ID,
        title='evt_3',
        description='',
        order=3,
        timestamp='3',
        location_entities=['Ye Olde Tavern'],
    ),
    TimelineEvent(
        id='evt_4',
        session_id=SESSION_ID,
        title='evt_4',
        description='',
        order=4,
        timestamp='4',
        location_entities=['the tavern'],
    ),
]


async def _seed() -> None:
    await timeline_store.clear_all()
    await timeline_store.add_events(EVENTS)


if __name__ == '__main__':
    asyncio.run(_seed())
    print(
        'Seeded evt_1..evt_4. Try http://localhost:8000/docs '
        'or curl http://localhost:8000/map/edges?session_id=default'
    )
    uvicorn.run(app, host='0.0.0.0', port=8000)
