from query_intake.extraction import extract_identifiers


def test_extracts_guid_correlation_id():
    result = extract_identifiers("issue with correlation E242431B-8B79-0982-00C4-E5F2F6E3FAD6 please help")
    assert result.correlation_id == "E242431B-8B79-0982-00C4-E5F2F6E3FAD6"


def test_no_guid_present_returns_none():
    result = extract_identifiers("phone update failed for a customer yesterday")
    assert result.correlation_id is None


def test_extracts_labeled_ecn():
    result = extract_identifiers("ECN 395769222219117 phone update did not sync")
    assert result.ecn == "395769222219117"


def test_extracts_labeled_account_number():
    result = extract_identifiers("account number 4471228 is showing the wrong phone")
    assert result.account_number == "4471228"


def test_extracts_acct_hash_shorthand():
    result = extract_identifiers("acct# ABC1234 phone sync issue")
    assert result.account_number == "ABC1234"


def test_bare_account_word_without_number_does_not_false_positive():
    result = extract_identifiers("my account settings need review")
    assert result.account_number is None


def test_bare_account_word_followed_by_prose_does_not_false_positive():
    result = extract_identifiers("the account is not working properly today")
    assert result.account_number is None


def test_extracts_raw_date_span():
    result = extract_identifiers("phone update failed on 2026-03-04 for this customer")
    assert result.raw_date_text == "2026-03-04"


def test_combined_extraction_all_present():
    text = (
        "correlationId E242431B-8B79-0982-00C4-E5F2F6E3FAD6, ECN 395769222219117, "
        "account number 4471228, happened 20260304"
    )
    result = extract_identifiers(text)
    assert result.correlation_id == "E242431B-8B79-0982-00C4-E5F2F6E3FAD6"
    assert result.ecn == "395769222219117"
    assert result.account_number == "4471228"
    assert result.raw_date_text == "20260304"
