import { useSessionStore } from '@/stores/session.ts'
// Set the server and enpdoints
export const SERVER_CONFIG = {
  get BASE_URL() {
    const store = useSessionStore();
    return store.backendUrl || "http://localhost:8000"; // Fallback
  },
  get LOCAL_NETWORK_IP() {
    const store = useSessionStore();
    return store.localNetworkIP || "";
  },
  ENDPOINTS: {
    RUN_LLM: '/llm/run',
    TRANSCRIBE_AUDIO_FILE: '/processAudioData/transcribeAudioFile',
    CHANGE_CONFIG: '/config/changeConfig',
    GET_CONFIG: '/config/getConfig',
    CHECK_CONNECTION: '/health/checkConnection',
    PLAYERS: '/players',
    WS_PLAYERS: '/ws/players',
    RULEBOOK_FOLDERS: '/rulebook/folders',
    RULEBOOK_FILE: '/rulebook/file',
    RULEBOOK_SEARCH: '/rulebook/search',
    EXPORT_SESSION: '/exportImport/export',
    IMPORT_SESSION: '/exportImport/import',
    GET_SESSIONS: '/exportImport/getSessions',
    GET_CAMPAIGNS: '/exportImport/getCampaigns',
    DELETE_SESSION_OR_CAMPAIGN: '/exportImport/deleteCampaignsOrSessions',
    RENAME_SESSION: '/exportImport/renameSession',

    TIMELINE_EVENTS: '/timeline/events',
    TIMELINE_GENERATE: '/timeline/generate',
    TIMELINE_SEED_SAMPLE: '/timeline/dev/seed-sample',
  },
}

// Set the available LLM models
export const LLM_OPTIONS = [
  { value: 'hf.co/bartowski/mistralai_Ministral-3-3B-Instruct-2512-GGUF:Q5_K_M', label: 'Ministral3-3B'},
  { value: 'hf.co/bartowski/mistralai_Ministral-3-14B-Instruct-2512-GGUF:Q5_K_M', label: 'Ministral3-14B'},
  { value: 'hf.co/bartowski/google_gemma-3-1b-it-qat-GGUF:Q5_K_M', label: 'Gemma3-1B' },
  { value: 'hf.co/bartowski/google_gemma-3-12b-it-qat-GGUF:Q5_K_M', label: 'Gemma3-12B' },
  { value: 'hf.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF:Q5_K_M', label: 'Phi4-3.8B' },
]

// Set the default LLM model
export const DEFAULT_LLM = LLM_OPTIONS[0].value

// Set the available transcription models
export const TRANSCRIPTION_MODELS = [
  { value: 'base', label: 'Base' },
  { value: 'medium', label: 'Medium' },
  { value: 'large-v3', label: 'Large' },
]

// Set the default transcription model
export const DEFAULT_TRANSCRIPTION_MODEL = TRANSCRIPTION_MODELS[0].value

// Set the available embedding models
export const EMBEDDING_MODELS = [
  { value: 'all-MiniLM-L6-v2', label: 'all-MiniLM-L6-v2' },
  { value: 'all-MiniLM-L12-v2', label: 'all-MiniLM-L12-v2' },
  { value: 'paraphrase-multilingual-MiniLM-L12-v2', label: 'paraphrase-multilingual-MiniLM-L12-v2' },
]

// Set the default embedding model
export const DEFAULT_EMBEDDING_MODEL = EMBEDDING_MODELS[0].value

// Set the available embedding models
export const EMBEDDING_TopK = [
  { value: '3', label: '3' },
  { value: '6', label: '6' },
  { value: '9', label: '9' },
  { value: '12', label: '12' },
]

// Set the default embedding model
export const DEFAULT_EMBEDDING_TopK = EMBEDDING_TopK[1].value
