<script setup lang="ts">
import { ref } from 'vue'
import { SERVER_CONFIG } from '@/config/config.ts'
import { useSessionStore } from '@/stores/session.ts'
import { useRecorderStore } from '@/stores/recorder.ts'
import { useConfigStore } from "@/stores/backendConfig.ts";
import { fetchConfig } from "@/api/backendConfigAPI.ts";
import ConfigView from '@/views/ConfigView.vue'
import RulebookView from '@/views/RulebookView.vue'
import { useRouter } from 'vue-router'

/** Holds Header and session saving */

interface SessionList {
  folders: string[]
}

interface CampaignsWithSessions {
  campaigns: Record<string, SessionList>
}

const store = useSessionStore()
const recorder = useRecorderStore()
const configStore = useConfigStore()

const router = useRouter()

const showNameModal = ref(false)
const sessionName = ref("")
const showCampaignSelectModal = ref(false)
const showCampaignCreateModal = ref(false)
const campaigns = ref<CampaignsWithSessions | null>(null)
const newCampaignName = ref("")
const selectedCampaign = ref<string | null>(null)
const selectedSession = ref<string | null>(null)
const showOverwriteConfirm = ref(false)
const showDeleteConfirm = ref(false)
const deleteTargetLabel = ref("")
const deleteTargetName = ref("")

const showConfigModal = ref(false)
const showRulebookModal = ref(false)
const isStartingNewSession = ref(false)

async function startNewSession(): Promise<void> {
  const confirmed = window.confirm(
    'Start a new session? You will leave the current session and return to the login page.',
  )

  if (!confirmed || isStartingNewSession.value) {
    return
  }

  isStartingNewSession.value = true

  try {
    await store.leave()

    await router.push({
      name: 'login',
    })
  } catch (error) {
    console.error(
      'Failed to start a new session:',
      error,
    )

    store.clearSession()

    await router.push({
      name: 'login',
    })
  } finally {
    isStartingNewSession.value = false
  }
}


const openConfig = async () => {
  try {
    const config = await fetchConfig();
    configStore.setConfig(config);

    showConfigModal.value = true;
  } catch (error) {
    console.error('Failed to load config:', error);
  }
};

interface Campaign {
  name: string
}

function isValidFolderName(name : string) {
  const regex = /^[A-Za-z0-9_-]+(?: [A-Za-z0-9_-]+)*$/
  return regex.test(name)
}

