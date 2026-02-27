# Cell Normalization Analysis: ground_truth.py

## Executive Summary

The `_normalize_cell()` function in `ground_truth.py` (lines 294-317) applies **6 normalization steps** to compare vision pipeline output against ground truth. However, it **has a critical gap**: it does **NOT normalize Unicode Greek letters to LaTeX equivalents or ASCII names**.

This causes the specific failure you mentioned:
- **Vision pipeline output**: `ln(B^{π,τ})` (using Unicode Greek letters π U+03C0, τ U+03C4)
- **Ground truth**: Same visual representation in the PDF but possibly encoded differently
- **Comparison result**: MISMATCH because the GT might have LaTeX `\pi`, `\tau` or different Unicode representation

---

## Current Normalization Code (lines 294-317)

```python
def _normalize_cell(text: str) -> str:
    """Normalize a cell value for comparison.

    Steps:
    1. Strip leading/trailing whitespace
    2. Collapse internal whitespace to single space
    3. Dash/hyphen normalization (unicode minus, en-dash, em-dash, etc.)
    4. Ligature normalization
    5. LaTeX super/subscript stripping (^{...} → ..., _{...} → ...)
    6. Unicode super/subscript → ASCII
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    # Normalize all dash-like characters to ASCII hyphen
    for ch in "\u2212\u2013\u2014\u2010\u2011\ufe63\uff0d":
        text = text.replace(ch, "-")
    for lig, replacement in _LIGATURE_MAP.items():
        text = text.replace(lig, replacement)
    # Strip LaTeX super/subscript notation: x^{2} → x2, x_{i} → xi
    text = _LATEX_SUPER_RE.sub(r"\1", text)
    text = _LATEX_SUB_RE.sub(r"\1", text)
    # Unicode super/subscript characters → ASCII equivalents
    text = text.translate(_SUPER_SUB_MAP)
    return text
```

### What It Currently Handles

| Normalization | Examples | Code Location |
|---------------|----------|---|
| **Whitespace** | `"  a  b  "` → `"a b"` | Line 305-306 |
| **Dashes** | `−` (U+2212), `–` (U+2013), `—` (U+2014) → `-` | Lines 308-309 |
| **Ligatures** | `ﬀ` → `ff`, `ﬁ` → `fi` | Lines 310-311 |
| **LaTeX super/subscript** | `^{2}`, `_{i}` → stripped to content | Lines 313-314 |
| **Unicode super/subscript** | `²` → `2`, `₁` → `1` | Lines 316 (via `_SUPER_SUB_MAP`) |

---

## Missing Normalization: Greek Letters

### The Gap

The current code does **NOT** normalize:
- **Unicode Greek letters** (α, β, γ, δ, ε, θ, λ, μ, π, ρ, σ, τ, ω, etc.)
- **LaTeX Greek commands** (\alpha, \beta, \pi, \tau, etc.)

### Evidence from vision_extract.py (lines 181-186)

The vision extraction pipeline is **explicitly instructed** to use Unicode Greek letters:

```
Special characters — prefer Unicode
≤ (U+2264), ≥ (U+2265), ± (U+00B1), × (U+00D7), − (U+2212 for minus sign),
… (U+2026 for ellipsis), α (U+03B1), β (U+03B2), γ (U+03B3), δ (U+03B4),
ε (U+03B5), θ (U+03B8), λ (U+03BB), μ (U+03BC), σ (U+03C3), χ (U+03C7),
ω (U+03C9), Δ (U+0394), Σ (U+03A3), ρ (U+03C1), τ (U+03C4), π (U+03C0),
φ (U+03C6), ψ (U+03C8).
```

But the **ground truth database** may have been entered with:
- Raw Unicode from the PDF (which varies by PDF encoding)
- LaTeX notation from manual entry
- Corrupted/encoded forms due to PDF font issues
- ASCII approximations from legacy entry methods

---

## The SCPXVBLY_table_3, Row 1 Case

From the database dump, row 1 contains:
```
"MDP.P" | "Probability of emitting an action." | ...
"... inverse temperature parameter α, which by default is
extremely large (α = 512)..."
```

**What likely happened**:
1. PDF contains `α` (U+03B1, GREEK SMALL LETTER ALPHA)
2. Vision pipeline transcribes it correctly as Unicode: `α`
3. Ground truth was entered as one of:
   - LaTeX: `\alpha` or `\textit{α}`
   - Different Unicode encoding due to PDF font layer issues
   - ASCII approximation: `a` or some variant
   - Different Greek letter entirely (encoding corruption)

