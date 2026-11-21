"""Seed a rich demo timeline, then run the API so the Map page populates.

The frontend Map page currently loads via Mansa's timeline fallback
(buildMapFromTimeline), which reads each event's location_entities from
GET /timeline/events and infers nodes + edges client-side. Seeding those
events here is enough to see a populated map — no audio or LLM needed.

Run:  cd backend && ../.venv/bin/python seed_timeline_demo.py
Then open the frontend, log in, and go to the Map page.

The journey below is designed to show every behaviour:
  - a multi-stop travel path (arrows between places)
  - an alias merge  ("the tavern" folds into "Ye Olde Tavern")
  - a proximity link (two places named in the same event)
  - a return leg     (back to a place visited earlier)
"""

import asyncio

import uvicorn

from app.domain.models import TimelineEvent, TimelineEventType
from app.domain.timeline_store import timeline_store
from app.main import app

SESSION_ID = 'default'


def _event(event_id, order, event_type, title, display_time, places):
    return TimelineEvent(
        id=event_id,
        session_id=SESSION_ID,
        title=title,
        description=title,
        event_type=event_type,
        order=order,
        timestamp=str(order),
        display_time=display_time,
        location_entities=places,
    )


EVENTS = [
    _event(
        'evt_1',
        1,
        TimelineEventType.travel,
        'Departure from Velmora Crossing',
        '06:45 AM',
        ['Velmora Crossing'],
    ),
    _event(
        'evt_2',
        2,
        TimelineEventType.discovery,
        'A hidden trail at Silver Lake',
        '12:00 PM',
        ['Silver Lake'],
    ),
    _event(
        'evt_3',
        3,
        TimelineEventType.rest,
        'Resting at Ye Olde Tavern',
        '07:30 PM',
        ['Ye Olde Tavern'],
    ),
    _event(
        'evt_4',
        4,
        TimelineEventType.dialogue,
        'Dragon rumours at the tavern',
        '08:15 PM',
        ['the tavern'],
    ),
    _event(
        'evt_5',
        5,
        TimelineEventType.travel,
        "Climb toward Dragon's Peak",
        '09:00 AM',
        ["Dragon's Peak"],
    ),
    _event(
        'evt_6',
        6,
        TimelineEventType.discovery,
        'The Old Watchtower beside the peak',
        '11:20 AM',
        ["Dragon's Peak", 'Old Watchtower'],
    ),
    _event(
        'evt_7',
        7,
        TimelineEventType.quest,
        'Return to Velmora Crossing',
        '05:00 PM',
        ['Velmora Crossing'],
    ),
]


async def _seed():
    await timeline_store.clear_all()
    added = await timeline_store.add_events(EVENTS)
    print(f'Seeded {len(added)} timeline events into session "{SESSION_ID}".')


if __name__ == '__main__':
    asyncio.run(_seed())
    print('---')
    print('Backend API:   http://localhost:8000/docs')
    print('Timeline feed: http://localhost:8000/timeline/events?session_id=default')
    print('My edges:      http://localhost:8000/map/edges?session_id=default')
    print('Now open the frontend (npm run dev), log in, and open the Map page.')
    print('---')
    uvicorn.run(app, host='0.0.0.0', port=8000)
