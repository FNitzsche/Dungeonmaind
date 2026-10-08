<script setup lang="ts">
/**
 * LoginView – the landing page where users set the backend URL,
 * check connectivity, and join as a new or existing player.
 * Leaders can also import saved sessions.
 */
import { ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { SERVER_CONFIG } from '@/config/config'
import { type PlayerOut, type Role } from '@/api/playersAPI.ts'
import { useSessionStore } from '@/stores/session.ts'
import * as api from '@/api/playersAPI.ts'

const store = useSessionStore()
const router = useRouter()

const isLocalhost =
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

// Logik für checkConnection

type Status = 'idle' | 'checking' | 'ok' | 'error'

// Typen für den Check
type JoinCheckStatus = 'available' | 'inactive_match' | 'active_conflict'
type JoinCheckOut = {
  status: JoinCheckStatus
  candidate?: PlayerOut
}

/**
 * Preflight join check: verify name availability, handle inactive-player reuse,
 * then join the session.
 * @param backendUrl - Backend server origin.
 * @param name - Desired player name.
 * @param role - Leader or member.
 */
async function preflightAndJoin(backendUrl: string, name: string, role: Role) {
  // 1) Preflight-Check
  console.debug(`preflightAndJoin: versuche mit ${name} zu joinen`)
  const checkUrl = new URL('/players/join/check', backendUrl)
  checkUrl.searchParams.set('name', name)
  const res = await fetch(checkUrl.toString(), { credentials: 'include' })
  if (!res.ok) {
    throw new Error(JSON.stringify({ detail: `Join-Check fehlgeschlagen (${res.status}` }))
  }
  const check: JoinCheckOut = await res.json()

  if (check.status === 'available') {
    // normaler Join
    console.debug(`preflightAndJoin: ${name} ist verfügbar`)
    await store.join(name, role)
    return
  }

  if (check.status === 'active_conflict') {
    console.debug(`preflightAndJoin: es gibt einen aktiven Spieler mit dem namen`)
    // Name schon bei einem aktiven Spieler belegt
    throw new Error(JSON.stringify({ detail: `Der Name "${name}" ist bereits vergeben.` }))
  }

  if (check.status === 'inactive_match' && check.candidate) {
    // Nutzer fragen: alten Spieler reaktivieren?
    console.debug(`preflightAndJoin: inaktiven Spieler mit dem Namen gefunden`)
    const reuse = window.confirm(
      `Es gibt einen inaktiven Spieler "${check.candidate.name}". ` +
        `Möchtest du diesen wiederverwenden (HP/Attribute bleiben erhalten)?`,
    )
    if (reuse) {
      // Reuse-Join
      console.debug(`preflightAndJoin: Spieler wird reaktiviert`)
      await store.join(name, role, check.candidate.id)
      return
    } else {
      // neuer Spieler mit gleichem Namen ist erlaubt (nur aktive Namen sind geblockt)
      console.debug(`preflightAndJoin: Spieler wird neu angelegt`)
      await store.join(name, role)
      return
    }
  }

  // sollte nie passieren
  await store.join(name, role)
}

// checkConnection
const baseUrl = ref<string>(`http://${window.location.hostname}:8000`)
const status = ref<Status>('idle')
const message = ref<string>('')
const lastStatus = ref<number | null>(null)
const setConnection = ref(false)

const networkIPs = __NETWORK_IPS__
const selectedNetworkIP = ref(networkIPs[0] || '')
let lastValidIP = selectedNetworkIP.value
let isValidIP = true

type CheckResult = {
  ok: boolean
  status?: number
  error?: string
}

interface SessionList {
  folders: string[]
}
interface CampaignsWithSessions {
  campaigns: Record<string, SessionList>
}
// For session import
const showImportModal = ref(false)
//const sessions = ref([])
const selectedSession = ref('')
const campaigns = ref<CampaignsWithSessions | null>(null)
const selectedCampaign = ref<string | null>(null)

const octet = '(?:25[0-5]|2[0-4]\\d|1?\\d{1,2})'
const localIPRegex = new RegExp(
  '^(' +
    // 10.x.x.x oder teilweise
    '1?|10(?:\\.(?:' +
    octet +
    ')?)?(?:\\.(?:' +
    octet +
    ')?)?(?:\\.(?:' +
    octet +
    ')?)?' +
    '|' +
    // 192.168.x.x oder teilweise
    '1|19|192(?:\\.(?:1|16|168)?(?:\\.(?:' +
    octet +
    ')?)?(?:\\.(?:' +
    octet +
    ')?)?)?' +
    '|' +
    // 172.16-31.x.x oder teilweise
    '1?|17?|172(?:\\.(?:(1[6-9]|2\\d|3[0-1])|[1-3])?(?:\\.(?:' +
    octet +
    ')?)?(?:\\.(?:' +
    octet +
    ')?)?)?' +
    ')$',
)

watch(selectedNetworkIP, (newVal) => {
  if (localIPRegex.test(newVal)) {
    lastValidIP = newVal
    isValidIP = true
  } else {
    isValidIP = false
  }
})

/**
 * Test backend connectivity by hitting the health endpoint.
 * On success, persists the URL in the session store.
 * @param backendUrl - The URL to test.
 * @param timeoutMs - Abort timeout in milliseconds.
 * @returns Whether the connection succeeded and any status/error.
 */
async function checkConnection(backendUrl: string, timeoutMs = 5000): Promise<CheckResult> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${backendUrl}${SERVER_CONFIG.ENDPOINTS.CHECK_CONNECTION}`, {
      method: 'GET',
      signal: controller.signal,
    })
    // response.ok == Status 200 (und auch 204)
    if (response.ok) {
      // (erfolgreich) getestete Adresse auch direkt setzen
      store.setBackendUrl(backendUrl)
      setConnection.value = true
    }
    return { ok: response.ok, status: response.status }
  } catch (err: unknown) {
    // AbortError unterscheidbar von echten Netzwerkfehlern
    const msg = err instanceof Error ? err.message : String(err)
    return { ok: false, error: msg }
  } finally {
    clearTimeout(timeoutId)
  }
}

async function onCheck() {
  status.value = 'checking'
  message.value = ''
  lastStatus.value = null

  const backendUrl = normalizeOrigin(baseUrl.value)
  const result = await checkConnection(backendUrl)

  if (result.ok) {
    status.value = 'ok'
    lastStatus.value = result.status ?? null
  } else {
    status.value = 'error'
    message.value = result.error ?? `HTTP ${result.status ?? '?'}`
  }
}

// --- Logik für Gruppe ---

// Zustand (reaktiv)
const role = ref<Role | null>(null) // null = noch nichts gewählt
const playerName = ref<string>('') // Eingabetext
const submitting = ref(false) // Button-Loading-Status
const touched = ref(false) // für einfache Fehlermeldungs-Steuerung
const serverError = ref('')

// einfache Validierung für den Namen
const nameError = computed(() => {
  const n = playerName.value.trim()
  if (n.length === 0) return 'Please enter a name.'
  if (n.length < 2) return 'Your name must be at least 2 characters.'
  return ''
})

// Button nur aktiv, wenn alles ok
const canSubmit = computed(
  () => (role.value !== null && nameError.value === '') || selectedPlayer.value !== undefined,
)

// Formular-Submit
async function onSubmit(e: Event) {
  e.preventDefault() // Browser-Reload verhindern
  const backendUrl = normalizeOrigin(baseUrl.value)
  const result = await checkConnection(backendUrl)
  if (result.ok) store.setBackendUrl(backendUrl)
  touched.value = true

  if (selectedPlayer.value !== undefined) {
    role.value = selectedPlayer.value.role
    playerName.value = selectedPlayer.value.name
  }

  if (!canSubmit.value || role.value == null) return

  const effectiveRole: Role = !isLocalhost && role.value === 'leader' ? 'member' : role.value

  if (!isLocalhost && role.value === 'leader') {
    window.alert('Ledaer kann nur über localhost beitreten. Du trittst als Member bei.')
  }

  if (nameError.value) return

  submitting.value = true
  try {
    await preflightAndJoin(backendUrl, playerName.value.trim(), effectiveRole)
    store.setLocalNetworkIP(lastValidIP)
    await router.push({ name: 'home' })
  } catch (err: any) {
    console.error('Join error:', err)
  } finally {
    submitting.value = false
  }
}

function normalizeOrigin(input: string): string {
  // Protokoll sicherstellen (http/https) oder protokoll-relative //host zulassen
  const withProtocol = /^(https?:)?\/\//i.test(input) ? input : `http://${input}`
  // Nur die Origin verwenden (Schema + Host + Port), Pfade abschneiden
  //    (damit "http://host:8000/health" -> "http://host:8000")
  return new URL(withProtocol).origin
}

