"""End-to-end vectorless RAG over a corpus:

  tag resolution (explicit tags, or auto-inferred from the question via
  tag descriptions, or none)
    -> document navigation (tournament if the candidate list is large)
    -> section navigation within the winning document
    -> answer, with a verified quote as evidence

Tag semantics, set by what the caller passes for `tags`:
  - tags=None        -> try to auto-infer tags from the question's intent
                         (tag_inference.py), filtered with OR semantics,
                         and fall back to the full corpus if inference
                         finds nothing or the inferred filter is empty.
  - tags=[]           -> explicit "search everything", no filter, no
                          inference attempted.
  - tags=[...]         -> explicit tags from the caller, AND semantics
                           (a document must carry every one). No
                           fallback: if nothing matches, that's a real,
                           reportable "no results", because the caller
                           asked for exactly this.
"""
from typing import List, Optional

from . import corpus_navigation, llm, repository, section_navigation, tag_inference
from .evidence import locate_quote, split_quote_and_answer
from .results import AnswerResult, TagFilterInfo

ANSWER_SYSTEM = (
    "Answer the question using ONLY the section text provided. First quote "
    "the exact sentence that supports your answer, verbatim, inside "
    "<quote></quote> tags. Then, on a new line, write 'Answer: ' followed "
    "by a one-sentence answer. If the section text doesn't contain the "
    "answer, say so plainly instead of guessing."
)


async def _resolve_tags(pool, question: str, tags: Optional[List[str]],
                         model: Optional[str]) -> TagFilterInfo:
    if tags == []:
        return TagFilterInfo(mode="none", tags_used=[])
    if tags:
        return TagFilterInfo(mode="explicit", tags_used=[t.strip().lower() for t in tags])

    all_tags = await repository.list_tags(pool)
    inference = await tag_inference.infer_tags(question, all_tags, model=model)
    return TagFilterInfo(mode="auto", tags_used=inference.inferred_tags, inference=inference)


async def answer(pool, question: str, tags: Optional[List[str]] = None,
                  batch_size: int = 40, model: Optional[str] = None) -> AnswerResult:
    total_calls = 0
    total_in = 0
    total_out = 0

    total_corpus = await repository.count_documents(pool)
    tag_filter = await _resolve_tags(pool, question, tags, model)
    if tag_filter.inference and tag_filter.inference.call:
        total_calls += 1
        total_in += tag_filter.inference.call.input_tokens
        total_out += tag_filter.inference.call.output_tokens

    if tag_filter.mode == "explicit":
        candidates = await repository.list_documents(pool, require_all_tags=tag_filter.tags_used)
        if not candidates:
            raise ValueError(
                f"No documents match all of tags {tag_filter.tags_used!r} "
                f"(corpus has {total_corpus} documents total)."
            )
    elif tag_filter.mode == "auto" and tag_filter.tags_used:
        candidates = await repository.list_documents(pool, require_any_tags=tag_filter.tags_used)
        if not candidates:
            # Inference is a guess; it never gets to produce a dead end.
            # Fall back to the full corpus and say so in the response.
            candidates = await repository.list_documents(pool)
            tag_filter.fell_back_to_full_corpus = True
            tag_filter.tags_used = []
    else:
        candidates = await repository.list_documents(pool)

    if not candidates:
        raise ValueError("The corpus has no documents yet.")

    winners, nav_stats = await corpus_navigation.select_documents(
        question, candidates, batch_size=batch_size, final_top_k=1, model=model,
    )
    total_calls += nav_stats.calls
    total_in += nav_stats.input_tokens
    total_out += nav_stats.output_tokens

    doc = winners[0]
    root = await repository.get_tree(pool, doc.id)
    if root is None:
        raise ValueError(f"Document '{doc.id}' has no indexed sections.")

    sections, sec_call = await section_navigation.navigate(question, root, model=model)
    total_calls += 1
    total_in += sec_call.input_tokens
    total_out += sec_call.output_tokens

    content = "\n\n".join(f"[{s.title}]\n{s.full_text()}" for s in sections)
    ans_call = await llm.ask_claude(ANSWER_SYSTEM, f"Section content:\n{content}\n\nQuestion: {question}")
    total_calls += 1
    total_in += ans_call.input_tokens
    total_out += ans_call.output_tokens

    quote, final = split_quote_and_answer(ans_call.text)
    ev = locate_quote(root.full_text(), quote) if quote else None

    return AnswerResult(
        final_answer=final or ans_call.text,
        evidence=ev,
        doc_id=doc.id,
        doc_title=doc.title,
        section_path=", ".join(s.title for s in sections),
        latency_s=nav_stats.latency_s + sec_call.latency_s + ans_call.latency_s,
        input_tokens=total_in,
        output_tokens=total_out,
        llm_calls=total_calls,
        tag_filter=tag_filter,
        tournament_trace=nav_stats.trace,
        candidates_considered=total_corpus,
        candidates_after_filter=len(candidates),
    )
