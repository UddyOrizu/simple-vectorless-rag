import { useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'
import type { SearchResponse, TagResponse } from '../lib/types'

type TagMode = 'auto' | 'explicit' | 'all'

export function SearchPage() {
  const [question, setQuestion] = useState('')
  const [tagMode, setTagMode] = useState<TagMode>('auto')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [allTags, setAllTags] = useState<TagResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SearchResponse | null>(null)

  useEffect(() => {
    api.listTags().then(setAllTags).catch(() => setAllTags([]))
  }, [])

  function toggleTag(name: string) {
    setSelectedTags((prev) => (prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]))
  }

  async function runSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const tags = tagMode === 'auto' ? undefined : tagMode === 'all' ? [] : selectedTags
      const res = await api.search({ question, tags })
      setResult(res)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong reaching the search API.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <h1>Ask the corpus</h1>
      <p className="muted">
        Vectorless RAG: no embeddings involved — the question is answered by reasoning over document and
        section summaries, then verified against an exact quote from the source text.
      </p>

      <form className="card search-form" onSubmit={runSearch}>
        <label htmlFor="question">Question</label>
        <textarea
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What happens if I move to the Rotterdam office for work?"
          rows={3}
        />

        <div className="tag-mode-row">
          <label className="radio">
            <input type="radio" checked={tagMode === 'auto'} onChange={() => setTagMode('auto')} />
            Auto-infer tags from the question
          </label>
          <label className="radio">
            <input type="radio" checked={tagMode === 'explicit'} onChange={() => setTagMode('explicit')} />
            Choose tags myself
          </label>
          <label className="radio">
            <input type="radio" checked={tagMode === 'all'} onChange={() => setTagMode('all')} />
            Search the whole corpus
          </label>
        </div>

        {tagMode === 'explicit' && (
          <div className="tag-chip-row">
            {allTags.length === 0 && <span className="muted">No tags defined yet.</span>}
            {allTags.map((t) => (
              <button
                type="button"
                key={t.name}
                className={`chip ${selectedTags.includes(t.name) ? 'chip-selected' : ''}`}
                onClick={() => toggleTag(t.name)}
                title={t.description ?? undefined}
              >
                {t.name}
              </button>
            ))}
          </div>
        )}

        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && <div className="error-box">{error}</div>}

      {result && <ResultPanel result={result} />}
    </div>
  )
}

function ResultPanel({ result }: { result: SearchResponse }) {
  const tf = result.tag_filter
  return (
    <div className="card result-panel">
      <h2>Answer</h2>
      <p className="answer-text">{result.answer}</p>

      <div className="source-line">
        from <strong>{result.doc_title}</strong> ({result.doc_id}) — {result.section_path}
      </div>

      {result.evidence && (
        <div className={`evidence-box ${result.evidence.verified ? 'evidence-verified' : 'evidence-unverified'}`}>
          <div className="evidence-label">
            {result.evidence.verified ? '✓ Verified quote' : '⚠ Unverified quote'}{' '}
            <span className="muted">(match {Math.round(result.evidence.match_score * 100)}%)</span>
          </div>
          <blockquote>
            {result.evidence.context_before && <span className="context">…{result.evidence.context_before}</span>}
            <mark>{result.evidence.quote}</mark>
            {result.evidence.context_after && <span className="context">{result.evidence.context_after}…</span>}
          </blockquote>
        </div>
      )}

      <details className="trace" open>
        <summary>Tag filtering — {tf.mode}</summary>
        <div className="trace-body">
          {tf.mode === 'explicit' && <p>Filtered to documents with ALL of: {tf.tags_used.join(', ') || '(none)'}</p>}
          {tf.mode === 'auto' && (
            <>
              <p>
                Tags inferred from the question's intent (OR semantics — narrows, never excludes everything):{' '}
                {tf.tags_used.length ? tf.tags_used.join(', ') : '(none matched)'}
              </p>
              {tf.inference_raw && (
                <p className="muted">
                  Raw inference reply: <code>{tf.inference_raw}</code>
                  {tf.tags_considered != null && ` · considered ${tf.tags_considered} tag(s) with descriptions`}
                </p>
              )}
              {tf.fell_back_to_full_corpus && (
                <p className="muted">Inferred tags matched no documents — fell back to the full corpus.</p>
              )}
            </>
          )}
          {tf.mode === 'none' && <p>No tag filter applied — searched the whole corpus.</p>}
        </div>
      </details>

      <details className="trace">
        <summary>
          Document tournament — {result.candidates_considered} candidate(s) → {result.candidates_after_filter} after
          filtering
        </summary>
        <div className="trace-body">
          {result.tournament_trace.length === 0 && <p className="muted">Single candidate, no rounds needed.</p>}
          {result.tournament_trace.map((r) => (
            <div key={r.round_num} className="round-row">
              round {r.round_num}: {r.candidates_in} candidates in {r.batches} batch(es) → kept{' '}
              {r.picks.join(', ')} ({r.candidates_out} total)
            </div>
          ))}
        </div>
      </details>

      <div className="stats-row muted">
        {result.llm_calls} LLM call(s) · {result.input_tokens + result.output_tokens} tokens ·{' '}
        {result.latency_s.toFixed(2)}s
      </div>
    </div>
  )
}