async function confirmImport() {
  if (!selectedSession.value) return

  try {
    const res = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.IMPORT_SESSION}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        campaign_name: selectedCampaign.value,
        session_name: selectedSession.value,
      }),
    })

    if (!res.ok) throw new Error('Import failed')
    const leader = await res.json()

    if (!leader) throw new Error('No leader returned from backend')

    store.setCurrentPlayer(leader)
    store.setLocalNetworkIP(lastValidIP)

    await router.push({ name: 'home' })

    showImportModal.value = false
    alert(`Session "${selectedSession.value}" imported successfully!`)
  } catch (err) {
    console.error(err)
    if (err instanceof Error) {
      alert('Import failed: ' + err.message)
    } else {
      alert('Import failed: ' + String(err))
    }
  }
}

async function onImport() {
  try {
    const res = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.GET_CAMPAIGNS}`)
    if (!res.ok) throw new Error('Failed to fetch sessions')

    campaigns.value = await res.json()
    //sessions.value = data.folders
    showImportModal.value = true
  } catch (err) {
    console.error(err)
  }
}

function selectSession(campaignName: string, sessionName: string) {
  selectedCampaign.value = campaignName
  selectedSession.value = sessionName
}

function deselectSession() {
  selectedCampaign.value = ''
  selectedSession.value = ''
}

const showNewPlayerModal = ref(false)

function JoinNewPlayer() {
  selectedPlayer.value = undefined
  serverError.value = ''
  touched.value = false
  showNewPlayerModal.value = true
}

const showExistingPlayerModal = ref(false)
const allPlayers = ref<PlayerOut[]>([])
const selectedPlayer = ref<PlayerOut>()

async function JoinExistingPlayer() {
  selectedPlayer.value = undefined
  if (!setConnection.value) await onCheck()
  if (setConnection.value) {
    allPlayers.value = await api.listPlayers(true)
    if (allPlayers.value.filter((p) => p.status === 'inactive').length === 0) {
      window.alert(`Es wurden keine inaktiven Spieler gefunden. ` + `Erstelle einen neuen.`)
      return
    }
    showExistingPlayerModal.value = true
  }
}
</script>

<template>
  <div class="login-page">
    <div class="rail-panel login-card">
      <h1>Login Page</h1>

      <div class="check-card">
        <label for="baseUrl">Backend-Adresse</label>
        <input
          class="input-field"
          id="baseUrl"
          v-model.trim="baseUrl"
          placeholder="z.B. http://localhost:8080"
          :disabled="status === 'checking'"
        />

        <button class="done-button" @click="onCheck" :disabled="!baseUrl || status === 'checking'">
          {{ status === 'checking' ? 'Checking...' : 'Check/Set Connection' }}
        </button>

        <p v-if="status === 'ok'">Erreichbar{{ lastStatus ? ` (HTTP ${lastStatus})` : '' }}</p>
        <p v-else-if="status === 'error'">Not available: {{ message }}</p>
      </div>

      <hr v-if="isLocalhost" style="margin: 1rem 0" />

      <div v-if="isLocalhost">
        <button class="done-button" @click="onImport">Import Session</button>
      </div>
      <div v-if="showImportModal" class="modal-overlay">
        <div class="modal">
          <h2>Select a session to import</h2>

          <div class="session-list">
            <div v-if="campaigns && Object.keys(campaigns.campaigns).length">
              <div v-for="(sessionList, campaignName) in campaigns.campaigns" :key="campaignName">
                <h3 class="campaign-name">{{ campaignName }}</h3>
                <ul>
                  <li
                    class="session-name-font session-clickable"
                    v-for="session in sessionList.folders"
                    :key="session"
                    :class="{
                      selected: selectedSession === session && selectedCampaign === campaignName,
                    }"
                    @click="selectSession(campaignName, session)"
                  >
                    {{ session }}
                  </li>
                </ul>
              </div>
            </div>
            <div v-else class="no-sessions-text">No loadable sessions available.</div>
          </div>
          <div>
            <div v-if="networkIPs.length > 1">
              <label for="networkIP">Select your local network IP:</label>
              <div style="margin-top: 1px"></div>
              <select id="networkIP" v-model="selectedNetworkIP">
                <option v-for="networkIP in networkIPs" :key="networkIP" :value="networkIP">
                  {{ networkIP }}
                </option>
              </select>
            </div>
            <div v-else>
              <label for="networkIP">Enter your local network IP:</label>
              <div style="margin-top: 1px"></div>
              <input
                id="networkIP"
                type="text"
                v-model="selectedNetworkIP"
                placeholder="e.g. FRITZ!Box: 192.168.178.x"
                style="width: 100%; max-width: 200px"
              />
            </div>
            <p v-if="!isValidIP">No valid local IP address<br />according to RFC 1918</p>
          </div>
          <div style="margin-top: 8px"></div>
          <div class="modal-buttons">
            <button
              class="btn-cancel"
              @click="
                () => {
                  showImportModal = false
                  deselectSession()
                }
              "
            >
              Cancel
            </button>
            <button class="btn-save" :disabled="!selectedSession" @click="confirmImport">
              Import
            </button>
          </div>
        </div>
      </div>

      <hr style="margin: 1rem 0" />

      <div class="button-row">
        <button class="button" @click="JoinNewPlayer">Join as new Player</button>
        <button class="button" @click="JoinExistingPlayer">Join as existing Player</button>
      </div>

      <hr v-if="!isLocalhost" style="margin: 1rem 0" />
      <label v-if="!isLocalhost" style="display: block; max-width: 410px">
        Joining as leader and importing a session are only possible if the server is running locally
        on your device and the page is opened via localhost or 127.0.0.1</label
      >

      <div v-if="showNewPlayerModal" class="modal-overlay">
        <div class="modal">
          <h2>Select a Role and a Name for your Player</h2>
          <form class="join-card" @submit="onSubmit">
            <!-- 1) select role-->
            <fieldset>
              <legend>Choose a role</legend>

              <label>
                <input
                  type="radio"
                  name="role"
                  :value="'leader'"
                  v-model="role"
                  :disabled="!isLocalhost"
                />
                Leader
              </label>

              <label>
                <input type="radio" name="role" :value="'member'" v-model="role" />
                Member
              </label>

              <p v-if="touched && !role" class="error">Please select a role.</p>
            </fieldset>

            <!-- 2) local network IP -->
            <div v-if="role === 'leader'">
              <div style="margin-top: 4px"></div>
              <div v-if="networkIPs.length > 1">
                <label for="networkIP">Select your local network IP:</label>
                <div style="margin-top: 1px"></div>
                <select id="networkIP" v-model="selectedNetworkIP">
                  <option v-for="networkIP in networkIPs" :key="networkIP" :value="networkIP">
                    {{ networkIP }}
                  </option>
                </select>
              </div>
              <div v-else>
                <label for="networkIP">Enter your local network IP:</label>
                <div style="margin-top: 1px"></div>
                <input
                  id="networkIP"
                  type="text"
                  v-model="selectedNetworkIP"
                  placeholder="e.g. FRITZ!Box: 192.168.178.x"
                  style="width: 100%; max-width: 200px"
                />
              </div>
              <p v-if="!isValidIP">No valid local IP address<br />according to RFC 1918</p>
            </div>

            <!-- 3) player name -->
            <div style="margin-top: 4px"></div>
            <!-- 2) Spielernamen -->
            <label for="playerName">Your Name</label>
            <input
              class="input-field"
              id="playerName"
              type="text"
              v-model.trim="playerName"
              maxlength="20"
              placeholder="z.B. Alex"
              @blur="touched = true"
              autocomplete="name"
            />
            <p v-if="touched && nameError" class="error">{{ nameError }}</p>
            <p v-if="serverError" class="error">{{ serverError }}</p>

            <!-- 4) join or cancel -->
            <div class="modal-buttons">
              <button class="done-button" type="submit" :disabled="!canSubmit || submitting">
                {{ submitting ? 'Join ...' : 'Join' }}
              </button>
              <button
                class="button"
                type="button"
                :disabled="submitting"
                @click="showNewPlayerModal = false"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
      <div v-if="showExistingPlayerModal" class="modal-overlay">
        <div class="modal">
          <h2>Select your player</h2>

          <div class="player-list">
            <div
              v-for="player in allPlayers.filter((p) => p.status === 'inactive')"
              :key="player.id ?? player.name"
              class="player-item"
              :class="{
                selected: selectedPlayer === player,
                disabled: !isLocalhost && player.role === 'leader',
              }"
              @click="
                () => {
                  if (!isLocalhost && player.role === 'leader') return
                  selectedPlayer = player
                }
              "
            >
              {{ player.name }} ({{ player.role }})
              <span v-if="!isLocalhost && player.role === 'leader'"> 🔒</span>
            </div>
          </div>

          <!-- IP nur anzeigen, wenn ein Leader ausgewählt ist -->
          <div v-if="selectedPlayer?.role === 'leader'">
            <div v-if="networkIPs.length > 1">
              <label for="networkIP">Select your local network IP:</label>
              <div style="margin-top: 1px"></div>
              <select id="networkIP" v-model="selectedNetworkIP">
                <option v-for="networkIP in networkIPs" :key="networkIP" :value="networkIP">
                  {{ networkIP }}
                </option>
              </select>
            </div>
            <div v-else>
              <label for="networkIP">Enter your local network IP:</label>
              <div style="margin-top: 1px"></div>
              <input
                id="networkIP"
                type="text"
                v-model="selectedNetworkIP"
                placeholder="e.g. FRITZ!Box: 192.168.178.x"
                style="width: 100%; max-width: 200px"
              />
            </div>
            <p v-if="!isValidIP">No valid local IP address<br />according to RFC 1918</p>
            <div style="margin-bottom: 12px"></div>
          </div>

          <div class="modal-buttons">
            <button class="done-button" type="submit" :disabled="submitting" @click="onSubmit">
              {{ submitting ? 'Join ...' : 'Join' }}
            </button>
            <button class="button" @click="showExistingPlayerModal = false">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style src="@/assets/styles.css"></style>
<style scoped>
.config-page {
  max-width: 600px;
  margin: 2rem auto;
  padding: 1rem;
  text-align: center;
}

.login-page {
  max-width: 600px;
  margin: 2rem auto;
  padding: 1rem;
}

.login-card {
  /* rail-panel liefert Hintergrund, Rahmen etc. */
  width: 100%;
  box-sizing: border-box;
}

select {
  padding: 0.5rem;
  font-size: 0.9rem;
}

.button,
.done-button {
  padding: 0.5rem 1rem;
  background-color: rgba(53, 73, 94, 0.9);
  border: 1px solid #4a575e;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  font-family: 'MedievalSharp', cursive;
  font-weight: normal;
  transition: background-color 0.3s ease;
}

.button:hover,
.done-button :hover {
  background-color: #4a575e;
}

.input-field {
  padding: 0.75rem;
  font-size: 1rem;
  margin-bottom: 1rem;
  border: 1px solid #695710;
  border-radius: 10px;
  font-family: 'MedievalSharp', cursive;
  font-weight: bolder;
  background-color: #f1e6b4;

  color: #4c3e06;
  width: 90%;
  box-sizing: border-box;
}

.login-page,
.login-page h1,
.login-page p,
.login-page label,
.login-page fieldset,
.login-page legend,
.login-page button {
  font-family: 'MedievalSharp', cursive;
}

.login-page input,
.login-page textarea,
.login-page select {
  font-family: inherit;
}

/* Modal base */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.modal {
  background: rgba(163, 148, 95, 0.8);
  border-radius: 12px;
  padding: 24px;
  width: 340px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  text-align: center;
  color: #000;
}

.modal h2 {
  font-size: 1.2rem;
  font-weight: 600;
  margin-bottom: 1rem;
}

/* Session list */
.player-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 6px;
  margin-bottom: 12px;
  padding: 4px;
}

.player-item,
.session-item {
  padding: 8px 10px;
  border-radius: 4px;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s ease;
}

.player-item:hover,
.session-item:hover {
  background: #f3f4f6; /* gray-100 */
}

.player-item.selected,
.session-item.selected {
  background: #8b5a2b; /* muted leather brown */
  color: #fdf6e3;
}

.player-item.disabled {
  opacity: 0.6;
  cursor: not-allowed;
  pointer-events: none;
}

/* Buttons */
.modal-buttons {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.session-name-font {
  cursor: pointer;
  display: block;
  color: black;
  font-family: 'MedievalSharp', cursive;
  padding: 3px 4px;
  border-radius: 4px;
}

.session-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 6px;
  margin-bottom: 8px;
  padding: 4px;
}

.selected {
  background: rgba(53, 73, 94, 0.35);
  border-radius: 4px;
}

.session-name-font:hover {
  background: rgba(0, 0, 0, 0.1);
}

.btn-cancel,
.btn-save {
  padding: 6px 12px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.2s ease;
}

.btn-cancel {
  background: #ddd;
}

.btn-cancel:hover {
  background: #ccc;
}

.btn-save {
  background-color: rgba(53, 73, 94, 0.9);
  color: white;
}

.btn-save:hover {
  background: #1d4ed8;
}

.btn-save:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

.campaign-name {
  color: black;
}

.session-clickable:hover {
  text-decoration: underline;
}

.no-sessions-text {
  color: #555;
  font-family: 'MedievalSharp', cursive;
  font-style: italic;
  padding: 0.5rem;
}

.button-row {
  display: flex;
  gap: 12px;
}
</style>
