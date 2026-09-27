"""Postgres repository: documents, tags (with descriptions), and the
section trees underneath each document. Async (asyncpg), used by the
FastAPI app and by ingest.py.

Tags are first-class rows here, not just labels on a document -- a tag
has a name AND a description, because the description is what
tag_inference.py reasons over when a query doesn't specify tags
explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import asyncpg

from .parser import Section

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tags (
    name TEXT PRIMARY KEY,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_tags (
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_name TEXT NOT NULL REFERENCES tags(name) ON DELETE CASCADE,
    PRIMARY KEY (doc_id, tag_name)
);
CREATE INDEX IF NOT EXISTS idx_document_tags_tag ON document_tags(tag_name);

CREATE TABLE IF NOT EXISTS sections (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_id TEXT,
    title TEXT NOT NULL,
    level INT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    order_index INT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sections_doc ON sections(doc_id);
CREATE INDEX IF NOT EXISTS idx_sections_parent ON sections(parent_id);
"""


@dataclass
class DocumentRow:
    id: str
    title: str
    summary: Optional[str]
    content_hash: str
    created_at: str
    updated_at: str
    tags: List[str] = field(default_factory=list)


@dataclass
class TagRow:
    name: str
    description: Optional[str]
    doc_count: int = 0


async def init_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)


# ---------------------------------------------------------------- documents

async def get_document_hash(pool: asyncpg.Pool, doc_id: str) -> Optional[str]:
    row = await pool.fetchrow("SELECT content_hash FROM documents WHERE id = $1", doc_id)
    return row["content_hash"] if row else None


async def upsert_document(pool: asyncpg.Pool, doc_id: str, title: str, summary: str,
                           content: str, content_hash: str) -> None:
    await pool.execute(
        """INSERT INTO documents (id, title, summary, content, content_hash, updated_at)
           VALUES ($1, $2, $3, $4, $5, now())
           ON CONFLICT (id) DO UPDATE SET
             title = excluded.title, summary = excluded.summary,
             content = excluded.content, content_hash = excluded.content_hash,
             updated_at = now()""",
        doc_id, title, summary, content, content_hash,
    )


async def delete_document(pool: asyncpg.Pool, doc_id: str) -> None:
    await pool.execute("DELETE FROM documents WHERE id = $1", doc_id)  # cascades


async def _hydrate(pool: asyncpg.Pool, rows) -> List[DocumentRow]:
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    tag_rows = await pool.fetch(
        "SELECT doc_id, tag_name FROM document_tags WHERE doc_id = ANY($1::text[]) ORDER BY tag_name", ids
    )
    tags_by_doc: Dict[str, List[str]] = {i: [] for i in ids}
    for r in tag_rows:
        tags_by_doc[r["doc_id"]].append(r["tag_name"])
    return [
        DocumentRow(
            id=r["id"], title=r["title"], summary=r["summary"],
            content_hash=r["content_hash"],
            created_at=r["created_at"].isoformat(), updated_at=r["updated_at"].isoformat(),
            tags=tags_by_doc[r["id"]],
        )
        for r in rows
    ]


async def get_document(pool: asyncpg.Pool, doc_id: str) -> Optional[DocumentRow]:
    row = await pool.fetchrow(
        "SELECT id, title, summary, content_hash, created_at, updated_at FROM documents WHERE id = $1",
        doc_id,
    )
    if not row:
        return None
    return (await _hydrate(pool, [row]))[0]


async def get_document_content(pool: asyncpg.Pool, doc_id: str) -> Optional[str]:
    row = await pool.fetchrow("SELECT content FROM documents WHERE id = $1", doc_id)
    return row["content"] if row else None


async def list_documents(pool: asyncpg.Pool, *, require_all_tags: Optional[List[str]] = None,
                          require_any_tags: Optional[List[str]] = None) -> List[DocumentRow]:
    """All documents, or a tag-filtered subset:
    - require_all_tags: AND semantics -- a document must carry every tag.
      Used for an explicit, user-specified filter (`--tags a,b`
      equivalent): if the caller asked for these tags specifically,
      "no results" is a real, honest answer.
    - require_any_tags: OR semantics -- a document needs at least one.
      Used for AUTO-INFERRED tags (see tag_inference.py): inference is
      a guess, so it should narrow generously, not exclude aggressively.
    Passing neither returns every document.
    """
    if require_all_tags:
        rows = await pool.fetch(
            """SELECT d.id, d.title, d.summary, d.content_hash, d.created_at, d.updated_at
               FROM documents d
               JOIN document_tags dt ON dt.doc_id = d.id
               WHERE dt.tag_name = ANY($1::text[])
               GROUP BY d.id
               HAVING COUNT(DISTINCT dt.tag_name) = $2
               ORDER BY d.id""",
            require_all_tags, len(require_all_tags),
        )
    elif require_any_tags:
        rows = await pool.fetch(
            """SELECT DISTINCT d.id, d.title, d.summary, d.content_hash, d.created_at, d.updated_at
               FROM documents d
               JOIN document_tags dt ON dt.doc_id = d.id
               WHERE dt.tag_name = ANY($1::text[])
               ORDER BY d.id""",
            require_any_tags,
        )
    else:
        rows = await pool.fetch(
            "SELECT id, title, summary, content_hash, created_at, updated_at FROM documents ORDER BY id"
        )
    return await _hydrate(pool, rows)


