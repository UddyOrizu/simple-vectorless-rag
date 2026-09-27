"""Pydantic request/response models for the API."""
from typing import List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------- documents

class DocumentCreateRequest(BaseModel):
    id: Optional[str] = Field(None, description="Slug id; derived from the title if omitted")
    title: Optional[str] = Field(None, description="Used only if content has no '# Heading'")
    content: str = Field(..., description="Markdown content, optionally starting with '<!-- tags: a, b -->'")
    tags: Optional[List[str]] = Field(None, description="Overrides any front-matter tags comment")


class DocumentSummary(BaseModel):
    id: str
    title: str
    summary: Optional[str]
    tags: List[str]
    created_at: str
    updated_at: str


class SectionNode(BaseModel):
    id: str
    title: str
    level: int
    summary: Optional[str]
    children: List["SectionNode"] = []


SectionNode.model_rebuild()


class DocumentDetail(DocumentSummary):
    content: str
    sections: Optional[SectionNode] = None


class DocumentTagsUpdateRequest(BaseModel):
    add: Optional[List[str]] = None
    remove: Optional[List[str]] = None
    set: Optional[List[str]] = None


class IngestStatus(BaseModel):
    id: str
    status: str  # "indexed" | "updated" | "unchanged"


# ------------------------------------------------------------------ tags

class TagCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class TagUpdateRequest(BaseModel):
    description: Optional[str] = None


class TagResponse(BaseModel):
    name: str
    description: Optional[str]
    doc_count: int


# ---------------------------------------------------------------- search

class SearchRequest(BaseModel):
    question: str
    # Omit entirely -> auto-infer tags from the question's intent.
    # Send [] explicitly -> search the whole corpus, no inference.
    # Send [...] -> use exactly these tags (AND semantics).
    tags: Optional[List[str]] = None
    batch_size: int = 40


class EvidenceResponse(BaseModel):
    quote: str
    verified: bool
    match_score: float
    context_before: str
    context_after: str


class RoundTraceResponse(BaseModel):
    round_num: int
    candidates_in: int
    batches: int
    candidates_out: int
    picks: List[str]


class TagFilterResponse(BaseModel):
    mode: str  # "explicit" | "auto" | "none"
    tags_used: List[str]
    fell_back_to_full_corpus: bool
    inference_raw: Optional[str] = None
    tags_considered: Optional[int] = None


class SearchResponse(BaseModel):
    answer: str
    doc_id: str
    doc_title: str
    section_path: str
    evidence: Optional[EvidenceResponse]
    tag_filter: TagFilterResponse
    tournament_trace: List[RoundTraceResponse]
    candidates_considered: int
    candidates_after_filter: int
    latency_s: float
    input_tokens: int
    output_tokens: int
    llm_calls: int
