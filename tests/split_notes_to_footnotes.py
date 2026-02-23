#!/usr/bin/env python
"""Split the 'notes' field in GT JSON files into 'notes' (reviewer commentary)
and 'footnotes' (paper footnotes).

Reads every table_*_gt.json in tests/ground_truth_workspace/, applies per-file
splitting rules derived from manual review of all 44 files, writes back with
the same formatting (2-space indent, trailing newline).

Run from repo root:
    "./.venv/Scripts/python.exe" tests/split_notes_to_footnotes.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import NamedTuple

sys.stdout.reconfigure(encoding="utf-8")


class SplitResult(NamedTuple):
    notes: str
    footnotes: str


# ── Per-file overrides ────────────────────────────────────────────────────────
# Keys are (paper_slug, table_index).
# Values are either:
#   "all_reviewer"   → entire notes stays in notes, footnotes = ""
#   "all_footnotes"  → entire notes becomes footnotes, notes = ""
#   a callable(notes_text) -> SplitResult  for mixed cases

def _split_at_marker(text: str, marker: str) -> SplitResult:
    """Split text at the first occurrence of *marker*.
    Everything before the marker is reviewer commentary, everything from
    the marker onward is paper footnotes.  Leading/trailing whitespace is
    stripped from both parts.
    """
    idx = text.find(marker)
    if idx == -1:
        # marker not found — treat entire text as reviewer commentary
        return SplitResult(notes=text.strip(), footnotes="")
    return SplitResult(
        notes=text[:idx].strip(),
        footnotes=text[idx:].strip(),
    )


def _split_at_regex(text: str, pattern: str) -> SplitResult:
    """Like _split_at_marker but uses a regex to find the split point."""
    m = re.search(pattern, text)
    if m is None:
        return SplitResult(notes=text.strip(), footnotes="")
    idx = m.start()
    return SplitResult(
        notes=text[:idx].strip(),
        footnotes=text[idx:].strip(),
    )


# ── active-inference-tutorial ────────────────────────────────────────────────

def _ait_table1(notes: str) -> SplitResult:
    # notes: "Table continues on next page. The header ... readability only."
    # All reviewer commentary — no paper footnotes
    return SplitResult(notes=notes, footnotes="")


def _ait_table2(notes: str) -> SplitResult:
    # "Continuation of Table 1 from page 15. Footnote: *While, for consistency..."
    return _split_at_marker(notes, "Footnote: *While")


def _ait_table3(notes: str) -> SplitResult:
    # "Table continues on next page. Equations contain mathematical notation.
    #  B† denotes the transpose of B (dagger notation). Aᵀ denotes A-transpose.
    #  ½ denotes one-half."
    # All reviewer commentary — notation clarifications from the reviewer
    return SplitResult(notes=notes, footnotes="")


def _ait_table4(notes: str) -> SplitResult:
    # "Table continues on next page. Equations contain complex mathematical
    #  notation. B† denotes... The rawtext has 'sightly' ..."
    # All reviewer commentary
    return SplitResult(notes=notes, footnotes="")


def _ait_table5(notes: str) -> SplitResult:
    # "This is the final row of Table 2. Variable names from rawtext: ...
    #  Table note: The term B†π,τ denotes the transpose of Bπ,τ ..."
    # Split at "Table note:" — that's the paper's actual footnote
    return _split_at_marker(notes, "Table note:")


def _ait_table6(notes: str) -> SplitResult:
    # "Table continues on next page. The table has 4 columns: MDP Field, ..."
    # All reviewer commentary
    return SplitResult(notes=notes, footnotes="")


def _ait_table7(notes: str) -> SplitResult:
    # "Continuation of Table 3 from page 30. Page bottom contains a footnote
    #  (partially visible): 'Constant α = 512...' with similar direction
    #  notation."
    # This describes a footnote but doesn't transcribe it — reviewer commentary
    return SplitResult(notes=notes, footnotes="")


# ── hallett-tms-primer ────────────────────────────────────────────────────────

def _hallett_table0(notes: str) -> SplitResult:
    # "The image shows the table title ... The PAS row has multi-line cell
    #  content in both Excitatory and Inhibitory columns joined with a space."
    # All reviewer commentary
    return SplitResult(notes=notes, footnotes="")


# ── helm-coregulation ────────────────────────────────────────────────────────

def _helm_table0(notes: str) -> SplitResult:
    # "Note (footnote, not transcribed as row): Models 1–7 are described in
    #  the text. −2 LL = the models −2 log-likelihood; df = the number of ..."
    # The ENTIRE content is a paper footnote (it starts with "Note (footnote")
    return SplitResult(notes="", footnotes=notes)


def _helm_table1(notes: str) -> SplitResult:
    # "The image shows ... 'Baseline' and 'Conversation' are sub-group headings
    #  ... Coefficient subscripts use m (male) and f (female). Note (footnote):
    #  β₀ = the average RSA ... male and female, respectively."
    return _split_at_marker(notes, "Note (footnote):")


# ── laird-fick-polyps ────────────────────────────────────────────────────────

def _laird_table0(notes: str) -> SplitResult:
    # "Two-level header: 'Sexᵃ' spans ... Lowest-level headers used.
    #  Footnote a (on Sex): Percent in row might not sum to 100 due to
    #  rounding. Chi-square tests ... Footnote b (on Total): Percent of
    #  all patients (n = 13,881)."
    return _split_at_marker(notes, "Footnote a")


def _laird_table1(notes: str) -> SplitResult:
    # "Two-level header: 'Sexᵃ' spans ... Lowest-level headers used.
    #  Footnote a (on Sex): Percent in row might not sum to 100 due to
    #  rounding. Footnote b (on Total): Percent of total patients."
    return _split_at_marker(notes, "Footnote a")


def _laird_table2(notes: str) -> SplitResult:
    # "Two-level header: 'Sex' spans ... Lowest-level headers used.
    #  Footnote a (on Total): Percent of patients (n = 9301)."
    return _split_at_marker(notes, "Footnote a")


def _laird_table3(notes: str) -> SplitResult:
    # "Header row has two levels: ... Sub-group header rows ... transcribed as
    #  rows with empty cells in other columns. Referent rows have no confidence
    #  limits or p-value. Footnote a (on Adjusted): Estimates from multiple
    #  logistic regression with Sex and Age."
    return _split_at_marker(notes, "Footnote a")


def _laird_table4(notes: str) -> SplitResult:
    # "Two-level header: 'Sexᵃ' spans ... Lowest-level headers used.
    #  Footnote a (on Sex): Percent in row might not sum to 100 due to
    #  rounding. Footnote b (on Total): Percent of total patients."
    return _split_at_marker(notes, "Footnote a")


# ── reyes-lf-hrv ─────────────────────────────────────────────────────────────

def _reyes_table0(notes: str) -> SplitResult:
    # "IBI, VLF, LF, HF are sub-group header rows ... BL = baseline. The last
    #  column header contains two effect sizes: one for BL comparison (LB) and
    #  one for Task comparison. Note at bottom of table: BL = baseline, IBI =
    #  interbeat interval, VLF = very low frequency, LF = low frequency, HF =
    #  high frequency."
    return _split_at_marker(notes, "Note at bottom of table:")


def _reyes_table1(notes: str) -> SplitResult:
    # "IBI, VLF, LF, HF are sub-group header rows ... F, p, and η² values
    #  appear only once per parameter group (on the A row), reflecting the
    #  interaction effect; S rows have empty values for those columns. Note.
    #  HRV was analyzed by means of adaptive autoregressive models ..."
    return _split_at_regex(notes, r"Note\. HRV")


def _reyes_table2(notes: str) -> SplitResult:
    # "Panel A and Panel B are sub-group header rows; other columns in those
    #  rows are empty. IBI-BL and IBI-Task rows have empty IBI column because
    #  correlation of IBI with itself is not reported. Note. BL = baseline,
    #  Task = mental arithmetic, VLF = very low frequency, LF = low frequency,
    #  HF = high frequency. +p < .05. *p < .01."
    return _split_at_regex(notes, r"Note\. BL = baseline")


def _reyes_table3(notes: str) -> SplitResult:
    # "Panel A and Panel B are sub-group header rows; other columns in those
    #  rows are empty. IBI-BL and IBI-Task rows have empty IBI column because
    #  correlation of IBI with itself is not reported. Note. VLF = very low
    #  frequency, LF = low frequency, HF = high frequency. +p < .05. *p < .01."
    return _split_at_regex(notes, r"Note\. VLF")


# ── yang-ppv-meta ────────────────────────────────────────────────────────────

def _yang_table0(notes: str) -> SplitResult:
    # "Footnotes: MICU, medical intensive care unit; NA, not available; SICU,
    #  surgical intensive care unit. aTwenty-two fluid challenges included.
    #  bTwenty-eight fluid challenges included."
    # Entire content is paper footnotes
    return SplitResult(notes="", footnotes=notes)


def _yang_table1(notes: str) -> SplitResult:
    # "CI, cardiac index; CO, cardiac output; Echo, echocardiography; HES, ..."
    # Entire content is paper footnotes (abbreviation definitions + superscript notes)
    return SplitResult(notes="", footnotes=notes)


def _yang_table2(notes: str) -> SplitResult:
    # "Footnotes: fn, false negative; fp, false positive; PPV, pulse pressure
    #  variation; ..."
    # Entire content is paper footnotes
    return SplitResult(notes="", footnotes=notes)


# ── roland-emg-filter ────────────────────────────────────────────────────────

def _roland_table8(notes: str) -> SplitResult:
    # "The table has no visible header row in the original; column headers
    #  'Abbreviation' and 'Meaning' are inferred from context. The section
    #  heading 'The following abbreviations are used in this manuscript:'
    #  appears above the table (partially visible at top of image). The µC
    #  entry uses the micro sign (µ)."
    # All reviewer commentary — structural observation
    return SplitResult(notes=notes, footnotes="")


# ── Mapping table ─────────────────────────────────────────────────────────────

OVERRIDES: dict[tuple[str, int], str | callable] = {
    # active-inference-tutorial
    ("active-inference-tutorial", 0): "all_reviewer",
    ("active-inference-tutorial", 1): _ait_table1,
    ("active-inference-tutorial", 2): _ait_table2,
    ("active-inference-tutorial", 3): _ait_table3,
    ("active-inference-tutorial", 4): _ait_table4,
    ("active-inference-tutorial", 5): _ait_table5,
    ("active-inference-tutorial", 6): _ait_table6,
    ("active-inference-tutorial", 7): _ait_table7,
    # fortune-impedance — all reviewer
    ("fortune-impedance", 0): "all_reviewer",
    ("fortune-impedance", 1): "all_reviewer",
    ("fortune-impedance", 2): "all_reviewer",
    ("fortune-impedance", 3): "all_reviewer",
    ("fortune-impedance", 4): "all_reviewer",
    ("fortune-impedance", 5): "all_reviewer",
    ("fortune-impedance", 6): "all_reviewer",
    # friston-life
    ("friston-life", 0): "all_reviewer",
    # hallett-tms-primer
    ("hallett-tms-primer", 0): _hallett_table0,
    # helm-coregulation
    ("helm-coregulation", 0): _helm_table0,
    ("helm-coregulation", 1): _helm_table1,
    # huang-emd-1998
    ("huang-emd-1998", 0): "all_reviewer",
    ("huang-emd-1998", 1): "all_reviewer",
    # laird-fick-polyps
    ("laird-fick-polyps", 0): _laird_table0,
    ("laird-fick-polyps", 1): _laird_table1,
    ("laird-fick-polyps", 2): _laird_table2,
    ("laird-fick-polyps", 3): _laird_table3,
    ("laird-fick-polyps", 4): _laird_table4,
    # reyes-lf-hrv
    ("reyes-lf-hrv", 0): _reyes_table0,
    ("reyes-lf-hrv", 1): _reyes_table1,
    ("reyes-lf-hrv", 2): _reyes_table2,
    ("reyes-lf-hrv", 3): _reyes_table3,
    ("reyes-lf-hrv", 4): "all_footnotes",
    # roland-emg-filter
    ("roland-emg-filter", 0): "all_reviewer",
    ("roland-emg-filter", 1): "all_reviewer",
    ("roland-emg-filter", 2): "all_reviewer",
    ("roland-emg-filter", 3): "all_reviewer",
    ("roland-emg-filter", 4): "all_reviewer",
    ("roland-emg-filter", 5): "all_reviewer",
    ("roland-emg-filter", 6): "all_reviewer",
    ("roland-emg-filter", 7): "all_reviewer",
    ("roland-emg-filter", 8): _roland_table8,
    # yang-ppv-meta
    ("yang-ppv-meta", 0): _yang_table0,
    ("yang-ppv-meta", 1): _yang_table1,
    ("yang-ppv-meta", 2): _yang_table2,
    ("yang-ppv-meta", 3): "all_reviewer",
}


def split_notes(paper: str, table_index: int, notes: str) -> SplitResult:
    """Apply the splitting rule for (paper, table_index)."""
    key = (paper, table_index)
    rule = OVERRIDES.get(key)

    if rule is None:
        # Safety: if a file is not in the override table, keep notes as-is
        # and set footnotes to empty.
        print(f"  WARNING: no override for {key}, keeping notes as-is")
        return SplitResult(notes=notes, footnotes="")

    if rule == "all_reviewer":
        return SplitResult(notes=notes, footnotes="")

    if rule == "all_footnotes":
        return SplitResult(notes="", footnotes=notes)

    if callable(rule):
        return rule(notes)

    raise ValueError(f"Unknown rule type for {key}: {rule!r}")


def main() -> None:
    workspace = pathlib.Path(__file__).resolve().parent / "ground_truth_workspace"
    if not workspace.is_dir():
        print(f"ERROR: workspace not found at {workspace}", file=sys.stderr)
        sys.exit(1)

    gt_files = sorted(workspace.rglob("table_*_gt.json"))
    print(f"Found {len(gt_files)} GT JSON files.\n")

    stats = {
        "all_reviewer": 0,
        "all_footnotes": 0,
        "mixed_split": 0,
        "already_has_footnotes": 0,
        "empty_notes": 0,
    }

    for fp in gt_files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        paper = data["paper"]
        table_index = data["table_index"]
        original_notes = data.get("notes", "")
        rel = fp.relative_to(workspace)

        # Skip files that already have a footnotes field (idempotent)
        if "footnotes" in data:
            stats["already_has_footnotes"] += 1
            print(f"  SKIP (already has footnotes): {rel}")
            continue

        if not original_notes:
            stats["empty_notes"] += 1
            data["footnotes"] = ""
            fp.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"  EMPTY notes: {rel}")
            continue

        result = split_notes(paper, table_index, original_notes)
        data["notes"] = result.notes
        data["footnotes"] = result.footnotes

        # Write back with 2-space indent and trailing newline
        fp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # Classify for summary
        if result.footnotes == "" and result.notes == original_notes:
            category = "all_reviewer"
        elif result.notes == "" and result.footnotes == original_notes:
            category = "all_footnotes"
        else:
            category = "mixed_split"
        stats[category] += 1

        # Print per-file report
        fn_preview = (result.footnotes[:80] + "...") if len(result.footnotes) > 80 else result.footnotes
        notes_preview = (result.notes[:80] + "...") if len(result.notes) > 80 else result.notes
        if category == "all_reviewer":
            print(f"  REVIEWER ONLY: {rel}")
        elif category == "all_footnotes":
            print(f"  FOOTNOTE ONLY: {rel}")
            print(f"    footnotes = {fn_preview!r}")
        else:
            print(f"  MIXED SPLIT:   {rel}")
            print(f"    notes     = {notes_preview!r}")
            print(f"    footnotes = {fn_preview!r}")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total files processed:     {len(gt_files)}")
    print(f"  All reviewer commentary:   {stats['all_reviewer']}")
    print(f"  All paper footnotes:       {stats['all_footnotes']}")
    print(f"  Mixed (split):             {stats['mixed_split']}")
    print(f"  Empty notes:               {stats['empty_notes']}")
    print(f"  Already had footnotes:     {stats['already_has_footnotes']}")
    print("\nDone.")


if __name__ == "__main__":
    main()
