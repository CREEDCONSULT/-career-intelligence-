from pipeline.io_utils import detect_encoding_sep


def test_detects_utf16_tab():
    raw = "﻿A\tB\tC\n1\t2\t3".encode("utf-16")
    enc, sep = detect_encoding_sep(raw)
    assert enc == "utf-16"
    assert sep == "\t"


def test_detects_utf8_comma():
    raw = "A,B,C\n1,2,3".encode("utf-8")
    enc, sep = detect_encoding_sep(raw)
    assert enc in ("utf-8", "utf-8-sig")
    assert sep == ","


def test_detects_utf8_bom():
    raw = "﻿A,B\n1,2".encode("utf-8-sig")
    enc, sep = detect_encoding_sep(raw)
    assert enc == "utf-8-sig"
    assert sep == ","
