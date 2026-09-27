"""Document-level navigation over a corpus: which document(s) are most
likely to answer the question? Same mechanism as section-level
navigation -- read titles and summaries, reason about which branch to
open -- one level up, with a tournament so the candidate list can be
arbitrarily long without the navigation call itself degrading (the
"context rot" problem, relocated from inside a document to the list of
documents, gets the same fix: split into batches small enough to trust,
run them concurrently, keep each batch's winner(s), repeat).
"""
from typing import List, Optional, Tuple

from . import llm
from .repository import DocumentRow
from .results import RoundTrace

NAV_SYSTEM_TEMPLATE = (
    "You are selecting which document(s), from the list below, are most "
    "likely to contain the answer to a question. Each entry shows a "
    "document's id, title, one-line summary, and tags. Pick the {top_k} "
    "id(s) most likely to contain the answer. Reply with ONLY the ids, "
    "comma-separated -- nothing else, no explanation."
)


class NavigationStats:
    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.latency_s = 0.0
        self.trace: List[RoundTrace] = []


def _format_candidates(batch: List[DocumentRow]) -> str:
    lines = []
    for d in batch:
        tag_str = f" [tags: {', '.join(d.tags)}]" if d.tags else ""
        lines.append(f"- [{d.id}] {d.title}: {d.summary or ''}{tag_str}")
    return "\n".join(lines)


async def navigate_batch(question: str, batch: List[DocumentRow], top_k: int,
                          model: str) -> Tuple[List[str], llm.ClaudeCall]:
    listing = _format_candidates(batch)
    system = NAV_SYSTEM_TEMPLATE.format(top_k=top_k)
    call = await llm.ask_claude(system, f"Documents:\n{listing}\n\nQuestion: {question}",
                                 max_tokens=64, model=model)
    valid_ids = {d.id for d in batch}
    ids = [x.strip() for x in call.text.split(",") if x.strip() in valid_ids]
    if not ids:
        ids = [batch[0].id]  # fail-safe: a batch always returns something
    return ids[:top_k], call


async def select_documents(question: str, candidates: List[DocumentRow], *,
                            batch_size: int = 40, top_k_per_batch: int = 2,
                            final_top_k: int = 1,
                            model: Optional[str] = None) -> Tuple[List[DocumentRow], NavigationStats]:
    """Narrows `candidates` down to final_top_k documents, batching and
    running rounds concurrently whenever the list exceeds batch_size."""
    if not candidates:
        raise ValueError("select_documents called with an empty candidate list")

    model = model or llm.FAST_MODEL
    stats = NavigationStats()
    by_id = {d.id: d for d in candidates}
    current = candidates
    round_num = 0

    while len(current) > batch_size:
        round_num += 1
        batches = [current[i:i + batch_size] for i in range(0, len(current), batch_size)]

        async def run(b: List[DocumentRow]) -> Tuple[List[str], llm.ClaudeCall]:
            return await navigate_batch(question, b, top_k_per_batch, model)

        results = await llm.parallel_map(run, batches)

        picks: List[str] = []
        round_latency = 0.0
        for ids, call in results:
            picks.extend(ids)
            stats.calls += 1
            stats.input_tokens += call.input_tokens
            stats.output_tokens += call.output_tokens
            round_latency = max(round_latency, call.latency_s)  # ran concurrently
        stats.latency_s += round_latency

        deduped = list(dict.fromkeys(picks))
        stats.trace.append(RoundTrace(round_num, len(current), len(batches), len(deduped), deduped))
        current = [by_id[i] for i in deduped]

    round_num += 1
    final_ids, call = await navigate_batch(question, current, final_top_k, model)
    stats.calls += 1
    stats.input_tokens += call.input_tokens
    stats.output_tokens += call.output_tokens
    stats.latency_s += call.latency_s
    stats.trace.append(RoundTrace(round_num, len(current), 1, len(final_ids), final_ids))

    return [by_id[i] for i in final_ids], stats
