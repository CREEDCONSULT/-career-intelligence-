from pipeline.noc_mapper import normalize_noc


def test_normalize_noc_strips_prefix_and_pads():
    assert normalize_noc("NOC_21231") == "21231"
    assert normalize_noc("2123") == "02123"
    assert normalize_noc(21231) == "21231"


def test_normalize_noc_handles_floats_and_blanks():
    assert normalize_noc("21231.0") == "21231"
    assert normalize_noc("") == ""
    assert normalize_noc(None) == ""
