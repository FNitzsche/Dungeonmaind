<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const userInput = ref<string>('')
const modelOutput = ref<string>('')
const isLoading = ref<boolean>(false)

function goToConfig() {
  router.push('/config')
}
async function handleSubmit() {
  if (isLoading.value) return // prevent spamming the button
  isLoading.value = true
  modelOutput.value = ''

  try {
    const response = await fetch('http://localhost:8000/llm/runLLM', {
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
</script>

<template>
  <div class="container">
     <div class="header">
       <div class="header-left"></div>
       <h1>Dungeonmaind</h1>
       <button class="config-button" @click="goToConfig">Config</button>
    </div>
    <h2>Enter Your Text</h2>
    <input v-model="userInput" type="text" placeholder="Type something..." class="input-field" />
    <button @click="handleSubmit" class="submit-button" :disabled="isLoading">
      {{ isLoading ? 'Loading...' : 'Submit' }}
    </button>
    <div v-if="modelOutput" class="output">
      <h3>Model Output:</h3>
      <p>{{ modelOutput }}</p>
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

.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  background-color: #35495e;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 1rem;
  box-sizing: border-box;
  color: white;
  z-index: 1000;
  gap: 100px;
}


.config-button {
  position: absolute;
  right: 1rem;
  padding: 0.5rem 1rem;
  background-color: #35495e;
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  z-index: 1001;
}

.config-button:hover {
  background-color: #2c3e50;
}

h2 {
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
