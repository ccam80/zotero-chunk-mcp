#!/usr/bin/env python
"""Create sample PDFs with known content for integration testing."""
import pymupdf
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def create_table_pdf():
    """Create a PDF with a known table for testing extraction."""
    doc = pymupdf.open()
    page = doc.new_page()

    # Add a title
    page.insert_text((72, 72), "Test Document with Table", fontsize=16)

    # Add caption above table
    page.insert_text((72, 120), "Table 1: Sample Data", fontsize=11)

    # Draw a simple table manually using lines and text
    # Table starts at y=140
    table_x = 72
    table_y = 140
    col_width = 100
    row_height = 20
    num_cols = 3
    num_rows = 4  # 1 header + 3 data rows

    # Headers
    headers = ["Name", "Value", "Category"]
    # Data rows
    data = [
        ["Alpha", "100", "Type A"],
        ["Beta", "200", "Type B"],
        ["Gamma", "300", "Type C"],
    ]

    # Draw table grid
    for row in range(num_rows + 1):
        y = table_y + row * row_height
        page.draw_line((table_x, y), (table_x + col_width * num_cols, y))

    for col in range(num_cols + 1):
        x = table_x + col * col_width
        page.draw_line((x, table_y), (x, table_y + num_rows * row_height))

    # Insert header text
    for col, header in enumerate(headers):
        x = table_x + col * col_width + 5
        y = table_y + 15
        page.insert_text((x, y), header, fontsize=10)

    # Insert data text
    for row_idx, row_data in enumerate(data):
        for col_idx, cell in enumerate(row_data):
            x = table_x + col_idx * col_width + 5
            y = table_y + (row_idx + 1) * row_height + 15
            page.insert_text((x, y), cell, fontsize=10)

    # Add some body text after the table
    page.insert_text((72, table_y + num_rows * row_height + 40),
                     "This paragraph references Table 1 above.", fontsize=11)

    output_path = FIXTURES_DIR / "sample_with_table.pdf"
    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path}")
    return output_path


def create_scanned_page_pdf():
    """Create a PDF simulating a scanned page (image-only, no text layer)."""
    doc = pymupdf.open()
    page = doc.new_page()

    # Create an image with text rendered into it (simulating a scan)
    # We'll create a pixmap, draw text on it, then insert as image
    rect = pymupdf.Rect(0, 0, 400, 200)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(rect), 1)
    pix.clear_with(255)  # White background

    # We can't easily draw text on a pixmap, so we'll create a temp page,
    # render it, then insert that as an image
    temp_doc = pymupdf.open()
    temp_page = temp_doc.new_page(width=400, height=200)
    temp_page.insert_text((20, 50), "This text is in an image", fontsize=14)
    temp_page.insert_text((20, 80), "OCR should extract this", fontsize=14)
    temp_page.insert_text((20, 110), "Sample scanned content", fontsize=14)

    # Render to pixmap
    pix = temp_page.get_pixmap(dpi=150)
    temp_doc.close()

    # Insert pixmap as image into the actual page
    page.insert_image(pymupdf.Rect(72, 72, 472, 272), pixmap=pix)

    output_path = FIXTURES_DIR / "sample_scanned.pdf"
    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path}")
    return output_path


def create_mixed_pdf():
    """Create a PDF with both text and tables on multiple pages."""
    doc = pymupdf.open()

    # Page 1: Introduction with text
    page1 = doc.new_page()
    page1.insert_text((72, 72), "1. Introduction", fontsize=14)
    page1.insert_text((72, 100),
        "This document contains multiple sections with tables and text. "
        "The purpose is to test the table extraction and section detection features.",
        fontsize=11)

    # Page 2: Methods with a table
    page2 = doc.new_page()
    page2.insert_text((72, 72), "2. Methods", fontsize=14)
    page2.insert_text((72, 100), "Table 2: Experimental Parameters", fontsize=11)

    # Simple table
    table_x, table_y = 72, 120
    col_width, row_height = 120, 20
    headers = ["Parameter", "Value"]
    data = [["Temperature", "25°C"], ["Pressure", "1 atm"], ["Duration", "60 min"]]

    for row in range(5):
        y = table_y + row * row_height
        page2.draw_line((table_x, y), (table_x + col_width * 2, y))
    for col in range(3):
        x = table_x + col * col_width
        page2.draw_line((x, table_y), (x, table_y + 4 * row_height))

    for col, h in enumerate(headers):
        page2.insert_text((table_x + col * col_width + 5, table_y + 15), h, fontsize=10)
    for r, row_data in enumerate(data):
        for c, cell in enumerate(row_data):
            page2.insert_text((table_x + c * col_width + 5, table_y + (r + 1) * row_height + 15),
                            cell, fontsize=10)

    # Page 3: Results with another table
    page3 = doc.new_page()
    page3.insert_text((72, 72), "3. Results", fontsize=14)
    page3.insert_text((72, 100), "Table 3: Outcome Measurements", fontsize=11)

    table_y = 120
    headers = ["Group", "Mean", "SD"]
    data = [["Control", "45.2", "3.1"], ["Treatment", "67.8", "4.2"]]

    for row in range(4):
        y = table_y + row * row_height
        page3.draw_line((table_x, y), (table_x + 100 * 3, y))
    for col in range(4):
        x = table_x + col * 100
        page3.draw_line((x, table_y), (x, table_y + 3 * row_height))

    for col, h in enumerate(headers):
        page3.insert_text((table_x + col * 100 + 5, table_y + 15), h, fontsize=10)
    for r, row_data in enumerate(data):
        for c, cell in enumerate(row_data):
            page3.insert_text((table_x + c * 100 + 5, table_y + (r + 1) * row_height + 15),
                            cell, fontsize=10)

    output_path = FIXTURES_DIR / "sample_mixed.pdf"
    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path}")
    return output_path


