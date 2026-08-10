<script setup lang="ts">
import { ref } from 'vue'
import { marked } from 'marked'

import { SERVER_CONFIG } from '@/config/config'
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const userInput = ref('')
const modelOutput = ref('')
const modelOutputRendered = ref('')
const isLoading = ref(false)
const askRulebook = ref(false)

const backendMarkdown = ref<string[]>([])
const currentMarkdownIndex = ref(0)
const renderedMarkdown = ref('')

async function handleQuestionSubmit(): Promise<void> {
  if (isLoading.value) {
    return
  }

  const question = userInput.value.trim()

  if (!question) {
    modelOutput.value = 'Please enter a question.'
    modelOutputRendered.value = marked.parse(
      modelOutput.value,
    ) as string

    return
  }

  if (askRulebook.value) {
    await searchRulebook(question)
    return
  }

  await askSessionQuestion(question)
}

async function askSessionQuestion(
  question: string,
): Promise<void> {
  const playerId = store.currentPlayer?.id

  if (!playerId) {
    modelOutput.value =
      'Your player session is missing. Please leave and join the session again.'

    modelOutputRendered.value = marked.parse(
      modelOutput.value,
    ) as string

    return
  }

  isLoading.value = true
  modelOutput.value = ''
  modelOutputRendered.value = ''

  backendMarkdown.value = []
  renderedMarkdown.value = ''

  try {
    const response = await fetch(
      `${SERVER_CONFIG.BASE_URL}` +
      `${SERVER_CONFIG.ENDPOINTS.RUN_LLM}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          player_id: playerId,
          input_string: question,
          use_rulebook: false,
        }),
      },
    )

    if (!response.ok) {
      let errorMessage =
        `Request failed with status ${response.status}`

      try {
        const errorBody = await response.json()

        if (typeof errorBody?.detail === 'string') {
          errorMessage = errorBody.detail
        } else if (Array.isArray(errorBody?.detail)) {
          errorMessage = errorBody.detail
            .map(
              (item: {
                loc?: Array<string | number>
                msg?: string
              }) => {
                const location =
                  item.loc?.join(' → ') ?? 'request'

                return `${location}: ${item.msg ?? 'Invalid value'}`
              },
            )
            .join(', ')
        }
      } catch {
        // Keep the fallback error message.
      }

      throw new Error(errorMessage)
    }

    if (!response.body) {
      throw new Error(
        'The server returned an empty response.',
      )
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')

    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        break
      }

      const chunk = decoder.decode(
        value,
        {
          stream: true,
        },
      )

      modelOutput.value += chunk

      modelOutputRendered.value = marked.parse(
        modelOutput.value,
      ) as string
    }

    if (!modelOutput.value.trim()) {
      modelOutput.value =
        'The model returned an empty answer.'

      modelOutputRendered.value = marked.parse(
        modelOutput.value,
      ) as string
    }
  } catch (error) {
    console.error(
      'Error calling LLM endpoint:',
      error,
    )

    modelOutput.value =
      error instanceof Error
        ? `Error: ${error.message}`
        : 'An unknown error occurred.'

    modelOutputRendered.value = marked.parse(
      modelOutput.value,
    ) as string
  } finally {
    isLoading.value = false
  }
}

async function searchRulebook(
  question: string,
): Promise<void> {
  isLoading.value = true
  modelOutput.value = ''
  modelOutputRendered.value = ''

  try {
    const response = await fetch(
      `${SERVER_CONFIG.BASE_URL}` +
      `${SERVER_CONFIG.ENDPOINTS.RULEBOOK_SEARCH}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input_string: question,
        }),
      },
    )

    if (!response.ok) {
      throw new Error(
        `Request failed with status ${response.status}`,
      )
    }

    const markdownJson = await response.json()

    backendMarkdown.value =
      markdownJson.markdown_texts || []

    if (backendMarkdown.value.length > 0) {
      currentMarkdownIndex.value = 0

      renderedMarkdown.value = await marked.parse(
        backendMarkdown.value[0],
      ) as string
    } else {
      renderedMarkdown.value =
        '<p>No matching rulebook pages were found.</p>'
    }
  } catch (error) {
    console.error(
      'Error calling Rulebook Search endpoint:',
      error,
    )

    renderedMarkdown.value =
      '<p>Rulebook search failed.</p>'
  } finally {
    isLoading.value = false
  }
}

