import pathlib

p = pathlib.Path(r'C:\Users\Administrator\Desktop\YQ\frontend\src\types\index.ts')
t = p.read_text(encoding='utf-8')

new_types = '''
// ===== Alert types =====
export interface AlertRule {
  id: number
  name: string
  description: string
  risk_threshold: number
  keywords: string
  sources: string
  risk_level: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface AlertRuleListResponse {
  items: AlertRule[]
  total: number
  page: number
  size: number
}

export interface AlertRecord {
  id: number
  rule_id: number
  rule_name: string
  risk_level: string
  opinion_id: number | null
  opinion_title: string
  event_id: number | null
  event_title: string
  trigger_reason: string
  handled: boolean
  created_at: string
}

export interface AlertRecordListResponse {
  items: AlertRecord[]
  total: number
  page: number
  size: number
}

export interface AlertEvaluateResponse {
  success: boolean
  total_checked: number
  alerts_created: number
}

// ===== Propagation types =====
export interface PropagationNode {
  id: number
  event_id: number | null
  opinion_id: number | null
  parent_id: number | null
  source: string
  source_url: string
  title: string
  publish_time: string | null
  risk_score: number
  sentiment: string
  keywords: string
  depth: number
  created_at: string
}

export interface PropagationLink {
  source_id: number
  target_id: number
  source_name: string
  target_name: string
}

export interface PropagationGraph {
  nodes: PropagationNode[]
  links: PropagationLink[]
  event_id: number | null
  event_title: string
  total_opinions: number
  source_summary: { source: string; count: number }[]
}

export interface PropagationEventSummary {
  event_id: number
  event_title: string
  risk_level: string
  opinion_count: number
  node_count: number
  first_time: string | null
  last_time: string | null
}

export interface PropagationRebuildResponse {
  success: boolean
  nodes_created: number
}
'''

if '// ===== Alert types' not in t:
    t += new_types
    p.write_text(t, encoding='utf-8')
    print('Types updated')
else:
    print('Types already present')
