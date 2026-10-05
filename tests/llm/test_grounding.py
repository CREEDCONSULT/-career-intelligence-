import pandas as pd

from llm.grounding import grounded, numbers_in


def test_numbers_in_extracts_numerics():
    nums = numbers_in("Sales leads with 665 postings, up 12.5% from $40.00/hr")
    assert 665 in nums and 12.5 in nums and 40.0 in nums


def test_grounded_passes_when_all_numbers_present():
    df = pd.DataFrame({"skill": ["Sales"], "postings": [665]})
    ok, unguarded = grounded("Sales had 665 postings.", df)
    assert ok and unguarded == []


def test_grounded_flags_invented_number():
    df = pd.DataFrame({"skill": ["Sales"], "postings": [665]})
    ok, unguarded = grounded("Sales had 999 postings.", df)
    assert not ok and 999 in unguarded


def test_grounded_flags_transposed_number():
    df = pd.DataFrame({"skill": ["Sales"], "postings": [665]})
    ok, unguarded = grounded("Sales had 656 postings.", df)
    assert not ok and 656 in unguarded


def test_grounded_allows_simple_derived_totals():
    df = pd.DataFrame({"skill": ["A", "B"], "postings": [100, 200]})
    ok, _ = grounded("Together they total 300 postings.", df, allow_sums=True)
    assert ok


def test_grounded_tolerates_currency_and_decimal_formatting():
    df = pd.DataFrame({"wage": [40.0]})
    ok, _ = grounded("The median is $40.00 per hour.", df)
    assert ok


def test_grounded_ignores_years_via_explicit_pass_when_present():
    # year 2026 present in the data is fine
    df = pd.DataFrame({"year": [2026], "n": [5]})
    ok, unguarded = grounded("In 2026 there were 5 roles.", df)
    assert ok and unguarded == []
