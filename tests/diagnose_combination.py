"""Diagnose why consensus boundary combination destroys accuracy on specific tables.

For each failing table (0% consensus accuracy despite individual methods achieving
100%), this script:

1. Looks up the paper item_key, page_num, and bbox from _stress_test_debug.db
2. Resolves the PDF path via Zotero client
3. Opens the PDF, creates a TableContext
4. Runs each structure method individually to collect BoundaryHypothesis objects
5. Runs combine_hypotheses() with trace=True to get a CombinationTrace
6. Reports per-table diagnostics: column counts, cluster formation, acceptance

Output: _combination_diagnosis.md in the project root.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import pymupdf

from zotero_chunk_rag.feature_extraction.combination import combine_hypotheses
from zotero_chunk_rag.feature_extraction.ground_truth import make_table_id
from zotero_chunk_rag.feature_extraction.models import (
    AxisTrace,
    BoundaryHypothesis,
    CombinationTrace,
    TableContext,
)
from zotero_chunk_rag.feature_extraction.pipeline import DEFAULT_CONFIG, Pipeline
from tests.create_ground_truth import _resolve_pdf_paths

FAILING_TABLE_IDS = [
    "SCPXVBLY_table_1_p16",
    "SCPXVBLY_table_3",
    "SCPXVBLY_table_3_p31",
    "5SIZVS65_table_4",
    "Z9X4JVZ5_table_5",
    "DPYRZTFI_table_2",
    "AQ3D94VC_table_1",
    "AQ3D94VC_table_2",
    "AQ3D94VC_table_3",
    "AQ3D94VC_table_4",
    "9GKLLJH9_table_2",
]

DB_PATH = _PROJECT_ROOT / "_stress_test_debug.db"
OUTPUT_PATH = _PROJECT_ROOT / "_combination_diagnosis.md"


def _find_extracted_table_for_id(con, table_id):
    """Find the extracted_tables row whose make_table_id() matches table_id."""
    cursor = con.execute(
        'SELECT item_key, table_index, page_num, caption, bbox, artifact_type '
        'FROM extracted_tables ORDER BY item_key, table_index'
    )
    for r in cursor.fetchall():
        item_key, table_index, page_num, caption, bbox_json, artifact_type = r
        generated_id = make_table_id(item_key, caption, page_num, table_index)
        if generated_id == table_id:
            bbox = json.loads(bbox_json) if bbox_json else [0, 0, 0, 0]
            return {
                'item_key': item_key,
                'table_index': table_index,
                'page_num': page_num,
                'caption': caption,
                'bbox': tuple(float(v) for v in bbox),
                'artifact_type': artifact_type,
            }
    return None


def _get_method_accuracies(con, table_id):
    """Get per-method GT accuracy for a table from method_results."""
    cursor = con.execute(
        'SELECT method_name, quality_score FROM method_results '
        'WHERE table_id = ? ORDER BY quality_score DESC',
        (table_id,),
    )
    return [(r[0], r[1]) for r in cursor.fetchall()]


def _format_axis_trace(axis_trace, axis_name):
    """Format an AxisTrace into readable markdown lines."""
    lines = []
    lines.append(f'#### {axis_name} Axis')
    lines.append('')
    lines.append(f'- **Input points**: {len(axis_trace.input_points)}')
    lines.append(f'- **Median confidence**: {axis_trace.median_confidence:.4f}')
    lines.append(f'- **Acceptance threshold**: {axis_trace.acceptance_threshold:.4f}')
    lines.append(f'- **Clusters formed**: {len(axis_trace.clusters)}')
    lines.append(f'- **Accepted positions**: {len(axis_trace.accepted_positions)}')
    lines.append('')

    expanded_count = sum(1 for e in axis_trace.expansions if e.was_expanded)
    lines.append(f'- **Points expanded**: {expanded_count}/{len(axis_trace.expansions)}')
    lines.append('')

    provenance_counts = {}
    for pt in axis_trace.input_points:
        provenance_counts[pt.provenance] = provenance_counts.get(pt.provenance, 0) + 1
    if provenance_counts:
        lines.append('**Input points by provenance:**')
        lines.append('')
        lines.append('| Method | Points |')
        lines.append('|--------|--------|')
        for prov, count in sorted(provenance_counts.items()):
            lines.append(f'| {prov} | {count} |')
        lines.append('')

    if axis_trace.clusters:
        lines.append('**Cluster details:**')
        lines.append('')
        lines.append('| # | Position | Confidence | Methods | Accepted | Threshold |')
        lines.append('|---|----------|------------|---------|----------|-----------|')
        for i, cluster in enumerate(axis_trace.clusters):
            provenances = set(pt.provenance for pt in cluster.points)
            prov_str = ', '.join(sorted(provenances))
            acc_str = 'YES' if cluster.accepted else 'NO'
            lines.append(
                f'| {i} | {cluster.weighted_position:.2f} | '
                f'{cluster.total_confidence:.4f} | '
                f'{cluster.distinct_methods} ({prov_str}) | '
                f'{acc_str} | {cluster.acceptance_threshold:.4f} |'
            )
        lines.append('')

    return lines


def diagnose_table(table_id, table_info, pdf_path, method_accuracies):
    """Run combination with trace for a single table and return diagnosis lines."""
    lines = []
    lines.append(f'### {table_id}')
    lines.append('')
    lines.append(f'- **Paper**: {table_info["item_key"]}')
    lines.append(f'- **Page**: {table_info["page_num"]}')
    cap = table_info['caption']
    lines.append(f'- **Caption**: {cap}')
    lines.append(f'- **BBox**: {table_info["bbox"]}')
    lines.append('')

    lines.append('**Per-method GT accuracy (from stress test):**')
    lines.append('')
    lines.append('| Method | Accuracy |')
    lines.append('|--------|----------|')
    for method_name, score in method_accuracies:
        score_str = f'{score:.1f}%' if score is not None else 'N/A'
        lines.append(f'| {method_name} | {score_str} |')
    lines.append('')

    doc = pymupdf.open(str(pdf_path))
    page_idx = table_info['page_num'] - 1
    if page_idx < 0 or page_idx >= len(doc):
        pn = table_info['page_num']
        lines.append(f'**ERROR**: Page {pn} out of range (doc has {len(doc)} pages)')
        doc.close()
        return lines

    page = doc[page_idx]
    ctx = TableContext(
        page=page,
        page_num=table_info['page_num'],
        bbox=table_info['bbox'],
        pdf_path=pdf_path,
    )

    lines.append('**Context properties (adaptive threshold inputs):**')
    lines.append('')
    lines.append(f'- median_word_height: {ctx.median_word_height:.4f}')
    lines.append(f'- median_word_gap: {ctx.median_word_gap:.4f}')
    lines.append(f'- median_ruled_line_thickness: {ctx.median_ruled_line_thickness}')
    lines.append(f'- word count: {len(ctx.words)}')
    lines.append(f'- drawing count: {len(ctx.drawings)}')
    lines.append('')

    pipeline = Pipeline(DEFAULT_CONFIG)
    all_hypotheses = []
    method_col_counts = {}
    method_row_counts = {}

    lines.append('**Structure method boundary counts:**')
    lines.append('')
    lines.append('| Method | Columns | Rows | Activated |')
    lines.append('|--------|---------|------|-----------|')

    for method in DEFAULT_CONFIG.structure_methods:
        predicate = DEFAULT_CONFIG.activation_rules.get(method.name)
        if predicate is not None and not predicate(ctx):
            lines.append(f'| {method.name} | - | - | SKIPPED |')
            continue
        try:
            hypothesis = method.detect(ctx)
        except Exception as exc:
            lines.append(f'| {method.name} | ERROR | ERROR | {exc!r} |')
            continue
        if hypothesis is None:
            lines.append(f'| {method.name} | 0 | 0 | No hypothesis |')
            continue
        n_cols = len(hypothesis.col_boundaries)
        n_rows = len(hypothesis.row_boundaries)
        method_col_counts[method.name] = n_cols
        method_row_counts[method.name] = n_rows
        lines.append(f'| {method.name} | {n_cols} | {n_rows} | YES |')
        all_hypotheses.append(hypothesis)

    lines.append('')

    if not all_hypotheses:
        lines.append('**No hypotheses produced -- cannot run combination.**')
        lines.append('')
        doc.close()
        return lines

    consensus, trace = combine_hypotheses(all_hypotheses, ctx, trace=True)

    lines.append('**Combination parameters:**')
    lines.append('')
    lines.append(f'- spatial_precision: {trace.spatial_precision:.4f}')
    lines.append(f'- source_methods: {len(trace.source_methods)}')
    lines.append('')

    consensus_col_count = len(consensus.col_boundaries)
    consensus_row_count = len(consensus.row_boundaries)
    lines.append(f'**Consensus result: {consensus_col_count} columns, {consensus_row_count} rows**')
    lines.append('')

    lines.append('**Column count comparison:**')
    lines.append('')
    lines.append('| Method | Columns | vs Consensus |')
    lines.append('|--------|---------|-------------|')
    for method_name, n_cols in sorted(method_col_counts.items()):
        delta = n_cols - consensus_col_count
        delta_str = f'+{delta}' if delta > 0 else str(delta)
        lines.append(f'| {method_name} | {n_cols} | {delta_str} |')
    lines.append(f'| **consensus** | **{consensus_col_count}** | - |')
    lines.append('')

    lines.extend(_format_axis_trace(trace.col_trace, 'Column'))
    lines.extend(_format_axis_trace(trace.row_trace, 'Row'))

    lines.append('#### Detailed Column Boundary Positions')
    lines.append('')
    for hyp in all_hypotheses:
        positions = sorted(
            (bp.min_pos + bp.max_pos) / 2 for bp in hyp.col_boundaries
        )
        pos_str = ', '.join(f'{p:.1f}' for p in positions)
        lines.append(f'- **{hyp.method}**: [{pos_str}]')

    consensus_positions = sorted(
        (bp.min_pos + bp.max_pos) / 2 for bp in consensus.col_boundaries
    )
    pos_str = ', '.join(f'{p:.1f}' for p in consensus_positions)
    lines.append(f'- **consensus**: [{pos_str}]')
    lines.append('')

    col_count_groups = {}
    for method_name, n_cols in method_col_counts.items():
        col_count_groups.setdefault(n_cols, []).append(method_name)
    lines.append('**Methods by column count:**')
    lines.append('')
    for n_cols, methods in sorted(col_count_groups.items()):
        method_list = ', '.join(methods)
        lines.append(f'- {n_cols} columns: {method_list}')
    lines.append('')

    lines.append('---')
    lines.append('')

    doc.close()
    return lines


def main():
    """Run combination diagnosis for all failing tables."""
    if not DB_PATH.exists():
        print(f'ERROR: Debug database not found at {DB_PATH}')
        sys.exit(1)

    print('Resolving PDF paths from Zotero library...')
    pdf_paths = _resolve_pdf_paths()
    print(f'  Found {len(pdf_paths)} PDFs')

    con = sqlite3.connect(str(DB_PATH))

    report_lines = []
    report_lines.append('# Combination Diagnosis Report')
    report_lines.append('')
    report_lines.append(
        'Analysis of why consensus boundary combination produces 0% accuracy '
        'on specific tables where individual methods achieve 100%.'
    )
    report_lines.append('')

    report_lines.append('## Summary')
    report_lines.append('')
    report_lines.append('| Table ID | Paper | Consensus Acc | Best Method Acc |')
    report_lines.append('|----------|-------|---------------|-----------------|')

    table_infos = []

    for table_id in FAILING_TABLE_IDS:
        table_info = _find_extracted_table_for_id(con, table_id)
        if table_info is None:
            report_lines.append(f'| {table_id} | NOT FOUND | - | - |')
            continue

        method_accs = _get_method_accuracies(con, table_id)
        best_acc = max((s for _, s in method_accs if s is not None), default=0.0)

        diff_row = con.execute(
            'SELECT cell_accuracy_pct FROM ground_truth_diffs '
            'WHERE table_id = ? ORDER BY rowid DESC LIMIT 1',
            (table_id,),
        ).fetchone()
        consensus_acc = diff_row[0] if diff_row else None
        consensus_str = f'{consensus_acc:.1f}%' if consensus_acc is not None else 'N/A'

        short_name_row = con.execute(
            'SELECT short_name FROM papers WHERE item_key = ?',
            (table_info['item_key'],),
        ).fetchone()
        short_name = short_name_row[0] if short_name_row else table_info['item_key']

        report_lines.append(
            f'| {table_id} | {short_name} | {consensus_str} | {best_acc:.1f}% |'
        )
        table_infos.append((table_id, table_info, method_accs))

    report_lines.append('')
    report_lines.append('## Per-Table Diagnosis')
    report_lines.append('')

    for table_id, table_info, method_accs in table_infos:
        item_key = table_info['item_key']
        pdf_path = pdf_paths.get(item_key)
        if pdf_path is None:
            report_lines.append(f'### {table_id}')
            report_lines.append('')
            report_lines.append(f'**ERROR**: No PDF found for item_key={item_key}')
            report_lines.append('')
            report_lines.append('---')
            report_lines.append('')
            continue

        print(f'Diagnosing {table_id}...')
        diagnosis = diagnose_table(table_id, table_info, pdf_path, method_accs)
        report_lines.extend(diagnosis)

    con.close()

    report_text = chr(10).join(report_lines) + chr(10)
    OUTPUT_PATH.write_text(report_text, encoding='utf-8')
    print(f'')
    print(f'Report written to {OUTPUT_PATH}')
    print(f'  {len(FAILING_TABLE_IDS)} tables diagnosed')


if __name__ == '__main__':
    main()
