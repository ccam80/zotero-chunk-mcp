# Cell Normalization Gap Analysis: ground_truth.py

## Executive Summary

The `_normalize_cell()` function in `ground_truth.py` (lines 294-317) applies 6
normalization steps when comparing extraction output against ground truth. Three
gaps cause false mismatches:

1. **Smart/curly quotes** — GT or vision may use `'` `'` `"` `"` vs ASCII `'` `"`
2. **Greek letters** — vision outputs Unicode (π, τ, α), GT may have LaTeX (`\pi`)
3. **Uppercase Greek/Latin collision** — some Greek capitals are visually identical
   to Latin letters and must NOT be normalized

Additionally, the vision viewer (`tools/vision_viewer.py`) mirrors this normalizer
and must be kept in sync.

---

## Current Normalization (6 steps)

```python
def _normalize_cell(text: str) -> str:
    text = text.strip()                              # 1. strip
    text = re.sub(r"\s+", " ", text)                 # 2. whitespace collapse (\n → space)
    for ch in "\u2212\u2013\u2014\u2010\u2011...":   # 3. dash unification
        text = text.replace(ch, "-")
    for lig, repl in _LIGATURE_MAP.items():           # 4. ligature expansion
        text = text.replace(lig, repl)
    text = _LATEX_SUPER_RE.sub(r"\1", text)           # 5. LaTeX super/sub extraction
    text = _LATEX_SUB_RE.sub(r"\1", text)
    text = text.translate(_SUPER_SUB_MAP)             # 6. Unicode super/sub → ASCII
    return text
```

**What already works**: whitespace (including `\n`), dashes (U+2212 etc.), ligatures,
LaTeX `^{...}`/`_{...}`, Unicode superscripts/subscripts.

---

## Gap 1: Smart/Curly Quotes

### Evidence

SCPXVBLY_table_3 row 3, col 1 — every agent outputs:
```
MDP.Fa is the negative free energy of parameter 'a' (if learning A matrix)
```
GT has:
```
MDP.Fa is the negative free energy of parameter \u2018a\u2019 (if learning A matrix)
```

- GT: `'` (U+2018 LEFT SINGLE QUOTATION MARK) and `'` (U+2019 RIGHT SINGLE)
- Vision: `'` (U+0027 APOSTROPHE)

The existing normalizer does not handle this. The `\s+` regex handles newlines
but there is no quote unification.

### Fix

Add after the dash normalization (line 309):

```python
# Normalize smart/curly quotes to ASCII
for ch in "\u2018\u2019\u201a\u0060":  # ' ' ‚ `
    text = text.replace(ch, "'")
for ch in "\u201c\u201d\u201e":         # " " „
    text = text.replace(ch, '"')
```

---

## Gap 2: Greek Letters

### Evidence

The vision pipeline is explicitly instructed (vision_extract.py lines 181-186) to
output Unicode Greek: `α β γ δ ε θ λ μ σ χ ω Δ Σ ρ τ π φ ψ`. GT may have been
entered with LaTeX commands (`\pi`, `\alpha`) or with different Unicode encodings
from PDF font mapping.

No specific mismatch was found in the current 10-paper corpus (SCPXVBLY_table_3's
mismatches are newline and smart-quote, not Greek). However, equation-heavy tables
in future papers will hit this: statistical tables with `α = 0.05`, physics tables
with `ω`, `σ`, `μ`, etc.

### Fix — Lowercase Greek Only

Add a map for **lowercase Greek only**. Uppercase Greek letters that are visually
identical to Latin must be excluded to avoid corrupting normal text.

```python
_GREEK_LETTER_MAP = {
    # Lowercase — all visually distinct from Latin
    "α": "alpha", "β": "beta",   "γ": "gamma",   "δ": "delta",
    "ε": "epsilon", "ζ": "zeta", "η": "eta",     "θ": "theta",
    "ι": "iota",  "κ": "kappa",  "λ": "lambda",  "μ": "mu",
    "ν": "nu",    "ξ": "xi",     "π": "pi",       "ρ": "rho",
    "σ": "sigma", "ς": "sigma",  "τ": "tau",      "υ": "upsilon",
    "φ": "phi",   "χ": "chi",    "ψ": "psi",      "ω": "omega",
    # Uppercase — ONLY visually distinct from Latin
    # EXCLUDED (identical to Latin): Α/A, Β/B, Ε/E, Ζ/Z, Η/H, Ι/I,
    #   Κ/K, Μ/M, Ν/N, Ο/O, Ρ/P, Τ/T, Χ/X
    "Γ": "Gamma", "Δ": "Delta",  "Θ": "Theta",   "Λ": "Lambda",
    "Ξ": "Xi",    "Π": "Pi",     "Σ": "Sigma",    "Φ": "Phi",
    "Ψ": "Psi",   "Ω": "Omega",
}

_LATEX_GREEK_RE = re.compile(
    r"\\(alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|"
    r"lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega|"
    r"Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Phi|Psi|Omega)"
)
```

**Why exclude uppercase Greek/Latin homoglyphs**: `Α` (U+0391 Greek Capital Alpha)
is visually identical to `A` (U+0041 Latin Capital A). If we mapped `Α` → `Alpha`,
any cell containing a regular "A" that happens to be encoded as Greek Alpha (common
in PDFs with Symbol fonts) would be silently corrupted. The risk is not theoretical
— PDF font encoding frequently maps Latin characters through Greek code points.

Add to `_normalize_cell()` after ligature handling:

```python
    # Normalize LaTeX Greek commands: \pi → pi, \alpha → alpha
    text = _LATEX_GREEK_RE.sub(lambda m: m.group(1).lower(), text)
    # Normalize Unicode Greek letters to ASCII names
    for greek_char, ascii_name in _GREEK_LETTER_MAP.items():
        text = text.replace(greek_char, ascii_name.lower())
