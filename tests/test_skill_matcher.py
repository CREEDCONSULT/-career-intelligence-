from pipeline.skill_matcher import SkillMatcher


def test_matches_known_skills():
    m = SkillMatcher({"python": "KS1", "sql": "KS2", "power bi": "KS3"})
    found = m.extract("Senior Python Developer with SQL and Power BI")
    ids = {f["skill_id"] for f in found}
    assert {"KS1", "KS2", "KS3"} <= ids


def test_no_substring_false_positive():
    m = SkillMatcher({"r": "KS9"})  # single-letter skill must not match inside words
    assert m.extract("Strong communicator") == []


def test_case_insensitive():
    m = SkillMatcher({"java": "KS10"})
    assert m.extract("JAVA engineer")[0]["skill_id"] == "KS10"


def test_dedupes_repeated_mentions():
    m = SkillMatcher({"python": "KS1"})
    found = m.extract("python python python")
    assert len(found) == 1
