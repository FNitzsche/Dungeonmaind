<script setup lang="ts">
/**
 * AudioUploadSection – allows the leader to upload a pre-recorded audio file
 * for transcription by the backend.
 */
import { ref } from 'vue'
import { SERVER_CONFIG } from '@/config/config'

const selectedAudioFile = ref<File | null>(null)
const audioUploadStatus = ref<string>('')

/** Audio upload */
async function handleAudioUpload() {
  if (!selectedAudioFile.value) {
    audioUploadStatus.value = 'Please choose an audio file.'
    return
  }

  const formData = new FormData()
  formData.append('audio', selectedAudioFile.value)

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
  }
}

function onAudioFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  selectedAudioFile.value = target?.files && target.files.length > 0 ? target.files[0] : null
}
</script>

<template>
  <div class="content-section">
    <!-- Leader-only: upload -->
    <h2>Upload Audio File</h2>
    <input type="file" accept="audio/*" @change="onAudioFileChange" class="input-field" />
    <button @click="handleAudioUpload" class="submit-button">Upload Audio</button>

    <div v-if="audioUploadStatus" class="output">
      <p>{{ audioUploadStatus }}</p>
    </div>
  </div>
</template>

<style src="@/assets/styles.css"></style>
