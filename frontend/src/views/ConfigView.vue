<script setup lang="ts">
/**
 * ConfigView – allows the leader to select LLM, transcription,
 * and embedding models, and submit the changes to the backend.
 */
import { ref, watch } from 'vue'
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
const errorMessage = ''

async function submitSelection() {
  isSubmitting.value = true
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
    <h1>Configuration Page</h1>

    <label for="selection">Choose an LLM:</label>
    <select id="selection" v-model="selectedLLM">
      <option v-for="llm in LLM_OPTIONS" :key="llm.value" :value="llm.value">
        {{ llm.label }}
      </option>
    </select>

    <hr style="margin: 1rem 0" />

    <label for="transModel">Choose Transcription Model:</label>
    <select id="transModel" v-model="selectedTranscriptionModel">
      <option v-for="model in TRANSCRIPTION_MODELS" :key="model.value" :value="model.value">
        {{ model.label }}
      </option>
    </select>

    <hr style="margin: 1rem 0" />
    <div>
      <label>
        <input type="checkbox" v-model="clearChat" />
        Clear Chat History
      </label>
    </div>

    <hr style="margin: 1rem 0" />

    <label for="embeddingModel">Choose Embedding Model:</label>
    <select id="embeddingModel" v-model="selectedEmbeddingModel">
      <option v-for="model in EMBEDDING_MODELS" :key="model.value" :value="model.value">
        {{ model.label }}
      </option>
    </select>

    <div style="margin-top: 1rem"></div>

    <label for="embeddingTopK">Choose Embedding TopK:</label>
    <select id="embeddingTopK" v-model="selectedEmbeddingTopK">
      <option v-for="model in EMBEDDING_TopK" :key="model.value" :value="model.value">
        {{ model.label }}
      </option>
    </select>

    <div style="margin-top: 1rem"></div>

    <div>
      <label>
        <input type="checkbox" v-model="deleteTranscriptions" />
        Delete transcriptions
      </label>
    </div>

    <hr style="margin: 1rem 0" />

    <label v-if="errorHappend">Error occured: {{ errorMessage }}</label>
    <button v-if="errorHappend" @click="cancelSubmit" class="done-button">Cancel</button>
    <button @click="submitSelection" class="done-button" :disabled="isSubmitting">
      {{ isSubmitting ? 'Submitting...' : 'Done' }}
    </button>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');

.config-page {
  max-width: 600px;
  margin: 80px auto 2rem auto; /* leave room for header */
  padding: 2rem;
  background-color: rgba(163, 148, 95, 0.8); /* parchment look */
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  font-family: 'MedievalSharp', cursive;
  font-weight: 600;
  font-size: 1.2rem;
  color: #392401;
  text-align: center;
  box-sizing: border-box;
}

label,
option,
input[type='checkbox'] + label {
  font-weight: 600;
  font-size: 1.1rem;
  font-family: 'MedievalSharp', cursive;
}

select {
  margin-top: 1rem;
  padding: 0.75rem;
  font-family: 'MedievalSharp', cursive;
  font-weight: 600;
  font-size: 1.1rem;
  width: 100%;
  border-radius: 10px;
  border: 1px solid #695710;
  background-color: #f1e6b4;
  color: #4c3e06;
  box-sizing: border-box;
}

.done-button {
  margin-top: 2rem;
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
</style>
