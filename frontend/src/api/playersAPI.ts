import { SERVER_CONFIG } from '@/config/config'

export type Role = 'leader' | 'member'
export type PlayerStatus = 'active' | 'inactive' | 'kicked'

/** Object mapping ability score keys to values (with extra unknown fields allowed). */
export type AbilityScores = {
  str?: number
  dex?: number
  con?: number
  int_?: number
  wis?: number
  cha?: number
} & Record<string, number | string | undefined>

/** Hit-point values for a player: current, max, and temporary HP. */
export type Hp = {
  current: number
  max: number
  temp: number
}

/** Full player object as returned and expected by the server. */
export type PlayerOut = {
  id: string
  name: string
  role: Role
  created_at: string
  last_seen_at: string
  backend_url: string
  status: PlayerStatus
  hp: Hp
  abilities?: AbilityScores | { [k: string]: any } | undefined
}

/** Valid ability score keys. */
export type AbilityKey = 'str' | 'dex' | 'con' | 'int_' | 'wis' | 'cha'

function base(baseUrl?: string): string {
  return baseUrl ?? SERVER_CONFIG.BASE_URL
}

/**
 * Join the group as leader or member.
 * Supports optional reuseId for re-joining an inactive player.
 */
export async function join(
  name: string,
  role: Role,
  reuseId?: string,
  baseUrl?: string,
): Promise<PlayerOut> {
  const url = new URL('/players', base(baseUrl)).toString()

  const payload: any = { name, role }
  if (reuseId) {
    payload.reuse_id = reuseId
  }

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText)
    throw new Error(msg || `HTTP ${res.status}`)
  }

  return (await res.json()) as PlayerOut
}

/**
 * Leave the group.
 */
export async function leave(playerId: string, baseUrl?: string): Promise<void> {
  const url = new URL(`/players/${playerId}`, base(baseUrl)).toString()
  const res = await fetch(url, { method: 'DELETE' })

  if (!res.ok && res.status !== 204) {
    throw new Error(`HTTP ${res.status}`)
  }
}

/**
 * List players.
 * - includeInactive=false -> only active players
 * - includeInactive=true  -> all players (used for "Join existing player" flow)
 */
export async function listPlayers(includeInactive = false, baseUrl?: string): Promise<PlayerOut[]> {
  const urlObj = new URL('/players', base(baseUrl))
  if (includeInactive) {
    urlObj.searchParams.set('include_inactive', 'true')
  }

  const res = await fetch(urlObj.toString())

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }

  return (await res.json()) as PlayerOut[]
}

/**
 * Update a player's max HP.
 * Returns the updated player.
 */
export async function updateMaxHp(
  playerId: string,
  newMax: number,
  baseUrl?: string,
): Promise<PlayerOut> {
  const url = new URL(`/players/${playerId}/health/max`, base(baseUrl)).toString()

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ max: newMax }),
  })

  if (!res.ok) {
    throw new Error(`Failed to update max HP: HTTP ${res.status}`)
  }

  return (await res.json()) as PlayerOut
}

/**
 * Apply damage to a player.
 */
export async function damagePlayer(
  playerId: string,
  amount: number,
  baseUrl?: string,
): Promise<void> {
  const url = new URL(`/players/${playerId}/damage`, base(baseUrl)).toString()

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ damage: amount }),
  })

  if (!res.ok) {
    throw new Error(`Failed to apply damage: HTTP ${res.status}`)
  }
}

/**
 * Heal a player.
 */
export async function healPlayer(
  playerId: string,
  amount: number,
  baseUrl?: string,
): Promise<void> {
  const url = new URL(`/players/${playerId}/heal`, base(baseUrl)).toString()

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ heal: amount }),
  })

  if (!res.ok) {
    throw new Error(`Failed to heal: HTTP ${res.status}`)
  }
}

/**
 * Patch a single ability score.
 * Uses X-Player-Id for self-authorization.
 */
export async function patchPlayerAbility(
  playerId: string,
  key: AbilityKey,
  value: number,
  baseUrl?: string,
): Promise<void> {
  const url = new URL(`/players/${playerId}`, base(baseUrl)).toString()

  const res = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-Player-Id': playerId,
    },
    body: JSON.stringify({ [key]: value }),
  })

  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText)
    throw new Error(msg || `Ability PATCH failed: HTTP ${res.status}`)
  }
}

/**
 * Kick a player.
 * Requires the caller (actorId) to be an active leader.
 * Backend checks X-Player-Id.
 */
export async function kickPlayer(
  playerId: string,
  actorId: string,
  baseUrl?: string,
): Promise<void> {
  const url = new URL(`/players/${playerId}/kick`, base(baseUrl)).toString()

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'X-Player-Id': actorId,
    },
    credentials: 'include',
  })

  if (!res.ok && res.status !== 204) {
    const msg = await res.text().catch(() => res.statusText)
    throw new Error(msg || `Kick failed: HTTP ${res.status}`)
  }
}

/**
 * Upload a voiceprint audio blob for a player.
 */
export async function postPlayerVoiceprint(playerId: string, voiceprint: Blob, baseUrl: string) {
  const fileExtension = voiceprint.type.split('/')[1]?.split(';')[0] || 'ogg'
  const url = new URL(`/players/${playerId}/voiceprint`, base(baseUrl)).toString()

  const formData = new FormData()
  formData.append('audio', voiceprint, `voiceprint.${fileExtension}`)
  const res = await fetch(url, {
    method: 'POST',
    body: formData,
    headers: {
      'X-Player-Id': playerId,
    },
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText)
    throw new Error(msg || `Failed to upload voiceprint: HTTP ${res.status}`)
  }
}

/**
 * Check if a player exists.
 */
export async function checkPlayerExists(
  playerId: string,
  baseUrl?: string,
): Promise<{ exists: boolean }> {
  const url = new URL(`/players/${playerId}/exists`, base(baseUrl)).toString()
  const res = await fetch(url)

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }

  return res.json()
}
