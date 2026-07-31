import { defineStore } from 'pinia'
import { reactive, ref, watch } from 'vue'

export interface AiWebPage {
  result_index?: number
  title: string
  url: string
  snippet: string
  source_domain: string
  source_type: string
  publish_time?: string | null
  citation_url?: string
  raw_json?: Record<string, unknown> | null
}

export interface AiSearchSession {
  id: number
  provider: string
  query: string
  freshness: string
  include?: string | null
  count: number
  answer: string
  answer_enabled: boolean
  follow_up_questions: string[]
  images: Record<string, any>[]
  modal_cards: Record<string, any>[]
  conversation_id?: string | null
  result_count: number
  status: 'success' | 'failed'
  error_message?: string | null
  created_at: string
  completed_at?: string | null
  duration_ms?: number | null
}

interface StoredState {
  form?: Partial<AiForm>
  session?: AiSearchSession | null
  pages?: AiWebPage[]
  images?: Record<string, any>[]
  modalCards?: Record<string, any>[]
  followUpQuestions?: string[]
}

export interface AiForm {
  query: string
  freshness: string
  count: number
  answer: boolean
  source: 'all' | 'weibo' | 'xiaohongshu' | 'custom'
  customInclude: string
}

const STORAGE_KEY = 'bocha_ai_search_state_v1'

function loadState(): StoredState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

export const useBochaAiSearchStore = defineStore('bocha-ai-search', () => {
  const saved = loadState()
  const form = reactive<AiForm>({
    query: saved.form?.query || '',
    freshness: saved.form?.freshness || 'noLimit',
    count: Math.min(Math.max(Number(saved.form?.count || 10), 1), 50),
    answer: saved.form?.answer ?? true,
    source: saved.form?.source || 'all',
    customInclude: saved.form?.customInclude || '',
  })
  const session = ref<AiSearchSession | null>(saved.session || null)
  const pages = ref<AiWebPage[]>(saved.pages || [])
  const images = ref<Record<string, any>[]>(saved.images || [])
  const modalCards = ref<Record<string, any>[]>(saved.modalCards || [])
  const followUpQuestions = ref<string[]>(saved.followUpQuestions || [])
  const savedIndexes = ref<Set<number>>(new Set())

  function setResult(nextSession: AiSearchSession, nextPages: AiWebPage[], nextImages: Record<string, any>[], nextCards: Record<string, any>[], nextQuestions: string[]) {
    session.value = nextSession
    pages.value = nextPages.map((item, index) => ({ ...item, result_index: item.result_index ?? index }))
    images.value = nextImages || []
    modalCards.value = nextCards || []
    followUpQuestions.value = nextQuestions || []
    savedIndexes.value = new Set()
  }

  function markSaved(index: number) {
    savedIndexes.value = new Set(savedIndexes.value).add(index)
  }

  watch(
    () => ({ form: { ...form }, session: session.value, pages: pages.value, images: images.value, modalCards: modalCards.value, followUpQuestions: followUpQuestions.value }),
    (value) => {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(value)) } catch { /* private mode/quota */ }
    },
    { deep: true },
  )

  return { form, session, pages, images, modalCards, followUpQuestions, savedIndexes, setResult, markSaved }
})
