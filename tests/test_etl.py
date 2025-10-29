from datetime import date

from app.etl_improved import _norm_cycle, _sum_int, _to14, _to_int, _todate


def test_to14_normalises_length():
    assert _to14("123456789") == "00000123456789"
    assert _to14("12 34 56 78 90 12 34") == "12345678901234"
    assert _to14(None) is None


def test_norm_cycle():
    assert _norm_cycle("Cycle 3") == "C3"
    assert _norm_cycle("c4") == "C4"
    assert _norm_cycle("C3") == "C3"
    assert _norm_cycle("") is None


def test_todate_parses_various_formats():
    assert _todate("2024-01-10") == date(2024, 1, 10)
    assert _todate("10/01/2024") == date(2024, 1, 10)
    assert _todate(None) is None


def test_to_int_and_sum_int():
    assert _to_int("10") == 10
    assert _to_int("10,0") == 10
    assert _to_int("not a number") is None
    assert _sum_int(["1", "2", "3"]) == 6
    assert _sum_int(["a", None]) is None
