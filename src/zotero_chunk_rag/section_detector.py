"""
Section detection for academic papers.

Detects document sections (Abstract, Introduction, Methods, Results, etc.) using
a 6-step pipeline:
1. Candidate extraction (regex patterns for heading schemes)
2. Structural verification (context checks)
3. Scheme detection and consistency filtering
4. Narrative order validation
5. Gap-fill with short-sentence fallback
6. Chunk assignment
"""
import re
from dataclasses import dataclass
from .models import PageText, SectionSpan, CONFIDENCE_SCHEME_MATCH, CONFIDENCE_GAP_FILL, CONFIDENCE_FALLBACK


# =============================================================================
# CATEGORY DEFINITIONS
# =============================================================================

# Category keywords mapped to labels, ordered by weight (highest first)
# When multiple keywords match, highest-weighted category wins
CATEGORY_KEYWORDS: list[tuple[str, list[str], float]] = [
    ("results", ["result", "findings", "outcomes"], 1.0),
    ("conclusion", ["conclusion", "concluding"], 1.0),
    ("methods", ["method", "materials", "experimental", "procedure",
                 "protocol", "design", "participants", "subjects"], 0.85),
    ("abstract", ["abstract"], 0.75),
    ("background", ["background", "literature review", "related work"], 0.7),
    ("discussion", ["discussion"], 0.65),
    ("introduction", ["introduction"], 0.5),
    ("appendix", ["appendix", "supplementa"], 0.3),
    ("references", ["reference", "bibliography"], 0.1),
]

# "summary" is special - matches conclusion unless combined with data-related words
SUMMARY_EXCLUDES = ["statistics", "table", "data", "results summary"]

# Position groups for narrative order validation
# Categories in same group are interchangeable in order
POSITION_GROUPS: dict[str, int] = {
    "abstract": 0,
    "introduction": 1,
    "background": 1,  # Same group as introduction
    "methods": 2,
    "results": 3,
    "discussion": 4,
    "conclusion": 5,
    "references": 6,
    "appendix": 7,
}


# =============================================================================
# HEADING SCHEME PATTERNS
# =============================================================================

@dataclass
class HeadingScheme:
    """A heading format pattern."""
    scheme_id: str
    pattern: re.Pattern
    is_subsection: bool = False


HEADING_SCHEMES = [
    HeadingScheme("roman_caps", re.compile(r"^[IVX]+\.\s+[A-Z][A-Z]")),
    HeadingScheme("roman_title", re.compile(r"^[IVX]+\.\s+[A-Z][a-z]")),
    HeadingScheme("numbered_dot", re.compile(r"^\d+\.?\s+[A-Z]")),
    HeadingScheme("numbered_sub", re.compile(r"^\d+\.\d+\.?\s+"), is_subsection=True),
    HeadingScheme("bare_caps", re.compile(r"^[A-Z][A-Z\s&]{3,}$")),
    HeadingScheme("bare_title", re.compile(
        r"^[A-Z][a-z]+(\s+(and|&|of|in|for|the|with)\s+[A-Z]?[a-z]+)*$"
    )),
]

# Prose starters that indicate a sentence, not a heading (case-sensitive)
PROSE_STARTERS = re.compile(
    r"^(In the|In this|The|We|Our|This|Their|These|It is|As |For the|From the|To the|A |An )\s"
)

# Caption patterns to reject
CAPTION_PATTERNS = re.compile(r"^(Fig|Figure|Table|©|DOI|http)", re.IGNORECASE)


# =============================================================================
# CANDIDATE DATACLASS
# =============================================================================

@dataclass
class HeadingCandidate:
    """A potential section heading found in the document."""
    line_text: str
    char_offset: int
    fractional_position: float
    scheme_id: str
    category: str
    weight: float


# =============================================================================
# MAIN DETECTION FUNCTION
# =============================================================================

