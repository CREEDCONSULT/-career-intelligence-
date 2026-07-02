from llm.usage import DailyUsage


def test_accumulates_within_day(tmp_path):
    u = DailyUsage(tmp_path / "usage.json", today_fn=lambda: "2026-07-02")
    assert u.today() == 0
    u.add(100)
    u.add(50)
    assert u.today() == 150


def test_persists_across_instances(tmp_path):
    p = tmp_path / "usage.json"
    DailyUsage(p, today_fn=lambda: "2026-07-02").add(75)
    assert DailyUsage(p, today_fn=lambda: "2026-07-02").today() == 75


def test_resets_on_new_day(tmp_path):
    p = tmp_path / "usage.json"
    DailyUsage(p, today_fn=lambda: "2026-07-02").add(500)
    u2 = DailyUsage(p, today_fn=lambda: "2026-07-03")
    assert u2.today() == 0
    u2.add(10)
    assert u2.today() == 10


def test_survives_corrupt_file(tmp_path):
    p = tmp_path / "usage.json"
    p.write_text("{not json", encoding="utf-8")
    u = DailyUsage(p, today_fn=lambda: "2026-07-02")
    assert u.today() == 0
