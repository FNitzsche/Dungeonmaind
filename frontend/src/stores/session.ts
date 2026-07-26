import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PlayerOut, Role, Hp, AbilityScores } from '@/api/playersAPI'
import * as api from '@/api/playersAPI'

/**
 * Session store – manages current player identity, player roster,
 * backend connection URL, local network IP, and WebSocket-based updates.
 */
export const useSessionStore = defineStore('session', () => {
  /** The locally-authenticated player (hydrated from sessionStorage). */
  const currentPlayer = ref<PlayerOut | null>(hydratePlayer())
  /** Full list of known players (from backend + WebSocket). */
  const players = ref<PlayerOut[]>([])
  /** The backend base URL (persisted in localStorage). */
  const backendUrl = ref<string | null>(hydrateBackendUrl())
  /** Local network IP for QR-code / join-link sharing (persisted). */
  const localNetworkIP = ref<string | null>(hydrateLocalNetworkIP())

  /** Whether the current player has the `leader` role. */
  const isLeader = computed(() => currentPlayer.value?.role === 'leader')

  /** Partial player payload used for WebSocket / PATCH upserts. */
  type PlayerUpsert = Partial<Omit<PlayerOut, 'hp' | 'abilities'>> & {
    hp?: Partial<Hp>
    abilities?: Partial<AbilityScores> | Record<string, unknown>
  }

  /* Internal helpers */

  /**
   * Deep-merge `hp` and `abilities` sub-objects; shallow-merge everything else.
   * @param base - The existing player object.
   * @param incoming - The partial update payload.
   * @returns A new merged PlayerOut-like object.
   */
  function mergePlayers(base: PlayerOut, incoming: PlayerUpsert): PlayerOut {
    return {
      ...base,
      ...incoming,
      hp: incoming.hp ? { ...base.hp, ...incoming.hp } : base.hp,
      abilities: incoming.abilities
        ? {
            ...(base.abilities ?? {}),
            ...(incoming.abilities as Record<string, unknown>),
          }
        : base.abilities,
    }
  }

  /**
   * Insert or update a player in the roster.
   * Also syncs the current player if the ID matches.
   * @param p - Full or partial PlayerOut (must include `id` when partial).
   */
  function upsertPlayer(p: PlayerOut | (PlayerUpsert & { id: string })) {
    const i = players.value.findIndex((x) => x.id === p.id)
    if (i === -1) {
      players.value.push(p as PlayerOut)
    } else {
      players.value[i] = mergePlayers(players.value[i], p)
    }

    if (currentPlayer.value?.id === p.id) {
      currentPlayer.value = mergePlayers(currentPlayer.value, p)
      persistPlayer(currentPlayer.value)
    }
  }

  /**
   * Sync the local `currentPlayer` snapshot with a fresh server list.
   * Keeps the session when the player is temporarily inactive (e.g. after
   * navigating away from Home and before the WebSocket reconnects).
   */
  function syncCurrentFromList(list: PlayerOut[]) {
    const id = currentPlayer.value?.id
    if (!id) return
    const fresh = list.find((p) => p.id === id)
    if (fresh) {
      currentPlayer.value = fresh
      persistPlayer(fresh)
    }
  }

  /**
   * Persist or clear the current player in sessionStorage.
   */
  function persistPlayer(p: PlayerOut | null) {
    try {
      if (p) {
        sessionStorage.setItem('player', JSON.stringify(p))
      } else {
        sessionStorage.removeItem('player')
      }
    } catch {
      // ignore
    }
  }

  /**
   * Persist the backend URL to localStorage.
   */
  function persistBackendUrl(url: string) {
    try {
      localStorage.setItem('backendUrl', url)
    } catch {
      // ignore
    }
  }

  /**
   * Persist or clear the local network IP in localStorage.
   */
  function persistLocalNetworkIP(ip: string | null) {
    try {
      if (ip) {
        localStorage.setItem('localNetworkIP', ip)
      } else {
        localStorage.removeItem('localNetworkIP')
      }
    } catch {
      // ignore
    }
  }

  /**
   * Read and parse the current player from sessionStorage.
   * @returns The deserialized player or null.
   */
  function hydratePlayer(): PlayerOut | null {
    try {
      const raw = sessionStorage.getItem('player')
      return raw ? (JSON.parse(raw) as PlayerOut) : null
    } catch {
      return null
    }
  }

  /**
   * Read the persisted backend URL from localStorage.
   */
  function hydrateBackendUrl(): string | null {
    try {
      return localStorage.getItem('backendUrl')
    } catch {
      return null
    }
  }

  /**
   * Read the persisted local network IP from localStorage.
   */
  function hydrateLocalNetworkIP(): string | null {
    try {
      const raw = localStorage.getItem('localNetworkIP')
      return raw ? raw : null
    } catch {
      return null
    }
  }

  /**
   * Remove the persisted player from sessionStorage.
   */
  function removePersistedPlayer() {
    try {
      sessionStorage.removeItem('player')
    } catch {
      // ignore
    }
  }

  /**
   * Clear all persisted session data (player, backend URL, IP).
   */
  function clearPersist() {
    removePersistedPlayer()
    try {
      localStorage.removeItem('backendUrl')
      localStorage.removeItem('localNetworkIP')
    } catch {
      // ignore
    }
  }

  /* API actions */

  /**
   * Join the session as a new or existing (reuse_id) player.
   * @param name - Display name.
   * @param role - Leader or member.
   * @param reuse_id - Optional ID to reactivate an inactive player.
   * @returns The created/updated player from the backend.
   */
  async function join(name: string, role: Role, reuse_id?: string) {
    const p = await api.join(name, role, reuse_id)
    currentPlayer.value = p
    persistPlayer(p)
    return p
  }

  /**
   * Fetch the full player list from the backend and sync the current player.
   */
  async function loadPlayers() {
    const list = await api.listPlayers()
    players.value = list
    syncCurrentFromList(list)
  }

  /**
   * Leave the session and clear all local state.
   */
  async function leave() {
    if (!currentPlayer.value) return
    try {
      await api.leave(currentPlayer.value.id)
    } finally {
      clearSession()
    }
  }

  /**
   * Overwrite the current player reference and persist it.
   */
  function setCurrentPlayer(p: PlayerOut) {
    currentPlayer.value = p
    persistPlayer(p)
  }

  /**
   * Set the backend URL and persist it.
   */
  function setBackendUrl(url: string) {
    backendUrl.value = url
    persistBackendUrl(url)
  }

  /**
   * Set the local network IP (or clear it) and persist.
   */
  function setLocalNetworkIP(ip: string) {
    if (!ip) {
      localNetworkIP.value = null
      persistLocalNetworkIP(null)
    } else {
      localNetworkIP.value = ip
      persistLocalNetworkIP(ip)
    }
  }

  /* Session / logout helpers */

  /**
   * Clear all session state (current player, roster, connection info, storage).
   */
  function clearSession() {
    currentPlayer.value = null
    players.value = []
    backendUrl.value = null
    localNetworkIP.value = null
    clearPersist()
  }

  /**
   * Force logout – clears session, used on WS close code 4001 (kicked) or connection loss.
   */
  function forceLogout() {
    clearSession()
  }

  /* WebSocket helpers */

  /**
   * Handle a WS `join` message – upsert the joining player.
   */
  function applyWsJoin(p: PlayerOut) {
    upsertPlayer(p)
  }

  /**
   * Handle a WS `leave` message – remove the player from the roster and
   * clear the current player if they left.
   */
  function applyWsLeave(id: string) {
    players.value = players.value.filter((pl) => pl.id !== id)
    if (currentPlayer.value?.id === id) {
      currentPlayer.value = null
      removePersistedPlayer()
    }
  }

  /**
   * Handle a WS `update` message – upsert the player with full or partial data.
   */
  function applyWsUpdate(p: PlayerOut | (PlayerUpsert & { id: string })) {
    upsertPlayer(p)
  }

  /**
   * Apply a partial patch to a player in the local roster and to the current
   * player snapshot if applicable. Does NOT send to the backend.
   */
  function patchPlayer(id: string, patch: PlayerUpsert) {
    const i = players.value.findIndex((p) => p.id === id)
    if (i !== -1) {
      players.value[i] = mergePlayers(players.value[i], patch)
    }
    if (currentPlayer.value?.id === id) {
      currentPlayer.value = mergePlayers(currentPlayer.value, patch)
      persistPlayer(currentPlayer.value)
    }
  }

  /* Expose store */
  return {
    // state
    currentPlayer,
    players,
    backendUrl,
    localNetworkIP,
    // getters
    isLeader,
    // actions
    join,
    loadPlayers,
    leave,
    setCurrentPlayer,
    setBackendUrl,
    setLocalNetworkIP,
    clearSession,
    forceLogout,
    // ws helpers
    applyWsJoin,
    applyWsLeave,
    applyWsUpdate,
    patchPlayer,
  }
})
