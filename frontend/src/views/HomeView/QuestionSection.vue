<script setup lang="ts">
/**
 * QuestionSection – allows the user to ask the LLM a question about the D&D session.
 * Supports streaming text responses and optional rulebook search results.
 */
import { ref } from 'vue'
import { SERVER_CONFIG } from '@/config/config'
import { marked } from 'marked'
import { useSessionStore } from '@/stores/session.ts'

/** Holds LLM Question Section */

const store = useSessionStore()

/** UI state */
const userInput = ref<string>('')
const modelOutput = ref<string>('')
const modelOutputRendered = ref<string>('')
const isLoading = ref<boolean>(false)
const askRulebook = ref<boolean>(false)

// Rulebook markdown
const backendMarkdown = ref<string[]>([])
const currentMarkdownIndex = ref(0)
const renderedMarkdown = ref('')

async function handleQuestionSubmit() {
  if (isLoading.value) return // prevent spamming the button
  isLoading.value = true
  modelOutput.value = ''

  if (askRulebook.value) {
    try {
      const response = await fetch(
        `${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.RULEBOOK_SEARCH}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ input_string: userInput.value }),
        },
      )
      if (!response.ok) throw new Error(`Request failed with status ${response.status}`)

      const markdownJson = await response.json()
      backendMarkdown.value = markdownJson.markdown_texts || []
      if (backendMarkdown.value.length > 0) {
        currentMarkdownIndex.value = 0
        renderedMarkdown.value = (await marked.parse(backendMarkdown.value[0])) as string
      }
    } catch (error) {
      console.error('Error calling Rulebook Search endpoint:', error)
    } finally {
      isLoading.value = false //  unlock after done
    }
  } else {
    try {
      const response = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.RUN_LLM}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_id: store.currentPlayer?.id,
          input_string: userInput.value,
          use_rulebook: askRulebook.value,
        }),
      })
      if (!response.ok || !response.body)
        throw new Error(`Request failed with status ${response.status}`)

      // Removes any still shown previous rulebook searches.
      backendMarkdown.value = []
      renderedMarkdown.value = ''

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        modelOutput.value += chunk
        modelOutputRendered.value = marked.parse(modelOutput.value) as string
      }
    } catch (error) {
      console.error('Error calling LLM endpoint:', error)
      modelOutput.value = 'Error calling model, error: ' + error
    } finally {
      isLoading.value = false //  unlock after done
    }
  }
}

function showNextMarkdown() {
  if (currentMarkdownIndex.value < backendMarkdown.value.length - 1) {
    currentMarkdownIndex.value++
    renderedMarkdown.value = marked.parse(
      backendMarkdown.value[currentMarkdownIndex.value],
    ) as string
  }
}

function showPrevMarkdown() {
  if (currentMarkdownIndex.value > 0) {
    currentMarkdownIndex.value--
    renderedMarkdown.value = marked.parse(
      backendMarkdown.value[currentMarkdownIndex.value],
    ) as string
  }
}
</script>

<template>
  <div class="content-section">
    <h2>Ask Something about the DnD-Session</h2>
    <input
      v-model="userInput"
      type="text"
      placeholder="Type something..."
      class="input-field"
      @keyup.enter="handleQuestionSubmit"
    />
    <label
      class="secondary-medieval-text"
      style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer"
    >
      <input type="checkbox" v-model="askRulebook" />
      show matching rulebook pages
    </label>

    <button @click="handleQuestionSubmit" class="submit-button" :disabled="isLoading">
      {{ isLoading ? 'Loading...' : 'Submit' }}
    </button>
    <div v-if="modelOutput" class="markdown-output">
      <h3>Model Output:</h3>
      <div v-html="modelOutputRendered"></div>
    </div>
    <div v-if="backendMarkdown.length" class="markdown-output scrollable-panel">
      <h3>Relevant SRD article</h3>
      <div class="markdown-navigation">
        <button @click="showPrevMarkdown" :disabled="currentMarkdownIndex === 0">Previous</button>
        <span>
          {{ currentMarkdownIndex + 1 }} /
          {{ backendMarkdown.length }}
        </span>
        <button
          @click="showNextMarkdown"
          :disabled="currentMarkdownIndex === backendMarkdown.length - 1"
        >
          Next
        </button>
      </div>
      <div v-html="renderedMarkdown"></div>
    </div>
  </div>
</template>

<style src="@/assets/styles.css"></style>
<style scoped>
/* Markdown styles */
:deep(.markdown-output) {
  font-family: 'MedievalSharp', cursive;
  color: #392401;
  line-height: 1.5;
  margin-top: 1rem;
}

:deep(.markdown-output h1) {
  font-size: 2rem;
  color: #1a3b1a;
  border-bottom: 2px solid #392401;
  padding-bottom: 0.3rem;
  margin-top: 1rem;
}

:deep(.markdown-output h2) {
  font-size: 1.5rem;
  color: #2a4b2a;
  border-bottom: 1px solid #392401;
  padding-bottom: 0.2rem;
  margin-top: 1rem;
}

:deep(.markdown-output h3),
:deep(.markdown-output h4),
:deep(.markdown-output h5),
:deep(.markdown-output h6) {
  color: #3a5b3a;
  margin-top: 0.8rem;
  font-weight: bold;
}

:deep(.markdown-output strong) {
  color: #8b0000;
  font-weight: bold;
}

:deep(.markdown-output em) {
  color: #003366;
  font-style: italic;
}

:deep(.markdown-output strong em),
:deep(.markdown-output em strong) {
  color: #800080;
  font-weight: bold;
  font-style: italic;
}

:deep(.markdown-output table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5rem 0;
  font-size: 0.95rem;
}

:deep(.markdown-output th),
:deep(.markdown-output td) {
  border: 1px solid #392401;
  padding: 0.3rem 0.5rem;
  text-align: center;
}

:deep(.markdown-output th) {
  background-color: #f5e6b4;
  font-weight: bold;
}

:deep(.markdown-output tr:nth-child(even)) {
  background-color: #faf0d4;
}

:deep(.markdown-output p) {
  margin: 0.4rem 0;
}

:deep(.markdown-output h6) {
  font-style: italic;
  color: #4b2e2e;
  margin-top: 0.5rem;
}

:deep(.scrollable-panel) {
  max-height: 400px;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: auto;
  padding: 1rem;
  border: 1px solid #ccc;
  border-radius: 8px;
  background-color: rgba(110, 97, 50, 0.7);
  box-sizing: border-box;
}

:deep(.markdown-navigation) {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
}
</style>
