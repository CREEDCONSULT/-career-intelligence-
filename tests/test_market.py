from pipeline.market import Market, load_market


def test_default_market_is_toronto():
    m = load_market()
    assert m.name == "Toronto"
    assert "toronto" in m.jobbank_cities
    assert "3530" in m.economic_region_codes
    assert m.indeed_metro == "Toronto, ON"
    assert m.statscan_geo_contains == "Toronto"


def test_market_loads_from_custom_yaml(tmp_path, monkeypatch):
    p = tmp_path / "vancouver.yaml"
    p.write_text(
        "name: Vancouver\ntagline: Vancouver, decoded.\n"
        "jobbank_cities: [vancouver, burnaby, richmond]\n"
        "economic_region_name: Lower Mainland--Southwest\n"
        "economic_region_codes: ['5920', 'ER5920']\n"
        "statscan_geo_contains: Vancouver\n"
        "indeed_metro: 'Vancouver, BC'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_CONFIG", str(p))
    load_market.cache_clear()
    m = load_market()
    assert m.name == "Vancouver"
    assert "burnaby" in m.jobbank_cities
    monkeypatch.delenv("MARKET_CONFIG")
    load_market.cache_clear()


def test_market_is_dataclass_with_all_fields():
    m = load_market()
    assert isinstance(m, Market)
    for field in ("name", "tagline", "jobbank_cities", "economic_region_name",
                  "economic_region_codes", "statscan_geo_contains", "indeed_metro"):
        assert getattr(m, field)
