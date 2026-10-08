<script setup lang="ts">
/**
 * RecordingSection – provides UI for starting/stopping microphone recording,
 * checking voiceprint readiness, and showing recording status/timer.
 */
import { computed } from 'vue'
import { useRecorderStore } from '@/stores/recorder.ts'
import { useSessionStore } from '@/stores/session.ts'

/** Holds recording section */

const recorder = useRecorderStore()
const store = useSessionStore()

const allVoiceprintsReady = computed(() => {
  const players = (store.players ?? []).filter(Boolean)
  if (!players.length) return false
  return players.every((p: any) => p?.has_voiceprint === true)
})

async function startRecording() {
  if (!allVoiceprintsReady.value) return
  await recorder.startRecording()
}

function stopRecording() {
  recorder.stopRecording()
}

function playRecording() {
  recorder.playRecording()
}

function getStatusClass() {
  if (recorder.isRecording) return 'output recording-active'
  if (recorder.transcriptionStatus) {
    return recorder.canExportSession
      ? 'output transcription-success'
      : 'output transcription-pending'
  }
  // Default or initial mic status
  return 'output'
}
</script>

<template>
  <div class="content-section">
    <h2>Record Using Microphone</h2>

    <!-- Leader-only: recording -->
    <div class="recording-controls">
      <button
        @click="startRecording"
        v-if="!recorder.isRecording"
        class="submit-button"
        :disabled="!allVoiceprintsReady"
      >
        Start Recording
      </button>
      <p v-if="!recorder.isRecording && !allVoiceprintsReady" class="secondary-medieval-text">
        Please record a voiceprint for each player<br />and for yourself before starting the
        recording
      </p>
      <button @click="stopRecording" v-if="recorder.isRecording" class="submit-button">
        Stop Recording
      </button>
    </div>

    <div
      v-if="recorder.micPermissionStatus || recorder.transcriptionStatus"
      :class="getStatusClass()"
    >
      <p v-if="recorder.transcriptionStatus">{{ recorder.transcriptionStatus }}</p>
      <p v-else-if="recorder.micPermissionStatus">{{ recorder.micPermissionStatus }}</p>
    </div>

    <div v-if="recorder.isRecording" class="recording-timer output">
      <p>Recording: {{ recorder.formattedRecordingTime }}</p>
    </div>

    <div v-if="recorder.recordedAudioURL" class="output">
      <p>Recording completed. Duration: {{ recorder.formattedRecordingTime }}</p>
    </div>

    <div v-if="recorder.recordedAudioURL" class="play-button">
      <button @click="playRecording" class="submit-button">Play Recording</button>
    </div>
  </div>
</template>

<style src="@/assets/styles.css"></style>
<style scoped>
/* Recording specific styles */
.recording-controls {
  display: flex;
  flex-direction: column;
  justify-content: center;
  margin-bottom: 1rem;
}

.recording-timer {
  padding: 1rem;
  margin-top: 1rem;
  background-color: rgba(183, 77, 48, 0.6);
  color: white;
  border-radius: 10px;
  border: 1px solid #000000;
  font-family: 'MedievalSharp', cursive;
  font-size: 1.1em;
  box-sizing: border-box;
  text-align: center;
}

.play-button {
  display: flex;
  justify-content: center;
  margin-top: 1rem;
  gap: 1rem;
}
</style>
