"""Table extraction from PDF pages using PyMuPDF."""
import logging
import re
from pathlib import Path

import pymupdf

from .models import ExtractedTable

logger = logging.getLogger(__name__)

# Caption detection patterns
CAPTION_PATTERNS = [
    re.compile(r"^Table\s*\d+[.:]?\s*", re.IGNORECASE),
    re.compile(r"^Tab\.\s*\d+[.:]?\s*", re.IGNORECASE),
    re.compile(r"^TABLE\s+[IVXLCDM]+[.:]?\s*", re.IGNORECASE),  # Roman numerals
]

# Table continuation patterns
CONTINUATION_PATTERNS = [
    re.compile(r"\(continued\)", re.IGNORECASE),
    re.compile(r"\(cont\.?\)", re.IGNORECASE),
    re.compile(r"continued\s+from", re.IGNORECASE),
]

# Extract table number from caption (e.g., "Table 3: Results" -> 3)
TABLE_NUMBER_PATTERN = re.compile(r"Table\s*(\d+)", re.IGNORECASE)

# Maximum distance (in points) to search for caption above/below table
DEFAULT_CAPTION_SEARCH_DISTANCE = 50.0


class TableExtractor:
    """Extract tables from PDF pages using PyMuPDF's find_tables().

    Requires PyMuPDF 1.23.0+ for find_tables() support.
    """

    def __init__(
        self,
        min_rows: int = 2,
        min_cols: int = 2,
        caption_search_distance: float = DEFAULT_CAPTION_SEARCH_DISTANCE,
    ):
        """
        Initialize table extractor.

        Args:
            min_rows: Minimum rows for a valid table (excludes noise)
            min_cols: Minimum columns for a valid table
            caption_search_distance: Points above/below table to search for caption
        """
        self.min_rows = min_rows
        self.min_cols = min_cols
        self.caption_search_distance = caption_search_distance

    def extract_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        """Extract all tables from a PDF, merging continuations.

        Tables spanning multiple pages are merged into single logical tables.
        A table is considered a continuation if:
        - Its caption contains "(continued)" or similar, OR
        - It has no caption (uncaptioned tables are assumed continuations)

        Only primary tables (with proper "Table N: description" captions) are returned.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of ExtractedTable objects sorted by (page_num, table_index)
        """
        doc = pymupdf.open(pdf_path)
        raw_tables = []

        try:
            for page_num, page in enumerate(doc, start=1):
                page_tables = self._extract_page_tables(page, page_num)
                raw_tables.extend(page_tables)
        finally:
            doc.close()

        # Merge continuations into primary tables
        return self._merge_continuations(raw_tables)

    def _extract_page_tables(
        self,
        page: pymupdf.Page,
        page_num: int
    ) -> list[ExtractedTable]:
        """Extract tables from a single page.

        Uses a two-pass strategy:
        1. First try lines strategy (for bordered tables)
        2. Fall back to text strategy with snap_tolerance for gridless tables

        Args:
            page: PyMuPDF page object
            page_num: 1-indexed page number

        Returns:
            List of ExtractedTable objects from this page
        """
        # PyMuPDF 1.23+ has find_tables()
        try:
            # Pass 1: Try lines strategy (bordered tables)
            found = page.find_tables(strategy="lines")
            if found.tables:
                tables = self._process_found_tables(found, page, page_num)
                if tables:
                    logger.debug(f"Found {len(tables)} bordered tables on page {page_num}")
                    return tables

            # Pass 2: Try text strategy for gridless tables
            # snap_tolerance=10 groups text more aggressively into cells
            found = page.find_tables(strategy="text", snap_tolerance=10)
            if found.tables:
                tables = self._process_found_tables(
                    found, page, page_num, is_gridless=True
                )
                if tables:
                    logger.debug(f"Found {len(tables)} gridless tables on page {page_num}")
                    return tables

        except AttributeError:
            logger.warning(
                "PyMuPDF version does not support find_tables(). "
                "Upgrade to PyMuPDF 1.23+ for table extraction."
            )

        return []

    def _process_found_tables(
        self,
        found,
        page: pymupdf.Page,
        page_num: int,
        is_gridless: bool = False
    ) -> list[ExtractedTable]:
        """Process tables found by find_tables().

        Args:
            found: TableFinder result from PyMuPDF
            page: PyMuPDF page object
            page_num: 1-indexed page number
            is_gridless: If True, apply stricter filtering for text-detected tables

        Returns:
            List of valid ExtractedTable objects
        """
        tables = []
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height

        for table_idx, table in enumerate(found.tables):
            # Extract cell data
            rows = []
            for row in table.extract():
                # Clean cell values
                cleaned = [self._clean_cell(cell) for cell in row]
                rows.append(cleaned)

            if not rows:
                continue

            # Get bounding box
            bbox = table.bbox  # (x0, y0, x1, y1)

            # For gridless tables, apply additional filtering
            if is_gridless:
                # Skip if table covers >60% of page (likely false positive)
                table_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                if table_area > page_area * 0.6:
                    logger.debug(
                        f"Skipping page-spanning table on page {page_num}: "
                        f"{table_area/page_area:.0%} of page"
                    )
                    continue

                # Skip if too many rows (likely body text, not table)
                if len(rows) > 30:
                    logger.debug(
                        f"Skipping large table on page {page_num}: "
                        f"{len(rows)} rows (likely body text)"
                    )
                    continue

                # Count non-empty cells to ensure it's actually tabular
                non_empty_rows = [r for r in rows if any(c and c.strip() for c in r)]
                if len(non_empty_rows) < self.min_rows:
                    continue

            # Check minimum size
            num_cols = max(len(row) for row in rows) if rows else 0
            if len(rows) < self.min_rows or num_cols < self.min_cols:
                logger.debug(
                    f"Skipping small table on page {page_num}: "
                    f"{len(rows)} rows x {num_cols} cols"
                )
                continue

            # Search for caption - first try outside bbox, then inside table content
            caption, caption_pos = self._find_caption(page, bbox)

            # For gridless tables, caption may be inside the table content
            if is_gridless and not caption:
                caption, rows = self._extract_caption_from_rows(rows)
                if caption:
                    caption_pos = "inline"

            # Separate headers from data using heuristics
            headers, data_rows = self._detect_header_row(rows)

            tables.append(ExtractedTable(
                page_num=page_num,
                table_index=table_idx,
                bbox=bbox,
                headers=headers,
                rows=data_rows,
                caption=caption,
                caption_position=caption_pos,
            ))

        return tables

    def _clean_cell(self, cell) -> str:
        """Clean a cell value.

        Args:
            cell: Cell value (may be None or any type)

        Returns:
            Cleaned string value
        """
        if cell is None:
            return ""
        text = str(cell).strip()
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text

    def _find_caption(
        self,
        page: pymupdf.Page,
        table_bbox: tuple[float, float, float, float]
    ) -> tuple[str, str]:
        """Find caption text near a table using hybrid approach.

        1. Primary: Position-aware block detection (full page width)
        2. Fallback: Expanded rect search

        Args:
            page: PyMuPDF page object
            table_bbox: Table bounding box (x0, y0, x1, y1)

        Returns:
            Tuple of (caption_text, position) where position is "above"|"below"|""
        """
        caption = self._find_caption_by_blocks(page, table_bbox)
        if caption[0]:
            return caption
        return self._find_caption_by_rect(page, table_bbox)

    def _find_caption_by_blocks(
        self,
        page: pymupdf.Page,
        table_bbox: tuple[float, float, float, float]
    ) -> tuple[str, str]:
        """Find caption by analyzing text blocks near the table.

        Searches full page width (not clipped to table X-bounds) since
        captions often start at page margin, not table edge.
        """
        x0, y0, x1, y1 = table_bbox

        blocks = page.get_text("dict")["blocks"]
        best_caption = ("", "")
        best_distance = float('inf')

        for block in blocks:
            if block.get("type") != 0:  # Skip images
                continue

            block_bbox = block["bbox"]
            block_y0, block_y1 = block_bbox[1], block_bbox[3]

            # Check above table (within 150pt)
            if block_y1 <= y0 and y0 - block_y1 < 150:
                text = " ".join(
                    span["text"]
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                )
                for pattern in CAPTION_PATTERNS:
                    if pattern.search(text):
                        distance = y0 - block_y1
                        if distance < best_distance:
                            best_distance = distance
                            best_caption = (self._extract_caption_text(text), "above")

            # Check below table (within 150pt)
            elif block_y0 >= y1 and block_y0 - y1 < 150:
                text = " ".join(
                    span["text"]
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                )
                for pattern in CAPTION_PATTERNS:
                    if pattern.search(text):
                        distance = block_y0 - y1
                        if distance < best_distance:
                            best_distance = distance
                            best_caption = (self._extract_caption_text(text), "below")

        return best_caption

    def _find_caption_by_rect(
        self,
        page: pymupdf.Page,
        table_bbox: tuple[float, float, float, float]
    ) -> tuple[str, str]:
        """Fallback: search full page width with expanded vertical range."""
        x0, y0, x1, y1 = table_bbox
        page_rect = page.rect

        # Search full page width, 100pt above
        above_rect = pymupdf.Rect(0, max(0, y0 - 100), page_rect.width, y0)
        above_text = page.get_text("text", clip=above_rect).strip()

        # Search full page width, 100pt below
        below_rect = pymupdf.Rect(0, y1, page_rect.width, min(page_rect.height, y1 + 100))
        below_text = page.get_text("text", clip=below_rect).strip()

        for pattern in CAPTION_PATTERNS:
            if above_text and pattern.search(above_text):
                return self._extract_caption_text(above_text), "above"
            if below_text and pattern.search(below_text):
                return self._extract_caption_text(below_text), "below"

        return "", ""

    def _extract_caption_text(self, text: str) -> str:
        """Extract just the caption text, cleaning up formatting.

        Args:
            text: Raw text from caption region

        Returns:
            Cleaned caption text (first paragraph only)
        """
        # Take first paragraph/sentence
        lines = text.split("\n")
        caption_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                break
            caption_lines.append(line)
        return " ".join(caption_lines)

    def _extract_caption_from_rows(
        self, rows: list[list[str]]
    ) -> tuple[str, list[list[str]]]:
        """Extract caption from table rows (for gridless tables).

        For gridless tables detected with text strategy, the caption
        is often included in the first few rows of the table content.

        Args:
            rows: All rows from table extraction

        Returns:
            Tuple of (caption, remaining_rows) where caption is the
            extracted caption text (or empty string), and remaining_rows
            are the rows with the caption row removed.
        """
        if not rows:
            return "", rows

        # Check first 3 rows for caption pattern
        for i, row in enumerate(rows[:3]):
            row_text = " ".join(c for c in row if c)

            for pattern in CAPTION_PATTERNS:
                match = pattern.search(row_text)
                if match:
                    # Extract caption text from this row
                    caption = self._extract_caption_text(row_text)
                    # Remove caption row from table data
                    remaining = rows[:i] + rows[i+1:]
                    logger.debug(f"Found inline caption: {caption[:50]}...")
                    return caption, remaining

        return "", rows

    def _is_likely_header_row(self, row: list[str]) -> bool:
        """Determine if a row is likely a header based on heuristics.

        Heuristics:
        1. Contains text (not purely numeric)
        2. Not empty

        Args:
            row: List of cell values

        Returns:
            True if row appears to be a header row
        """
        if not row or all(not cell.strip() for cell in row):
            return False

        numeric_cells = 0
        text_cells = 0

        for cell in row:
            cell = cell.strip()
            if not cell:
                continue
            cleaned = cell.replace('.', '').replace('-', '').replace(',', '').replace('%', '')
            if cleaned.isdigit():
                numeric_cells += 1
            else:
                text_cells += 1

        # Purely numeric rows are not headers
        if text_cells == 0 and numeric_cells > 0:
            return False

        return True

    def _detect_header_row(self, rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
        """Detect and separate header row from data rows.

        Args:
            rows: All rows from table extraction

        Returns:
            Tuple of (header_row, data_rows)
        """
        if not rows:
            return [], []

        if self._is_likely_header_row(rows[0]):
            return rows[0], rows[1:]

        # Default: first row is header even if it doesn't pass heuristics
        return rows[0] if rows else [], rows[1:] if len(rows) > 1 else []

    def _is_continuation(self, table: ExtractedTable) -> bool:
        """Check if a table is a continuation of a previous table.

        A table is considered a continuation if:
        - Its caption contains "(continued)" or similar, OR
        - It has no caption (uncaptioned = continuation)

        Args:
            table: ExtractedTable to check

        Returns:
            True if this is a continuation table
        """
        if not table.caption:
            return True  # Uncaptioned = continuation

        for pattern in CONTINUATION_PATTERNS:
            if pattern.search(table.caption):
                return True

        return False

    def _extract_table_number(self, caption: str) -> int | None:
        """Extract table number from caption (e.g., 'Table 3: Results' -> 3).

        Args:
            caption: Caption text

        Returns:
            Table number if found, None otherwise
        """
        if not caption:
            return None
        match = TABLE_NUMBER_PATTERN.search(caption)
        return int(match.group(1)) if match else None

    def _merge_continuations(self, tables: list[ExtractedTable]) -> list[ExtractedTable]:
        """Merge continuation tables with structural validation.

        A table is merged as continuation only if:
        1. Caption contains "(continued)" or similar, OR
        2. No caption AND on consecutive page AND matching column structure

        Orphaned continuations (no matching primary) are kept standalone with caption=None.

        Args:
            tables: All extracted tables from document

        Returns:
            List of primary tables plus orphaned continuations (as standalone tables)
        """
        if not tables:
            return []

        primary_tables: dict[int, ExtractedTable] = {}
        continuations: list[ExtractedTable] = []
        orphans: list[ExtractedTable] = []

        for table in tables:
            if self._is_continuation(table):
                continuations.append(table)
            else:
                table_num = self._extract_table_number(table.caption)
                if table_num is not None:
                    primary_tables[table_num] = table

        # Match continuations with structural validation
        for cont_table in continuations:
            best_match = self._find_matching_primary(cont_table, primary_tables)

            if best_match and self._columns_match(best_match, cont_table):
                best_match.rows.extend(cont_table.rows)
                logger.debug(f"Merged {len(cont_table.rows)} rows from page {cont_table.page_num}")
            else:
                # Keep as standalone orphan with caption=None
                cont_table.caption = None  # Clear any "(continued)" caption
                orphans.append(cont_table)
                logger.debug(
                    f"Orphaned continuation on page {cont_table.page_num} "
                    f"kept as standalone table"
                )

        # Return primaries + orphans
        all_tables = list(primary_tables.values()) + orphans
        return sorted(all_tables, key=lambda t: (t.page_num, t.table_index))

    def _find_matching_primary(
        self,
        cont_table: ExtractedTable,
        primaries: dict[int, ExtractedTable]
    ) -> ExtractedTable | None:
        """Find the primary table this continuation belongs to.

        Continuation must be on page N+1 of primary (not same page).

        Args:
            cont_table: The continuation table
            primaries: Dict of table_num -> primary table

        Returns:
            The matching primary table, or None if no match
        """
        candidates = []
        for table_num, primary in primaries.items():
            page_diff = cont_table.page_num - primary.page_num
            if page_diff == 1:  # Only consecutive page
                candidates.append((page_diff, primary))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    def _columns_match(self, primary: ExtractedTable, continuation: ExtractedTable) -> bool:
        """Check if column structure matches for safe merging.

        Args:
            primary: The primary table
            continuation: The continuation table

        Returns:
            True if column count matches (and headers are similar if both present)
        """
        if primary.num_cols != continuation.num_cols:
            logger.debug(
                f"Column mismatch: primary has {primary.num_cols}, "
                f"continuation has {continuation.num_cols}"
            )
            return False

        # If both have headers, check similarity
        if continuation.headers and primary.headers:
            try:
                from rapidfuzz import fuzz
                similarity = fuzz.ratio(
                    " ".join(primary.headers),
                    " ".join(continuation.headers)
                )
                if similarity < 70:
                    logger.debug(
                        f"Header similarity too low: {similarity}%"
                    )
                    return False
            except ImportError:
                pass  # rapidfuzz not available, skip header check

        return True

    def get_table_count(self, pdf_path: Path) -> int:
        """Quick count of tables without full extraction.

        Uses same two-pass strategy as extract_tables:
        1. Try lines strategy (bordered tables)
        2. Fall back to text strategy (gridless tables)

        Args:
            pdf_path: Path to PDF file

        Returns:
            Total number of tables found (before filtering)
        """
        doc = pymupdf.open(pdf_path)
        count = 0
        try:
            for page in doc:
                try:
                    # Try lines strategy first
                    found = page.find_tables(strategy="lines")
                    if found.tables:
                        count += len(found.tables)
                    else:
                        # Fall back to text strategy
                        found = page.find_tables(strategy="text", snap_tolerance=10)
                        count += len(found.tables)
                except AttributeError:
                    break
        finally:
            doc.close()
        return count

    @staticmethod
    def is_available() -> bool:
        """Check if table extraction is available (PyMuPDF 1.23+).

        Returns:
            True if find_tables() is available
        """
        try:
            version_parts = pymupdf.version[0].split(".")[:2]
            version = tuple(map(int, version_parts))
            return version >= (1, 23)
        except Exception:
            return False
