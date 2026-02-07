"""Lightweight section heading classification.

Classifies heading text into academic paper section categories
using keyword matching and positional heuristics.
"""
from __future__ import annotations

from .models import SectionSpan, CONFIDENCE_FALLBACK

# Category keywords mapped to labels, ordered by weight (highest first).
# When multiple keywords match, highest-weighted category wins.
CATEGORY_KEYWORDS: list[tuple[str, list[str], float]] = [
    ("results", ["result", "findings", "outcomes"], 1.0),
    ("conclusion", ["conclusion", "concluding"], 1.0),
    ("methods", ["method", "materials", "experimental", "procedure",
                 "protocol", "design", "participants", "subjects"], 0.85),
    ("abstract", ["abstract"], 0.75),
    ("background", ["background", "literature review", "related work"], 0.7),
    ("discussion", ["discussion"], 0.65),
    ("introduction", ["introduction"], 0.5),
    ("appendix", ["appendix", "supplementa", "acknowledgment", "acknowledgement",
                  "grant", "funding", "disclosure", "conflict of interest"], 0.3),
    ("references", ["reference", "bibliography"], 0.1),
]

# "summary" is special — matches conclusion unless combined with data words.
SUMMARY_EXCLUDES = ["statistics", "table", "data", "results summary"]

# Position groups for narrative order validation.
POSITION_GROUPS: dict[str, int] = {
    "abstract": 0,
    "introduction": 1,
    "background": 1,
    "methods": 2,
    "results": 3,
    "discussion": 4,
    "conclusion": 5,
    "references": 6,
    "appendix": 7,
    "figure": 99,
    "table": 99,
}


def categorize_heading(heading: str) -> tuple[str | None, float]:
    """Determine category from heading text using keyword matching.

    Returns (category, weight) or (None, 0) if no match.
    """
    heading_lower = heading.lower()

    # Check keyword list first — explicit category keywords take priority
    for category, keywords, weight in CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword in heading_lower:
                return (category, weight)

    # Special handling for "summary" (only if no other category matched above)
    if "summary" in heading_lower:
        for exclude in SUMMARY_EXCLUDES:
            if exclude in heading_lower:
                return ("results", 1.0)
        return ("conclusion", 1.0)

    return (None, 0.0)


def categorize_by_position(
    fractional_pos: float,
    prev_category: str | None,
    next_category: str | None,
) -> str:
    """Classify a non-standard heading by its document position.

    If between intro/background and results → methods (weight 0.85).
    If between results and conclusion → discussion.
    If both neighbours share a category → inherit that category.
    Otherwise → unknown.
    """
    # If both neighbours are the same category, inherit it
    if prev_category and prev_category == next_category:
        return prev_category

    prev_group = POSITION_GROUPS.get(prev_category, -1) if prev_category else -1
    next_group = POSITION_GROUPS.get(next_category, 99) if next_category else 99

    # Between intro/background and methods/results → methods
    if prev_group <= 1 and next_group >= 2:
        return "methods"
    # Between methods and results → methods (sub-sections within methods block)
    if prev_group <= 2 and next_group <= 3:
        return "methods"
    # Between results and conclusion → discussion
    if prev_group <= 3 and next_group >= 5:
        return "discussion"
    # Between methods and discussion → results
    if prev_group <= 2 and next_group >= 4:
        return "results"
    # Between discussion and conclusion → discussion
    if prev_group <= 4 and next_group >= 5:
        return "discussion"
    # Between discussion and references → discussion
    if prev_group <= 4 and next_group >= 6:
        return "discussion"
    return "unknown"


def assign_section(char_start: int, spans: list[SectionSpan]) -> str:
    """Find the section label for a given character position."""
    label, _ = assign_section_with_confidence(char_start, spans)
    return label


def assign_section_with_confidence(
    char_start: int, spans: list[SectionSpan]
) -> tuple[str, float]:
    """Find section label and confidence for a character position."""
    for span in spans:
        if span.char_start <= char_start < span.char_end:
            return span.label, span.confidence
    return "unknown", CONFIDENCE_FALLBACK
