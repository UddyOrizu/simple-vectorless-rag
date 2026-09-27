import { useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'
import type { DocumentSummary, TagResponse } from '../lib/types'

export function CorpusPage() {
  const [tags, setTags] = useState<TagResponse[]>([])
  const [docs, setDocs] = useState<DocumentSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    setError(null)
    try {
      const [t, d] = await Promise.all([api.listTags(), api.listDocuments()])
      setTags(t)
      setDocs(d)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the API.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  return (
    <div className="page">
      <h1>Corpus management</h1>
      <p className="muted">Manage documents and tags. Tag descriptions are what auto-inference reasons over.</p>
      {error && <div className="error-box">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : (
        <div className="corpus-grid">
          <TagsPanel tags={tags} onChange={refresh} />
          <DocumentsPanel docs={docs} tags={tags} onChange={refresh} />
        </div>
      )}
    </div>
  )
}

// -------------------------------------------------------------------- tags

function TagsPanel({ tags, onChange }: { tags: TagResponse[]; onChange: () => void }) {
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [editing, setEditing] = useState<Record<string, string>>({})

  async function createTag(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    setBusy(true)
    setErr(null)
    try {
      await api.createTag(newName.trim().toLowerCase(), newDesc.trim() || undefined)
      setNewName('')
      setNewDesc('')
      onChange()
    } catch (err) {
      setErr(err instanceof ApiError ? err.message : 'Could not create tag.')
    } finally {
      setBusy(false)
    }
  }

  async function saveDescription(name: string) {
    const description = editing[name] ?? ''
    setBusy(true)
    try {
      await api.updateTag(name, description)
      onChange()
    } catch (err) {
      setErr(err instanceof ApiError ? err.message : 'Could not update tag.')
    } finally {
      setBusy(false)
    }
  }

  async function removeTag(name: string) {
    if (!confirm(`Delete tag "${name}"? This removes it from every document.`)) return
    setBusy(true)
    try {
      await api.deleteTag(name)
      onChange()
    } catch (err) {
      setErr(err instanceof ApiError ? err.message : 'Could not delete tag.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>Tags</h2>
      <p className="muted small">
        A description is what lets a question that never says the tag's name still match it — write what kind of
        document or topic the tag covers, not just a keyword.
      </p>
      {err && <div className="error-box">{err}</div>}

      <table className="tag-table">
        <tbody>
          {tags.map((t) => (
            <tr key={t.name}>
              <td className="tag-name">
                {t.name} <span className="muted small">({t.doc_count})</span>
              </td>
              <td>
                <input
                  className="desc-input"
                  value={editing[t.name] ?? t.description ?? ''}
                  placeholder="No description yet"
                  onChange={(e) => setEditing((prev) => ({ ...prev, [t.name]: e.target.value }))}
                  onBlur={() => {
                    if (editing[t.name] !== undefined && editing[t.name] !== (t.description ?? '')) {
                      saveDescription(t.name)
                    }
                  }}
                />
              </td>
              <td>
                <button type="button" className="link-btn danger" disabled={busy} onClick={() => removeTag(t.name)}>
                  delete
                </button>
              </td>
            </tr>
          ))}
          {tags.length === 0 && (
            <tr>
              <td colSpan={3} className="muted">
                No tags yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <form className="inline-form" onSubmit={createTag}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="new-tag-name"
          className="name-input"
        />
        <input
          value={newDesc}
          onChange={(e) => setNewDesc(e.target.value)}
          placeholder="Description (used for auto-mapping)"
          className="desc-input"
        />
        <button type="submit" disabled={busy || !newName.trim()}>
          Add tag
        </button>
      </form>
    </section>
  )
}

// --------------------------------------------------------------- documents

function DocumentsPanel({
  docs,
  tags,
  onChange,
}: {
  docs: DocumentSummary[]
  tags: TagResponse[]
  onChange: () => void
}) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function removeDoc(id: string) {
    if (!confirm(`Delete document "${id}"?`)) return
    setBusy(true)
    try {
      await api.deleteDocument(id)
      onChange()
    } catch (err) {
      setErr(err instanceof ApiError ? err.message : 'Could not delete document.')
    } finally {
      setBusy(false)
    }
  }

  async function toggleDocTag(doc: DocumentSummary, tagName: string) {
    setBusy(true)
    try {
      if (doc.tags.includes(tagName)) {
        await api.updateDocumentTags(doc.id, { remove: [tagName] })
      } else {
        await api.updateDocumentTags(doc.id, { add: [tagName] })
      }
      onChange()
    } catch (err) {
      setErr(err instanceof ApiError ? err.message : 'Could not update tags.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>Documents</h2>
      {err && <div className="error-box">{err}</div>}

      <div className="doc-list">
        {docs.map((d) => (
          <div key={d.id} className="doc-row">
            <div className="doc-row-header" onClick={() => setExpanded(expanded === d.id ? null : d.id)}>
              <div>
                <strong>{d.title}</strong> <span className="muted small">{d.id}</span>
                <div className="muted small">{d.summary}</div>
              </div>
              <button
                type="button"
                className="link-btn danger"
                disabled={busy}
                onClick={(e) => {
                  e.stopPropagation()
                  removeDoc(d.id)
                }}
              >
                delete
              </button>
            </div>
            <div className="tag-chip-row">
              {tags.map((t) => (
                <button
                  type="button"
                  key={t.name}
                  className={`chip ${d.tags.includes(t.name) ? 'chip-selected' : ''}`}
                  disabled={busy}
                  onClick={() => toggleDocTag(d, t.name)}
                  title={t.description ?? undefined}
                >
                  {t.name}
                </button>
              ))}
            </div>
            {expanded === d.id && <DocumentDetail id={d.id} />}
          </div>
        ))}
        {docs.length === 0 && <p className="muted">No documents yet — add one below.</p>}
      </div>

      <AddDocumentForm tags={tags} onChange={onChange} />
    </section>
  )
}

function DocumentDetail({ id }: { id: string }) {
  const [content, setContent] = useState<string | null>(null)

  useEffect(() => {
    api.getDocument(id).then((d) => setContent(d.content))
  }, [id])

  if (content === null) return <p className="muted small">Loading…</p>
  return <pre className="doc-content">{content}</pre>
}

function AddDocumentForm({ tags, onChange }: { tags: TagResponse[]; onChange: () => void }) {
  const [id, setId] = useState('')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  function toggle(name: string) {
    setSelectedTags((prev) => (prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!content.trim()) return
    setBusy(true)
    setErr(null)
    setStatus(null)
    try {
      const res = await api.createDocument({
        id: id.trim() || undefined,
        title: title.trim() || undefined,
        content,
        tags: selectedTags,
      })
      setStatus(`${res.status}: ${res.id}`)
      setId('')
      setTitle('')
      setContent('')
      setSelectedTags([])
      onChange()
    } catch (err) {
      setErr(err instanceof ApiError ? err.message : 'Could not add document.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card add-doc-form" onSubmit={submit}>
      <h3>Add a document</h3>
      {err && <div className="error-box">{err}</div>}
      {status && <div className="status-box">{status}</div>}
      <div className="two-col">
        <input value={id} onChange={(e) => setId(e.target.value)} placeholder="id (optional, slugified from title)" />
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="title (optional if content starts with '# Heading')"
        />
      </div>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={'# Document title\n\n## Section\n\nMarkdown content...'}
        rows={8}
      />
      <div className="tag-chip-row">
        {tags.map((t) => (
          <button
            type="button"
            key={t.name}
            className={`chip ${selectedTags.includes(t.name) ? 'chip-selected' : ''}`}
            onClick={() => toggle(t.name)}
            title={t.description ?? undefined}
          >
            {t.name}
          </button>
        ))}
      </div>
      <button type="submit" disabled={busy || !content.trim()}>
        {busy ? 'Ingesting…' : 'Add document'}
      </button>
    </form>
  )
}
