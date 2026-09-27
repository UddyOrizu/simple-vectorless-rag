"""Parse, summarize, and store one document. Shared by the API's
document-upload endpoint and seed_corpus.py.

Incremental by design: content is hashed, and a document whose hash
hasn't changed since last time is skipped -- no LLM calls, no rewrite --
unless the caller passes tags to update (tagging is metadata, so it's
still applied even on an otherwise-unchanged document) or force=True.
"""
import hashlib
from typing import List, Optional

from . import llm, repository
from .parser import Section, extract_front_matter_tags, parse_markdown

SECTION_SUMMARY_SYSTEM = (
    "Summarize this section of a document in ONE short sentence, under "
    "15 words, capturing what a reader would come here to find. "
    "Reply with the sentence only, nothing else."
)

DOC_SUMMARY_SYSTEM = (
    "Summarize this document in ONE sentence, under 20 words, capturing "
    "what it is and who would need it. Reply with the sentence only."
)


async def summarize_sections(root: Section) -> None:
    nodes = [n for n in root.flatten() if n.level > 0 and n.content.strip()]
    for node in nodes:
        call = await llm.ask_claude(SECTION_SUMMARY_SYSTEM, node.content[:1500],
                                     max_tokens=40, model=llm.FAST_MODEL)
        node.summary = call.text.strip()


async def summarize_document(title: str, root: Section) -> str:
    excerpt = root.full_text()[:2500]
    call = await llm.ask_claude(DOC_SUMMARY_SYSTEM, f"Title: {title}\n\n{excerpt}",
                                 max_tokens=50, model=llm.FAST_MODEL)
    return call.text.strip()


async def ingest_document(pool, doc_id: str, raw_text: str,
                           explicit_tags: Optional[List[str]] = None,
                           force: bool = False) -> str:
    """Returns 'indexed', 'updated', or 'unchanged'.

    explicit_tags, when given, always wins over any front-matter
    '<!-- tags: ... -->' comment in raw_text -- that comment is only a
    convenience default for the very first ingest of a document.
    """
    front_matter_tags, content = extract_front_matter_tags(raw_text)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    existing_hash = await repository.get_document_hash(pool, doc_id)

    if existing_hash == content_hash and not force:
        if explicit_tags is not None:
            await repository.set_document_tags(pool, doc_id, explicit_tags)
        return "unchanged"

    root = parse_markdown(content, doc_id)
    title = next((c.title for c in root.children), doc_id)
    await summarize_sections(root)
    doc_summary = await summarize_document(title, root)

    await repository.upsert_document(pool, doc_id, title, doc_summary, content, content_hash)
    await repository.replace_sections(pool, doc_id, root)

    tags_to_set = explicit_tags if explicit_tags is not None else front_matter_tags
    if tags_to_set:
        await repository.set_document_tags(pool, doc_id, tags_to_set)

    return "indexed" if existing_hash is None else "updated"
