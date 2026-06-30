from pipeline.salary import to_hourly, parse_salary_row


def test_annual_to_hourly():
    assert round(to_hourly(83200, "Year"), 2) == 40.0  # 83200 / 2080


def test_weekly_to_hourly():
    assert round(to_hourly(1600, "Week"), 2) == 40.0  # 1600 / 40


def test_hourly_passthrough():
    assert to_hourly(40, "Hour") == 40.0


def test_parse_row_min_max_median():
    r = parse_salary_row({"Salary Minimum": "30", "Salary Maximum": "50", "Salary Per": "Hour"})
    assert r["salary_min"] == 30.0
    assert r["salary_max"] == 50.0
    assert r["salary_median"] == 40.0


def test_parse_row_annual_normalized():
    r = parse_salary_row({"Salary Minimum": "62400", "Salary Maximum": "83200", "Salary Per": "Year"})
    assert round(r["salary_min"], 2) == 30.0
    assert round(r["salary_max"], 2) == 40.0


def test_parse_row_handles_na_and_blank():
    r = parse_salary_row({"Salary Minimum": "NA", "Salary Maximum": "", "Salary Per": "Hour"})
    assert r["salary_min"] is None
    assert r["salary_max"] is None
    assert r["salary_median"] is None
