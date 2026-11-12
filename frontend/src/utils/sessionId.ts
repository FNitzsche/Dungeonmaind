/** Session key used until a campaign and session name have been saved. */
export const UNSAVED_SESSION_ID = 'unsaved'

/**
 * Build the campaign/session key used by timeline, map, and transcription APIs.
 * Matches SavedSessions folder paths: `campaignName/sessionName`.
 */
export function buildSessionId(
  campaignName: string | null | undefined,
  sessionName: string | null | undefined,
): string {
  const campaign = campaignName?.trim() ?? ''
  const session = sessionName?.trim() ?? ''
  if (!campaign || !session) return UNSAVED_SESSION_ID
  return `${campaign}/${session}`
}