async def count_documents(pool: asyncpg.Pool) -> int:
    return await pool.fetchval("SELECT COUNT(*) FROM documents")


# ------------------------------------------------------------------ tags

async def list_tags(pool: asyncpg.Pool) -> List[TagRow]:
    rows = await pool.fetch(
        """SELECT t.name, t.description, COUNT(dt.doc_id) AS doc_count
           FROM tags t
           LEFT JOIN document_tags dt ON dt.tag_name = t.name
           GROUP BY t.name, t.description
           ORDER BY t.name"""
    )
    return [TagRow(name=r["name"], description=r["description"], doc_count=r["doc_count"]) for r in rows]


async def get_tag(pool: asyncpg.Pool, name: str) -> Optional[TagRow]:
    row = await pool.fetchrow(
        """SELECT t.name, t.description, COUNT(dt.doc_id) AS doc_count
           FROM tags t LEFT JOIN document_tags dt ON dt.tag_name = t.name
           WHERE t.name = $1 GROUP BY t.name, t.description""",
        name,
    )
    return TagRow(name=row["name"], description=row["description"], doc_count=row["doc_count"]) if row else None


async def create_tag(pool: asyncpg.Pool, name: str, description: Optional[str] = None) -> TagRow:
    await pool.execute(
        """INSERT INTO tags (name, description) VALUES ($1, $2)
           ON CONFLICT (name) DO UPDATE SET description = excluded.description""",
        name.strip().lower(), description,
    )
    return await get_tag(pool, name.strip().lower())


async def update_tag_description(pool: asyncpg.Pool, name: str, description: Optional[str]) -> Optional[TagRow]:
    result = await pool.execute("UPDATE tags SET description = $2 WHERE name = $1", name, description)
    if result == "UPDATE 0":
        return None
    return await get_tag(pool, name)


async def delete_tag(pool: asyncpg.Pool, name: str) -> None:
    await pool.execute("DELETE FROM tags WHERE name = $1", name)  # cascades out of document_tags


async def ensure_tags_exist(pool: asyncpg.Pool, tag_names: List[str]) -> None:
    """Creates any tag names that don't exist yet, with no description.
    Called when a document is tagged with a name nobody has described
    yet -- the tag still works as a filter immediately; someone can add
    its description later without re-tagging anything."""
    names = [t.strip().lower() for t in tag_names if t.strip()]
    if not names:
        return
    await pool.executemany(
        "INSERT INTO tags (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
        [(n,) for n in names],
    )


async def set_document_tags(pool: asyncpg.Pool, doc_id: str, tags: List[str]) -> None:
    names = [t.strip().lower() for t in tags if t.strip()]
    await ensure_tags_exist(pool, names)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM document_tags WHERE doc_id = $1", doc_id)
            if names:
                await conn.executemany(
                    "INSERT INTO document_tags (doc_id, tag_name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    [(doc_id, n) for n in names],
                )


async def add_document_tags(pool: asyncpg.Pool, doc_id: str, tags: List[str]) -> None:
    names = [t.strip().lower() for t in tags if t.strip()]
    await ensure_tags_exist(pool, names)
    await pool.executemany(
        "INSERT INTO document_tags (doc_id, tag_name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        [(doc_id, n) for n in names],
    )


async def remove_document_tags(pool: asyncpg.Pool, doc_id: str, tags: List[str]) -> None:
    names = [t.strip().lower() for t in tags]
    await pool.executemany(
        "DELETE FROM document_tags WHERE doc_id = $1 AND tag_name = $2",
        [(doc_id, n) for n in names],
    )


# --------------------------------------------------------------- sections

async def replace_sections(pool: asyncpg.Pool, doc_id: str, root: Section) -> None:
    rows = []

    def walk(node: Section, parent_id: Optional[str], order_index: int):
        rows.append((node.id, doc_id, parent_id, node.title, node.level,
                      node.content, node.summary, order_index))
        for i, child in enumerate(node.children):
            walk(child, node.id, i)

    walk(root, None, 0)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM sections WHERE doc_id = $1", doc_id)
            await conn.executemany(
                """INSERT INTO sections (id, doc_id, parent_id, title, level, content, summary, order_index)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                rows,
            )


async def get_tree(pool: asyncpg.Pool, doc_id: str) -> Optional[Section]:
    rows = await pool.fetch(
        """SELECT id, parent_id, title, level, content, summary
           FROM sections WHERE doc_id = $1 ORDER BY parent_id NULLS FIRST, order_index""",
        doc_id,
    )
    if not rows:
        return None

    nodes: Dict[str, Section] = {}
    parent_of: Dict[str, Optional[str]] = {}
    for r in rows:
        nodes[r["id"]] = Section(id=r["id"], title=r["title"], level=r["level"],
                                  content=r["content"], summary=r["summary"])
        parent_of[r["id"]] = r["parent_id"]

    root = None
    for sid, node in nodes.items():
        parent_id = parent_of[sid]
        if parent_id is None:
            root = node
        else:
            nodes[parent_id].children.append(node)
    return root
