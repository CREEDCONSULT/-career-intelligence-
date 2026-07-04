from llm.features.resume import cover_letter, extract_text, review, tailor
from llm.gateway import Response


class FakeGW:
    def __init__(self, text="OUTPUT"):
        self.text = text
        self.prompts = []

    def complete(self, messages, tier="interactive", cache_prefix=None):
        self.prompts.append(messages[-1]["content"])
        return Response(text=self.text, tokens=1)


def test_extract_text_plaintext_is_token_free():
    # .txt path decodes directly (no markitdown, no LLM)
    assert extract_text(b"Line cook, 5 years, food safety.", "resume.txt") == "Line cook, 5 years, food safety."


def test_extract_text_handles_docx(tmp_path):
    import pytest
    docx = pytest.importorskip("docx")
    d = docx.Document()
    d.add_paragraph("Jane Doe — Registered Nurse, patient care and clinical assessment.")
    p = tmp_path / "r.docx"
    d.save(str(p))
    text = extract_text(p.read_bytes(), "r.docx")
    assert "Registered Nurse" in text
    assert "patient care" in text


def test_review_uses_market_facts_and_forbids_fabrication():
    gw = FakeGW("Your resume is strong in X.")
    out = review("my resume text", "Top demanded skills: Python, SQL", gw)
    assert out == "Your resume is strong in X."
    prompt = gw.prompts[-1]
    assert "my resume text" in prompt
    assert "Python, SQL" in prompt


def test_tailor_prompt_bans_inventing_experience():
    gw = FakeGW("TAILORED RESUME")
    out = tailor("resume text", "Data scientists", ["Python", "Machine Learning"], gw)
    assert out == "TAILORED RESUME"
    p = gw.prompts[-1].lower()
    assert "data scientists" in p
    assert "python" in p
    assert "not" in p and ("invent" in p or "fabricat" in p)


def test_cover_letter_includes_role_and_market_context():
    gw = FakeGW("Dear Hiring Manager...")
    out = cover_letter("resume text", "Cooks", "median wage $18/hr; 3000 postings", gw)
    assert out.startswith("Dear")
    p = gw.prompts[-1]
    assert "Cooks" in p and "3000 postings" in p
