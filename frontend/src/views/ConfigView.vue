<script setup lang="ts">
/**
 * ConfigView – allows the leader to select LLM, transcription,
 * and embedding models, and submit the changes to the backend.
 *
 * Shown as a modal from HomeHeader and as a standalone page on /config.
 * The layout is a header, a scrolling body and a footer, so the Done button
 * stays reachable however short the window is.
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session.ts'
import { useConfigStore } from '@/stores/backendConfig'
import {
  LLM_OPTIONS,
  TRANSCRIPTION_MODELS,
  EMBEDDING_MODELS,
  EMBEDDING_TopK,
} from '@/config/config'
import { type Payload, submitConfig } from '@/api/backendConfigAPI.ts'

const store = useSessionStore()
const configStore = useConfigStore()
const isSubmitting = ref(false)
const selectedLLM = ref(configStore.selectedLLM)
const selectedTranscriptionModel = ref(configStore.transcriptionModel)
const selectedEmbeddingModel = ref(configStore.embeddingModel)
const selectedEmbeddingTopK = ref(configStore.embeddingTopK)
const clearChat = ref(false)
const deleteTranscriptions = ref(false)

const emit = defineEmits(['submit-success'])

const errorHappend = ref(false)
const errorMessage = ref('')

interface SelectOption {
  value: string
  label: string
}

/**
 * The options for one dropdown, plus the value the backend currently reports
 * when that value is not one of them. Without this the dropdown renders blank
 * and hides which model is actually in use.
 * @param options - The known options for this setting.
 * @param current - The value the backend reported.
 */
function withCurrentValue(options: readonly SelectOption[], current: unknown): SelectOption[] {
  const value = current == null ? '' : String(current)
  if (!value || options.some((option) => option.value === value)) {
    return [...options]
  }
  return [...options, { value, label: `${value} (in use)` }]
}

const llmOptions = computed(() => withCurrentValue(LLM_OPTIONS, selectedLLM.value))
const transcriptionOptions = computed(() =>
  withCurrentValue(TRANSCRIPTION_MODELS, selectedTranscriptionModel.value),
)
const embeddingOptions = computed(() =>
  withCurrentValue(EMBEDDING_MODELS, selectedEmbeddingModel.value),
)
const topKOptions = computed(() => withCurrentValue(EMBEDDING_TopK, selectedEmbeddingTopK.value))

async function submitSelection() {
  isSubmitting.value = true
  errorHappend.value = false
  errorMessage.value = ''
  //goHome()
  const payload: Payload = {
    player_id: store.currentPlayer?.id,
    selected_LLM: selectedLLM.value,
    transcription_model: selectedTranscriptionModel.value,
    embedding_model: selectedEmbeddingModel.value,
    embedding_top_k: selectedEmbeddingTopK.value,
    clear_chat: clearChat.value,
    delete_transcriptions: deleteTranscriptions.value,
  }
  try {
    await submitConfig(payload)
    console.log('Configuration successfully submitted')
    emit('submit-success')
  } catch (error) {
    console.error('Error calling submitConfig:', error)
    // Show the backend's reason instead of leaving the page looking stuck.
    errorHappend.value = true
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    isSubmitting.value = false
  }
}

function cancelSubmit() {
  emit('submit-success')
}
</script>

<template>
  <div class="config-page">
    <header class="config-header">
      <h1>Configuration Page</h1>
    </header>

    <div class="config-body">
      <div class="config-field">
        <label for="selection">Choose an LLM:</label>
        <select id="selection" v-model="selectedLLM">
          <option v-for="llm in llmOptions" :key="llm.value" :value="llm.value">
            {{ llm.label }}
          </option>
        </select>
      </div>

      <hr />

      <div class="config-field">
        <label for="transModel">Choose Transcription Model:</label>
        <select id="transModel" v-model="selectedTranscriptionModel">
          <option v-for="model in transcriptionOptions" :key="model.value" :value="model.value">
            {{ model.label }}
          </option>
        </select>
      </div>

      <hr />

      <div class="config-field">
        <label class="checkbox-label">
          <input type="checkbox" v-model="clearChat" />
          <span>Clear Chat History</span>
        </label>
      </div>

      <hr />

      <div class="config-field">
        <label for="embeddingModel">Choose Embedding Model:</label>
        <select id="embeddingModel" v-model="selectedEmbeddingModel">
          <option v-for="model in embeddingOptions" :key="model.value" :value="model.value">
            {{ model.label }}
          </option>
        </select>
      </div>

      <div class="config-field">
        <label for="embeddingTopK">Choose Embedding TopK:</label>
        <select id="embeddingTopK" v-model="selectedEmbeddingTopK">
          <option v-for="model in topKOptions" :key="model.value" :value="model.value">
            {{ model.label }}
          </option>
        </select>
      </div>

      <div class="config-field">
        <label class="checkbox-label">
          <input type="checkbox" v-model="deleteTranscriptions" />
          <span>Delete transcriptions</span>
        </label>
      </div>
    </div>

    <footer class="config-footer">
      <p v-if="errorHappend" class="config-error">Error occured: {{ errorMessage }}</p>
      <div class="config-actions">
        <button @click="cancelSubmit" class="done-button done-button-secondary">Cancel</button>
        <button @click="submitSelection" class="done-button" :disabled="isSubmitting">
          {{ isSubmitting ? 'Submitting...' : 'Done' }}
        </button>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* MedievalSharp is self-hosted and declared once in `assets/styles.css`. */

