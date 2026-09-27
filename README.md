# Vectorless RAG Service

A standalone project for question-answering over a growing corpus of
documents — **no embeddings, no vector database anywhere**. Instead of
retrieving chunks by similarity, the system reads titles and one-line
summaries (never full text up front) and has Claude *reason* about which
document, then which section, is likely to hold the answer — the same idea
behind tools like PageIndex, and a direct response to the "lost in the
middle" / "context rot" problems that plague both long-context stuffing and
naive vector RAG.

This project turns that technique into something with real edges: a
Postgres-backed API, a natural-language search UI, and an admin UI for
corpus management (upload documents, tag them, and manage tag descriptions).

## Storage: Postgres

The schema is intentionally simple — four tables (`documents`, `tags`,
`document_tags`, `sections`), no ORM, raw SQL via `asyncpg`. It's not
"simple" in the sense of a flat file, but it *is* simple as Postgres schemas
go, and you get transactions, cascading deletes, and indexing for free.

## Tag auto-mapping from descriptions

This is the other half of your ask: users can attach a **description** to
each tag (e.g. the `netherlands` tag might be described as "Applies to
Netherlands-based employees or operations, including the Rotterdam clinical
partnership site."). When a search request doesn't specify tags explicitly,
the system:

1. Sends the question, plus every tag's name *and description*, to Claude.
2. Claude reasons about which tags — if any — describe what the question is
   about, based on what the tag actually *means*, not whether the question
   happens to contain the tag's name as a keyword.
3. Those inferred tags are used to filter candidate documents with **OR**
   semantics — narrowing the search, never eliminating it. If the inferred
   tags would match zero documents, the system quietly falls back to
   searching the whole corpus rather than returning a false "no results,"
   and reports that fallback in the response (`fell_back_to_full_corpus`).

Try asking "What happens if I move to the Rotterdam office for work?"
against the seed corpus below — there's no tag literally named "rotterdam,"
but it should infer `netherlands` (and probably `hr-policy`) purely from
what those tags' descriptions say.

Explicit tags (when the caller does pass `tags: [...]`) behave differently
on purpose: they use **AND** semantics and a real "no documents match" error
instead of a fallback, because a user who names tags explicitly is asking a
precise question and deserves an honest empty result rather than a silently
broadened one.

| tags in request      | meaning                          | semantics | on empty match         |
|-----------------------|-----------------------------------|-----------|-------------------------|
| omitted                | auto-infer from question intent   | OR        | fall back to full corpus |
| `[]` (explicit empty)  | skip inference, search everything | —         | n/a                     |
| `["a", "b"]`           | use exactly these tags            | AND       | error (400)             |

## Project layout

```
vectorless-rag-service/
├── docker-compose.yml     # Postgres for local dev
├── backend/               # FastAPI + asyncpg + Anthropic SDK
│   ├── app/
│   │   ├── main.py            # FastAPI routes
│   │   ├── rag.py             # orchestrator: tag resolution -> tournament -> section nav -> answer
│   │   ├── repository.py      # all Postgres access (schema + queries)
│   │   ├── tag_inference.py   # the description-based auto-mapping
│   │   ├── corpus_navigation.py   # document-level tournament (scales to large corpora)
│   │   ├── section_navigation.py  # section-level navigation within a chosen document
│   │   ├── ingest.py          # markdown -> section tree -> summaries -> DB, with content-hash skip
│   │   ├── parser.py          # markdown -> section tree
│   │   ├── evidence.py        # exact/fuzzy quote verification against source text
│   │   ├── llm.py             # async Claude client + bounded-concurrency parallel_map
│   │   ├── schemas.py         # Pydantic API models
│   │   ├── config.py, db.py
│   ├── seed_corpus.py     # loads a 4-document demo corpus with tag descriptions
│   └── requirements.txt
└── frontend/              # React + TypeScript + Vite
    └── src/
        ├── pages/SearchPage.tsx   # NL search: question, tag mode, answer + evidence + traces
        ├── pages/CorpusPage.tsx   # admin: documents, tags, tag descriptions
        └── lib/{api,types}.ts     # typed client mirroring backend/app/schemas.py
```

## Running it

**1. Start Postgres:**

```bash
docker compose up -d
```

**2. Backend:**

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env       # fill in your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

**3. Seed the demo corpus** (four Meridian Health Group documents — annual
report, HR policy, IT security policy, vendor policy — with tags and
descriptions crafted so the Rotterdam-inference example above actually
demonstrates something):

```bash
cd backend
python seed_corpus.py
```

**4. Frontend** (proxies `/api/*` to `localhost:8000`, see
`frontend/vite.config.ts`):

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL: **Search** for natural-language questions,
**Corpus** to manage documents and tags.

## API summary

| Route | Purpose |
|---|---|
| `GET /api/documents`, `POST /api/documents` | list / ingest documents |
| `GET /api/documents/{id}`, `DELETE /api/documents/{id}` | detail (with section tree), delete |
| `PATCH /api/documents/{id}/tags` | `{add, remove, set}` tags on a document |
| `GET /api/tags`, `POST /api/tags` | list / create tags (with descriptions) |
| `PATCH /api/tags/{name}`, `DELETE /api/tags/{name}` | edit description, delete |
| `POST /api/search` | `{question, tags?, batch_size?}` -> answer + evidence + full trace |

`tags` omitted vs. `[]` vs. `[...]` on `/api/search` is meaningful — see the
table above.

## Testing

Both layers were tested end-to-end against a real local Postgres instance
with the Claude API mocked (deterministic fixture responses keyed off each
call's system prompt), rather than mocking the database too — the
Postgres-specific SQL (`ON CONFLICT`, `ANY($1::text[])`,
`GROUP BY ... HAVING COUNT(DISTINCT ...)`, cascading foreign keys) needed
real verification, not just a plausible-looking mock. Coverage included:
document/tag CRUD, all three tag-filter modes, the empty-result fallback,
and the API's JSON serialization of the dataclass-based pipeline results.

