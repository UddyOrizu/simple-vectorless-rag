"""Parse a Markdown document into a hierarchical section tree, and pull
a leading '<!-- tags: a, b, c -->' comment off the top as convenience
initial tags (the primary way to tag a document is still the API/UI,
this just saves a step when pasting markdown that already has them).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

TAG_COMMENT_RE = re.compile(r"^<!--\s*tags:\s*(.*?)\s*-->\s*$", re.I)
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")


@dataclass
class Section:
    id: str
    title: str
    level: int
    content: str
    children: List["Section"] = field(default_factory=list)
    summary: Optional[str] = None

    def full_text(self) -> str:
        parts = [self.content]
        for child in self.children:
            parts.append(f"### {child.title}\n{child.full_text()}")
        return "\n\n".join(p.strip() for p in parts if p.strip())

    def leaves(self) -> List["Section"]:
        if not self.children:
            return [self]
        out: List[Section] = []
        for c in self.children:
            out.extend(c.leaves())
        return out

    def flatten(self) -> List["Section"]:
        out = [self]
        for c in self.children:
            out.extend(c.flatten())
        return out


def extract_front_matter_tags(text: str) -> Tuple[List[str], str]:
    lines = text.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines):
        m = TAG_COMMENT_RE.match(lines[i].strip())
        if m:
            tags = [t.strip().lower() for t in m.group(1).split(",") if t.strip()]
            remaining = "\n".join(lines[:i] + lines[i + 1:])
            return tags, remaining
    return [], text


def parse_markdown(text: str, doc_id: str) -> Section:
    """Turn '# Title\\ncontent\\n## Sub\\ncontent' into a Section tree,
    with every node's id prefixed by doc_id so it's globally unique."""
    root = Section(id=doc_id, title="ROOT", level=0, content="")
    path: Dict[int, Section] = {0: root}
    current_level = 0
    buffer: List[str] = []
    child_counts: Dict[Tuple[str, int], int] = {}

    def flush():
        nonlocal buffer
        if buffer:
            path[current_level].content += "\n".join(buffer).strip() + "\n\n"
            buffer = []

    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()

            parent_level = level - 1
            while parent_level not in path:
                parent_level -= 1
            parent = path[parent_level]

            key = (parent.id, level)
            child_counts[key] = child_counts.get(key, 0) + 1
            node = Section(id=f"{parent.id}.{child_counts[key]}", title=title,
                            level=level, content="")
            parent.children.append(node)

            path[level] = node
            for lvl in [l for l in path if l > level]:
                del path[lvl]
            current_level = level
        else:
            buffer.append(line)
    flush()
    return root
