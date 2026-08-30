import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import * as api from '@/api/playersAPI';
import type { PlayerOut, Role, Hp, AbilityScores } from '@/api/playersAPI';
import { SERVER_CONFIG } from '@/config/config'

export const useSessionStore = defineStore('session', () => {
  /* State */
  const currentPlayer = ref<PlayerOut | null>(hydratePlayer());
  const players = ref<PlayerOut[]>([]);
  const backendUrl = ref<string | null>(hydrateBackendUrl());
  const localNetworkIP = ref<string | null>(hydrateLocalNetworkIP());
  const playerSocket = ref<WebSocket | null>(null)
  const socketManualClose = ref(false)

  /* Getters */
  const isLeader = computed(() => currentPlayer.value?.role === 'leader');

  /* Types for WS/patch upserts */
  type PlayerUpsert =
    Partial<Omit<PlayerOut, 'hp' | 'abilities'>> & {
      hp?: Partial<Hp>;
      abilities?: Partial<AbilityScores> | Record<string, unknown>;
    };

  /* Internal helpers */

  // Deep-merge hp and abilities; shallow-merge everything else
  function mergePlayers(base: PlayerOut, incoming: PlayerUpsert): PlayerOut {
    return {
      ...base,
      ...incoming,
      hp: incoming.hp
        ? { ...base.hp, ...incoming.hp }
        : base.hp,
      abilities: incoming.abilities
        ? {
            ...(base.abilities ?? {}),
            ...(incoming.abilities as Record<string, unknown>),
          }
        : base.abilities,
    };
  }

  // Accept full or partial PlayerOut-like payloads (must have id when partial)
  function upsertPlayer(p: PlayerOut | (PlayerUpsert & { id: string })) {
    const i = players.value.findIndex(x => x.id === p.id);
    if (i === -1) {
      players.value.push(p as PlayerOut);
    } else {
      players.value[i] = mergePlayers(players.value[i], p);
    }

    if (currentPlayer.value?.id === p.id) {
      currentPlayer.value = mergePlayers(currentPlayer.value, p);
      persistPlayer(currentPlayer.value);
    }
  }

  function syncCurrentFromList(
    list: PlayerOut[],
  ): void {
    const id = currentPlayer.value?.id
  
    if (!id) {
      return
    }
  
    const fresh = list.find(
      (player) => player.id === id,
    )
  
    if (fresh) {
      currentPlayer.value = fresh
      persistPlayer(fresh)
    }
  
    /*
     * Do not delete the current player merely because it is
     * temporarily absent from one player-list response.
     *
     * The player session should only be removed after:
     * - an explicit leave,
     * - a server kick,
     * - or a confirmed missing-player response.
     */
  }

  function persistPlayer(p: PlayerOut | null) {
    try {
      if (p) {
        sessionStorage.setItem('player', JSON.stringify(p));
      } else {
        sessionStorage.removeItem('player');
      }
    } catch {
      // ignore
    }
  }


  function persistBackendUrl(url: string) {
    try {
      localStorage.setItem('backendUrl', url);
    } catch {
      // ignore
    }
  }

  function persistLocalNetworkIP(ip: string | null) {
    try {
      if (ip) {
        localStorage.setItem('localNetworkIP', ip);
      } else {
        localStorage.removeItem('localNetworkIP');
      }
    } catch {
      // ignore
    }
  }

  function hydratePlayer(): PlayerOut | null {
    try {
      const raw = sessionStorage.getItem('player');
      return raw ? (JSON.parse(raw) as PlayerOut) : null;
    } catch {
      return null;
    }
  }

  function hydrateBackendUrl(): string | null {
    try {
      return localStorage.getItem('backendUrl');
    } catch {
      return null;
    }
  }

  function hydrateLocalNetworkIP(): string | null {
    try {
      const raw = localStorage.getItem('localNetworkIP');
      return raw ? raw : null;
    } catch {
      return null;
    }
  }

  function removePersistedPlayer() {
    try {
      sessionStorage.removeItem('player');
    } catch {
      // ignore
    }
  }

  function clearPersist() {
    removePersistedPlayer();
    try {
      localStorage.removeItem('backendUrl');
      localStorage.removeItem('localNetworkIP');
    } catch {
      // ignore
    }
  }

  /* API actions */

  async function join(name: string, role: Role, reuse_id?: string) {
    const p = await api.join(name, role, reuse_id);
    currentPlayer.value = p;
    persistPlayer(p);
    return p;
  }

  async function loadPlayers() {
    const list = await api.listPlayers();
    players.value = list;
    syncCurrentFromList(list);
  }

  async function leave() {
    if (!currentPlayer.value) {
      return
    }

    disconnectPlayerSocket()

    try {
      await api.leave(
        currentPlayer.value.id,
      )
    } finally {
      clearSession()
    }
  }

  function setCurrentPlayer(p: PlayerOut) {
    currentPlayer.value = p;
    persistPlayer(p);
  }

  function setBackendUrl(url: string) {
    backendUrl.value = url;
    persistBackendUrl(url);
  }

  function setLocalNetworkIP(ip: string) {
    if (!ip) {
      localNetworkIP.value = null;
      persistLocalNetworkIP(null);
    } else {
      localNetworkIP.value = ip;
      persistLocalNetworkIP(ip);
    }
  }

  /* Session / logout helpers */

  function clearSession() {
    disconnectPlayerSocket()

    currentPlayer.value = null
    players.value = []
    backendUrl.value = null
    localNetworkIP.value = null

    clearPersist()
  }

  // Used e.g. when WS close code 4001 (kicked)
  function forceLogout() {
    clearSession();
  }

  /* WebSocket helpers */

  function applyWsJoin(p: PlayerOut) {
    upsertPlayer(p);
  }

  function applyWsLeave(id: string) {
    players.value = players.value.filter(pl => pl.id !== id);
    if (currentPlayer.value?.id === id) {
      currentPlayer.value = null;
      removePersistedPlayer();
    }
  }

  // Accept full or partial updates
  function applyWsUpdate(p: PlayerOut | (PlayerUpsert & { id: string })) {
    upsertPlayer(p);
  }

  function patchPlayer(id: string, patch: PlayerUpsert) {
    const i = players.value.findIndex(p => p.id === id);
    if (i !== -1) {
      players.value[i] = mergePlayers(players.value[i], patch);
    }
    if (currentPlayer.value?.id === id) {
      currentPlayer.value = mergePlayers(currentPlayer.value, patch);
      persistPlayer(currentPlayer.value);
    }
  }

  function apiBase(): string {
    return backendUrl.value ?? SERVER_CONFIG.BASE_URL
  }

  function wsUrl(
    baseHttpUrl: string,
    path: string,
  ): string {
    const url = new URL(baseHttpUrl)

    url.protocol =
      url.protocol === 'https:'
        ? 'wss:'
        : 'ws:'

    url.pathname = path.startsWith('/')
      ? path
      : `/${path}`

    return url.toString()
  }

  async function connectPlayerSocket(): Promise<void> {
    const player = currentPlayer.value

    if (!player) {
      return
    }

    if (
      playerSocket.value &&
      (
        playerSocket.value.readyState === WebSocket.OPEN ||
        playerSocket.value.readyState === WebSocket.CONNECTING
      )
    ) {
      return
    }

    socketManualClose.value = false

    const baseWs = wsUrl(
      apiBase(),
      SERVER_CONFIG.ENDPOINTS.WS_PLAYERS,
    )

    const url = new URL(baseWs)

    url.search = new URLSearchParams({
      player_id: player.id,
      name: player.name,
      role: player.role,
    }).toString()

    const socket = new WebSocket(
      url.toString(),
    )

    playerSocket.value = socket

    socket.onopen = async () => {
      try {
        await loadPlayers()
      } catch (error) {
        console.error(
          'Loading players failed:',
          error,
        )
      }
    }

    socket.onmessage = (event) => {
      let message: any

      try {
        message = JSON.parse(event.data)
      } catch {
        return
      }

      if (message.type === 'join') {
        applyWsJoin(message.player)
      } else if (message.type === 'leave') {
        applyWsLeave(message.player_id)
      } else if (
        message.type === 'update' &&
        message.player?.id
      ) {
        applyWsUpdate(message.player)
      } else if (
        message.type === 'health/update' &&
        message.hp
      ) {
        patchPlayer(
          message.player_id,
          {
            hp: message.hp,
          },
        )
      }
    }

    socket.onclose = (event) => {
      playerSocket.value = null

      if (event.code === 4001) {
        forceLogout()
        return
      }

      if (!socketManualClose.value) {
        console.warn(
          `Player WebSocket closed with code ${event.code}`,
        )
      }
    }

    socket.onerror = (error) => {
      console.error(
        'Player WebSocket error:',
        error,
      )
    }
  }

  function disconnectPlayerSocket(): void {
    socketManualClose.value = true

    if (playerSocket.value) {
      try {
        playerSocket.value.close(
          1000,
          'Player left session',
        )
      } catch {
        // Ignore close errors.
      }
    }

    playerSocket.value = null
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
    playerSocket,
    connectPlayerSocket,
    disconnectPlayerSocket,
  };
});
