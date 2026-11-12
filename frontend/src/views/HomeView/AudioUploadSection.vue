<script setup lang="ts">
/**
 * AudioUploadSection – allows the leader to upload a pre-recorded audio file
 * for transcription by the backend.
 */
import { ref } from 'vue'
import { SERVER_CONFIG } from '@/config/config'
import { useSessionStore } from '@/stores/session'

const selectedAudioFile = ref<File | null>(null)
const audioUploadStatus = ref<string>('')
const isUploading = ref<boolean>(false)

/** Audio upload */
async function handleAudioUpload() {
  if (!selectedAudioFile.value) {
    audioUploadStatus.value = 'Please choose an audio file.'
    return
  }

  const formData = new FormData()
  formData.append('audio', selectedAudioFile.value)
  formData.append('session_id', useSessionStore().sessionId)

  isUploading.value = true
  audioUploadStatus.value = 'Audio is uploading, please wait...'

  try {
    const response = await fetch(
      `${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.TRANSCRIBE_AUDIO_FILE}`,
      {
        method: 'POST',
        body: formData,
      },
    )
    if (!response.ok) {
      throw new Error(`Upload failed with status ${response.status}`)
    }
    const result = await response.json()
    audioUploadStatus.value = `Upload successful: ${result.message || 'Audio file received'}`
  } catch (error) {
    console.error('An error occurred while uploading your audio file:', error)
    audioUploadStatus.value = 'Upload error'
  } finally {
    isUploading.value = false
  }
}

function onAudioFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  selectedAudioFile.value = target?.files && target.files.length > 0 ? target.files[0] : null
}
</script>

<style scoped>
.output {
  margin-bottom: var(--dm-space-4);
}
</style>

<template>
  <div class="content-section">
    <!-- Leader-only: upload -->
    <h2>Upload Audio File</h2>
    <input type="file" accept="audio/*" @change="onAudioFileChange" class="input-field" />

    <div v-if="audioUploadStatus" class="output">
      <p>{{ audioUploadStatus }}</p>
    </div>

    <button @click="handleAudioUpload" class="submit-button" :disabled="isUploading">
      {{ isUploading ? 'Uploading...' : 'Upload Audio' }}
    </button>
  </div>
</template>
