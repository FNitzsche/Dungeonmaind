import { SERVER_CONFIG } from '@/config/config'

/** Identity of the session the backend is currently running. */
export interface SessionInfo {
  /** Key to send with every timeline, map, transcription and question request. */
  session_id: string
  /** Whether the session has been saved under a campaign. */
  saved: boolean
  campaign_name: string | null
  session_name: string | null
}

async function readSessionInfo(res: Response): Promise<SessionInfo> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const body = (await res.json()) as Partial<SessionInfo> | null
  if (!body || typeof body.session_id !== 'string' || !body.session_id.trim()) {
    throw new Error('Backend did not report an active session')
  }
  return {
    session_id: body.session_id,
    saved: Boolean(body.saved),
    campaign_name: body.campaign_name ?? null,
    session_name: body.session_name ?? null,
  }
}

/**
 * Ask the backend which session is active. Every device at the table gets the
 * same answer, so they all read and write the same session.
 */
export async function getCurrentSession(): Promise<SessionInfo> {
  const res = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.SESSION_CURRENT}`)
  return readSessionInfo(res)
}

/**
 * Start a new, empty session on the backend. Nothing is deleted; the previous
 * session keeps its data under its own key.
 */
export async function startNewSession(): Promise<SessionInfo> {
  const res = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.SESSION_NEW}`, {
    method: 'POST',
  })
  return readSessionInfo(res)
}