def _create_color_pixmap(width: int, height: int, r: int, g: int, b: int) -> "pymupdf.Pixmap":
    """Create a solid color pixmap (RGB) by rendering a temp page."""
    # Create a temporary document with a colored rectangle
    temp_doc = pymupdf.open()
    temp_page = temp_doc.new_page(width=width, height=height)
    rect = pymupdf.Rect(0, 0, width, height)
    temp_page.draw_rect(rect, color=(r/255, g/255, b/255), fill=(r/255, g/255, b/255))
    # Add some visual content so it's clearly a "figure"
    if width > 80 and height > 40:
        temp_page.insert_text((10, height/2), "IMG", fontsize=min(width, height) // 4)
    # Render to pixmap
    pix = temp_page.get_pixmap(dpi=72)
    temp_doc.close()
    return pix


def create_figures_pdf():
    """Create a PDF with actual embedded images for testing figure extraction.

    Contains:
    - A large figure with caption below (tests caption detection)
    - A large figure with caption above (tests alternate caption location)
    - An orphan figure without caption (tests orphan handling)
    - A small icon image (tests size filtering - should be excluded)

    Uses actual embedded images (not drawn rectangles) so PyMuPDF's
    get_images() can detect them.
    """
    doc = pymupdf.open()

    # Page 1: Figure with caption below
    page1 = doc.new_page()
    page1.insert_text((72, 50), "Results", fontsize=14)

    # Create actual image pixmap (150x120 pixels) - blue tint
    pix1 = _create_color_pixmap(150, 120, 200, 200, 255)
    fig1_rect = pymupdf.Rect(72, 80, 222, 200)
    page1.insert_image(fig1_rect, pixmap=pix1)

    # Caption below figure
    page1.insert_text((72, 220), "Figure 1. Heart rate variability analysis showing", fontsize=10)
    page1.insert_text((72, 235), "significant differences between groups.", fontsize=10)

    # Page 2: Figure with caption above + orphan figure
    page2 = doc.new_page()
    page2.insert_text((72, 50), "Methods", fontsize=14)

    # Caption above figure
    page2.insert_text((72, 100), "Fig. 2: Electrode placement diagram", fontsize=10)

    # Figure below the caption (150x100) - green tint
    pix2 = _create_color_pixmap(150, 100, 200, 255, 200)
    fig2_rect = pymupdf.Rect(72, 115, 222, 215)
    page2.insert_image(fig2_rect, pixmap=pix2)

    # Orphan figure (no caption nearby) - 180x150, red tint
    # Place it far from any text that could be a caption
    pix_orphan = _create_color_pixmap(180, 150, 255, 200, 200)
    orphan_rect = pymupdf.Rect(300, 400, 480, 550)
    page2.insert_image(orphan_rect, pixmap=pix_orphan)

    # Page 3: Small icon (should be filtered out) + another captioned figure
    page3 = doc.new_page()

    # Small icon (50x50 - below MIN_SIZE threshold of 100) - gray
    pix_icon = _create_color_pixmap(50, 50, 200, 200, 200)
    icon_rect = pymupdf.Rect(72, 72, 122, 122)
    page3.insert_image(icon_rect, pixmap=pix_icon)

    # Another proper figure with Roman numeral caption style
    page3.insert_text((72, 200), "FIGURE III: Signal processing pipeline", fontsize=10)
    pix3 = _create_color_pixmap(200, 150, 230, 200, 230)
    fig3_rect = pymupdf.Rect(72, 215, 272, 365)
    page3.insert_image(fig3_rect, pixmap=pix3)

    output_path = FIXTURES_DIR / "sample_with_figures.pdf"
    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path}")
    return output_path


if __name__ == "__main__":
    create_table_pdf()
    create_scanned_page_pdf()
    create_mixed_pdf()
    create_figures_pdf()
    print("\nAll test PDFs created successfully!")
