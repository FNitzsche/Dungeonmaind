# TimelineEvent Model Implementation Plan

## Changes

### 1. `backend/app/domain/models.py`
- Add `TimelineEventType` enum
- Add `TimelineEvent` dataclass

### 2. `backend/app/base_models/timeline_base_models.py` (new)
- `TimelineEventOut` Pydantic schema
- `TimelineEventListResponse` wrapper

### 3. `backend/app/domain/timeline_store.py` (new)
- `TimelineStore` in-memory store
- Global `timeline_store` singleton

### 4. `backend/app/api/mappers/timeline_mapper.py` (new)
- `timeline_event_to_out()` mapper function

### 5. `backend/app/api/routers/timeline.py` (new)
- `GET /timeline/events` — list events by session
- `GET /timeline/events/{event_id}` — get single event
- `DELETE /timeline/events/{event_id}` — delete event
- `DELETE /timeline/events?session_id=...` — clear session events

### 6. `backend/app/main.py`
- Register timeline router

### 7. `frontend/src/api/timelineAPI.ts` (new)
- TypeScript types + API client

### 8. `frontend/src/stores/timeline.ts` (new)
- Pinia store

### 9. `frontend/src/config/config.ts`
- Add timeline endpoints

### 10. `frontend/src/router/index.ts`
- Add `/timeline` route
