# Nice-to-Have Features

Features that would be valuable but are not on the critical path. Preserved here for future consideration.

---

## ML-Based Section Detection

**Goal**: Improve section detection accuracy from ~70% to ~90% using a small classifier as fallback when rule-based detection is uncertain.

### Architecture

```python
def detect_section(text: str, heading: str) -> tuple[str, float]:
    # Try rule-based first
    rule_result, rule_conf = rule_based_detect(heading)
    if rule_conf > 0.8:
        return rule_result, rule_conf

    # Fall back to ML
    ml_result, ml_conf = ml_classifier.predict(text[:512])

    # Ensemble: prefer rule-based if confident, else ML
    if rule_conf > 0.5 and ml_conf < 0.7:
        return rule_result, rule_conf
    return ml_result, ml_conf
```

### Training Data Sources

- **PubMed Central Open Access subset** — has section labels in XML (`sec-type` attribute)
- **arXiv papers** — different structure, good for generalization
- ~1000 manually labeled examples from diverse fields

### Model Options

| Model | Size | Notes |
|-------|------|-------|
| `distilbert-base-uncased` | ~66MB | Fine-tuned on section classification |
| `all-MiniLM-L6-v2` | ~22MB | Add classification head, faster |

Ship as ONNX for cross-platform inference.

### Training Script Sketch

```python
"""scripts/train_section_classifier.py"""
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
import joblib

# Load training data (JSONL: {"text": "...", "label": "introduction"})
data = [json.loads(line) for line in open("section_training.jsonl")]

encoder = SentenceTransformer("all-MiniLM-L6-v2")
X = encoder.encode([d["text"] for d in data])
y = [d["label"] for d in data]

clf = LogisticRegression(max_iter=1000)
clf.fit(X, y)

joblib.dump(clf, "section_classifier.joblib")
```

### Integration Point

In `section_detector.py`, add ML fallback to the gap-fill step (Step 5) when rule-based detection leaves large gaps.

---

## Web UI

**Goal**: Browser-based interface for users uncomfortable with CLI.

### Why Deprioritized

- Claude Code is the UI for the target audience
- A web UI would be a separate product requiring:
  - Frontend framework (React/Vue/Svelte)
  - Backend API (FastAPI/Flask)
  - Authentication if multi-user
  - Hosting/deployment

### If Implemented

Would likely be a thin FastAPI wrapper around the existing retriever with a simple search interface.

---

## Multi-User Support

**Goal**: Shared access to a library for research teams.

### Why Out of Scope

- Requires authentication/authorization
- Concurrent access to ChromaDB
- User-specific tags/collections
- Significantly different architecture

### Alternative

Each team member runs their own instance pointing at a shared Zotero library (via Zotero sync).
