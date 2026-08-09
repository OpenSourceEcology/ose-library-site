from __future__ import annotations

import json
from pathlib import Path

from generator.workbench_bridge import split_combined_report, write_split_reports


COMBINED_REPORT = {
    "id": "mini_box",
    "layer": "module",
    "status": "active",
    "tier": "code+output",
    "checks": [
        {"name": "code:schema_data_only", "passed": True, "detail": ""},
        {"name": "code:meta_complete", "passed": True, "detail": ""},
        {"name": "output:compiles", "passed": True, "detail": ""},
        {"name": "output:completeness", "passed": False, "detail": "solids min_count shortfall"},
    ],
    "passed": False,
}


def test_split_combined_report_separates_tiers_and_strips_prefixes():
    code_report, output_report = split_combined_report(COMBINED_REPORT)

    assert [check["name"] for check in code_report["checks"]] == [
        "schema_data_only",
        "meta_complete",
    ]
    assert [check["name"] for check in output_report["checks"]] == [
        "compiles",
        "completeness",
    ]
    assert code_report["tier"] == "code"
    assert output_report["tier"] == "output"
    assert code_report["passed"] is True
    assert output_report["passed"] is False
    assert code_report["id"] == output_report["id"] == "mini_box"


def test_write_split_reports_writes_both_files(tmp_path: Path):
    code_path, output_path = write_split_reports(COMBINED_REPORT, tmp_path)

    assert code_path == tmp_path / "reports" / "code" / "mini_box.json"
    assert output_path == tmp_path / "reports" / "output" / "mini_box.json"

    code_data = json.loads(code_path.read_text(encoding="utf-8"))
    output_data = json.loads(output_path.read_text(encoding="utf-8"))
    assert code_data["passed"] is True
    assert output_data["passed"] is False
