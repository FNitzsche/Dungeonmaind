<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { SERVER_CONFIG } from '../config/config'

const router = useRouter()
const userInput = ref<string>('')
const modelOutput = ref<string>('')
const isLoading = ref<boolean>(false)

const selectedAudioFile = ref<File | null>(null)
const audioUploadStatus = ref<string>('')

const micPermissionStatus = ref('')
const isRecording = ref(false)
const audioStream = ref<MediaStream | null> (null)
const mediaRecorder = ref<MediaRecorder | null >(null)
const audioChunks = ref<Blob[]>([])
const recordedAudioURL = ref<string | null>(null)
const currentAudio = ref<HTMLAudioElement | null>(null)

const diceResult = ref<string>('')

function goToConfig() {
  router.push('/config')
}

async function handleLLMQuestionSubmit() {
  if (isLoading.value) return // prevent spamming the button
  isLoading.value = true
  modelOutput.value = ''

  try {
    const response = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.RUN_LLM}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({input_string: userInput.value}),
    })
    if (!response.ok || !response.body) {
      throw new Error(`Request failed with status ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    while (true) {
      const {done, value} = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, {stream: true})
      modelOutput.value += chunk
    }
  } catch (error) {
    console.error('Error calling LLM endpoint:', error)
    modelOutput.value = 'Error calling model, error: ' + error
  } finally {
    isLoading.value = false //  unlock after done
  }
}

async function handleAudioUpload() {
  if (!selectedAudioFile.value) {
    audioUploadStatus.value = 'Please choose an audio file.'
    return
  }

  const formData = new FormData()
  formData.append('audio', selectedAudioFile.value)

  try {
    const response = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.TRANSCRIBE_AUDIO_FILE}`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      throw new Error(`Upload failed with status ${response.status}`)
    }
    const result = await response.json()
    audioUploadStatus.value = `Upload successfull: ${result.message || 'Audio file received'}`
  } catch (error) {
    console.error('An error occured while uploading your audio file:', error)
    audioUploadStatus.value = 'Upload error'
  }
}

function onAudioFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  if (target?.files && target.files.length > 0) {
    selectedAudioFile.value = target.files[0]
  } else {
    selectedAudioFile.value = null
  }
}

async function startRecording(){
  try{
    const stream = await navigator.mediaDevices.getUserMedia({audio: true})
    micPermissionStatus.value = 'Microphone access granted.'
    audioStream.value = stream
    audioChunks.value = []
    recordedAudioURL.value = null

    mediaRecorder.value = new MediaRecorder(stream)
    mediaRecorder.value.ondataavailable = (e) => e.data.size && audioChunks.value.push(e.data)
    mediaRecorder.value.onstop = () => {
      const audioBlob = new Blob(audioChunks.value, {type: 'audio/wav'  })
      recordedAudioURL.value = URL.createObjectURL(audioBlob)
    }

    mediaRecorder.value.start()
    isRecording.value = true
  } catch(error){
    console.error('Microphone access denied:', error)
    micPermissionStatus.value = 'Microphone access required'
  }
}


function stopRecording(){
    mediaRecorder.value?.stop()
    isRecording.value = false
}


function playRecording(){
  if(!recordedAudioURL.value) return

  if(!currentAudio.value) {
    currentAudio.value = new Audio(recordedAudioURL.value)
  }

  currentAudio.value.pause()
  currentAudio.value.currentTime = 0
  currentAudio.value.play()

}

