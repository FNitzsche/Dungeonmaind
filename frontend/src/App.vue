<script setup lang="ts">
import { ref } from 'vue'

const userInput = ref<string>('')
const modelOutput = ref<string>('')

const selectedAudioFile = ref<File | null>(null)
const audioUploadStatus = ref<string>('')

async function handleLLMQuestionSubmit() {
  try {
    const response = await fetch('http://localhost:8000/llm/runLLM', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ input_string: userInput.value }),
    })
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`)
    }
    const data = await response.json()
    modelOutput.value = data.output
  } catch (error) {
    console.error('Error calling LLM endpoint:', error)
    modelOutput.value = 'Error calling model'
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
    const response = await fetch('http://localhost:8000/processAudioData/transcribeAudioFile', {
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
</script>

<template>
  <div class="container">
    <h1>Enter Your Text</h1>
    <input v-model="userInput" type="text" placeholder="Type something..." class="input-field" />
    <button @click="handleLLMQuestionSubmit" class="submit-button">Submit</button>

    <div v-if="modelOutput" class="output">
      <h2>Model Output:</h2>
      <p>{{ modelOutput }}</p>
    </div>

    <hr style="margin: 2rem 0" />

    <h1>Upload Audio File</h1>
    <input type="file" accept="audio/*" @change="onAudioFileChange" class="input-field" />
    <button @click="handleAudioUpload" class="submit-button">Upload Audio</button>

    <div v-if="audioUploadStatus" class="output">
      <p>{{ audioUploadStatus }}</p>
    </div>
  </div>
</template>


<style scoped>
.container {
  max-width: 600px;
  margin: 2rem auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

h1 {
  margin-bottom: 1rem;
  text-align: center;
}

.input-field {
  padding: 0.5rem;
  font-size: 1rem;
  margin-bottom: 1rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.submit-button {
  padding: 0.75rem;
  font-size: 1rem;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 1rem;
}

.submit-button:hover {
  background-color: #369f6e;
}

.output {
  padding: 1rem;
  background-color: #f9f9f9;
  border-radius: 4px;
  border: 1px solid #eee;
}
</style>
