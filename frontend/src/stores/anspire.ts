import { defineStore } from 'pinia'
import { reactive, ref, watch } from 'vue'

export interface AnspireResult { result_index: number; title: string; url: string; snippet: string; summary: string; source_name: string; publish_time?: string | null; provider_score?: number | null; raw_json?: Record<string, unknown> | null }
export interface AnspireSession { id: number; provider: string; provider_request_id?: string | null; query: string; result_count: number; status: 'success' | 'failed'; created_at: string; duration_ms?: number | null }
export type AnspireLeadStatus = 'new' | 'confirmed' | 'rejected' | 'promoted'
export interface AnspireLead { id: number; provider?: string; provider_score?: number | null; query: string; title: string; url: string; snippet: string; summary: string; source_name: string; publish_time?: string | null; status: AnspireLeadStatus; search_session_id?: number | null; result_index?: number | null; created_at: string; updated_at?: string }
const STORAGE_KEY = 'anspire_search_state_v1'
export const useAnspireSearchStore = defineStore('anspire-search', () => {
  let stored: any = {}
  try { stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') } catch { /* ignore invalid local state */ }
  const form = reactive({ query: stored.form?.query || '', top_k: stored.form?.top_k || 10, insite: stored.form?.insite || '', from_time: stored.form?.from_time || '', to_time: stored.form?.to_time || '', region_mode: stored.form?.region_mode ?? 0 })
  const session = ref<AnspireSession | null>(stored.session || null); const results = ref<AnspireResult[]>(stored.results || []); const savedIndexes = ref<Set<number>>(new Set(stored.savedIndexes || [])); const selectedIndexes = ref<Set<number>>(new Set(stored.selectedIndexes || [])); const resultPage = ref(Math.max(Number(stored.resultPage || 1), 1))
  function setResult(nextSession: AnspireSession, items: AnspireResult[]) { session.value = nextSession; results.value = items; savedIndexes.value = new Set(); selectedIndexes.value = new Set(); resultPage.value = 1 }
  function markSaved(index: number) { savedIndexes.value = new Set(savedIndexes.value).add(index) }
  function setSelected(index: number, selected: boolean) { const next = new Set(selectedIndexes.value); selected ? next.add(index) : next.delete(index); selectedIndexes.value = next }
  function setSelectedIndexes(indexes: number[]) { selectedIndexes.value = new Set(indexes) }
  function clearSelected() { selectedIndexes.value = new Set() }
  function setResultPage(page: number) { resultPage.value = Math.max(Number(page || 1), 1) }
  watch(() => ({ form: { ...form }, session: session.value, results: results.value, savedIndexes: [...savedIndexes.value], selectedIndexes: [...selectedIndexes.value], resultPage: resultPage.value }), state => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)) } catch { /* ignore storage failures */ } }, { deep: true })
  return { form, session, results, savedIndexes, selectedIndexes, resultPage, setResult, markSaved, setSelected, setSelectedIndexes, clearSelected, setResultPage }
})
