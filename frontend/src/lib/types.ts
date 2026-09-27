// Mirrors backend/app/schemas.py exactly -- keep these two in sync.

export interface DocumentSummary {
  id: string
  title: string
  summary: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface SectionNode {
  id: string
  title: string
  level: number
  summary: string | null
  children: SectionNode[]
}

export interface DocumentDetail extends DocumentSummary {
  content: string
  sections: SectionNode | null
}

export interface IngestStatus {
  id: string
  status: 'indexed' | 'updated' | 'unchanged'
}

export interface TagResponse {
  name: string
  description: string | null
  doc_count: number
}

// tags omitted            -> auto-infer from the question's intent
// tags: []                -> search the whole corpus, no inference
// tags: ['a', 'b']         -> use exactly these tags (AND semantics)
export interface SearchRequest {
  question: string
  tags?: string[]
  batch_size?: number
}

export interface EvidenceResponse {
  quote: string
  verified: boolean
  match_score: number
  context_before: string
  context_after: string
}

export interface RoundTraceResponse {
  round_num: number
  candidates_in: number
  batches: number
  candidates_out: number
  picks: string[]
}

export type TagFilterMode = 'explicit' | 'auto' | 'none'

export interface TagFilterResponse {
  mode: TagFilterMode
  tags_used: string[]
  fell_back_to_full_corpus: boolean
  inference_raw: string | null
  tags_considered: number | null
}

export interface SearchResponse {
  answer: string
  doc_id: string
  doc_title: string
  section_path: string
  evidence: EvidenceResponse | null
  tag_filter: TagFilterResponse
  tournament_trace: RoundTraceResponse[]
  candidates_considered: number
  candidates_after_filter: number
  latency_s: number
  input_tokens: number
  output_tokens: number
  llm_calls: number
}

export interface ApiErrorBody {
  detail: string
}
