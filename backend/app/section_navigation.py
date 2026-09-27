"""Section-level navigation within one already-chosen document -- read
the document's own table of contents (titles + summaries), reason about
which branch holds the answer, fetch that branch's real content."""
from typing import List, Optional, Tuple

from . import llm
from .parser import Section

NAV_SYSTEM = (
    "You are navigating a document's table of contents to find where a "
    "question is answered. You see only titles and one-line summaries, "
    "never the full text. Pick the 1-2 section IDs most likely to contain "
    "the answer. Reply with ONLY the IDs, comma-separated -- nothing else."
)


def _tree_outline(root: Section) -> str:
    lines = []

    def walk(node: Section):
        if node.level > 0:
            indent = "  " * (node.level - 1)
            lines.append(f"{indent}- [{node.id}] {node.title}: {node.summary or ''}")
        for c in node.children:
            walk(c)

    walk(root)
    return "\n".join(lines)


def _find_by_id(root: Section, node_id: str) -> Optional[Section]:
    for n in root.flatten():
        if n.id == node_id:
            return n
    return None


async def navigate(question: str, root: Section, model: Optional[str] = None) -> Tuple[List[Section], llm.ClaudeCall]:
    outline = _tree_outline(root)
    call = await llm.ask_claude(
        NAV_SYSTEM, f"Table of contents:\n{outline}\n\nQuestion: {question}",
        max_tokens=64, model=model or llm.FAST_MODEL,
    )
    ids = [x.strip() for x in call.text.split(",") if x.strip()]
    sections = [s for s in (_find_by_id(root, i) for i in ids) if s]
    if not sections:
        sections = [root]
    return sections, call
