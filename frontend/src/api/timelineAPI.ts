import { SERVER_CONFIG } from '@/config/config'

/** The category of a timeline event. */
export type EventType = 'combat' | 'discovery' | 'dialogue' | 'travel' | 'rest' | 'quest' | 'other'

/** A single timeline event entry returned by the backend. */
export interface TimelineEventOut {
  id: string
  session_id: string
  title: string
  description: string
  event_type: EventType
  order: number
  timestamp: number
  transcription_chunk_id: string | null
  player_id: string | null
  speaker_name: string | null
  temporal_entities: string[]
  location_entities: string[]
  characters: string[]
  display_time: string | null
  created_at: string
}

/** Response shape for listing timeline events. */
export interface TimelineEventListResponse {
  session_id: string
  events: TimelineEventOut[]
  total: number
}

/** Response shape for generating timeline events from session data. */
export interface TimelineGenerateResponse {
  session_id: string
  events_generated: number
  events: TimelineEventOut[]
}

function base(): string {
  return SERVER_CONFIG.BASE_URL
}

async function throwTimelineError(res: Response): Promise<never> {
  let message = `HTTP ${res.status}`
  try {
    const body = await res.json()
    if (typeof body.detail === 'string' && body.detail.trim()) {
      message = body.detail
    }
  } catch {
    // Keep the HTTP status when the backend does not return JSON.
  }
  throw new Error(message)
}

/**
 * Fetch all timeline events for a given session.
 * @param sessionId - The session identifier (defaults to 'default').
 */
export async function listEvents(sessionId = 'default'): Promise<TimelineEventListResponse> {
  const url = new URL('/timeline/events', base())
  url.searchParams.set('session_id', sessionId)
  const res = await fetch(url.toString())
  if (!res.ok) await throwTimelineError(res)
  return (await res.json()) as TimelineEventListResponse
}

/**
 * Fetch a single timeline event by its ID.
 * @param eventId - The event's unique identifier.
 */
export async function getEvent(eventId: string): Promise<TimelineEventOut> {
  const res = await fetch(`${base()}/timeline/events/${encodeURIComponent(eventId)}`)
  if (!res.ok) await throwTimelineError(res)
  return (await res.json()) as TimelineEventOut
}

/**
 * Delete a single timeline event by its ID.
 * @param eventId - The event's unique identifier.
 */
export async function deleteEvent(eventId: string): Promise<void> {
  const res = await fetch(`${base()}/timeline/events/${encodeURIComponent(eventId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) await throwTimelineError(res)
}

/**
 * Delete all timeline events for a session.
 * @param sessionId - The session identifier (defaults to 'default').
 */
export async function clearSessionEvents(sessionId = 'default'): Promise<void> {
  const url = new URL('/timeline/events', base())
  url.searchParams.set('session_id', sessionId)
  const res = await fetch(url.toString(), { method: 'DELETE' })
  if (!res.ok) await throwTimelineError(res)
}

/**
 * Trigger the backend to generate timeline events from transcribed session data.
 * @param sessionId - The session identifier (defaults to 'default').
 */
export async function generateEvents(sessionId = 'default'): Promise<TimelineGenerateResponse> {
  const res = await fetch(`${base()}/timeline/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!res.ok) await throwTimelineError(res)
  return (await res.json()) as TimelineGenerateResponse
}
