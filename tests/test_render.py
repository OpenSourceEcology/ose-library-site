from __future__ import annotations

from pathlib import Path

from generator.build import _jinja_env
from generator.render import (
    badge_state,
    bom_rows,
    envelope_dimensions,
    entry_page_context,
    parameter_groups,
    source_components,
)


def test_badge_state_truth_table() -> None:
    passing = {"passed": True, "checks": [{"name": "ok", "passed": True}]}
    failing = {"passed": False, "checks": [{"name": "bad", "passed": False}]}

    assert badge_state(passing, "active")["state"] == "pass"
    assert badge_state(failing, "active")["state"] == "fail"
    assert badge_state(failing, "wip")["state"] == "report-only"
    assert badge_state({"passed": False, "checks": []}, "active")["state"] == "fail"
    assert badge_state({"passed": False, "checks": []}, "wip")["state"] == "report-only"
    assert badge_state(None, "active")["state"] == "not-validated"


def test_parameter_grouping_and_envelope() -> None:
    exported = {
        "schema": {
            "schema_name": "Thing",
            "document_name": "ThingDocument",
            "width_in": 10,
            "source_parts": [{"label": "Ignored inline source", "sha256": "a" * 64}],
            "nested": {"offset_in": 1.25, "fastener_count": 4},
        }
    }
    groups = parameter_groups(exported)

    assert [group["name"] for group in groups] == ["General", "Nested"]
    assert [row["key"] for row in groups[0]["rows"]] == ["width_in"]
    assert [row["key"] for row in groups[1]["rows"]] == ["offset_in", "fastener_count"]
    assert envelope_dimensions({"envelope": {"bbox_in": {"x": [0, 10], "y": 2, "z": [1, 4]}}}) == {
        "x": 10.0,
        "y": 2.0,
        "z": 3.0,
    }


def test_fixed_source_components_are_compact_and_parameter_dimensions_remain() -> None:
    parts = [
        {
            "id": f"part_{index:03d}",
            "label": f"Source component {index}",
            "solid_count": 1,
            "source_object": f"Compound/Part{index}",
            "file": f"upstream/part_{index:03d}.brp",
            "sha256": "a" * 64,
        }
        for index in range(1, 23)
    ]
    exported = {
        "schema": {
            "schema_name": "power_cube_1708",
            "document_name": "power_cube_1708",
            "units": "in",
            "source_parts": parts,
            "outer_diameter_in": 0.78,
            "inner_diameter_in": 0.5,
            "thickness_in": 0.04,
        }
    }

    components = source_components(exported)
    groups = parameter_groups(exported)
    context = entry_page_context(
        {"id": "power_cube_1708", "meta": {"geometry_mode": "fixed_source_geometry"}},
        exported,
        {"code": None, "output": None},
        {},
        {},
        {},
    )

    assert len(components) == 22
    assert components[0] == {
        "label": "Source component 1",
        "solid_count": "1",
        "source_object": "Compound/Part1",
        "file": "upstream/part_001.brp",
    }
    assert [row["key"] for row in groups[0]["rows"]] == [
        "units",
        "outer_diameter_in",
        "inner_diameter_in",
        "thickness_in",
    ]
    assert context["source_component_count"] == 22
    assert context["fixed_source_geometry"] is True
    html = _jinja_env().get_template("entry.html").render(**context)
    assert "Fixed source geometry" in html
    assert "Source components (22)" in html
    assert "outer_diameter_in" in html
    assert "a" * 64 not in html


def test_bom_csv_rows() -> None:
    path = Path("tests/fixtures/library/.site-build/slots/alpha_bracket.bom.csv")
    rows = bom_rows(path)

    assert rows[0]["count"] == "2"
    assert rows[0]["description"] == "2x4"
    assert rows[1]["material_class"] == "sheet"
