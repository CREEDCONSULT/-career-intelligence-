"""Career OS core layer (M1 vertical slice).

Deterministic career-domain state: opportunities, evidence, fit evaluation,
the application state machine, and the next-best-action engine.

Design rules for this package:
- Deterministic only. No LLM calls live here (LLM features stay in ``llm.features``).
- Unknown stays unknown: parsers never fabricate missing values.
- Every mutation records provenance.
- Stores accept an explicit ``db_path`` so tests can run against temp databases.
"""