async function loadCampaigns() {
  const res = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.GET_CAMPAIGNS}`)
  campaigns.value = await res.json()
  console.log(campaigns.value)
}

/* The Save Sess ion button now opens the campaign selector */
function openSaveFlow() {
  showCampaignSelectModal.value = true
  loadCampaigns()
}

//function selectCampaign(campaign: string) {
//  selectedCampaign.value = campaign
//  const sessionCount = campaigns.value?.campaigns[campaign]?.folders.length ?? 0
//  sessionName.value = "Session_" + (sessionCount+1).toString()
//  showCampaignSelectModal.value = false
//  showNameModal.value = true
//}

function selectCampaign(campaign: string) {
  selectedCampaign.value = campaign
  selectedSession.value = null
}

function selectSession(session: string, campaign: string) {
  selectedCampaign.value = campaign
  selectedSession.value = session
}

function deselectSessionAndCampaign() {
  selectedCampaign.value = null
  selectedSession.value = null
}

function resetSelection() {
  selectedCampaign.value = null
  selectedSession.value = null
}

function confirmSelection() {
  if (selectedSession.value) {
    // Overwrite Session by opening the "are you sure you want to overwrite ..." modal
    console.log("Overwrite the session")
    showOverwriteConfirm.value = true
  } else if (selectedCampaign.value) {
    // Create new session inside selected campaign by opening the Session name modal
    getNewSessionName(selectedCampaign.value)
    showNameModal.value = true
  }
}

function getNewSessionName(campaignName: string) {
  const sessionCount = campaigns.value?.campaigns[campaignName]?.folders.length ?? 0
  sessionName.value = "Session_" + (sessionCount+1).toString()
  showCampaignSelectModal.value = false
}

// Opens a new creation campaign modal
function openCreateCampaign() {
  showCampaignCreateModal.value = true
}

// Creates a new campaign
async function createCampaign() {
  const name = newCampaignName.value.trim()
  if (!name) return alert("Enter campaign name")
  if(!isValidFolderName(name)) {
      return alert("Campaign name is only allowed to have alpah-numeric values, whitespaces, '-' or '_'")
  }

  // The new campaign is at first only added locally with an empty session list
  // and will later be saved only if an actual session in the campaign is saved
  if (!campaigns.value) {
    campaigns.value = { campaigns: {} }
  }

  // Check for duplicate campaign names
  if (campaigns.value.campaigns[name]) {
    return alert("A campaign with this name already exists")
  }

  campaigns.value.campaigns[name] = { folders: [] }
  selectedCampaign.value = name
  getNewSessionName(selectedCampaign.value)

  // Reset input and modals
  newCampaignName.value = ""
  showCampaignCreateModal.value = false
  showCampaignSelectModal.value = false
  showNameModal.value = true
}

// Exports/saves the current session
async function onExport() {
  const name = sessionName.value.trim()
  const campaign = selectedCampaign.value
  if (!name.trim()) return alert("Please enter a session name.")
  if(!isValidFolderName(name)) {
    return alert("Session name is only allowed to have alpah-numeric values, whitespaces, '-' or '_'")
  }
  if (!campaign) return alert("No campaign selected.")
  if (campaigns.value && campaigns.value.campaigns[campaign]) {
    const existingSessions = campaigns.value.campaigns[campaign].folders
    if (existingSessions.includes(name)) {
      return alert(`A session with the name "${name}" already exists in this campaign.`)
    }
  }

  showNameModal.value = false

  try {
    await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.EXPORT_SESSION}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        campaign_name: selectedCampaign.value,
        session_name: sessionName.value,
      }),
    })
  } catch (err) {
    console.error(err);
    if (err instanceof Error) {
      alert("Saving/Exporting Session failed: " + err.message);
    } else {
      alert("Saving/Exporting Session failed: " + String(err));
    }
  }
}

async function confirmOverwrite() {
  const name = selectedSession.value
  const campaign = selectedCampaign.value
  // ISO-String has ':' in it, which causes a problem in the backend, when the name is interpreted as a path
  const timestamp = new Date().toISOString().replace(/:/g, "-");
  const overwriteName = name + "_" + timestamp
  let overwriteSuccessful = false
  let savingSuccessful = false
  try {
    await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.RENAME_SESSION}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        campaign_name: campaign,
        old_session_name: name,
        new_session_name: overwriteName,
      }),
    })
    overwriteSuccessful = true
  } catch (err) {
    console.error(err);
    if (err instanceof Error) {
      alert("Couldn't back up Session. Overwrite failed: " + err.message);
    } else {
      alert("Couldn't back up Session failed. Overwrite failed: " + String(err));
    }
  }

  if(overwriteSuccessful) {
    try {
      await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.EXPORT_SESSION}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          campaign_name: campaign,
          session_name: name,
        }),
      })

      savingSuccessful = true
    } catch (err) {
      console.error(err);
      if (err instanceof Error) {
        alert("Overwriting Session failed, in trying to save new session: " + err.message);
      } else {
        alert("Overwriting Session failed, in trying to save new session: " + String(err));
      }
    }
  } else {
    alert("Overwrite failed");
    showOverwriteConfirm.value = false
    return
  }

  if(savingSuccessful) {
    try {
      await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.DELETE_SESSION_OR_CAMPAIGN}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ campaign_or_session_name: `${campaign}/${overwriteName}` }),
      })
    } catch (err) {
      console.error(err);
      if (err instanceof Error) {
        alert("Deletion of overwrite Session failed: " + err.message);
      } else {
        alert("Deletion of overwrite Session failed: " + String(err));
      }
    }
  } else {
    try {
      await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.RENAME_SESSION}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          campaign_name: campaign,
          old_session_name: overwriteName,
          new_session_name: name,
        }),
      })
    } catch (err) {
      console.error(err);
      if (err instanceof Error) {
        alert("Couldn't rename backup session. Backup Session does still exist though" + "under " + overwriteName + ": " + err.message);
      } else {
        alert("Couldn't rename backup session. Backup Session does still exist though" + "under " + overwriteName + ": " + String(err));
      }
    }
      alert("Overwrite failed");
      showOverwriteConfirm.value = false
      return
  }
  showOverwriteConfirm.value = false

}

function openDeletePrompt() {
  if (selectedSession.value) {
    deleteTargetLabel.value = "Session"
    deleteTargetName.value = selectedSession.value
  } else if (selectedCampaign.value) {
    deleteTargetLabel.value = "Campaign"
    deleteTargetName.value = selectedCampaign.value
  } else {
    return
  }

  showDeleteConfirm.value = true
}

function confirmDelete() {
  console.log(`DELETE: ${deleteTargetLabel.value} = ${deleteTargetName.value}`)
  confirmDeletion()
  showDeleteConfirm.value = false
}

function cancelDelete() {
  deleteTargetName.value = ""
  deleteTargetLabel.value = ""
  showDeleteConfirm.value = false
}

function getSessionPerSelectedCampaign(): number {
  if (!campaigns.value || !selectedCampaign.value) {
      return 0
  }
  const sessions = campaigns.value.campaigns[selectedCampaign.value]?.folders ?? []
  return sessions.length
}

function buildNameToDelete(deleteCampaignForSession : boolean) {
  if (!selectedCampaign.value) {
    return null
  }

  if (!selectedSession.value) {
    return selectedCampaign.value
  } else {
    if(deleteCampaignForSession) {
      return selectedCampaign.value
    } else {
      return `${selectedCampaign.value}/${selectedSession.value}`
    }
  }
}

async function confirmDeletion() {
  try {
    let nameToDelete = null;
    if(deleteTargetLabel.value === "Session") {
      const nrSessions = getSessionPerSelectedCampaign()
      if(nrSessions == 1) {
        nameToDelete = buildNameToDelete(true)
        deleteTargetLabel.value = "Campaign"
      } else {
        nameToDelete = buildNameToDelete(false)
      }
    } else {
      nameToDelete = buildNameToDelete(false)
    }
    console.log(nameToDelete)
    if (nameToDelete === null) {
      alert("No campaign or session selected")
      return
    }
    await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.DELETE_SESSION_OR_CAMPAIGN}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ campaign_or_session_name: nameToDelete }),
    })

    if(deleteTargetLabel.value === "Campaign") {
      delete campaigns.value!.campaigns[selectedCampaign.value!]
      selectedCampaign.value = null
    } else {
      const sessionList = campaigns.value!.campaigns[selectedCampaign.value!].folders
      campaigns.value!.campaigns[selectedCampaign.value!] = {
        folders: sessionList.filter(s => s !== selectedSession.value)
      }
      selectedSession.value = null
    }

  } catch (err) {
    console.error(err);
    if (err instanceof Error) {
      alert("Deletion Campaign/Session failed: " + err.message);
    } else {
      alert("Deletion Campaign/Session failed: " + String(err));
    }
  }
}


</script>

<template>
  <div class="header">
    <div class="header-left"></div>
    <h1>Dungeonmaind</h1>
    <div class="header-right">
      <button
        type="button"
        class="timeline-button"
        @click="router.push({ name: 'timeline' })"
      >
        Timeline
      </button>

      <button
        type="button"
        class="new-session-button"
        :disabled="isStartingNewSession"
        @click="startNewSession"
      >
        {{
          isStartingNewSession
            ? 'Leaving...'
            : 'Start New Session'
        }}
      </button>

      <button class="rulebook-button" @click="showRulebookModal = true">Rulebook</button>
      <button v-if="store.isLeader" class="config-button" @click="openConfig">Config</button>
      <button
        v-if="store.isLeader"
        class="export-button"
        @click="openSaveFlow"
        :disabled="recorder.isRecording || recorder.isStopping || (!!recorder.recordedAudioURL && !recorder.canExportSession)"
      >
        Save Session
      </button>

    </div>
    <div v-if="showNameModal" class="modal-overlay">
      <div class="modal">
        <h2>Name your session</h2>
        <input
          v-model="sessionName"
          placeholder="Enter session name"
          class="modal-input"
        />
        <div class="modal-buttons">
          <button class="btn-cancel" @click="showNameModal = false; deselectSessionAndCampaign()">Cancel</button>
          <button class="btn-save" @click="onExport">Save</button>
        </div>
      </div>
    </div>
    <div v-if="showConfigModal" class="modal-overlay">
      <ConfigView @submit-success="showConfigModal = false" />
    </div>
    <div v-if="showRulebookModal" class="modal-overlay">
      <RulebookView @submit-success="showRulebookModal = false" />
    </div>
  </div>
  <div v-if="showCampaignSelectModal" class="modal-overlay">
    <div class="modal">
      <h2>Select a Campaign</h2>

      <div class="session-list">
        <div v-if="campaigns && Object.keys(campaigns.campaigns).length">
          <div v-for="(sessionList, campaignName) in campaigns?.campaigns" :key="campaignName">
            <h3 class="campaign-name"
                @click="selectCampaign(campaignName)"
                :class="{ selected: selectedCampaign  === campaignName }">
              {{ campaignName }}
            </h3>
            <ul>
              <li class="session-name-font"
                  v-for="session in sessionList.folders" :key="session"
                  :class="{ selected: selectedSession === session && selectedCampaign === campaignName }"
                  @click="selectSession(session, campaignName)">
                {{ session }}
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div class="button-group">
        <button
          class="btn-save"
          :disabled="!(selectedCampaign || selectedSession)"
          @click="confirmSelection"
        >
          {{ selectedSession ? 'Overwrite Session' : 'Create New Session' }}
        </button>
      </div>

      <div class="button-group">
        <button class="btn-save" @click="openCreateCampaign">
          Create new Campaign
        </button>
      </div>

      <div class="button-group">
        <button
          class="btn-delete"
          :disabled="!selectedCampaign && !selectedSession"
          @click="openDeletePrompt"
        >
          Delete
        </button>
      </div>

      <div class="button-group">
        <button class="btn-cancel" @click="showCampaignSelectModal = false; deselectSessionAndCampaign()">
          Cancel
        </button>
      </div>
    </div>
  </div>
  <div v-if="showCampaignCreateModal" class="modal-overlay">
    <div class="modal">
      <h2>Create New Campaign</h2>

      <input
        v-model="newCampaignName"
        placeholder="Campaign name"
        class="modal-input"
      />

      <div class="modal-buttons">
        <button class="btn-cancel" @click="showCampaignCreateModal = false">
          Cancel
        </button>
        <button class="btn-save" @click="createCampaign">
          Create
        </button>
      </div>
    </div>
  </div>

  <div v-if="showDeleteConfirm" class="modal-overlay">
    <div class="modal">
      <h2 style="font-family: 'MedievalSharp', cursive; color: black;">Confirm Deletion</h2>

      <p style="font-weight: bold; margin-bottom: 1rem; font-family: 'MedievalSharp', cursive; color: black;">
        Are you sure you want to delete
        <span style="color: darkred;">
          {{ deleteTargetLabel }} "{{ deleteTargetName }}"
        </span>?
      </p>

      <div class="modal-buttons">
        <button class="btn-cancel" @click="cancelDelete">Cancel</button>
        <button class="btn-save" style="background: darkred;" @click="confirmDelete">
          Delete
        </button>
      </div>
    </div>
  </div>

  <div v-if="showOverwriteConfirm" class="modal-overlay">
    <div class="modal">
      <h2 style="font-family: 'MedievalSharp', cursive; color: black;">Confirm Overwrite</h2>

      <p style="font-weight: bold; margin-bottom: 1rem; font-family: 'MedievalSharp', cursive; color: black;">
        Are you sure you want to overwrite
        <span style="color: darkred;">
          {{ selectedSession }}
        </span>?
      </p>

      <div class="modal-buttons">
        <button class="btn-cancel" @click="showOverwriteConfirm = false">Cancel</button>
        <button class="btn-save" style="background: darkred;" @click="confirmOverwrite">
          Overwrite
        </button>
      </div>
    </div>
  </div>

</template>

<style src="@/assets/styles.css"></style>
<style scoped>
/* Header */
.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 50px;
  background-color: rgba(160, 122, 57, 0.95);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
  box-sizing: border-box;
  color: #e0d5b7;
  z-index: 1000;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.timeline-button,
.new-session-button,
.rulebook-button,
.config-button,
.export-button {
  padding: 0.5rem 1rem;
  background-color: rgba(53, 73, 94, 0.9);
  border: 1px solid #4a575e;
  border-radius: 4px;
  color: #fff;
  cursor: pointer;
  font-family: 'MedievalSharp', cursive;
  font-weight: normal;
  transition: background-color 0.3s ease;
}

.timeline-button:hover,
.new-session-button:hover,
.rulebook-button:hover,
.config-button:hover,
.export-button:hover {
  background-color: #4a575e;
}

.new-session-button {
  background-color: #8f3f28;
  border-color: #6a2f20;
}

.new-session-button:hover {
  background-color: #6f2f20;
}

.timeline-button:disabled,
.new-session-button:disabled,
.rulebook-button:disabled,
.config-button:disabled,
.export-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.modal {
  background: rgba(163, 148, 95, 0.8);
  border-radius: 12px;
  padding: 24px;
  width: 320px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  text-align: center;
}

.modal h2 {
  font-size: 1.2rem;
  font-weight: 600;
  margin-bottom: 1rem;
  font-family: 'MedievalSharp', cursive;
}

.modal-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 1rem;
  font-family: 'MedievalSharp', cursive;
  font-weight: bolder;
  margin-bottom: 1rem;
  outline: none;
}

.modal-input:focus {
  border-color: #3b82f6;
  background-color: #f1e6b4;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
}

.modal-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-delete,
.btn-cancel,
.btn-save {
  background-color: rgba(53, 73, 94, 0.9);
  padding: 6px 12px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-family: 'MedievalSharp', cursive;
  font-weight: 500;
  transition: background 0.2s ease;
}

.btn-delete {
  background-color: #b74d30;
  color: white;
  border: 1px solid #8e7513;
}

.btn-cancel {
  background: #ddd;
}

.btn-cancel:hover {
  background: #ccc;
}

.btn-save {
  background-color: rgba(53, 73, 94, 0.9);
  border: 1px solid #4a575e;
  border-radius: 4px;
  color: #fff;
}

.btn-save:disabled,
.btn-delete:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.btn-delete:hover {
  background-color: #7e6f34;
}

.btn-save:hover {
  background-color: #4a575e;
}

.button-group {
  margin-bottom: 12px;
}

.button-group:last-child {
  margin-bottom: 0;
}

.campaign-name {
  cursor: pointer;
  color: black;
  font-weight: bold;
  font-family: 'MedievalSharp', cursive;
  display: block;
  margin-bottom: 4px;
}

.campaign-name:hover {
  text-decoration: underline;
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
  margin-bottom: 1rem;
  padding: 4px;
}

.selected {
  background: rgba(53, 73, 94, 0.35);
  border-radius: 4px;
}

.session-name-font:hover {
  background: rgba(0,0,0,0.1);
}
</style>
