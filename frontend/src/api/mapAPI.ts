import { SERVER_CONFIG } from '@/config/config'

export type MapRelation =
  | 'north_of'
  | 'south_of'
  | 'east_of'
  | 'west_of'
  | 'near'
  | 'inside'
  | 'contains'
  | 'connected_to'
  | 'travelled_to'

// Provisional #46 contract: string IDs, integer mention counts, session-relative
// timestamps in seconds, and plain-text evidence. Keep assumptions here.
export interface MapNode {
  id: string
  name: string
  mentions: number
  first_seen: number
  last_seen: number
}

export interface MapEdge {
  id: string
  source: string
  target: string
  relation: MapRelation
  evidence: string
  timestamp: number
}

export interface MapData {
  nodes: MapNode[]
  edges: MapEdge[]
  source_segment_count: number
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function isTimestamp(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

const relations: MapRelation[] = [
  'north_of',
  'south_of',
  'east_of',
  'west_of',
  'near',
  'inside',
  'contains',
  'connected_to',
  'travelled_to',
]

function isMapNode(value: unknown): value is MapNode {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.name === 'string' &&
    isCount(value.mentions) &&
    isTimestamp(value.first_seen) &&
    isTimestamp(value.last_seen)
  )
}

function isMapEdge(value: unknown): value is MapEdge {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.source === 'string' &&
    typeof value.target === 'string' &&
    relations.some((relation) => relation === value.relation) &&
    typeof value.evidence === 'string' &&
    isTimestamp(value.timestamp)
  )
}

// #49 does not define a response envelope. Assume both endpoints return MapData
// directly, including empty arrays when no map exists. Adapt this boundary when
// the backend contract is final, rather than spreading wire-format assumptions.
export function parseMapData(value: unknown): MapData {
  if (
    !isRecord(value) ||
    !Array.isArray(value.nodes) ||
    !value.nodes.every(isMapNode) ||
    !Array.isArray(value.edges) ||
    !value.edges.every(isMapEdge) ||
    !isCount(value.source_segment_count)
  ) {
    throw new Error(
      'The backend returned an unsupported map format. Please check the map API version.',
    )
  }

  return {
    nodes: value.nodes,
    edges: value.edges,
    source_segment_count: value.source_segment_count,
  }
}

async function parseError(response: Response): Promise<string> {
  const fallback =
    response.status === 404 || response.status === 501
      ? 'The geographic map API is not available on this backend yet.'
      : `Map request failed (HTTP ${response.status}). Please try again.`

  try {
    const body: unknown = await response.json()
    if (isRecord(body)) {
      const detail = body.detail ?? body.message
      if (typeof detail === 'string' && detail.trim()) {
        return `${fallback} ${detail}`
      }
      // FastAPI validation errors use an array of objects with msg fields.
      if (Array.isArray(detail)) {
        const messages = detail
          .filter(isRecord)
          .map((item) => item.msg)
          .filter((message): message is string => typeof message === 'string')
        if (messages.length) return `${fallback} ${messages.join('; ')}`
      }
    }
  } catch {
    // Empty/non-JSON error bodies still get an understandable status message.
  }

  return fallback
}

async function requestMap(endpoint: string, method: 'GET' | 'POST'): Promise<MapData> {
  let response: Response
  try {
    response = await fetch(`${SERVER_CONFIG.BASE_URL}${endpoint}`, { method })
  } catch {
    throw new Error(
      'Cannot reach the map backend. Check the backend address and connection, then try again.',
    )
  }

  if (!response.ok) throw new Error(await parseError(response))

  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new Error('The backend returned an unreadable map response. Expected JSON map data.')
  }
  return parseMapData(body)
}

export async function fetchMap(): Promise<MapData> {
  return requestMap(SERVER_CONFIG.ENDPOINTS.MAP, 'GET')
}

// No body or session identifier is specified in #49; use the current backend
// session, consistent with the existing timeline client.
export async function generateMap(): Promise<MapData> {
  return requestMap(SERVER_CONFIG.ENDPOINTS.MAP_GENERATE, 'POST')
}
