from query_intake.date_parsing import find_date_span, resolve_date


def test_resolve_missing_date():
    result = resolve_date(None)
    assert result.status == "missing"
    assert result.normalized is None


def test_resolve_yyyymmdd_no_confirmation_needed():
    result = resolve_date("20260304")
    assert result.status == "valid_no_confirm_needed"
    assert result.normalized == "20260304"


def test_resolve_invalid_yyyymmdd_shape_rejected():
    # 8 digits but not a real calendar date (month 13, day 45)
    result = resolve_date("20261345")
    assert result.status == "invalid_needs_reprompt"
    assert result.normalized is None
    assert "YYYYMMDD" in result.message


def test_resolve_alternate_format_needs_confirmation():
    result = resolve_date("March 4, 2026")
    assert result.status == "needs_confirmation"
    assert result.normalized == "20260304"
    assert "confirm" in result.message.lower()


def test_resolve_slash_format_needs_confirmation():
    result = resolve_date("2026-03-04")
    assert result.status == "needs_confirmation"
    assert result.normalized == "20260304"


def test_resolve_unparseable_text_rejected():
    result = resolve_date("sometime last week probably")
    assert result.status == "invalid_needs_reprompt"
    assert result.normalized is None


def test_find_date_span_locates_yyyymmdd():
    assert find_date_span("it failed on 20260304 for this account") == "20260304"


def test_find_date_span_locates_month_name_form():
    assert find_date_span("it failed on March 4, 2026 for this account") == "March 4, 2026"


def test_find_date_span_returns_none_when_absent():
    assert find_date_span("phone update failed for this customer") is None
