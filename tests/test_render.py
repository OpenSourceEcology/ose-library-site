from __future__ import annotations

from pathlib import Path

from generator.render import badge_state, bom_rows, envelope_dimensions, parameter_groups


def test_badge_state_truth_table() -> None:
    passing = {"passed": True, "checks": [{"name": "ok", "passed": True}]}
    failing = {"passed": False, "checks": [{"name": "bad", "passed": False}]}

    assert badge_state(passing, "active")["state"] == "pass"
    assert badge_state(failing, "active")["state"] == "fail"
    assert badge_state(failing, "wip")["state"] == "report-only"
    assert badge_state(None, "active")["state"] == "not-validated"


def test_parameter_grouping_and_envelope() -> None:
    exported = {
        "schema": {
            "schema_name": "Thing",
            "width_in": 10,
            "nested": {"offset_in": 1.25, "fastener_count": 4},
        }
    }
    groups = parameter_groups(exported)

    assert [group["name"] for group in groups] == ["General", "Nested"]
    assert [row["key"] for row in groups[1]["rows"]] == ["offset_in", "fastener_count"]
    assert envelope_dimensions({"envelope": {"bbox_in": {"x": [0, 10], "y": 2, "z": [1, 4]}}}) == {
        "x": 10.0,
        "y": 2.0,
        "z": 3.0,
    }


def test_bom_csv_rows() -> None:
    path = Path("tests/fixtures/library/.site-build/slots/alpha_bracket.bom.csv")
    rows = bom_rows(path)

    assert rows[0]["count"] == "2"
    assert rows[0]["description"] == "2x4"
    assert rows[1]["material_class"] == "sheet"

