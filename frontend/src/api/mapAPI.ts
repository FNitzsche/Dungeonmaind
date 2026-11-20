import { SERVER_CONFIG } from '@/config/config'
import { UNSAVED_SESSION_ID } from '@/utils/sessionId'

/** Edge types between places on the campaign map. */
export type MapEdgeType = 'traveled' | 'near' | 'north_of' | 'inside' | 'other'

/** A place node on the session map. */
export interface MapNode {
  id: string
  label: string
  aliases?: string[]
  event_ids?: string[]
}

/** Backend vocabulary for a stored map link. */
export type MapRelationship = 'travel' | 'proximity'

/** A connection between two places. */
export interface MapEdge {
  from: string
  to: string
  type: MapEdgeType
}

/** The map graph the views consume, assembled from the backend endpoints. */
export interface MapGraphResponse {
  session_id: string
  nodes: MapNode[]
  edges: MapEdge[]
}

/** Timeline events linked to a single place. */
export interface MapPlaceEventsResponse {
  place_id: string
  event_ids: string[]
}

/** A resolved place as returned by GET /map/locations. */
interface MapLocationOut {
  id: string
  canonical_name: string
  aliases?: string[]
  event_ids?: string[]
}

/** An inferred link as returned by GET /map/edges. */
interface MapEdgeOut {
  from_location_id: string
  to_location_id: string
  relationship: string
}

/**
 * Translate the backend's relationship vocabulary (`travel` | `proximity`)
 * into the edge types the map legend renders.
 */
function toEdgeType(relationship: string): MapEdgeType {
  switch (relationship) {
    case 'travel':
      return 'traveled'
    case 'proximity':
      return 'near'
    default:
      return 'other'
  }
}

function base(): string {
  return SERVER_CONFIG.BASE_URL
}

async function throwMapError(res: Response): Promise<never> {
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

/** GET `path` with a `session_id` query parameter and decode the JSON body. */
async function getJson<T>(path: string, sessionId: string): Promise<T> {
  const url = new URL(path, base())
  url.searchParams.set('session_id', sessionId)
  const res = await fetch(url.toString())
  if (!res.ok) await throwMapError(res)
  return (await res.json()) as T
}

/**
 * Fetch the session map graph.
 *
 * The backend exposes places and links as two separate collections
 * (`/map/locations` and `/map/edges`), so they are requested together and
 * assembled into the single graph the map view renders.
 * @param sessionId - The session identifier (defaults to 'unsaved').
 */
export async function getMap(sessionId = UNSAVED_SESSION_ID): Promise<MapGraphResponse> {
  const [locations, edges] = await Promise.all([
    getJson<{ locations: MapLocationOut[] }>('/map/locations', sessionId),
    getJson<{ edges: MapEdgeOut[] }>('/map/edges', sessionId),
  ])

  return {
    session_id: sessionId,
    nodes: (locations.locations ?? []).map((location) => ({
      id: location.id,
      label: location.canonical_name,
      ...(location.aliases?.length ? { aliases: location.aliases } : {}),
      ...(location.event_ids?.length ? { event_ids: location.event_ids } : {}),
    })),
    edges: (edges.edges ?? []).map((edge) => ({
      from: edge.from_location_id,
      to: edge.to_location_id,
      type: toEdgeType(edge.relationship),
    })),
  }
}

/**
 * Resolve places and links from the session timeline and save them on the backend.
 * @param sessionId - The session identifier (defaults to 'unsaved').
 */
export async function generateMap(sessionId = UNSAVED_SESSION_ID): Promise<void> {
  const res = await fetch(`${base()}/map/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!res.ok) await throwMapError(res)
}

/**
 * Fetch timeline event ids linked to a place on the map.
 * @param sessionId - The session identifier.
 * @param placeId - The place node id.
 */
function relationshipFromEdgeType(type: MapEdgeType): MapRelationship {
  return type === 'near' ? 'proximity' : 'travel'
}

async function postOverride(path: string, body: Record<string, unknown>): Promise<void> {
  const res = await fetch(`${base()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await throwMapError(res)
}

/** Persist a place rename in map_overrides.json. */
export async function renamePlace(
  sessionId: string,
  locationId: string,
  canonicalName: string,
): Promise<void> {
  await postOverride('/map/overrides/rename', {
    session_id: sessionId,
    location_id: locationId,
    canonical_name: canonicalName,
  })
}

/** Fold source places into a surviving target. */
export async function mergePlaces(
  sessionId: string,
  sourceLocationIds: string[],
  targetLocationId: string,
): Promise<void> {
  await postOverride('/map/overrides/merge', {
    session_id: sessionId,
    source_location_ids: sourceLocationIds,
    target_location_id: targetLocationId,
  })
}

/** Carve a new place out of an existing one. */
export async function splitPlace(
  sessionId: string,
  sourceLocationId: string,
  canonicalName: string,
  eventIds: string[],
): Promise<void> {
  await postOverride('/map/overrides/split', {
    session_id: sessionId,
    source_location_id: sourceLocationId,
    canonical_name: canonicalName,
    event_ids: eventIds,
  })
}

/** Add a link between two places. */
export async function connectPlaces(
  sessionId: string,
  fromLocationId: string,
  toLocationId: string,
  type: MapEdgeType = 'traveled',
): Promise<void> {
  await postOverride('/map/overrides/connect', {
    session_id: sessionId,
    from_location_id: fromLocationId,
    to_location_id: toLocationId,
    relationship: relationshipFromEdgeType(type),
  })
}

/** Remove a link between two places. */
export async function disconnectPlaces(
  sessionId: string,
  fromLocationId: string,
  toLocationId: string,
  type?: MapEdgeType,
): Promise<void> {
  await postOverride('/map/overrides/disconnect', {
    session_id: sessionId,
    from_location_id: fromLocationId,
    to_location_id: toLocationId,
    ...(type ? { relationship: relationshipFromEdgeType(type) } : {}),
  })
}

export async function getPlaceEvents(
  sessionId: string,
  placeId: string,
): Promise<MapPlaceEventsResponse> {
  const body = await getJson<{ events: { id: string }[] }>(
    `/map/locations/${encodeURIComponent(placeId)}/events`,
    sessionId,
  )
  return {
    place_id: placeId,
    event_ids: (body.events ?? []).map((event) => event.id),
  }
}