When `_normalize_cell()` compares them, Unicode `α` ≠ LaTeX `\alpha` because there's no conversion between them.

---

## The Exact Normalization Code Missing

### Current `_LATEX_SUPER_RE` and `_LATEX_SUB_RE` (lines 228-229)

```python
_LATEX_SUPER_RE = re.compile(r"\^{([^}]*)}")
_LATEX_SUB_RE = re.compile(r"_{([^}]*)}")
```

These handle `^{π,τ}` by extracting the content `π,τ`. But they do NOT handle LaTeX commands **inside** those braces (e.g., `^{\pi,\tau}`).

### What's Needed

**Add Greek letter normalization map** (after line 226):

```python
_GREEK_LETTER_MAP = {
    # Lowercase Greek (Unicode) → ASCII name
    "α": "alpha",      # U+03B1
    "β": "beta",       # U+03B2
    "γ": "gamma",      # U+03B3
    "δ": "delta",      # U+03B4
    "ε": "epsilon",    # U+03B5
    "ζ": "zeta",       # U+03B6
    "η": "eta",        # U+03B7
    "θ": "theta",      # U+03B8
    "ι": "iota",       # U+03B9
    "κ": "kappa",      # U+03BA
    "λ": "lambda",     # U+03BB
    "μ": "mu",         # U+03BC
    "ν": "nu",         # U+03BD
    "ξ": "xi",         # U+03BE
    "ο": "omicron",    # U+03BF
    "π": "pi",         # U+03C0
    "ρ": "rho",        # U+03C1
    "σ": "sigma",      # U+03C3
    "ς": "final_sigma",# U+03C2
    "τ": "tau",        # U+03C4
    "υ": "upsilon",    # U+03C5
    "φ": "phi",        # U+03C6
    "χ": "chi",        # U+03C7
    "ψ": "psi",        # U+03C8
    "ω": "omega",      # U+03C9

    # Uppercase Greek (Unicode)
    "Α": "Alpha",      # U+0391
    "Β": "Beta",       # U+0392
    "Γ": "Gamma",      # U+0393
    "Δ": "Delta",      # U+0394
    "Ε": "Epsilon",    # U+0395
    "Ζ": "Zeta",       # U+0396
    "Η": "Eta",        # U+0397
    "Θ": "Theta",      # U+0398
    "Ι": "Iota",       # U+0399
    "Κ": "Kappa",      # U+039A
    "Λ": "Lambda",     # U+039B
    "Μ": "Mu",         # U+039C
    "Ν": "Nu",         # U+039D
    "Ξ": "Xi",         # U+039E
    "Ο": "Omicron",    # U+039F
    "Π": "Pi",         # U+03A0
    "Ρ": "Rho",        # U+03A1
    "Σ": "Sigma",      # U+03A3
    "Τ": "Tau",        # U+03A4
    "Υ": "Upsilon",    # U+03A5
    "Φ": "Phi",        # U+03A6
    "Χ": "Chi",        # U+03A7
    "Ψ": "Psi",        # U+03A8
    "Ω": "Omega",      # U+03A9
}

_LATEX_GREEK_RE = re.compile(
    r"\\(alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|"
    r"lambda|mu|nu|xi|omicron|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega|"
    r"Alpha|Beta|Gamma|Delta|Epsilon|Zeta|Eta|Theta|Iota|Kappa|"
    r"Lambda|Mu|Nu|Xi|Omicron|Pi|Rho|Sigma|Tau|Upsilon|Phi|Chi|Psi|Omega)"
)
```

**Modify `_normalize_cell()` to add normalization** (after ligature handling, line 311):

```python
    # Normalize LaTeX Greek commands: \pi → pi, \alpha → alpha
    text = _LATEX_GREEK_RE.sub(lambda m: m.group(1).lower(), text)

    # Normalize Unicode Greek letters to ASCII names
    for greek_char, ascii_name in _GREEK_LETTER_MAP.items():
        text = text.replace(greek_char, ascii_name)
```

---

## Why This Matters: Concrete Example

### Current Behavior (INCONSISTENT)

