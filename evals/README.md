# Curated regression corpus

These samples are **hand-written and curated**. They are not a real-world production corpus and do not measure field precision.

Each file is labeled positive (must produce at least one finding) or negative (must stay clean). `evaluate.py` reports TP / FP / TN / FN, precision, and recall. Committed `expected.json` is the gate: CI fails if those metrics worsen.

Keep the set small. Add a pair (one positive, one negative) when you change a rule.