function showNextMarkdown(): void {
  if (
    currentMarkdownIndex.value <
    backendMarkdown.value.length - 1
  ) {
    currentMarkdownIndex.value += 1

    renderedMarkdown.value = marked.parse(
      backendMarkdown.value[
        currentMarkdownIndex.value
      ],
    ) as string
  }
}

function showPrevMarkdown(): void {
  if (currentMarkdownIndex.value > 0) {
    currentMarkdownIndex.value -= 1

    renderedMarkdown.value = marked.parse(
      backendMarkdown.value[
        currentMarkdownIndex.value
      ],
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
      :disabled="isLoading"
      @keyup.enter="handleQuestionSubmit"
    />

    <label
      class="secondary-medieval-text"
      style="
        display: flex;
        align-items: center;
        gap: 0.5rem;
        cursor: pointer;
      "
    >
      <input
        v-model="askRulebook"
        type="checkbox"
        :disabled="isLoading"
      />

      Show matching rulebook pages
    </label>

    <button
      type="button"
      class="submit-button"
      :disabled="isLoading || !userInput.trim()"
      @click="handleQuestionSubmit"
    >
      {{ isLoading ? 'Loading...' : 'Submit' }}
    </button>

    <div
      v-if="modelOutput"
      class="markdown-output"
    >
      <h3>Model Output:</h3>

      <div v-html="modelOutputRendered"></div>
    </div>

    <div
      v-if="backendMarkdown.length"
      class="markdown-output scrollable-panel"
    >
      <h3>Relevant SRD article</h3>

      <div class="markdown-navigation">
        <button
          type="button"
          :disabled="currentMarkdownIndex === 0"
          @click="showPrevMarkdown"
        >
          Previous
        </button>

        <span>
          {{ currentMarkdownIndex + 1 }}
          /
          {{ backendMarkdown.length }}
        </span>

        <button
          type="button"
          :disabled="
            currentMarkdownIndex ===
            backendMarkdown.length - 1
          "
          @click="showNextMarkdown"
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
:deep(.markdown-output) {
  margin-top: 1rem;
  color: #392401;
  font-family: 'MedievalSharp', cursive;
  line-height: 1.5;
}

:deep(.markdown-output h1) {
  margin-top: 1rem;
  padding-bottom: 0.3rem;
  border-bottom: 2px solid #392401;
  color: #1a3b1a;
  font-size: 2rem;
}

:deep(.markdown-output h2) {
  margin-top: 1rem;
  padding-bottom: 0.2rem;
  border-bottom: 1px solid #392401;
  color: #2a4b2a;
  font-size: 1.5rem;
}

:deep(.markdown-output h3),
:deep(.markdown-output h4),
:deep(.markdown-output h5),
:deep(.markdown-output h6) {
  margin-top: 0.8rem;
  color: #3a5b3a;
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

:deep(.markdown-output table) {
  width: 100%;
  margin: 0.5rem 0;
  border-collapse: collapse;
  font-size: 0.95rem;
}

:deep(.markdown-output th),
:deep(.markdown-output td) {
  padding: 0.3rem 0.5rem;
  border: 1px solid #392401;
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

:deep(.scrollable-panel) {
  box-sizing: border-box;
  max-width: 100%;
  max-height: 400px;
  overflow: auto;
  padding: 1rem;
  border: 1px solid #ccc;
  border-radius: 8px;
  background-color: rgba(110, 97, 50, 0.7);
}

:deep(.markdown-navigation) {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
}
</style>