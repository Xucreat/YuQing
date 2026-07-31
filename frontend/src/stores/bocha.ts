import { defineStore } from 'pinia'
import { reactive, ref, watch } from 'vue'

export type LeadStatus = 'new' | 'confirmed' | 'rejected' | 'promoted'

export interface SearchResult {
  result_index: number
  title: string
  url: string
  snippet: string
  summary: string
  source_name: string
  publish_time?: string | null
}

export interface SearchSession {
  id: number
  query: string
  freshness?: string | null
  summary: boolean
  count: number
  result_count: number
  status: 'success' | 'failed'
  error_message?: string | null
  created_by?: number | null
  created_at: string
  completed_at?: string | null
  duration_ms?: number | null
}

export interface BochaLead {
  id: number
  query: string
  title: string
  url: string
  snippet: string
  summary: string
  source_name: string
  publish_time?: string | null
  status: LeadStatus
  opinion_id?: number | null
  created_by?: number | null
  creator_name?: string | null
  search_session_id?: number | null
  result_index?: number | null
  created_at: string
  updated_at: string
}

const STORAGE_KEY = 'bocha_search_state_v1'

interface StoredBochaState {
  form?: {
    query?: string
    freshness?: string
    summary?: boolean
    count?: number
  }
  activeSession?: SearchSession | null
  results?: SearchResult[]
  savedIndexes?: number[]
  selectedIndexes?: number[]
  resultPage?: number
}

function loadStoredState(): StoredBochaState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

export const useBochaSearchStore = defineStore('bocha-search', () => {
  const stored = loadStoredState()
  const form = reactive({
    query: stored.form?.query || '',
    freshness: stored.form?.freshness || '',
    summary: stored.form?.summary ?? true,
    count: Math.min(Math.max(Number(stored.form?.count || 8), 1), 100),
  })

  const activeSession = ref<SearchSession | null>(stored.activeSession || null)
  const results = ref<SearchResult[]>(stored.results || [])
  const savedIndexes = ref<Set<number>>(new Set(stored.savedIndexes || []))
  const selectedIndexes = ref<Set<number>>(new Set(stored.selectedIndexes || []))
  const resultPage = ref(Math.max(Number(stored.resultPage || 1), 1))

  function resetSearchResults() {
    activeSession.value = null
    results.value = []
    savedIndexes.value = new Set()
    selectedIndexes.value = new Set()
    resultPage.value = 1
  }

  function setSearchResult(session: SearchSession, items: SearchResult[]) {
    activeSession.value = session
    results.value = items
    savedIndexes.value = new Set()
    selectedIndexes.value = new Set()
    resultPage.value = 1
  }

  function markSaved(index: number) {
    savedIndexes.value = new Set(savedIndexes.value).add(index)
    selectedIndexes.value = new Set([...selectedIndexes.value].filter((i) => i !== index))
  }

  function setSelected(index: number, selected: boolean) {
    const next = new Set(selectedIndexes.value)
    if (selected) next.add(index)
    else next.delete(index)
    selectedIndexes.value = next
  }

  function setSelectedIndexes(indexes: number[]) {
    selectedIndexes.value = new Set(indexes)
  }

  function clearSelected() {
    selectedIndexes.value = new Set()
  }

  function setResultPage(page: number) {
    resultPage.value = Math.max(Number(page || 1), 1)
  }

  watch(
    () => ({
      form: { ...form },
      activeSession: activeSession.value,
      results: results.value,
      savedIndexes: [...savedIndexes.value],
      selectedIndexes: [...selectedIndexes.value],
      resultPage: resultPage.value,
    }),
    (state) => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
      } catch {
        /* ignore storage quota/private-mode failures */
      }
    },
    { deep: true },
  )

  return {
    form,
    activeSession,
    results,
    savedIndexes,
    selectedIndexes,
    resultPage,
    resetSearchResults,
    setSearchResult,
    markSaved,
    setSelected,
    setSelectedIndexes,
    clearSelected,
    setResultPage,
  }
})
