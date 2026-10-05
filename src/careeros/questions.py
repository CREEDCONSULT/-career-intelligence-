"""Application-question workspace (M2 §7).

Common application questions with a hard separation:

- **Factual answers** come only from the user's explicit entries or the
  career profile - never inferred. Legal / work-authorization facts are
  NEVER inferred: the question exists, but the answer is always the user's
  own confirmed text (or explicitly unanswered).
- **Narrative answers** are generated (deterministic scaffold without an API
  key; LLM polish with one), evidence-cited like every other generated asset,
  with unsupported claims excluded.

Status per question: draft -> approved. Nothing is auto-submitted anywhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb

#: Canonical question bank. ``factual`` questions draw ONLY from
#: user-confirmed profile/answers; ``narrative`` questions may be generated.
QUESTION_BANK: list[dict] = [
    {"key": "why_company", "label": "Why this company?", "kind": "narrative"},
    {"key": "why_role", "label": "Why this role?", "kind": "narrative"},
    {
        "key": "relevant_experience",
        "label": "Describe your relevant experience",
        "kind": "narrative",
    },
    {"key": "salary_expectations", "label": "Salary expectations", "kind": "factual"},
    {"key": "start_date", "label": "Earliest start date", "kind": "factual"},
    {
        "key": "work_authorization",
        "label": "Work authorization status",
        "kind": "factual",
        "never_infer": True,
    },
    {"key": "location_preferences", "label": "Location / hybrid preferences", "kind": "factual"},
]
QUESTION_KEYS = [q["key"] for q in QUESTION_BANK]
QUESTION_BY_KEY = {q["key"]: q for q in QUESTION_BANK}


@dataclass
class ApplicationQuestion:
    question_id: int
    application_id: int
    question_key: str
    factual_answer: Optional[str] = None  # user-provided only (never inferred)
    narrative_answer: Optional[str] = None  # generated, evidence-cited
    evidence_used: list[int] = field(default_factory=list)
    excluded_claims: list[str] = field(default_factory=list)
    status: str = "draft"  # draft | approved
    provenance: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return asdict(self)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS application_questions (
    question_id INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL,
    question_key VARCHAR NOT NULL,
    factual_answer VARCHAR,
    narrative_answer VARCHAR,
    evidence_used VARCHAR,
    excluded_claims VARCHAR,
    status VARCHAR,
    provenance VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""


def _row_to_question(row) -> ApplicationQuestion:
    return ApplicationQuestion(
        question_id=row[0],
        application_id=row[1],
        question_key=row[2],
        factual_answer=row[3],
        narrative_answer=row[4],
        evidence_used=json.loads(row[5] or "[]"),
        excluded_claims=json.loads(row[6] or "[]"),
        status=row[7],
        provenance=row[8],
        created_at=row[9],
        updated_at=row[10],
    )


class QuestionStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = duckdb.connect(self.db_path)
        conn.execute(_SCHEMA)
        return conn

    # -- writes -----------------------------------------------------------
    def set_factual(
        self,
        application_id: int,
        question_key: str,
        answer: str,
        provenance: str = "user:confirmed",
    ) -> ApplicationQuestion:
        """Set a FACTUAL answer. Only user-confirmed text is accepted - this
        method is deliberately the only writer for factual answers and never
        derives anything. Work-authorization answers arrive ONLY here."""
        if question_key not in QUESTION_BY_KEY:
            raise ValueError(f"unknown question: {question_key!r}")
        q = self.get(application_id, question_key)
        conn = self._connect()
        try:
            now = datetime.now().isoformat(sep=" ")
            if q is None:
                qid = conn.execute(
                    "SELECT COALESCE(MAX(question_id), 0) + 1 FROM application_questions"
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO application_questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        qid,
                        application_id,
                        question_key,
                        answer,
                        None,
                        json.dumps([]),
                        json.dumps([]),
                        "draft",
                        provenance,
                        now,
                        now,
                    ],
                )
            else:
                conn.execute(
                    "UPDATE application_questions SET factual_answer = ?, "
                    "provenance = ?, updated_at = ? WHERE question_id = ?",
                    [answer, _append_prov(q.provenance, provenance), now, q.question_id],
                )
        finally:
            conn.close()
        return self.get(application_id, question_key)  # type: ignore[return-value]

    def set_narrative(
        self,
        application_id: int,
        question_key: str,
        answer: str,
        evidence_used: Optional[list[int]] = None,
        excluded_claims: Optional[list[str]] = None,
        provenance: str = "generated:evidence-cited",
    ) -> ApplicationQuestion:
        """Set a NARRATIVE (generated) answer with its evidence traceability."""
        if question_key not in QUESTION_BY_KEY:
            raise ValueError(f"unknown question: {question_key!r}")
        if QUESTION_BY_KEY[question_key]["kind"] != "narrative":
            raise ValueError(
                f"question {question_key!r} is factual - narrative generation is not allowed for it"
            )
        q = self.get(application_id, question_key)
        conn = self._connect()
        try:
            now = datetime.now().isoformat(sep=" ")
            if q is None:
                qid = conn.execute(
                    "SELECT COALESCE(MAX(question_id), 0) + 1 FROM application_questions"
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO application_questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        qid,
                        application_id,
                        question_key,
                        None,
                        answer,
                        json.dumps(evidence_used or []),
                        json.dumps(excluded_claims or []),
                        "draft",
                        provenance,
                        now,
                        now,
                    ],
                )
            else:
                conn.execute(
                    "UPDATE application_questions SET narrative_answer = ?, "
                    "evidence_used = ?, excluded_claims = ?, provenance = ?, "
                    "updated_at = ? WHERE question_id = ?",
                    [
                        answer,
                        json.dumps(evidence_used or []),
                        json.dumps(excluded_claims or []),
                        _append_prov(q.provenance, provenance),
                        now,
                        q.question_id,
                    ],
                )
        finally:
            conn.close()
        return self.get(application_id, question_key)  # type: ignore[return-value]

    def approve(
        self, application_id: int, question_key: str, provenance: str = "user:approved"
    ) -> ApplicationQuestion:
        q = self.get(application_id, question_key)
        if q is None:
            raise ValueError("question not started")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE application_questions SET status = 'approved', provenance = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE question_id = ?",
                [_append_prov(q.provenance, provenance), q.question_id],
            )
        finally:
            conn.close()
        return self.get(application_id, question_key)  # type: ignore[return-value]

    # -- reads ------------------------------------------------------------
    def get(self, application_id: int, question_key: str) -> Optional[ApplicationQuestion]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM application_questions WHERE application_id = ? AND question_key = ?",
                [application_id, question_key],
            ).fetchone()
            return _row_to_question(row) if row else None
        finally:
            conn.close()

    def list_for_application(self, application_id: int) -> list[ApplicationQuestion]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM application_questions WHERE application_id = ? ORDER BY question_id",
                [application_id],
            ).fetchall()
            return [_row_to_question(r) for r in rows]
        finally:
            conn.close()


def _append_prov(existing: Optional[str], addition: str) -> str:
    return f"{existing} | {addition}" if existing else addition


# ---------------------------------------------------------------------------
# Narrative generation (evidence-constrained, like all generated assets)
# ---------------------------------------------------------------------------


def build_narrative_answer(
    question_key: str,
    opportunity,
    evidence,
    fit,
    gw=None,
) -> dict:
    """Generate one narrative answer. Deterministic scaffold without a key;
    evidence-cited LLM draft with one. Returns {markdown, evidence_used,
    excluded_claims, model_used}."""
    from llm.features.evidence_resume import _evidence_block  # reuse formatter

    question = QUESTION_BY_KEY.get(question_key)
    if not question or question["kind"] != "narrative":
        raise ValueError(f"not a narrative question: {question_key!r}")
    claimable = [e for e in evidence if e.claims_allowed]
    excluded = sorted({g.skill for g in fit.gaps})
    cited: set[int] = set()

    role = opportunity.role_title or "this role"
    company = opportunity.company or "the company"
    if question_key == "why_company":
        scaffold = [
            f"### Why {company}?",
            "(Deterministic scaffold - refine with the specifics only you know:)",
            "- What in the posted description genuinely matches your evidence: "
            + ", ".join(s.skill for s in fit.strengths[:3]),
            "- Which cited experiences connect to their stated needs:",
        ]
    elif question_key == "why_role":
        scaffold = [
            f"### Why {role}?",
            "- Required skills you have evidence for: "
            + ", ".join(s.skill for s in fit.strengths[:4]),
            f"- Fit assessment: {fit.band} ({fit.recommendation})",
        ]
    else:  # relevant_experience
        scaffold = [
            "### Relevant experience",
            "- Your most relevant, cited experiences for this role:",
        ]

    for ev in claimable[:5]:
        relevant = any(ev.evidence_id in s.evidence_ids for s in fit.strengths)
        if question_key == "relevant_experience" or relevant:
            cited.add(ev.evidence_id)
            scaffold.append(
                f"- [E{ev.evidence_id}] {ev.title}"
                + (f" at {ev.organization}" if ev.organization else "")
                + (f" - {ev.description}" if ev.description else "")
            )
    scaffold.append("")
    scaffold.append(
        "> Add the human specifics before submitting; unsupported "
        "keywords are excluded by design: " + (", ".join(excluded) or "none")
    )

    result = {
        "markdown": "\n".join(scaffold),
        "evidence_used": sorted(cited),
        "excluded_claims": excluded,
        "model_used": False,
    }

    if gw is not None:
        try:
            from llm.features.evidence_resume import _EVIDENCE_FOOTER

            prompt = (
                f"Answer this application question for the candidate in 120-180 words.\n\n"
                f"QUESTION: {question['label']}\n"
                f"JOB: {role} at {company}\n"
                f"JOB DESCRIPTION:\n{opportunity.description_raw or ''}\n\n"
                f"EVIDENCE LEDGER (cite IDs like [E3] for every claim):\n"
                f"{_evidence_block(claimable)}\n\n"
                "Do NOT invent experience, metrics, or company facts not in the "
                "job record. After the answer, output exactly this footer:\n"
                f"{_EVIDENCE_FOOTER}\n"
                '{"evidence_used": [<int IDs used>], "excluded_claims": '
                "[<unsupported job keywords>]}"
            )
            raw = gw.complete([{"role": "user", "content": prompt}], tier="interactive").text or ""
            if _EVIDENCE_FOOTER in raw:
                md, _, footer = raw.rpartition(_EVIDENCE_FOOTER)
                data = json.loads(footer.strip().strip("`").strip())
                valid = {e.evidence_id for e in claimable}
                used = [i for i in data.get("evidence_used", []) if i in valid]
                result = {
                    "markdown": md.strip(),
                    "evidence_used": sorted(set(used)),
                    "excluded_claims": [str(x) for x in data.get("excluded_claims", [])],
                    "model_used": True,
                }
        except Exception:  # noqa: BLE001 - generation is best-effort
            pass
    return result
