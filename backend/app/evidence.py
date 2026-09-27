"""Evidence extraction and verification -- unchanged from the corpus
CLI project. Every answer must come with an exact quoted span from the
source document; this checks whether that quote actually appears
(near-verbatim) before it's reported as verified."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Tuple


@dataclass
class Evidence:
    quote: str
    verified: bool
    match_score: float
    context_before: str
    context_after: str


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def locate_quote(source_text: str, claimed_quote: str, window: int = 100) -> Evidence:
    norm_source = _normalize(source_text)
    norm_quote = _normalize(claimed_quote)
    if not norm_quote:
        return Evidence(quote=claimed_quote, verified=False, match_score=0.0,
                         context_before="", context_after="")

    idx = norm_source.find(norm_quote)
    if idx != -1:
        score = 1.0
        end = idx + len(norm_quote)
    else:
        matcher = difflib.SequenceMatcher(None, norm_source, norm_quote)
        match = matcher.find_longest_match(0, len(norm_source), 0, len(norm_quote))
        idx, end = match.a, match.a + max(match.size, 1)
        score = round((2 * match.size) / (len(norm_quote) + match.size + 1e-6), 2)

    return Evidence(
        quote=claimed_quote,
        verified=score >= 0.85,
        match_score=score,
        context_before=norm_source[max(0, idx - window):idx],
        context_after=norm_source[end:end + window],
    )


def split_quote_and_answer(text: str) -> Tuple[str, str]:
    m = re.search(r"<quote>(.*?)</quote>(.*)", text, re.S)
    if not m:
        return "", text.strip()
    quote = m.group(1).strip()
    rest = m.group(2).strip(" :\n-")
    rest = re.sub(r"^answer\s*:\s*", "", rest, flags=re.I).strip()
    return quote, rest
