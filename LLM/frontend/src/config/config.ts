// Set the server and enpdoints
export const SERVER_CONFIG = {
  BASE_URL: 'http://localhost:8000',
  ENDPOINTS: {
    RUN_LLM: '/llm/runLLM',
    TRANSCRIBE_AUDIO_FILE: '/processAudioData/transcribeAudioFile',
    CHANGE_CONFIG: '/config/changeConfig',
  },
}

// Set the available LLM models
export const LLM_OPTIONS = [
  { value: 'hf.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF:Q5_K_M', label: 'Phi4-3.8B' },
  { value: 'hf.co/bartowski/Qwen_Qwen3-1.7B-GGUF:Q5_K_M', label: 'Qwen3-1.7B' },
  { value: 'hf.co/bartowski/google_gemma-3-1b-it-qat-GGUF:Q5_K_M', label: 'Gemma3-1B' },
  { value: 'hf.co/bartowski/google_gemma-3-12b-it-qat-GGUF:Q5_K_M', label: 'Gemma3-12B' },
]

// Set the default LLM model
export const DEFAULT_LLM = LLM_OPTIONS[0].value

// Set the available transcription models
export const TRANSCRIPTION_MODELS = [
  { value: 'base', label: 'Base' },
  { value: 'medium', label: 'Medium' },
]

// Set the default transcription model
export const DEFAULT_TRANSCRIPTION_MODEL = TRANSCRIPTION_MODELS[0].value
