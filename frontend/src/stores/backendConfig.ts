import { defineStore } from 'pinia'
import {
  DEFAULT_LLM,
  DEFAULT_TRANSCRIPTION_MODEL,
  DEFAULT_EMBEDDING_MODEL,
  DEFAULT_EMBEDDING_TopK,
} from '@/config/config'

/**
 * Config store – holds the current backend LLM, transcription,
 * and embedding configuration selected by the user.
 */
export const useConfigStore = defineStore('config', {
  state: () => ({
    selectedLLM: DEFAULT_LLM,
    transcriptionModel: DEFAULT_TRANSCRIPTION_MODEL,
    embeddingModel: DEFAULT_EMBEDDING_MODEL,
    embeddingTopK: DEFAULT_EMBEDDING_TopK,
  }),
  actions: {
    /**
     * Overwrite all config values from a backend response object.
     * @param cfg - Raw config object with `selected_LLM`, `transcription_model`,
     *              `embedding_model`, and `embedding_top_k` fields.
     */
    setConfig(cfg: any) {
      this.selectedLLM = cfg.selected_LLM
      this.transcriptionModel = cfg.transcription_model
      this.embeddingModel = cfg.embedding_model
      this.embeddingTopK = cfg.embedding_top_k
    },
  },
})