async function transcribeRecording() {
  if (!audioChunks.value.length){
    audioUploadStatus.value = 'No audio to transcribe !'
    return
  }

  const audioBlob = new Blob(audioChunks.value,{type: 'audio/wav'})
  const formData = new FormData()
  formData.append('audio', audioBlob, 'recording.wav')

  try {
    const response = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.TRANSCRIBE_AUDIO_FILE}`,{
      method: 'POST',
      body: formData
    })

    if (!response.ok){
      throw new Error(`Transcription failed with status ${response.status}`)
    }

    const result = await response.json()
    audioUploadStatus.value = `Transcription: ${result.message || 'Success'}`
  } catch (error) {
    console.error('Transcription error:', error)
    audioUploadStatus.value = 'Transcription failed.'
  }
}

function rollDice(sides: number) {
  const result = Math.floor(Math.random() * sides) + 1
  diceResult.value = `W${sides} → ${result}`
}

</script>

<template>
  <div class="container">

    <div class="header">
      <div class="header-left"></div>
      <h1>Dungeonmaind</h1>
      <button class="config-button" @click="goToConfig">Config</button>
    </div>

    <div class="centered-content">
      <div class="content-section">
        <h2>Enter Your Text</h2>
        <input v-model="userInput" type="text" placeholder="Type something..." class="input-field" />
        <button @click="handleLLMQuestionSubmit" class="submit-button" :disabled="isLoading">
          {{ isLoading ? 'Loading...' : 'Submit' }}
        </button>
        <div v-if="modelOutput" class="output">
          <h3>Model Output:</h3>
          <p>{{ modelOutput }}</p>
        </div>
      </div>

      <hr style="margin: 2rem 0" />

      <div class="content-section">
        <h2> Record Using Microphone</h2>
        <button @click="startRecording" v-if="!isRecording" class="submit-button"> Start Recording </button>
        <button @click="stopRecording" v-if="isRecording" class="submit-button"> Stop Recording </button>

        <div v-if="isRecording" class="output">
          <p> Recording in progress </p>
        </div>

        <div v-if="micPermissionStatus" class="output">
          <p>{{ micPermissionStatus }} </p>
        </div>

        <div v-if="recordedAudioURL" class="output">
          <p>Recording completed </p>
        </div>

        <div v-if="recordedAudioURL" class="play-button">
          <button @click="playRecording" class="submit-button"> Play Recording </button>
          <button @click="transcribeRecording" class="submit-button"> Transcribe Recording </button>
        </div>
      </div>

      <hr style="margin: 2rem 0" />

      <div class="content-section">
        <h2>Upload Audio File</h2>
        <input type="file" accept="audio/*" @change="onAudioFileChange" class="input-field" />
        <button @click="handleAudioUpload" class="submit-button">Upload Audio</button>

        <div v-if="audioUploadStatus" class="output">
          <p>{{ audioUploadStatus }}</p>
        </div>
      </div> <!-- Close content-section before dice-widget -->

      <div class="dice-widget">
        <div class="dice-buttons">
          <button @click="rollDice(4)" class="dice-button">W4</button>
          <button @click="rollDice(6)" class="dice-button">W6</button>
          <button @click="rollDice(8)" class="dice-button">W8</button>
          <button @click="rollDice(12)" class="dice-button">W12</button>
          <button @click="rollDice(20)" class="dice-button">W20</button>
        </div>
        <div class="dice-result" v-if="diceResult">
          {{ diceResult }}
        </div>
      </div>
    </div> <!-- Close centered-content -->
  </div> <!-- Close container -->
</template>


<!-- This block essential for full-page background -->
<style>
html,
body {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  background-image: url('/bg-texture.jpg');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
  background-color: rgba(160, 122, 57, 0.95);
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
</style>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');

.container {
  max-width: 600px;
  margin: 2rem auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  max-height: 90vh; /* limits height to viewport height minus some margin */
}

.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 50px;
  background-color: rgba(160, 122, 57, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 1rem;
  box-sizing: border-box;
  color: #e0d5b7;
  z-index: 1000;
}

.centered-content {
  background-color: rgba(163, 148, 95, 0.8);
  padding: 2rem;
  border-radius: 8px;
  max-width: 600px;
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
}

.config-button {
  position: absolute;
  right: 1rem;
  padding: 0.5rem 1rem;
  background-color: rgba(53, 73, 94, 0.9);
  border: 1px solid #4a575e;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  font-family: 'MedievalSharp', cursive;
  font-weight: normal; 
  z-index: 1001;
  transition: background-color 0.3s ease;
}

.config-button:hover {
  background-color: #4a575e;
}

.content-section {
  display: flex;
  flex-direction: column;
  align-items: center;
}

h1 {
  color: #392401;
  text-align: center;
  padding-top: 20px;
  margin-top: 0;
  margin-bottom: 1.5rem;
  font-family: 'MedievalSharp', cursive;
  font-weight: bolder; 
}


h2 {
  color: #392401;
  text-align: center;
  margin-top: 0;
  font-size: x-large;
  margin-bottom: 1.5rem;
  font-family: 'MedievalSharp', cursive;
  font-weight: bolder; 
}

hr {
  width: 100%;
  border: none;
  border-top: 1px solid rgba(94, 80, 53, 0.5);
  margin: 2rem 0;
}

.input-field {
  padding: 0.75rem;
  font-size: 1rem;
  margin-bottom: 1rem;
  border: 1px solid #695710;
  border-radius: 10px;
  font-family: 'MedievalSharp', cursive;
  font-weight: bolder; 
  background-color: #f1e6b4;
  
  color: #4c3e06;
  width: 90%;
  box-sizing: border-box;
}

.submit-button {
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  background-color: #b74d30;
  color: white;
  border: 1px solid #8e7513;
  border-radius: 10px;
  cursor: pointer;
  margin-bottom: 1rem;
  font-family: 'MedievalSharp', cursive;
  font-weight: normal; 
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  transition: all 0.2s ease;
}

.submit-button:hover:not(:disabled) {
  background-color: #7e6f34;
  transform: translateY(-1px);
}

.submit-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.play-button {
  display: flex;
  justify-content: center;
  margin-top: 1rem;
  gap: 1rem;
}

.output {
  width: 100%;
  max-height: 300px;
  overflow-y: auto;
  padding: 1rem;
  margin-top: 1rem;
  background-color: rgba(110, 97, 50, 0.7);
  color: white;
  border-radius: 10px;
  border: 1px solid #000000;
  font-family: 'MedievalSharp', cursive;
  font-weight: bold; 
  font-weight: 400;
  box-sizing: border-box;
}

.output p {
  margin: 0;
}

.output h3 {
  margin-top: 0;
  margin-bottom: 0.5rem;
  color: #f1e6b4;
}

.dice-widget {
  position: fixed;
  right: 25%;
  top: 43%;
  transform: translateX(20%);
  background-color: rgba(163, 148, 95, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 1.5rem;
  width: 300px;
  margin-left: 2rem;
  z-index: 100;
  font-family: 'MedievalSharp', cursive;
  color: #392401;
}

.dice-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}

.dice-button {
  flex: 1 0 30%;
  padding: 0.75rem;
  font-size: 1rem;
  background-color: #b74d30;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.dice-button:hover {
  background-color: #369f6e;
}

.dice-result {
  margin-top: 1rem;
  text-align: center;
  font-weight: bold;
}
</style>
