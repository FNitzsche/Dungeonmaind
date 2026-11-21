import { SERVER_CONFIG } from '@/config/config'

/** Payload shape for submitting configuration changes to the backend. */
export type Payload = {
  player_id?: string | undefined
  selected_LLM: string
  transcription_model: string
  embedding_model: string
  embedding_top_k: string
  clear_chat: boolean
  delete_transcriptions: boolean
}

/**
 * Fetch the current backend configuration (LLM, transcription, embedding models).
 * @returns The raw config JSON from the server.
 */
export async function fetchConfig() {
  const res = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.GET_CONFIG}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch config: ${res.status}`)
  }
  return res.json()
}

/**
 * Read the backend's `detail` message from a failed response, so the page can
 * show why a configuration change was rejected instead of a bare status code.
 * @param response - The failed response.
 */
async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string' && body.detail.trim()) {
      return body.detail
    }
  } catch {
    // Keep the status when the backend did not return JSON.
  }
  return `Request failed with status ${response.status}`
}

/**
 * Submit configuration changes to the backend.
 * @param payload - The configuration values to send.
 */
export async function submitConfig(payload: Payload) {
  const response = await fetch(
    `${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.CHANGE_CONFIG}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    },
  )

  if (!response.ok) {
    throw new Error(await readErrorMessage(response))
  }
}
