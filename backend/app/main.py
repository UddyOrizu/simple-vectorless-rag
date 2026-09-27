"""FastAPI app: document + tag management, and the NL search endpoint
that runs the vectorless RAG pipeline (tag resolution -> document
tournament -> section navigation -> answer + evidence)."""
import re
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, ingest, rag, repository
from .parser import Section
from .schemas import (
    DocumentCreateRequest, DocumentDetail, DocumentSummary, DocumentTagsUpdateRequest,
    EvidenceResponse, IngestStatus, RoundTraceResponse, SearchRequest, SearchResponse,
    SectionNode, TagCreateRequest, TagFilterResponse, TagResponse, TagUpdateRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(title="Vectorless RAG Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "document"


def _section_to_node(s: Section) -> SectionNode:
    return SectionNode(id=s.id, title=s.title, level=s.level, summary=s.summary,
                        children=[_section_to_node(c) for c in s.children])


def _doc_row_to_summary(d: repository.DocumentRow) -> DocumentSummary:
    return DocumentSummary(id=d.id, title=d.title, summary=d.summary, tags=d.tags,
                            created_at=d.created_at, updated_at=d.updated_at)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ------------------------------------------------------------- documents

@app.get("/api/documents", response_model=list[DocumentSummary])
async def list_documents(tag: Optional[str] = None):
    pool = db.get_pool()
    docs = await repository.list_documents(pool, require_all_tags=[tag] if tag else None)
    return [_doc_row_to_summary(d) for d in docs]


@app.post("/api/documents", response_model=IngestStatus)
async def create_document(req: DocumentCreateRequest):
    pool = db.get_pool()
    doc_id = req.id or _slugify(req.title or req.content.splitlines()[0].lstrip("# ").strip()[:60])
    content = req.content
    if req.title and not content.lstrip().startswith("#"):
        content = f"# {req.title}\n\n{content}"
    status = await ingest.ingest_document(pool, doc_id, content, explicit_tags=req.tags)
    return IngestStatus(id=doc_id, status=status)


@app.get("/api/documents/{doc_id}", response_model=DocumentDetail)
async def get_document(doc_id: str):
    pool = db.get_pool()
    doc = await repository.get_document(pool, doc_id)
    if not doc:
        raise HTTPException(404, f"No document '{doc_id}'")
    content = await repository.get_document_content(pool, doc_id)
    tree = await repository.get_tree(pool, doc_id)
    return DocumentDetail(
        id=doc.id, title=doc.title, summary=doc.summary, tags=doc.tags,
        created_at=doc.created_at, updated_at=doc.updated_at,
        content=content or "", sections=_section_to_node(tree) if tree else None,
    )


@app.delete("/api/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str):
    pool = db.get_pool()
    if not await repository.get_document(pool, doc_id):
        raise HTTPException(404, f"No document '{doc_id}'")
    await repository.delete_document(pool, doc_id)


@app.patch("/api/documents/{doc_id}/tags", response_model=DocumentSummary)
async def update_document_tags(doc_id: str, req: DocumentTagsUpdateRequest):
    pool = db.get_pool()
    if not await repository.get_document(pool, doc_id):
        raise HTTPException(404, f"No document '{doc_id}'")
    if req.set is not None:
        await repository.set_document_tags(pool, doc_id, req.set)
    if req.add:
        await repository.add_document_tags(pool, doc_id, req.add)
    if req.remove:
        await repository.remove_document_tags(pool, doc_id, req.remove)
    return _doc_row_to_summary(await repository.get_document(pool, doc_id))


# ------------------------------------------------------------------ tags

@app.get("/api/tags", response_model=list[TagResponse])
async def list_tags():
    pool = db.get_pool()
    tags = await repository.list_tags(pool)
    return [TagResponse(name=t.name, description=t.description, doc_count=t.doc_count) for t in tags]


@app.post("/api/tags", response_model=TagResponse)
async def create_tag(req: TagCreateRequest):
    pool = db.get_pool()
    t = await repository.create_tag(pool, req.name, req.description)
    return TagResponse(name=t.name, description=t.description, doc_count=t.doc_count)


@app.patch("/api/tags/{name}", response_model=TagResponse)
async def update_tag(name: str, req: TagUpdateRequest):
    pool = db.get_pool()
    t = await repository.update_tag_description(pool, name, req.description)
    if not t:
        raise HTTPException(404, f"No tag '{name}'")
    return TagResponse(name=t.name, description=t.description, doc_count=t.doc_count)


@app.delete("/api/tags/{name}", status_code=204)
async def delete_tag(name: str):
    pool = db.get_pool()
    if not await repository.get_tag(pool, name):
        raise HTTPException(404, f"No tag '{name}'")
    await repository.delete_tag(pool, name)


# ---------------------------------------------------------------- search

@app.post("/api/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    pool = db.get_pool()
    try:
        result = await rag.answer(pool, req.question, tags=req.tags, batch_size=req.batch_size)
    except ValueError as e:
        raise HTTPException(400, str(e))

    tf = result.tag_filter
    return SearchResponse(
        answer=result.final_answer,
        doc_id=result.doc_id,
        doc_title=result.doc_title,
        section_path=result.section_path,
        evidence=(EvidenceResponse(**vars(result.evidence)) if result.evidence else None),
        tag_filter=TagFilterResponse(
            mode=tf.mode, tags_used=tf.tags_used, fell_back_to_full_corpus=tf.fell_back_to_full_corpus,
            inference_raw=tf.inference.raw_response if tf.inference else None,
            tags_considered=tf.inference.considered if tf.inference else None,
        ),
        tournament_trace=[RoundTraceResponse(**vars(r)) for r in result.tournament_trace],
        candidates_considered=result.candidates_considered,
        candidates_after_filter=result.candidates_after_filter,
        latency_s=result.latency_s,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        llm_calls=result.llm_calls,
    )
