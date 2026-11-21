import { onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { SERVER_CONFIG } from '@/config/config'
import { useMapStore } from '@/stores/map'
import { useSessionStore } from '@/stores/session'
import type { PlayerOut } from '@/api/playersAPI'

/**
 * Keep the player presence WebSocket open for the whole logged-in session,
 * including Map and Timeline, so roster and map updates arrive without a refresh.
 */
export function usePlayerPresence() {
  const store = useSessionStore()
  const mapStore = useMapStore()
  const router = useRouter()

  let socket: WebSocket | null = null
  let manualClose = false
  let connectionLost = false
  let connectedPlayerId: string | null = null

  function apiBase(): string {
    return store.backendUrl ?? SERVER_CONFIG.BASE_URL
  }

  function wsUrl(baseHttpUrl: string, path: string): string {
    const u = new URL(baseHttpUrl)
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
    u.pathname = path.startsWith('/') ? path : `/${path}`
    return u.toString()
  }

  function disconnectToLogin() {
    manualClose = true
    try {
      socket?.close(1000, 'user acknowledged')
    } catch {
      // ignore
    }
    socket = null
    connectedPlayerId = null
    store.forceLogout()
    void router.push({ name: 'login' })
  }

  function markConnectionLost(reason: string) {
    if (connectionLost) return
    connectionLost = true
    manualClose = true
    try {
      socket?.close(4000, 'connection lost')
    } catch {
      // ignore
    }
    socket = null
    connectedPlayerId = null
    try {
      window.confirm(
        `Verbindung zum Server unterbrochen.\n\n${reason}\n\nDu wirst jetzt zum Login weitergeleitet.`,
      )
    } finally {
      disconnectToLogin()
    }
  }

  function handleMessage(raw: string) {
    let msg: { type?: string; [key: string]: unknown }
    try {
      msg = JSON.parse(raw)
    } catch {
      return
    }

    if (msg.type === 'join') {
      store.applyWsJoin(msg.player as PlayerOut)
    } else if (msg.type === 'leave') {
      store.applyWsLeave(String(msg.player_id))
    } else if (msg.type === 'update' && (msg.player as PlayerOut | undefined)?.id) {
      store.applyWsUpdate(msg.player as PlayerOut)
    } else if (msg.type === 'health/update' && msg.hp) {
      store.patchPlayer(String(msg.player_id), { hp: msg.hp as PlayerOut['hp'] })
    } else if (msg.type === 'session_changed' || msg.type === 'session_imported') {
      void store.refreshActiveSession()
    } else if (msg.type === 'map_updated') {
      mapStore.applyRemoteGraph({
        session_id: typeof msg.session_id === 'string' ? msg.session_id : undefined,
        locations: Array.isArray(msg.locations) ? msg.locations : [],
        edges: Array.isArray(msg.edges) ? msg.edges : [],
      })
    }
  }

  function connect(player: PlayerOut) {
    const baseWs = wsUrl(apiBase(), SERVER_CONFIG.ENDPOINTS.WS_PLAYERS)
    const url = new URL(baseWs)
    url.search = new URLSearchParams({
      player_id: player.id,
      name: player.name,
      role: player.role,
    }).toString()

    const ws = new WebSocket(url.toString())
    socket = ws
    connectedPlayerId = player.id

    ws.onopen = async () => {
      try {
        await store.loadPlayers()
      } catch (e) {
        console.error('loadPlayers failed', e)
      }
    }

    ws.onmessage = (ev) => {
      handleMessage(String(ev.data))
    }

    ws.onclose = (ev) => {
      if (socket !== ws) return
      if (ev.code === 4001) {
        store.forceLogout()
        void router.push({ name: 'login' })
        socket = null
        connectedPlayerId = null
        return
      }
      socket = null
      connectedPlayerId = null
      if (!manualClose) {
        markConnectionLost(`Websocket closed (code ${ev.code || 'n/a'})`)
      }
    }

    ws.onerror = () => {
      if (socket !== ws) return
      markConnectionLost('Websocket error')
    }
  }

  function disconnect() {
    manualClose = true
    try {
      socket?.close(1000, 'unmount')
    } catch {
      // ignore
    }
    socket = null
    connectedPlayerId = null
  }

  watch(
    () => store.currentPlayer?.id,
    (id) => {
      const player = store.currentPlayer
      if (!id || !player) {
        disconnect()
        return
      }
      if (
        id === connectedPlayerId &&
        socket &&
        (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
      ) {
        return
      }
      disconnect()
      manualClose = false
      connectionLost = false
      connect(player)
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    disconnect()
  })
}
