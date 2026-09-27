"""Shared result / trace dataclasses returned by the pipeline, used both
by rag.py internally and to shape the API's JSON response."""
from dataclasses import dataclass, field
from typing import List, Optional

from .evidence import Evidence
from .tag_inference import TagInferenceResult


@dataclass
class RoundTrace:
    round_num: int
    candidates_in: int
    batches: int
    candidates_out: int
    picks: List[str] = field(default_factory=list)


@dataclass
class TagFilterInfo:
    mode: str  # "explicit" | "auto" | "none"
    tags_used: List[str] = field(default_factory=list)
    inference: Optional[TagInferenceResult] = None
    fell_back_to_full_corpus: bool = False


@dataclass
class AnswerResult:
    final_answer: str
    evidence: Optional[Evidence]
    doc_id: str
    doc_title: str
    section_path: str
    latency_s: float
    input_tokens: int
    output_tokens: int
    llm_calls: int
    tag_filter: TagFilterInfo
    tournament_trace: List[RoundTrace] = field(default_factory=list)
    candidates_considered: int = 0
    candidates_after_filter: int = 0
