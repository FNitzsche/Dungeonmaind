<script setup lang="ts">
import { ref } from 'vue'

import { SERVER_CONFIG } from '@/config/config'
import { useTimelineStore } from '@/stores/timeline'

interface TranscriptionSegment {
  start: number
  end: number
  text: string
}

interface TranscriptionResponse {
  output: TranscriptionSegment[]
}

const timelineStore = useTimelineStore()

const selectedAudioFile = ref<File | null>(null)
const audioUploadStatus = ref('')
const isUploading = ref(false)

async function handleAudioUpload(): Promise<void> {
  if (!selectedAudioFile.value) {
    audioUploadStatus.value =
      'Please choose an audio file.'
    return
  }

  const formData = new FormData()

  formData.append(
    'audio',
    selectedAudioFile.value,
  )

  isUploading.value = true

  audioUploadStatus.value =
    'Uploading and transcribing audio. This may take several minutes...'

  try {
    const requestUrl = new URL(
      `${SERVER_CONFIG.BASE_URL}` +
      `${SERVER_CONFIG.ENDPOINTS.TRANSCRIBE_AUDIO_FILE}`,
    )

    // Uploaded audio should replace the previous recording data.
    requestUrl.searchParams.set(
      'replace_existing',
      'true',
    )

    // Uploaded audio starts from the beginning.
    requestUrl.searchParams.set(
      'time_offset',
      '0',
    )

    const response = await fetch(
      requestUrl.toString(),
      {
        method: 'POST',
        body: formData,
      },
    )

    if (!response.ok) {
      let errorMessage =
        `Upload failed with status ${response.status}`

      try {
        const errorBody = await response.json()

        if (
          typeof errorBody?.detail === 'string'
        ) {
          errorMessage = errorBody.detail
        }
      } catch {
        // Keep the fallback error message.
      }

      throw new Error(errorMessage)
    }

    const result =
      (await response.json()) as TranscriptionResponse

    const segmentCount = Array.isArray(
      result.output,
    )
      ? result.output.length
      : 0

    if (segmentCount === 0) {
      throw new Error(
        'The audio was processed, but no speech was detected.',
      )
    }

    audioUploadStatus.value =
      `Transcription completed with ${segmentCount} ` +
      `segment${segmentCount === 1 ? '' : 's'}. ` +
      'Generating timeline...'

    await timelineStore.regenerateTimeline()

    audioUploadStatus.value =
      `Audio processed successfully. ${segmentCount} ` +
      `transcription segment${segmentCount === 1 ? '' : 's'} ` +
      'were added and the timeline was updated.'

    selectedAudioFile.value = null
  } catch (error) {
    console.error(
      'An error occurred while uploading the audio file:',
      error,
    )

    audioUploadStatus.value =
      error instanceof Error
        ? error.message
        : 'Audio upload or transcription failed.'
  } finally {
    isUploading.value = false
  }
}

function onAudioFileChange(
  event: Event,
): void {
  const target =
    event.target as HTMLInputElement

  selectedAudioFile.value =
    target.files &&
    target.files.length > 0
      ? target.files[0]
      : null

  audioUploadStatus.value = ''
}
</script>

<template>
  <div class="content-section">
    <h2>Upload Audio File</h2>

    <input
      type="file"
      accept="audio/*"
      class="input-field"
      :disabled="isUploading"
      @change="onAudioFileChange"
    />

    <button
      type="button"
      class="submit-button"
      :disabled="
        isUploading ||
        !selectedAudioFile
      "
      @click="handleAudioUpload"
    >
      {{
        isUploading
          ? 'Processing Audio…'
          : 'Upload Audio'
      }}
    </button>

    <div
      v-if="audioUploadStatus"
      class="output"
      aria-live="polite"
    >
      <p>{{ audioUploadStatus }}</p>
    </div>
  </div>
</template>

<style src="@/assets/styles.css"></style>