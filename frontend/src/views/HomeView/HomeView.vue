<script setup lang="ts">
/**
 * HomeView – the main game dashboard. Manages the WebSocket connection,
 * player roster sync, and renders sub-components for questions, recording,
 * audio upload, and the right rail (dice, abilities, join link).
 */
import { onMounted, onUnmounted, onBeforeUnmount, ref } from 'vue'
import { useSessionStore } from '@/stores/session.ts'
import { useRouter } from 'vue-router'
import { SERVER_CONFIG } from '@/config/config'
import HomeHeader from '@/views/HomeView/HomeHeader.vue'
import SessionOverview from '@/views/HomeView/SessionOverview.vue'
import QuestionSection from '@/views/HomeView/QuestionSection.vue'
import RecordingSection from '@/views/HomeView/RecordingSection.vue'
import AudioUploadSection from '@/views/HomeView/AudioUploadSection.vue'
import RightRail from '@/views/HomeView/RightRail.vue'

const router = useRouter()
const store = useSessionStore()

let socket: WebSocket | null = null
let manualClose = false
let connectionLost = false

function disconnectToLogin() {
  manualClose = true
  try {
    socket?.close(1000, 'user acknowledged')
  } catch {}
  socket = null

  store.forceLogout()
  router.push({ name: 'login' })
}

function markConnectionLost(reason: string) {
  if (connectionLost) return // nur einmal auslösen
  connectionLost = true

  //Socket schließen (triggert onclose), aber Modal bleibt
  manualClose = true
  try {
    socket?.close(4000, 'connection lost')
  } catch {}
  socket = null

  try {
    window.confirm(
      `Verbindung zum Server unterbrochen.\n\n${reason}\n\nDu wirst jetzt zum Login weitergeleitet.`,
    )
  } finally {
    disconnectToLogin()
  }
}

function apiBase(): string {
  return store.backendUrl ?? SERVER_CONFIG.BASE_URL
}

/** Build WS URL from HTTP base + path */
function wsUrl(baseHttpUrl: string, path: string): string {
  const u = new URL(baseHttpUrl)
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
  u.pathname = path.startsWith('/') ? path : `/${path}`
  return u.toString()
}

/** WebSocket lifecycle */
onMounted(() => {
  // Guard: ohne Player -> zurück zum Login
  const p = store.currentPlayer
  if (!p) {
    router.push({ name: 'login' })
    return
  }

  connectionLost = false
  manualClose = false

  // Use wsUrl() to ensure ws/wss scheme, then attach query params
  const baseWs = wsUrl(apiBase(), SERVER_CONFIG.ENDPOINTS.WS_PLAYERS)
  const url = new URL(baseWs)
  url.search = new URLSearchParams({
    player_id: p.id,
    name: p.name,
    role: p.role,
  }).toString()

  socket = new WebSocket(url.toString())

  socket.onopen = async () => {
    try {
      await store.loadPlayers() // initial list
    } catch (e) {
      console.error('loadPlayers failed', e)
    }
  }

  socket.onmessage = (ev) => {
    let msg: any
    try {
      msg = JSON.parse(ev.data)
    } catch {
      return
    }

    if (msg.type === 'join') {
      // centralized in store
      store.applyWsJoin(msg.player)
    } else if (msg.type === 'leave') {
      store.applyWsLeave(msg.player_id)
    } else if (msg.type === 'update' && msg.player?.id) {
      // generic upsert path (expects full PlayerOut with nested hp)
      store.applyWsUpdate(msg.player)
    } else if (msg.type === 'health/update' && msg.hp) {
      // backend now sends nested hp directly
      store.patchPlayer(msg.player_id, { hp: msg.hp })
    }
  }

  socket.onclose = (ev) => {
    // 4001 = vom Server gekickt
    if (ev.code === 4001) {
      store.forceLogout()
      router.push({ name: 'login' })
      socket = null
      return
    }
    socket = null

    // Wenn nicht bewusst geschlossen, ist es "verbindung verloren"
    if (!manualClose) {
      markConnectionLost(`Websocket closed (code ${ev.code || 'n/a'})`)
    }
  }

  socket.onerror = () => {
    markConnectionLost('Websocket error')
  }
})

onBeforeUnmount(() => {
  manualClose = true
  try {
    socket?.close(1000, 'unmount')
  } catch {}
  socket = null
})
</script>

<template>
  <div class="container">
    <HomeHeader />

    <div class="centered-content">
      <SessionOverview />

      <!-- Left: main LLM -->
      <QuestionSection />

      <hr style="margin: 2rem 0" v-if="store.isLeader" />

      <!-- Leader-only: recording -->
      <RecordingSection v-if="store.isLeader" />

      <hr style="margin: 2rem 0" v-if="store.isLeader" />

      <!-- Leader-only: upload -->
      <AudioUploadSection v-if="store.isLeader" />
    </div>

    <RightRail />
  </div>
</template>

<style src="@/assets/styles.css"></style>
<style scoped>
/* Main container */
.container {
  max-width: 600px;
  margin: 2rem auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  max-height: 90vh;
  position: relative;
}

/* Centered content */
.centered-content {
  background-color: rgba(163, 148, 95, 0.8);
  padding: 2rem;
  border-radius: 8px;
  max-width: 600px;
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
  margin-top: 60px;
}

/* Responsive design */
@media (max-width: 1200px) {
  .container {
    max-width: 100%;
    margin: 1rem;
    align-items: center;
  }
}
</style>
