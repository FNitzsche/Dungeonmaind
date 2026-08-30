
import { defineStore } from 'pinia'
import { ref, computed, type Ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import { SERVER_CONFIG } from '@/config/config'
import { useTimelineStore } from '@/stores/timeline'

export const useRecorderStore = defineStore('recorder', () => {

  const timelineStore = useTimelineStore()

  const micPermissionStatus = ref<string>('')
  const isRecording = ref<boolean>(false)
  const audioStream = ref<MediaStream | null>(null)
  const mediaRecorder = ref<MediaRecorder | null>(null)
  const audioChunks = ref<Blob[]>([])
  const recordedAudioURL = ref<string | null>(null)
  const currentAudio = ref<HTMLAudioElement | null>(null)
  const audioRecorderInterval: Ref<number | null> = ref(null)
  const isFinalStop = ref(false)
  const isStopping = ref(false)
  const isFirstUploadedChunk = ref(true)

  const timerInterval: Ref<number | null> = ref(null)
  const currentRecordingTime = ref(0)
  const recordingStartTime = ref<number | null>(null)
  const recordingDuration = ref<number>(0)

  const transcriptionStatus = ref<string>('')
  const canExportSession = ref<boolean>(false)

  const uploadedDurationSeconds = ref(0)
  
  let cleanupDone = false
  let uploadQueue: Promise<void> = Promise.resolve()

  function baseUrl(): string {
    const session = useSessionStore()
    return session.backendUrl ?? SERVER_CONFIG.BASE_URL
  }

  function endpoint(path: string): string {
    const u = new URL(baseUrl())
    u.pathname = path.startsWith('/') ? path : `/${path}`
    return u.toString()
  }

  function pickMimeType(): string | undefined {
    const candidates = [
      'audio/ogg;codecs=opus',
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
    ]
    for (const t of candidates) if (MediaRecorder.isTypeSupported(t)) return t
    return undefined
  }

  const formattedRecordingTime = computed(() => {
    const elapsed = currentRecordingTime.value
    const seconds = Math.floor(elapsed / 1000)
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60

    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
  })

  function startTimer() { //timer for recorded audio
    stopTimer()
  currentRecordingTime.value = 0
  recordingStartTime.value = Date.now()

  timerInterval.value = window.setInterval(() => {
    if (recordingStartTime.value && isRecording.value) {
      currentRecordingTime.value = Date.now() - recordingStartTime.value
    } else if (!isRecording.value) {
      // Auto-stop timer if recording stopped elsewhere
      stopTimer()
    }
  }, 100)
}

  function stopTimer() {
    if (timerInterval.value) {
      clearInterval(timerInterval.value)
      timerInterval.value = null
    }

    if (recordingStartTime.value && isRecording.value) {
      recordingDuration.value = Date.now() - recordingStartTime.value
      currentRecordingTime.value = recordingDuration.value
    }
  }

  function resetTimer() {
    stopTimer()
    currentRecordingTime.value = 0
    recordingDuration.value = 0
  }

   function cleanup() { //detach beforeunload handler(emergency cleanup) when recording starts
    if (cleanupDone) {
      window.removeEventListener('beforeunload', immediateShutdown)
      cleanupDone = false
    }
  }

  function immediateShutdown() { // hard stop recorder if still active
    try {
      if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
        mediaRecorder.value.stop()
      }
    } catch (err) {
      console.warn('Recorder shutdown error (stop):', err)
    }
    try {
      audioStream.value?.getTracks().forEach(t => t.stop())
    } catch (err) {
      console.warn('Recorder shutdown error (tracks):', err)
    }
    stopTimer()
  }

  async function startRecording() {
    if (isRecording.value) return
    micPermissionStatus.value = ''
    transcriptionStatus.value = ''
    canExportSession.value = false


    resetTimer()
    recordingStartTime.value = Date.now()
    clearAudioPreview()
    audioChunks.value = []
    isFinalStop.value = false
    isFirstUploadedChunk.value = true
    uploadedDurationSeconds.value = 0
    uploadQueue = Promise.resolve()

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      micPermissionStatus.value = 'Microphone access granted.'
      audioStream.value = stream

      const mimeType = pickMimeType()
      if (!mimeType) {
        micPermissionStatus.value = 'No supported audio format.'
        stream.getTracks().forEach(t => t.stop())
        return
      }

      mediaRecorder.value = new MediaRecorder(stream, { mimeType })

      mediaRecorder.value.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.value.push(e.data)
      }

      mediaRecorder.value.onstop = () => {
        isStopping.value = false
        isRecording.value = !isFinalStop.value
        const chunks = audioChunks.value
        audioChunks.value = []

        queueMicrotask(async () => {
          if (chunks.length > 0) {
            const last = new Blob(chunks, { type: mediaRecorder.value?.mimeType })
            void queueAudioChunk(last, isFinalStop.value)
          }

          if (isFinalStop.value) {
            try { audioStream.value?.getTracks().forEach(t => t.stop()) }
            catch (err) {
              console.warn('Audio track stop failed during finalization:', err)
            }
            const finalBlob = new Blob(chunks, { type: mediaRecorder.value?.mimeType })
            recordedAudioURL.value = URL.createObjectURL(finalBlob)

            stopTimer()
            if (recordingStartTime.value) {
              recordingDuration.value = Date.now() - recordingStartTime.value
            }
          } else {
            mediaRecorder.value?.start()
          }
        })
      }

      mediaRecorder.value.start()
      isRecording.value = true

      startTimer()

      setTimeout(() => {  //early flush
        if (mediaRecorder.value && mediaRecorder.value.state === 'recording') {
          mediaRecorder.value.requestData()
        }
      }, 250)

      //rotate every 30 sek
      const spliceTime = 3 * 10 * 1000
      if (audioRecorderInterval.value) clearInterval(audioRecorderInterval.value)
      audioRecorderInterval.value = window.setInterval(rotateRecording, spliceTime)

      if (!cleanupDone) {
        window.addEventListener('beforeunload', immediateShutdown, { passive: true })
        cleanupDone = true
      }
    } catch (err) {
      console.error('Microphone access denied:', err)
      micPermissionStatus.value = 'Microphone access required'
    }
  }

  function rotateRecording() {
    const mr = mediaRecorder.value
    if (!mr || mr.state !== 'recording' || isStopping.value) return

    requestAnimationFrame(() => {
      try { mr.requestData() } catch (err) {
        console.warn('Failed to request audio data during rotation:', err)
      }
      setTimeout(() => { try { mr.stop() } catch (err) {
        console.warn('Failed to stop recorder during rotation', err)
      } }, 100)
    })
  }

  function stopRecording() {
  if (!mediaRecorder.value || mediaRecorder.value.state === 'inactive' || isStopping.value) return

  isStopping.value = true
  isFinalStop.value = true

  transcriptionStatus.value = 'Transcribing the audio recording currently.'
  canExportSession.value = false

  if (audioRecorderInterval.value) {
    clearInterval(audioRecorderInterval.value)
    audioRecorderInterval.value = null
  }
  stopTimer()

  requestAnimationFrame(() => {
    try { mediaRecorder.value?.requestData() } catch (err) {
      console.warn('Failed to request data before stopping recording:', err)
    }

    setTimeout(() => {
      try { mediaRecorder.value?.stop() } catch (err) {
        console.warn('Failed to stop MediaRecorder cleanly:', err)
      }
    }, 120)
  })
}
  
  async function getAudioDuration(blob: Blob): Promise<number> {
    return new Promise((resolve) => {
      const audio = document.createElement('audio')
      const objectUrl = URL.createObjectURL(blob)

      audio.preload = 'metadata'
      audio.src = objectUrl

      audio.onloadedmetadata = () => {
        const duration = Number.isFinite(audio.duration)
          ? audio.duration
          : 0

        URL.revokeObjectURL(objectUrl)
        resolve(duration)
      }

      audio.onerror = () => {
        URL.revokeObjectURL(objectUrl)
        resolve(0)
      }
    })
  }

  function queueAudioChunk(
    chunk: Blob,
    isFinalSegment = false,
  ): Promise<void> {
    uploadQueue = uploadQueue.then(
      () => sendAudioChunk(chunk, isFinalSegment),
    )

    return uploadQueue
  }

  async function sendAudioChunk(
    chunk: Blob,
    isFinalSegment = false,
  ): Promise<void> {
    const form = new FormData()
  
    const fileExtension =
      chunk.type.split('/')[1]?.split(';')[0] || 'webm'
  
    form.append(
      'audio',
      chunk,
      `chunk_${Date.now()}.${fileExtension}`,
    )
  
    try {
      const chunkDuration = await getAudioDuration(chunk)
    
      const requestUrl = new URL(
        endpoint(
          SERVER_CONFIG.ENDPOINTS.TRANSCRIBE_AUDIO_FILE,
        ),
      )
    
      // First chunk clears old transcription data.
      // Later chunks are appended.
      requestUrl.searchParams.set(
        'replace_existing',
        String(isFirstUploadedChunk.value),
      )
    
      // Add the duration of previous chunks to this chunk's timestamps.
      requestUrl.searchParams.set(
        'time_offset',
        String(uploadedDurationSeconds.value),
      )
    
      const response = await fetch(
        requestUrl.toString(),
        {
          method: 'POST',
          body: form,
        },
      )
    
      if (!response.ok) {
        console.error(
          'Chunk upload failed:',
          response.status,
        )
      
        if (isFinalSegment) {
          transcriptionStatus.value = 'Transcription failed.'
          canExportSession.value = true
        }
      
        return
      }
    
      const result = await response.json()
    
      console.log(
        'Chunk transcribed successfully:',
        result,
      )
    
      // From now on, do not delete previous chunks.
      isFirstUploadedChunk.value = false
    
      // Example:
      // first chunk = 30 seconds
      // next chunk starts at 30 seconds
      uploadedDurationSeconds.value += chunkDuration
    
      if (isFinalSegment) {
        transcriptionStatus.value =
          'Transcription completed. Generating timeline...'

        await timelineStore.regenerateTimeline()

        if (timelineStore.error) {
          transcriptionStatus.value =
            `Transcription completed, but timeline generation failed: ${timelineStore.error}`
        } else {
          transcriptionStatus.value =
            'Transcription and timeline generation completed. This session can now be saved.'
        }

        canExportSession.value = true
      }
    } catch (error) {
      console.error(
        'Error sending audio chunk:',
        error,
      )
    
      if (isFinalSegment) {
        transcriptionStatus.value = 'Transcription failed.'
        canExportSession.value = true
      }
    }
  }

  function playRecording() {
  if (!recordedAudioURL.value) return
  if (!currentAudio.value) currentAudio.value = new Audio(recordedAudioURL.value)
  currentAudio.value.pause()
  currentAudio.value.currentTime = 0
  currentAudio.value.play().catch(err => {
    console.error('Error playing recording:', err)
    micPermissionStatus.value = 'Error playing audio'
  })
}

  function clearAudioPreview() { //clear recorded audio to free memory
    if (recordedAudioURL.value) {
      URL.revokeObjectURL(recordedAudioURL.value)
      recordedAudioURL.value = null
    }
  }

  return {
    micPermissionStatus,
    isRecording,
    audioStream,
    mediaRecorder,
    audioChunks,
    recordingDuration,
    recordingStartTime,
    recordedAudioURL,
    currentAudio,
    isStopping,
    formattedRecordingTime,
    transcriptionStatus,
    canExportSession,
    startRecording,
    stopRecording,
    rotateRecording,
    playRecording,
    clearAudioPreview,
    cleanup,
  }
})
