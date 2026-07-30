type AdmissionHit = Record<string, unknown>

function formatAdmissionHit(hit: unknown): string {
  if (typeof hit === 'string' || typeof hit === 'number') return String(hit)
  if (!hit || typeof hit !== 'object' || Array.isArray(hit)) return ''

  const value = hit as AdmissionHit
  for (const key of ['word', 'name', 'label', 'value', 'code']) {
    const candidate = value[key]
    if (typeof candidate === 'string' || typeof candidate === 'number') return String(candidate)
  }
  return ''
}

/** Formats stored admission hits while supporting both legacy strings and region-hit objects. */
export function formatAdmissionHits(value: unknown, limit: number): string {
  if (!Array.isArray(value)) return ''
  return value
    .map(formatAdmissionHit)
    .filter(Boolean)
    .slice(0, limit)
    .join('、')
}
