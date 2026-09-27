import type {
  DocumentDetail,
  DocumentSummary,
  IngestStatus,
  SearchRequest,
  SearchResponse,
  TagResponse,
} from './types'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  // ---------------------------------------------------------- documents
  listDocuments: (tag?: string) =>
    request<DocumentSummary[]>(`/documents${tag ? `?tag=${encodeURIComponent(tag)}` : ''}`),

  getDocument: (id: string) => request<DocumentDetail>(`/documents/${encodeURIComponent(id)}`),

  createDocument: (body: { id?: string; title?: string; content: string; tags?: string[] }) =>
    request<IngestStatus>('/documents', { method: 'POST', body: JSON.stringify(body) }),

  deleteDocument: (id: string) =>
    request<void>(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  updateDocumentTags: (id: string, body: { add?: string[]; remove?: string[]; set?: string[] }) =>
    request<DocumentSummary>(`/documents/${encodeURIComponent(id)}/tags`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // --------------------------------------------------------------- tags
  listTags: () => request<TagResponse[]>('/tags'),

  createTag: (name: string, description?: string) =>
    request<TagResponse>('/tags', { method: 'POST', body: JSON.stringify({ name, description }) }),

  updateTag: (name: string, description: string) =>
    request<TagResponse>(`/tags/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      body: JSON.stringify({ description }),
    }),

  deleteTag: (name: string) => request<void>(`/tags/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  // ------------------------------------------------------------- search
  search: (req: SearchRequest) =>
    request<SearchResponse>('/search', { method: 'POST', body: JSON.stringify(req) }),
}

export { ApiError }
