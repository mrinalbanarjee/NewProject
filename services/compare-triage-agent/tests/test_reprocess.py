from __future__ import annotations

import pytest

from compare_triage_agent.reprocess import build_reprocess_script


def test_build_reprocess_script_includes_primary_and_selected_ids():
    script = build_reprocess_script("CORR-PRIMARY", ["CORR-DEP-1", "CORR-DEP-2"])

    assert '"CORR-PRIMARY"' in script
    assert '"CORR-DEP-1"' in script
    assert '"CORR-DEP-2"' in script
    assert "// Primary Boarding Message" in script
    assert script.count("// Selected Dependent Message") == 2


def test_build_reprocess_script_targets_the_right_collection_and_status_transition():
    script = build_reprocess_script("CORR-PRIMARY", ["CORR-DEP-1"])

    assert "db.customerevent.updateMany(" in script
    assert '"status": "FAILED"' in script
    assert '"status": "Reprocess"' in script
    assert '"reprocessRequestedBy": "AI_AGENT_DIAGNOSTIC"' in script
    assert '"retryCount": 0' in script


def test_build_reprocess_script_only_last_id_has_no_trailing_comma():
    script = build_reprocess_script("CORR-PRIMARY", ["CORR-DEP-1"])

    lines = [line.strip() for line in script.splitlines() if '"CORR-' in line]
    assert lines[0].startswith('"CORR-PRIMARY",')
    assert lines[-1].startswith('"CORR-DEP-1"') and not lines[-1].startswith('"CORR-DEP-1",')


def test_build_reprocess_script_dedupes_selected_id_that_matches_primary():
    script = build_reprocess_script("CORR-PRIMARY", ["CORR-PRIMARY", "CORR-DEP-1"])

    assert script.count('"CORR-PRIMARY"') == 1


def test_build_reprocess_script_dedupes_repeated_selected_ids():
    script = build_reprocess_script(None, ["CORR-DEP-1", "CORR-DEP-1"])

    assert script.count('"CORR-DEP-1"') == 1


def test_build_reprocess_script_works_with_no_primary():
    script = build_reprocess_script(None, ["CORR-DEP-1"])

    assert "Primary Boarding Message" not in script
    assert '"CORR-DEP-1"' in script


def test_build_reprocess_script_raises_when_nothing_selected():
    with pytest.raises(ValueError):
        build_reprocess_script(None, [])
