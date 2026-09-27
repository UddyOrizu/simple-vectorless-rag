"""Auto-map a natural-language query to tags, using each tag's
DESCRIPTION rather than its name -- so a question like "what's our
policy for staff moving to the Rotterdam office" can match a tag named
`international-assignments` even though none of those words appear in
the tag name itself, as long as the description says what the tag
actually covers.

This runs only when the caller didn't pass explicit tags (see
rag.answer): it's a convenience for a plain natural-language query, not
a replacement for a user who already knows which tags they want.

Safety property that matters more than the inference being clever:
inference must never be able to make a query fail that an unfiltered
search would have answered. Two things enforce that -- (1) this module
returns an EMPTY list, never an error, when nothing clearly matches,
and (2) the caller (rag.answer) treats an inferred filter that excludes
every document as a signal to fall back to the full corpus, not as a
dead end. This module only ever narrows; it never has the authority to
produce a "no results."
"""
from dataclasses import dataclass, field
from typing import List, Optional

from . import llm
from .repository import TagRow

NAV_SYSTEM = (
    "Below is a list of tags used to categorize documents in a corpus. Each "
    "tag has a name and a description of what kinds of documents it covers. "
    "Given a user's question, decide which tags, if any, describe what the "
    "question is about -- reason from the DESCRIPTIONS, not just whether a "
    "tag's name shares words with the question. A question may match zero, "
    "one, or several tags. If nothing clearly matches, or a tag has no "
    "description to reason from, don't guess -- leave it out. Reply with "
    "ONLY a comma-separated list of matching tag names, or the single word "
    "NONE if nothing matches. No explanation."
)


@dataclass
class TagInferenceResult:
    inferred_tags: List[str] = field(default_factory=list)
    raw_response: str = ""
    considered: int = 0
    skipped_no_description: List[str] = field(default_factory=list)
    call: Optional[llm.ClaudeCall] = None


def _format_tags(tags: List[TagRow]) -> str:
    lines = []
    for t in tags:
        desc = t.description or "(no description set)"
        lines.append(f"- {t.name}: {desc}")
    return "\n".join(lines)


async def infer_tags(question: str, all_tags: List[TagRow],
                      model: Optional[str] = None) -> TagInferenceResult:
    if not all_tags:
        return TagInferenceResult(inferred_tags=[], raw_response="(no tags defined in corpus)")

    undescribed = [t.name for t in all_tags if not t.description]
    listing = _format_tags(all_tags)
    call = await llm.ask_claude(
        NAV_SYSTEM, f"Tags:\n{listing}\n\nQuestion: {question}",
        max_tokens=80, model=model or llm.FAST_MODEL,
    )

    valid = {t.name for t in all_tags}
    if call.text.strip().upper() == "NONE":
        inferred: List[str] = []
    else:
        inferred = [x.strip().lower() for x in call.text.split(",") if x.strip().lower() in valid]

    return TagInferenceResult(
        inferred_tags=inferred,
        raw_response=call.text,
        considered=len(all_tags),
        skipped_no_description=undescribed,
        call=call,
    )