If GT was manually entered with LaTeX and vision uses Unicode:
```
GT (from manual entry):    "ln(B^{\\pi,\\tau})"
Vision (from PDF image):   "ln(B^{π,τ})"

After _normalize_cell():
  GT:     "ln(B^{\\pi,\\tau})"    [unchanged — no LaTeX Greek handling]
  Vision: "ln(B^{π,τ})"           [unchanged — no Unicode Greek handling]

Result: MISMATCH ✗
Expected: ln(B^{pi,tau}) for both
```

### Fixed Behavior (CORRECT)

After adding Greek normalization:
```
GT (from manual entry):    "ln(B^{\\pi,\\tau})"
Vision (from PDF image):   "ln(B^{π,τ})"

After _normalize_cell() with fix:
  GT:     "ln(B^{pi,tau})"       [LaTeX \pi → pi, \tau → tau, content extracted]
  Vision: "ln(B^{pi,tau})"       [Unicode π → pi, τ → tau, content extracted]

Result: MATCH ✓
```

---

## Full Updated `_normalize_cell()` Function

```python
def _normalize_cell(text: str) -> str:
    """Normalize a cell value for comparison.

    Steps:
    1. Strip leading/trailing whitespace
    2. Collapse internal whitespace to single space
    3. Dash/hyphen normalization (unicode minus, en-dash, em-dash, etc.)
    4. Ligature normalization
    5. LaTeX Greek commands → ASCII names (\pi → pi)
    6. Unicode Greek letters → ASCII names (π → pi)
    7. LaTeX super/subscript extraction (^{...} → ..., _{...} → ...)
    8. Unicode super/subscript → ASCII
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    # Normalize all dash-like characters to ASCII hyphen
    for ch in "\u2212\u2013\u2014\u2010\u2011\ufe63\uff0d":
        text = text.replace(ch, "-")

    # Normalize ligatures
    for lig, replacement in _LIGATURE_MAP.items():
        text = text.replace(lig, replacement)

    # Normalize LaTeX Greek commands: \pi → pi, \alpha → alpha, etc.
    text = _LATEX_GREEK_RE.sub(lambda m: m.group(1).lower(), text)

    # Normalize Unicode Greek letters to ASCII names
    for greek_char, ascii_name in _GREEK_LETTER_MAP.items():
        text = text.replace(greek_char, ascii_name)

    # Strip LaTeX super/subscript notation: x^{2} → x2, x_{i} → xi
    text = _LATEX_SUPER_RE.sub(r"\1", text)
    text = _LATEX_SUB_RE.sub(r"\1", text)

    # Unicode super/subscript characters → ASCII equivalents
    text = text.translate(_SUPER_SUB_MAP)

    return text
```

---

## Impact Analysis

### Affected Table Cases

From SCPXVBLY_table_3 (continued), row 6 (MDP.P):
- Contains `α` (inverse temperature parameter)
- Currently: If GT has `\alpha`, comparison fails
- After fix: Both normalize to `alpha`, comparison succeeds

From any equation-heavy table:
- `π`, `τ`, `σ`, `μ`, `λ`, `ω` in formulas
- `β` in statistical coefficients
- `α` in significance levels (α = 0.05)

### Testing the Fix

```python
def test_normalize_cell_greek_letters():
    """Test that Greek letters normalize consistently."""
    # Unicode π should match "pi"
    assert _normalize_cell("π") == "pi"

    # LaTeX \pi should also be "pi"
    assert _normalize_cell("\\pi") == "pi"

    # In context: LaTeX \pi,\tau matches Unicode π,τ
    assert _normalize_cell("ln(B^{\\pi,\\tau})") == _normalize_cell("ln(B^{π,τ})")

    # Full table row comparison
    gt_row = ["ln(B^{\\pi,\\tau})", "α = 0.512"]
    vis_row = ["ln(B^{π,τ})", "α = 0.512"]
    assert all(_normalize_cell(g) == _normalize_cell(v) for g, v in zip(gt_row, vis_row))
```

---

## Recommendation

**Add both maps and the normalization code to `ground_truth.py`**:

1. Add `_GREEK_LETTER_MAP` dict after line 226
2. Add `_LATEX_GREEK_RE` regex after the map
3. Insert Greek normalization in `_normalize_cell()` after ligature handling (line 311)
4. Update the docstring to list the 8 normalization steps
5. Add unit tests in `tests/test_feature_extraction/test_ground_truth.py`

This is a **one-time fix** that will eliminate Greek letter encoding mismatches across all 44 ground truth tables and all future comparisons.