def detect_sections(
    pages: list[PageText],
    *,
    gap_fill_min_chars: int = 2000,
    gap_fill_min_fraction: float = 0.30,
) -> list[SectionSpan]:
    """
    Detect document sections from page text.

    Args:
        pages: List of PageText objects from PDF extraction
        gap_fill_min_chars: Minimum gap size for short-sentence fallback
        gap_fill_min_fraction: Minimum gap fraction for short-sentence fallback

    Returns:
        List of SectionSpan covering the entire document with no gaps.
        Every character belongs to exactly one span.
    """
    if not pages:
        return []

    # Concatenate pages with newline separator (consistent with chunker.py)
    full_text = "\n".join(p.text for p in pages)
    total_len = len(full_text)

    if total_len == 0:
        return []

    # Step 1: Extract candidates
    candidates = _extract_candidates(full_text, total_len)

    # Step 2: Structural verification
    candidates = _verify_structure(candidates, full_text)

    # Step 3: Scheme detection and consistency filtering
    candidates = _filter_by_scheme(candidates)

    # Step 4: Narrative order validation
    candidates = _validate_order(candidates)

    # Step 5: Gap-fill with fallback
    candidates = _gap_fill(
        candidates, full_text, total_len,
        min_chars=gap_fill_min_chars,
        min_fraction=gap_fill_min_fraction,
    )

    # Step 6: Build section spans
    spans = _build_spans(candidates, total_len)

    return spans


# =============================================================================
# STEP 1: CANDIDATE EXTRACTION
# =============================================================================

def _extract_candidates(full_text: str, total_len: int) -> list[HeadingCandidate]:
    """Extract heading candidates by matching against scheme patterns."""
    candidates = []

    # Track position as we iterate through lines
    char_offset = 0

    for line in full_text.split("\n"):
        stripped = line.strip()

        # Skip empty lines or lines too long to be headings
        if not stripped or len(stripped) > 80:
            char_offset += len(line) + 1  # +1 for newline
            continue

        # Try each heading scheme
        matched_scheme = None
        for scheme in HEADING_SCHEMES:
            if scheme.pattern.match(stripped):
                matched_scheme = scheme
                break

        if matched_scheme:
            # Determine category from keywords
            category, weight = _categorize_heading(stripped)

            if category:  # Only keep if we found a known section keyword
                candidates.append(HeadingCandidate(
                    line_text=stripped,
                    char_offset=char_offset,
                    fractional_position=char_offset / total_len if total_len > 0 else 0,
                    scheme_id=matched_scheme.scheme_id,
                    category=category,
                    weight=weight,
                ))

        char_offset += len(line) + 1  # +1 for newline

    return candidates


def _categorize_heading(heading: str) -> tuple[str | None, float]:
    """
    Determine category from heading text using keyword matching.
    Returns (category, weight) or (None, 0) if no match.
    Highest-weighted matching category wins.
    """
    heading_lower = heading.lower()

    # Special handling for "summary"
    if "summary" in heading_lower:
        # Check if it's data-related (-> results) or concluding (-> conclusion)
        for exclude in SUMMARY_EXCLUDES:
            if exclude in heading_lower:
                return ("results", 1.0)
        return ("conclusion", 1.0)

    # Check categories in weight order (CATEGORY_KEYWORDS is pre-sorted)
    for category, keywords, weight in CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword in heading_lower:
                return (category, weight)

    return (None, 0.0)


# =============================================================================
# STEP 2: STRUCTURAL VERIFICATION
# =============================================================================

def _verify_structure(
    candidates: list[HeadingCandidate],
    full_text: str
) -> list[HeadingCandidate]:
    """Filter candidates using structural context checks."""
    verified = []
    lines = full_text.split("\n")

    # Build line index for lookup
    line_starts: list[int] = []
    offset = 0
    for line in lines:
        line_starts.append(offset)
        offset += len(line) + 1

    for cand in candidates:
        # Find which line this candidate is on
        line_idx = _find_line_index(cand.char_offset, line_starts)
        if line_idx is None:
            continue

        # Check: paragraph boundary (preceded by newline or start of doc)
        if cand.char_offset > 0:
            prev_char = full_text[cand.char_offset - 1]
            if prev_char != "\n":
                continue

        # Check: not a prose starter (case-sensitive check on original)
        if PROSE_STARTERS.match(cand.line_text):
            continue

        # Check: not a caption
        if CAPTION_PATTERNS.match(cand.line_text):
            continue

        # Check: next non-empty line doesn't start with lowercase
        # (would indicate this is mid-sentence)
        next_line = _get_next_nonempty_line(lines, line_idx)
        if next_line and next_line[0].islower():
            continue

        verified.append(cand)

    return verified


def _find_line_index(char_offset: int, line_starts: list[int]) -> int | None:
    """Find which line index contains the given character offset."""
    for i, start in enumerate(line_starts):
        if i + 1 < len(line_starts):
            if start <= char_offset < line_starts[i + 1]:
                return i
        else:
            if start <= char_offset:
                return i
    return None


