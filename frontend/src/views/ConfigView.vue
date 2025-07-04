<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const STORAGE_KEY = 'selectedLLM'
const selectedLLM = ref(localStorage.getItem(STORAGE_KEY) || 'hf.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF:Q5_K_M')

watch(selectedLLM, (newVal) => {
  localStorage.setItem(STORAGE_KEY, newVal)
})

function goHome() {
  router.push('/')
}

async function submitSelection() {
  goHome()
  try {
    const response = await fetch('http://localhost:8000/config/changeConfig', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ selected_LLM: selectedLLM.value })
    })

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`)
    }

    console.log('Auswahl erfolgreich gesendet:', selectedLLM.value)
  } catch (error) {
    console.error('Error calling LLM endpoint:', error)
  }
}

</script>

<template>
  <div class="config-page">
    <h1>Configuration Page</h1>

    <label for="selection">Choose an LLM:</label>
    <select id="selection" v-model="selectedLLM">
      <option value="hf.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF:Q5_K_M">Phi4-3.8B</option>
      <option value="hf.co/bartowski/Qwen_Qwen3-1.7B-GGUF:Q5_K_M">Qwen3-1.7B</option>
      <option value="hf.co/bartowski/google_gemma-3-1b-it-qat-GGUF:Q5_K_M">Gemma3-1B</option>
      <option value="hf.co/bartowski/google_gemma-3-12b-it-qat-GGUF:Q5_K_M">Gemma3-12B</option>
      <option value="option5">Option 5</option>
    </select>

    <button @click="submitSelection" class="done-button">Done</button>
  </div>
</template>

<style scoped>
.config-page {
  max-width: 600px;
  margin: 2rem auto;
  padding: 1rem;
  text-align: center;
}

select {
  margin-top: 1rem;
  padding: 0.5rem;
  font-size: 1rem;
}

.done-button {
  margin-top: 2rem;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.done-button:hover {
  background-color: #369f6e;
}
</style>