.config-page {
  /* Header, scrolling body and footer, so the actions are always reachable. */
  display: flex;
  flex-direction: column;
  width: min(600px, calc(100% - 2rem));
  /* Never taller than the window, whether centred in the modal overlay or
     laid out on the /config page. */
  max-height: min(90vh, calc(100vh - 2rem));
  margin: 1rem auto;
  /* Opaque so the page behind never shows through the text. */
  background-color: #a3945f; /* parchment look */
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  font-family: 'MedievalSharp', cursive;
  font-weight: 600;
  font-size: 1.2rem;
  color: #392401;
  text-align: center;
  box-sizing: border-box;
  overflow: hidden; /* keeps the scrolling body inside the rounded corners */
}

.config-header {
  flex: 0 0 auto;
  padding: 1.25rem 1.5rem 0.85rem;
  background-color: #968855;
  border-bottom: 1px solid rgba(57, 36, 1, 0.3);
}

.config-header h1 {
  margin: 0;
  font-size: 1.7rem;
  line-height: 1.2;
}

.config-body {
  flex: 1 1 auto;
  min-height: 0; /* lets the body shrink so it can scroll */
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 1.25rem 1.5rem;
}

.config-footer {
  flex: 0 0 auto;
  padding: 0.9rem 1.5rem 1.1rem;
  background-color: #968855;
  border-top: 1px solid rgba(57, 36, 1, 0.3);
}

.config-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.config-error {
  margin: 0 0 0.75rem;
  font-size: 1rem;
  color: #6b1f0c;
}

.config-field {
  margin-bottom: 1.1rem;
}

.config-field:last-child {
  margin-bottom: 0;
}

.config-field > label {
  display: block;
  margin-bottom: 0.5rem;
}

.config-body hr {
  margin: 1.1rem 0;
  border: none;
  border-top: 1px solid rgba(57, 36, 1, 0.25);
}

label,
option,
input[type='checkbox'] + label {
  font-weight: 600;
  font-size: 1.1rem;
  font-family: 'MedievalSharp', cursive;
}

.checkbox-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  cursor: pointer;
}

.checkbox-label input[type='checkbox'] {
  flex: 0 0 auto;
  width: 1.1rem;
  height: 1.1rem;
  margin: 0;
  accent-color: #b74d30;
  cursor: pointer;
}

select {
  padding: 0.75rem;
  font-family: 'MedievalSharp', cursive;
  font-weight: 600;
  font-size: 1.1rem;
  width: 100%;
  max-width: 100%;
  border-radius: 10px;
  border: 1px solid #695710;
  background-color: #f1e6b4;
  color: #4c3e06;
  box-sizing: border-box;
}

.done-button {
  padding: 0.75rem 1.5rem;
  font-family: 'MedievalSharp';
  font-weight: bold;
  font-weight: 400;
  font-size: 1rem;
  background-color: #b74d30;
  color: white;
  border: 1px solid #8e7513;
  border-radius: 10px;
  cursor: pointer;
}

.done-button:disabled {
  background-color: #7e6f34;
  cursor: not-allowed;
  opacity: 0.7;
}

.done-button:hover {
  background-color: #7e6f34;
}

.done-button-secondary {
  background-color: #6d5a2a;
}

/* Short windows: give the body as much of the height as possible. */
@media (max-height: 560px) {
  .config-header {
    padding: 0.75rem 1.25rem 0.6rem;
  }

  .config-header h1 {
    font-size: 1.3rem;
  }

  .config-body {
    padding: 0.85rem 1.25rem;
  }

  .config-field {
    margin-bottom: 0.8rem;
  }

  .config-body hr {
    margin: 0.8rem 0;
  }

  .config-footer {
    padding: 0.7rem 1.25rem 0.8rem;
  }
}

/* Narrow windows: keep everything inside the width, no sideways scrolling. */
@media (max-width: 480px) {
  .config-page {
    font-size: 1.05rem;
  }

  .config-header,
  .config-body,
  .config-footer {
    padding-left: 1rem;
    padding-right: 1rem;
  }

  .config-actions .done-button {
    flex: 1 1 8rem;
  }
}
</style>