def _get_next_nonempty_line(lines: list[str], current_idx: int) -> str | None:
    """Get the next non-empty line after current_idx."""
    for i in range(current_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped:
            return stripped
    return None


# =============================================================================
# STEP 3: SCHEME DETECTION AND CONSISTENCY FILTERING
# =============================================================================

def _filter_by_scheme(candidates: list[HeadingCandidate]) -> list[HeadingCandidate]:
    """
    Detect primary heading scheme and filter for consistency.
    Subsection schemes (numbered_sub) always pass through.
    """
    if not candidates:
        return []

    # Count candidates per scheme (excluding subsection schemes)
    scheme_counts: dict[str, int] = {}
    for cand in candidates:
        scheme = HEADING_SCHEMES[[s.scheme_id for s in HEADING_SCHEMES].index(cand.scheme_id)]
        if not scheme.is_subsection:
            scheme_counts[cand.scheme_id] = scheme_counts.get(cand.scheme_id, 0) + 1

    if not scheme_counts:
        # Only subsections found - return all
        return candidates

    # Find primary scheme (most candidates)
    primary_scheme = max(scheme_counts, key=lambda s: scheme_counts[s])
    primary_count = scheme_counts[primary_scheme]

    # Check for scheme conflict (top two counts within 1 of each other)
    sorted_counts = sorted(scheme_counts.values(), reverse=True)
    scheme_conflict = len(sorted_counts) > 1 and sorted_counts[0] - sorted_counts[1] <= 1

    # Filter: keep primary scheme + subsections + others that fill gaps
    filtered = []
    primary_offsets = []

    # First pass: collect primary scheme candidates
    for cand in candidates:
        scheme = HEADING_SCHEMES[[s.scheme_id for s in HEADING_SCHEMES].index(cand.scheme_id)]
        if cand.scheme_id == primary_scheme or scheme.is_subsection:
            filtered.append(cand)
            if cand.scheme_id == primary_scheme:
                primary_offsets.append(cand.char_offset)

    primary_offsets.sort()

    # Second pass: add non-primary candidates that fill gaps
    for cand in candidates:
        if cand.scheme_id != primary_scheme:
            scheme = HEADING_SCHEMES[[s.scheme_id for s in HEADING_SCHEMES].index(cand.scheme_id)]
            if scheme.is_subsection:
                continue  # Already added

            # If scheme conflict, be lenient - accept all verified candidates
            if scheme_conflict:
                filtered.append(cand)
                continue

            # Check if before first primary (allow section before main content)
            if primary_offsets and cand.char_offset < primary_offsets[0]:
                filtered.append(cand)
                continue

            # Check if after last primary (allow references/appendix after main content)
            if primary_offsets and cand.char_offset > primary_offsets[-1]:
                filtered.append(cand)
                continue

            # For candidates between primary headings, require >500 char gap
            min_dist = min(
                (abs(cand.char_offset - po) for po in primary_offsets),
                default=float('inf')
            )
            if min_dist > 500:
                filtered.append(cand)

    # Sort by document order
    filtered.sort(key=lambda c: c.char_offset)
    return filtered


# =============================================================================
# STEP 4: NARRATIVE ORDER VALIDATION
# =============================================================================

def _validate_order(candidates: list[HeadingCandidate]) -> list[HeadingCandidate]:
    """
    Validate candidates against expected narrative order.
    Discard candidates that appear out of order.
    """
    if not candidates:
        return []

    validated = []
    max_group_seen = -1

    for cand in candidates:
        group = POSITION_GROUPS.get(cand.category, 99)  # Unknown categories at end

        if group >= max_group_seen:
            validated.append(cand)
            max_group_seen = group
        # else: skip - out of order

    return validated


# =============================================================================
# STEP 5: GAP-FILL WITH FALLBACK
# =============================================================================

def _gap_fill(
    candidates: list[HeadingCandidate],
    full_text: str,
    total_len: int,
    *,
    min_chars: int = 2000,
    min_fraction: float = 0.30,
) -> list[HeadingCandidate]:
    """
    Fill large gaps with short-sentence keyword fallback.
    Only applies to gaps exceeding min_fraction of document AND min_chars.
    """
    if total_len == 0:
        return candidates

    # Build list of covered regions
    boundaries = [0] + [c.char_offset for c in candidates] + [total_len]

    gap_fills: list[HeadingCandidate] = []

    for i in range(len(boundaries) - 1):
        gap_start = boundaries[i]
        gap_end = boundaries[i + 1]
        gap_size = gap_end - gap_start

        # Check if gap is large enough to warrant fallback
        if gap_size <= min_chars or gap_size / total_len <= min_fraction:
            continue

        # Scan gap for short keyword lines
        gap_text = full_text[gap_start:gap_end]
        offset_in_gap = 0

        for line in gap_text.split("\n"):
            stripped = line.strip()

            # Short line with keyword?
            if stripped and len(stripped) <= 60:
                category, weight = _categorize_heading(stripped)

                if category:
                    # Apply structural checks
                    char_offset = gap_start + offset_in_gap

                    # Paragraph boundary check
                    if char_offset > 0 and full_text[char_offset - 1] != "\n":
                        offset_in_gap += len(line) + 1
                        continue

                    # Not a prose starter
                    if PROSE_STARTERS.match(stripped):
                        offset_in_gap += len(line) + 1
                        continue

                    # Not a caption
                    if CAPTION_PATTERNS.match(stripped):
                        offset_in_gap += len(line) + 1
                        continue

                    # Check order against existing candidates
                    group = POSITION_GROUPS.get(category, 99)

                    # Find max group before this position
                    max_before = -1
                    for c in candidates:
                        if c.char_offset < char_offset:
                            g = POSITION_GROUPS.get(c.category, 99)
                            max_before = max(max_before, g)

                    # Find min group after this position
                    min_after = 99
                    for c in candidates:
                        if c.char_offset > char_offset:
                            g = POSITION_GROUPS.get(c.category, 99)
                            min_after = min(min_after, g)

                    # Valid if fits between existing sections
                    if max_before <= group <= min_after:
                        gap_fills.append(HeadingCandidate(
                            line_text=stripped,
                            char_offset=char_offset,
                            fractional_position=char_offset / total_len,
                            scheme_id="fallback",
                            category=category,
                            weight=weight,
                        ))
                        # Only take first valid fill per gap
                        break

            offset_in_gap += len(line) + 1

    # Merge and sort
    all_candidates = candidates + gap_fills
    all_candidates.sort(key=lambda c: c.char_offset)
    return all_candidates


# =============================================================================
# STEP 6: BUILD SECTION SPANS
# =============================================================================

def _build_spans(candidates: list[HeadingCandidate], total_len: int) -> list[SectionSpan]:
    """Convert candidates to SectionSpan list covering entire document."""
    if not candidates:
        # No sections detected - entire doc is unknown
        return [SectionSpan(
            label="unknown",
            char_start=0,
            char_end=total_len,
            heading_text="",
            confidence=CONFIDENCE_FALLBACK,
        )]

    spans = []

    # Add preamble if first heading isn't at start
    if candidates[0].char_offset > 0:
        spans.append(SectionSpan(
            label="preamble",
            char_start=0,
            char_end=candidates[0].char_offset,
            heading_text="",
            confidence=CONFIDENCE_SCHEME_MATCH,
        ))

    # Add spans for each candidate
    for i, cand in enumerate(candidates):
        # Determine confidence
        if cand.scheme_id == "fallback":
            confidence = CONFIDENCE_GAP_FILL
        else:
            confidence = CONFIDENCE_SCHEME_MATCH

        # char_end is start of next candidate, or end of document
        if i + 1 < len(candidates):
            char_end = candidates[i + 1].char_offset
        else:
            char_end = total_len

        spans.append(SectionSpan(
            label=cand.category,
            char_start=cand.char_offset,
            char_end=char_end,
            heading_text=cand.line_text,
            confidence=confidence,
        ))

    return spans


# =============================================================================
# UTILITY: ASSIGN SECTION TO CHUNK
# =============================================================================

def assign_section_with_confidence(char_start: int, spans: list[SectionSpan]) -> tuple[str, float]:
    """
    Find section label and confidence for a character position.

    Args:
        char_start: Character offset in concatenated document text
        spans: List of SectionSpan from detect_sections()

    Returns:
        Tuple of (section_label, confidence)
    """
    for span in spans:
        if span.char_start <= char_start < span.char_end:
            return span.label, span.confidence
    return "unknown", CONFIDENCE_FALLBACK


def assign_section(char_start: int, spans: list[SectionSpan]) -> str:
    """
    Find the section label for a given character position.

    Args:
        char_start: Character offset in concatenated document text
        spans: List of SectionSpan from detect_sections()

    Returns:
        Section label string
    """
    label, _ = assign_section_with_confidence(char_start, spans)
    return label
