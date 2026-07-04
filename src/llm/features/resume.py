"""Resume & cover-letter Studio: parse, review, tailor, and draft cover letters.

File parsing uses the markitdown library (deterministic, TOKEN-FREE) — PDFs and
DOCX are converted to text without any LLM call, so the model only ever sees the
extracted text. The generative actions are grounded in real market facts and are
forbidden from inventing experience the candidate doesn't have.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_PLAINTEXT_EXT = {".txt", ".md", ""}
_ANTI_FABRICATION = (
    "Do NOT invent experience, employers, dates, credentials, or skills the resume "
    "does not already contain. Only reorganize, rephrase, and emphasize what is there."
)


def extract_text(data: bytes, filename: str) -> str:
    """Extract plain text from an uploaded resume. Token-free (no LLM)."""
    ext = Path(filename).suffix.lower()
    if ext in _PLAINTEXT_EXT:
        return data.decode("utf-8", errors="replace").strip()
    from markitdown import MarkItDown
    with tempfile.NamedTemporaryFile(suffix=ext or ".bin", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        return (MarkItDown().convert(path).text_content or "").strip()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def review(resume_text: str, market_facts: str, gw) -> str:
    """Market-aware critique: strengths, gaps vs. current demand, keyword suggestions."""
    prompt = (
        "You are a Toronto career coach reviewing a resume against current market demand.\n\n"
        f"RESUME:\n{resume_text}\n\n"
        f"MARKET FACTS (from real Toronto job data — cite only these for any market claim):\n{market_facts}\n\n"
        "Give concise, specific feedback in three short sections: **Strengths**, "
        "**Gaps vs. demand** (skills employers want that the resume lacks), and "
        "**Suggested keywords** (drawn only from the market facts). Be honest and practical."
    )
    return (gw.complete([{"role": "user", "content": prompt}], tier="interactive").text or "").strip()


def tailor(resume_text: str, target_role: str, demanded_skills: list[str], gw) -> str:
    """Rewrite/reorder the resume to emphasize a target role's demanded skills."""
    skills = ", ".join(demanded_skills)
    prompt = (
        f"Tailor this resume for the target role: {target_role}.\n\n"
        f"RESUME:\n{resume_text}\n\n"
        f"This role most demands these skills (from real Toronto postings): {skills}.\n\n"
        "Rewrite the resume to surface and emphasize the candidate's genuine experience that "
        f"aligns with those skills — reorder bullets, sharpen wording, and mirror relevant "
        f"keywords where the candidate truly has the background. {_ANTI_FABRICATION}\n"
        "Return the tailored resume in clean Markdown."
    )
    return (gw.complete([{"role": "user", "content": prompt}], tier="interactive").text or "").strip()


def cover_letter(resume_text: str, target_role: str, market_facts: str, gw) -> str:
    """Draft a cover letter for a target role, grounded in honest market context."""
    prompt = (
        f"Write a concise, professional cover letter for the role: {target_role}.\n\n"
        f"CANDIDATE RESUME:\n{resume_text}\n\n"
        f"MARKET CONTEXT (real Toronto data — reference only these figures if you cite any):\n{market_facts}\n\n"
        f"Base every claim about the candidate on the resume. {_ANTI_FABRICATION} "
        "Keep it to 3-4 short paragraphs, specific and free of clichés. Return only the letter."
    )
    return (gw.complete([{"role": "user", "content": prompt}], tier="interactive").text or "").strip()
