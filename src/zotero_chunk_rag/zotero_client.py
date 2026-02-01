"""Zotero SQLite database client."""
import sqlite3
from pathlib import Path
from .models import ZoteroItem


class ZoteroClient:
    """
    Read-only access to Zotero's SQLite database.

    Key schema notes:
    - itemTypeID 1 = note, 14 = attachment (filter these for "real" items)
    - EAV pattern: itemData + itemDataValues + fields tables
    - Attachments: linkMode 0,1,4 = storage/{key}/, linkMode 2 = linked file
    """

    # Combined query: items with PDFs and all metadata
    ITEMS_WITH_PDFS_SQL = """
    WITH
        base_items AS (
            SELECT items.itemID, items."key" AS itemKey, items.itemTypeID
            FROM items
            WHERE items.itemTypeID NOT IN (1, 14)
              AND items.itemID NOT IN (SELECT itemID FROM deletedItems)
        ),
        titles AS (
            SELECT itemData.itemID, itemDataValues.value AS title
            FROM itemData
            JOIN itemDataValues ON itemData.valueID = itemDataValues.valueID
            JOIN fields ON itemData.fieldID = fields.fieldID
            WHERE fields.fieldName = 'title'
        ),
        years AS (
            SELECT itemData.itemID, CAST(substr(itemDataValues.value, 1, 4) AS INTEGER) AS year
            FROM itemData
            JOIN itemDataValues ON itemData.valueID = itemDataValues.valueID
            JOIN fields ON itemData.fieldID = fields.fieldID
            WHERE fields.fieldName = 'date'
        ),
        authors AS (
            SELECT
                items.itemID,
                CASE
                    WHEN COUNT(*) = 1 THEN
                        MAX(creators.lastName) ||
                        CASE WHEN MAX(creators.firstName) IS NOT NULL AND MAX(creators.firstName) != ''
                             THEN ', ' || substr(MAX(creators.firstName), 1, 1) || '.'
                             ELSE '' END
                    ELSE
                        MAX(CASE WHEN itemCreators.orderIndex = 0 THEN creators.lastName END) || ' et al.'
                END AS authors
            FROM items
            JOIN itemCreators ON items.itemID = itemCreators.itemID
            JOIN creators ON itemCreators.creatorID = creators.creatorID
            GROUP BY items.itemID
        ),
        publications AS (
            SELECT itemData.itemID, itemDataValues.value AS publication
            FROM itemData
            JOIN itemDataValues ON itemData.valueID = itemDataValues.valueID
            JOIN fields ON itemData.fieldID = fields.fieldID
            WHERE fields.fieldName = 'publicationTitle'
        ),
        pdfs AS (
            SELECT
                COALESCE(ia.parentItemID, ia.itemID) AS parentItemID,
                items."key" AS attachmentKey,
                ia.linkMode,
                ia.path
            FROM itemAttachments ia
            JOIN items ON ia.itemID = items.itemID
            WHERE ia.contentType = 'application/pdf'
              AND ia.linkMode IN (0, 1, 2)
        )
    SELECT
        base_items.itemKey,
        COALESCE(titles.title, '[No Title]') AS title,
        COALESCE(authors.authors, '[No Author]') AS authors,
        years.year,
        COALESCE(publications.publication, '') AS publication,
        pdfs.attachmentKey,
        pdfs.linkMode,
        pdfs.path
    FROM base_items
    LEFT JOIN titles ON base_items.itemID = titles.itemID
    LEFT JOIN years ON base_items.itemID = years.itemID
    LEFT JOIN authors ON base_items.itemID = authors.itemID
    LEFT JOIN publications ON base_items.itemID = publications.itemID
    JOIN pdfs ON base_items.itemID = pdfs.parentItemID
    ORDER BY base_items.itemID;
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "zotero.sqlite"
        self.bbt_db_path = self.data_dir / "better-bibtex.sqlite"
        if not self.db_path.exists():
            raise FileNotFoundError(f"Zotero database not found: {self.db_path}")

    def _load_citation_keys(self) -> dict[str, str]:
        """Load BetterBibTeX citation keys. Returns itemKey -> citationKey mapping."""
        if not self.bbt_db_path.exists():
            return {}
        conn = sqlite3.connect(f"file:{self.bbt_db_path}?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT itemKey, citationKey FROM citationkey").fetchall()
            return {row["itemKey"]: row["citationKey"] for row in rows}
        finally:
            conn.close()

    def _resolve_pdf_path(self, path_field: str | None, link_mode: int, attachment_key: str) -> Path | None:
        """
        Resolve attachment path based on linkMode.

        Link modes (from Zotero source):
        - 0: IMPORTED_FILE - storage/{attachmentKey}/{filename}
        - 1: IMPORTED_URL  - storage/{attachmentKey}/{filename}
        - 2: LINKED_FILE   - relative to linked attachment base dir (skip for now)
        - 3: LINKED_URL    - no local file
        - 4: EMBEDDED_IMAGE - storage/{attachmentKey}/{filename}
        """
        if path_field is None:
            return None

        if link_mode == 2:
            # Linked file - would need base dir from Zotero prefs
            # Skip for now, or make configurable
            return None

        if path_field.startswith("storage:"):
            filename = path_field[len("storage:"):]
            full_path = self.data_dir / "storage" / attachment_key / filename
            return full_path if full_path.exists() else None

        return None

    def get_all_items_with_pdfs(self) -> list[ZoteroItem]:
        """Get all Zotero items that have PDF attachments."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.execute(self.ITEMS_WITH_PDFS_SQL)
            rows = cursor.fetchall()
        finally:
            conn.close()

        citation_keys = self._load_citation_keys()

        items = []
        for row in rows:
            pdf_path = self._resolve_pdf_path(
                row["path"],
                row["linkMode"],
                row["attachmentKey"]
            )
            item_key = row["itemKey"]
            items.append(ZoteroItem(
                item_key=item_key,
                title=row["title"],
                authors=row["authors"],
                year=row["year"],
                pdf_path=pdf_path,
                citation_key=citation_keys.get(item_key, ""),
                publication=row["publication"],
            ))

        return items

    def get_item(self, item_key: str) -> ZoteroItem | None:
        """Get a specific item by key."""
        # For now, just filter from all items
        # Could optimize with a WHERE clause if needed
        all_items = self.get_all_items_with_pdfs()
        for item in all_items:
            if item.item_key == item_key:
                return item
        return None
