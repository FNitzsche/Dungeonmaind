import { SERVER_CONFIG } from '@/config/config'

export type TimelineCategory =
  | 'travel'
  | 'combat'
  | 'dialogue'
  | 'discovery'
  | 'rest'
  | 'quest'
  | 'item'
  | 'other'

export interface TimelineSourceSegment {
  text: string
  speaker: string
  start_time: number
  end_time: number
}

export interface TimelineEvent {
  id: string
  title: string
  description: string
  category: TimelineCategory
  start_time: number
  end_time: number
  speakers: string[]
  locations: string[]
  temporal_entities: string[]
  source_segments: TimelineSourceSegment[]
  created_automatically: boolean
  created_at: string
  updated_at: string
}

export interface TimelineResponse {
  events: TimelineEvent[]
  total: number
}

export interface TimelineGenerationResponse {
  events: TimelineEvent[]
  generated_count: number
  source_segment_count: number
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json()

    if (typeof body?.detail === 'string') {
      return body.detail
    }

    return JSON.stringify(body)
  } catch {
    return `Request failed with status ${response.status}`
  }
}

export async function fetchTimelineEvents(): Promise<TimelineResponse> {
  const response = await fetch(
    `${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.TIMELINE_EVENTS}`,
  )

  if (!response.ok) {
    throw new Error(await parseError(response))
  }

  return response.json()
}

export async function generateTimeline(): Promise<TimelineGenerationResponse> {
  const response = await fetch(
    `${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.TIMELINE_GENERATE}`,
    {
      method: 'POST',
    },
  )

  if (!response.ok) {
    throw new Error(await parseError(response))
  }

  return response.json()
}

export async function seedTimelineSample(): Promise<void> {
  const response = await fetch(
    `${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.TIMELINE_SEED_SAMPLE}`,
    {
      method: 'POST',
    },
  )

  if (!response.ok) {
    throw new Error(await parseError(response))
  }
}