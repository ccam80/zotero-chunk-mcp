"""Document chunking with overlap and page tracking."""
from .models import PageText, Chunk
from .section_detector import detect_sections, assign_section_with_confidence


class Chunker:
    """Split documents into overlapping chunks."""

    def __init__(
        self,
        chunk_size: int = 400,
        overlap: int = 100,
        gap_fill_min_chars: int = 2000,
        gap_fill_min_fraction: float = 0.30,
    ):
        """
        Args:
            chunk_size: Target chunk size in tokens (estimated as chars/4)
            overlap: Overlap between chunks in tokens
            gap_fill_min_chars: Minimum gap size in chars for section gap-fill
            gap_fill_min_fraction: Minimum gap fraction for section gap-fill
        """
        self.chunk_chars = chunk_size * 4
        self.overlap_chars = overlap * 4
        self.gap_fill_min_chars = gap_fill_min_chars
        self.gap_fill_min_fraction = gap_fill_min_fraction

    def chunk(self, pages: list[PageText]) -> list[Chunk]:
        """
        Split pages into overlapping chunks.

        Attempts to break at sentence boundaries when possible.
        Tracks which page each chunk primarily belongs to.
        Assigns document section labels to each chunk.
        """
        if not pages:
            return []

        # Detect sections for the document
        section_spans = detect_sections(
            pages,
            gap_fill_min_chars=self.gap_fill_min_chars,
            gap_fill_min_fraction=self.gap_fill_min_fraction,
        )

        # Concatenate all text
        full_text = "\n".join(p.text for p in pages)

        # Build page boundary index
        page_boundaries = [(p.char_start, p.page_num) for p in pages]

        chunks = []
        start = 0
        chunk_idx = 0

        while start < len(full_text):
            end = min(start + self.chunk_chars, len(full_text))

            # Try to break at sentence boundary in last 20% of chunk
            if end < len(full_text):
                search_start = start + int(self.chunk_chars * 0.8)
                best_break = end

                for punct in ['. ', '.\n', '? ', '?\n', '! ', '!\n']:
                    pos = full_text.rfind(punct, search_start, end)
                    if pos != -1:
                        best_break = pos + len(punct)
                        break

                end = best_break

            chunk_text = full_text[start:end].strip()

            if chunk_text:
                # Find page number for chunk start
                page_num = 1
                for offset, pnum in page_boundaries:
                    if offset <= start:
                        page_num = pnum
                    else:
                        break

                # Assign section label and confidence
                section, section_confidence = assign_section_with_confidence(start, section_spans)

                chunks.append(Chunk(
                    text=chunk_text,
                    chunk_index=chunk_idx,
                    page_num=page_num,
                    char_start=start,
                    char_end=end,
                    section=section,
                    section_confidence=section_confidence,
                ))
                chunk_idx += 1

            # Move start with overlap, ensuring forward progress
            next_start = end - self.overlap_chars
            if next_start <= start:
                next_start = end
            start = next_start

        return chunks
