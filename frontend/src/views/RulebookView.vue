<script setup lang="ts">
/**
 * RulebookView – a file explorer for browsing and reading
 * System Reference Document (SRD) markdown files served by the backend.
 */
import { computed, ref } from 'vue'
import { SERVER_CONFIG } from '../config/config'
import { marked } from 'marked'
import { useRouter } from 'vue-router'

const router = useRouter()
interface FolderData {
  files: string[]
}
const folderStructure = ref<Record<string, FolderData>>({})
const visibleFolders = computed(() => {
  // remove entries with empty keys
  return Object.entries(folderStructure.value)
    .filter(([folder]) => folder.trim() !== '')
    .reduce(
      (acc, [folder, data]) => {
        acc[folder] = data
        return acc
      },
      {} as Record<string, FolderData>,
    )
})
const selectedFile = ref('')
const markdownContent = ref('')
const renderedMarkdown = ref('')
const expandedFolders = ref<Set<string>>(new Set())

const emit = defineEmits(['submit-success'])

async function fetchFolders() {
  const res = await fetch(`${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.RULEBOOK_FOLDERS}`)
  const data = await res.json()
  console.log('Fetched folders:', Object.keys(data))
  delete data['']
  folderStructure.value = data
}
fetchFolders()

async function fetchFile(path: string) {
  selectedFile.value = path
  const res = await fetch(
    `${SERVER_CONFIG.BASE_URL}${SERVER_CONFIG.ENDPOINTS.RULEBOOK_FILE}?path=${encodeURIComponent(path)}`,
  )
  const data = await res.json()
  markdownContent.value = data.content
  renderedMarkdown.value = marked.parse(data.content) as string
}

function toggleFolder(folder: string) {
  if (expandedFolders.value.has(folder)) {
    expandedFolders.value.delete(folder)
  } else {
    expandedFolders.value.add(folder)
  }
}
</script>

<template>
  <div class="explorer-page">
    <div class="sidebar">
      <h2>System Reference Documents (SRD) v.5</h2>
      <ul>
        <li v-for="(data, folder) in visibleFolders" :key="folder">
          <div @click="toggleFolder(folder)" class="folder">▶ {{ folder }}</div>
          <ul v-if="expandedFolders.has(folder)">
            <li
              v-for="file in data.files"
              :key="file"
              class="file"
              @click="fetchFile(folder ? folder + '/' + file : file)"
            >
              {{ (file as string).replace(/\.md$/, '') }}
            </li>
          </ul>
        </li>
      </ul>
    </div>

    <div class="viewer">
      <div
        v-if="selectedFile"
        v-html="renderedMarkdown"
        class="markdown-output scrollable-panel"
      ></div>
      <button class="goHome-button" @click="emit('submit-success')">return</button>
    </div>
  </div>
</template>

<style scoped>
.explorer-page {
  display: flex;
  height: 100%;
}

.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  width: 20%;
  background: rgba(163, 148, 95, 0.8);
  color: #392401;
  padding: 2rem 1rem;
  overflow-y: auto;
  height: 100vh;
  border-right: 2px solid #8e7513;
  font-family: 'MedievalSharp', cursive;
  font-weight: 600;
  box-sizing: border-box;
  border-radius: 8px 0 0 8px;
}

.sidebar ul {
  padding-right: 0.5rem;
}

.folder {
  font-weight: bold;
  cursor: pointer;
  margin: 0.5rem 0;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  transition: background-color 0.2s ease;
}

.folder:hover {
  background-color: rgba(200, 180, 100, 0.6);
}

.file {
  margin-left: 1rem;
  cursor: pointer;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  transition: background-color 0.2s ease;
}

.file:hover {
  background-color: rgba(180, 150, 70, 0.6);
}

.sidebar h2 {
  font-family: 'MedievalSharp', cursive;
  font-weight: 700;
  font-size: 1.5rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid #392401;
  padding-bottom: 0.3rem;
}

.viewer {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}

.goHome-button {
  padding: 0.7rem 1.4rem;
  background-color: rgba(53, 73, 94, 0.9);
  border: 1px solid #4a575e;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  font-family: 'MedievalSharp', cursive;
  font-weight: normal;
  font-size: 0.9rem;
  transition: background-color 0.3s ease;
  margin-top: 10px;
  margin-left: 20%;
}

.goHome-button :hover {
  background-color: #4a575e;
}

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
  color: #800080; /* purple */
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
  max-height: 90%;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: auto;
  padding: 3rem;
  border: 1px solid #ccc;
  border-radius: 8px;
  background-color: rgba(110, 97, 50, 0.95);
  box-sizing: border-box;
  margin-left: 20%;
}
</style>