```

---

## Gap 3 (not in current normalizer, but relevant): Newline-as-separator

### Non-issue for accuracy

The `\s+` → single space normalization already handles GT newlines vs vision spaces.
SCPXVBLY_table_3 col 2 has `\n` in GT ("Rows = policies.\nColumns = time points.")
that normalizes to match the vision's space-separated version.

However, the **y_verifier's slash insertion** on row 3 col 0 (`MDP.Fa\nMDP.Fd` →
`MDP.Fa / MDP.Fd / MDP.Fb / ...`) is a real content change (adding ` / ` characters),
not a normalization issue. This correctly registers as a diff.

---

## Updated `_normalize_cell()` — Full Function

```python
def _normalize_cell(text: str) -> str:
    """Normalize a cell value for comparison.

    Steps:
    1. Strip leading/trailing whitespace
    2. Collapse internal whitespace to single space
    3. Dash/hyphen normalization (unicode minus, en-dash, em-dash, etc.)
    4. Smart/curly quote normalization
    5. Ligature normalization
    6. LaTeX Greek commands → ASCII names (\\pi → pi)
    7. Unicode Greek letters → ASCII names (π → pi)
    8. LaTeX super/subscript extraction (^{...} → ..., _{...} → ...)
    9. Unicode super/subscript → ASCII
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    # Dashes
    for ch in "\u2212\u2013\u2014\u2010\u2011\ufe63\uff0d":
        text = text.replace(ch, "-")
    # Smart quotes
    for ch in "\u2018\u2019\u201a\u0060":
        text = text.replace(ch, "'")
    for ch in "\u201c\u201d\u201e":
        text = text.replace(ch, '"')
    # Ligatures
    for lig, replacement in _LIGATURE_MAP.items():
        text = text.replace(lig, replacement)
    # LaTeX Greek → ASCII name
    text = _LATEX_GREEK_RE.sub(lambda m: m.group(1).lower(), text)
    # Unicode Greek → ASCII name
    for greek_char, ascii_name in _GREEK_LETTER_MAP.items():
        text = text.replace(greek_char, ascii_name.lower())
    # LaTeX super/subscript
    text = _LATEX_SUPER_RE.sub(r"\1", text)
    text = _LATEX_SUB_RE.sub(r"\1", text)
    # Unicode super/subscript
    text = text.translate(_SUPER_SUB_MAP)
    return text
```

---

## Implementation Checklist

### In `ground_truth.py`

1. Add `_GREEK_LETTER_MAP` dict after line 226 (after `_SUPER_SUB_MAP`)
2. Add `_LATEX_GREEK_RE` regex after the map
3. Add smart quote normalization to `_normalize_cell()` after dash handling (line 309)
4. Add Greek normalization to `_normalize_cell()` after ligature handling (line 311)
5. Update the docstring to list all 9 normalization steps

### In `tools/vision_viewer.py`

6. Add `_GREEK_LETTER_MAP` and `_LATEX_GREEK_RE` to the viewer's local copy
7. Add smart quote normalization to the viewer's `_normalize_cell()`
8. Add Greek normalization to the viewer's `_normalize_cell()`

### Tests

9. Add to `tests/test_feature_extraction/test_ground_truth.py`:

```python
def test_normalize_cell_smart_quotes():
    assert _normalize_cell("\u2018a\u2019") == _normalize_cell("'a'")
    assert _normalize_cell("\u201chi\u201d") == _normalize_cell('"hi"')

def test_normalize_cell_greek_lowercase():
    assert _normalize_cell("π") == "pi"
    assert _normalize_cell("\\pi") == "pi"
    assert _normalize_cell("α = 0.05") == "alpha = 0.05"
    assert _normalize_cell("\\alpha = 0.05") == "alpha = 0.05"

def test_normalize_cell_greek_uppercase_safe():
    # Visually distinct uppercase should normalize
    assert _normalize_cell("Δ") == "delta"
    assert _normalize_cell("Σ") == "sigma"
    # Latin-identical uppercase should NOT be normalized
    # (these are Latin A, B, E — not Greek Alpha, Beta, Epsilon)
    assert _normalize_cell("A") == "A"
    assert _normalize_cell("B") == "B"
    assert _normalize_cell("E") == "E"

def test_normalize_cell_greek_in_context():
    gt = "ln(B^{\\pi,\\tau})"
    vis = "ln(B^{π,τ})"
    assert _normalize_cell(gt) == _normalize_cell(vis)
```

---

## What This Does NOT Affect

- **Semantic search / indexing**: Normalization is test-time only, not part of the
  ChromaDB indexing pipeline. Embeddings handle encoding variants naturally.
- **Vision pipeline output**: Agents are instructed to use Unicode Greek. This does
  not change that. The normalization only affects accuracy *measurement*.
- **Existing passing tests**: All existing normalization (dashes, ligatures, super/sub)
  is preserved. New steps are additive.
