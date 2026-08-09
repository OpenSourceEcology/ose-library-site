"""Adapter between the ose-library-workbench's headless validation output and
this generator's ``--skip-freecad`` data-root convention.

The workbench's ``core.validate_live`` runs both validation tiers in one pass
and writes a single combined report (``tier="code+output"``, checks prefixed
``code:``/``output:``) to ``<library>/reports/<entry-id>.json``. The
generator's normal (non-FreeCAD-skipping) build instead produces two reports
per entry under ``<data-root>/reports/code/`` and ``.../reports/output/``.

This module bridges the two: it splits a combined workbench report back into
the per-tier shape ``render.badge_state``/``render.report_checks`` expect, so
a library validated entirely through the workbench (no FreeCAD available)
can still be built into a site with accurate code/output badges, instead of
falling back to a single "not yet validated" state for both tiers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CODE_PREFIX = "code:"
_OUTPUT_PREFIX = "output:"


def split_combined_report(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a combined ``code+output`` report dict into ``(code, output)`` report dicts.

    Checks without a recognized ``code:``/``output:`` prefix are included in
    both tiers (conservative: a check with no home tier is not skipped).
    """

    code_checks: list[dict[str, Any]] = []
    output_checks: list[dict[str, Any]] = []

    for check in report.get("checks", []):
        name = check.get("name", "")
        if name.startswith(_CODE_PREFIX):
            code_checks.append({**check, "name": name[len(_CODE_PREFIX):]})
        elif name.startswith(_OUTPUT_PREFIX):
            output_checks.append({**check, "name": name[len(_OUTPUT_PREFIX):]})
        else:
            code_checks.append(check)
            output_checks.append(check)

    base = {"id": report["id"], "layer": report["layer"], "status": report["status"]}
    code_report = {
        **base,
        "tier": "code",
        "checks": code_checks,
        "passed": all(check["passed"] for check in code_checks) if code_checks else True,
    }
    output_report = {
        **base,
        "tier": "output",
        "checks": output_checks,
        "passed": all(check["passed"] for check in output_checks) if output_checks else True,
    }
    return code_report, output_report


def write_split_reports(report: dict[str, Any], site_build_root: Path) -> tuple[Path, Path]:
    """Split a combined report and write it into ``<site_build_root>/reports/{code,output}/``.

    ``site_build_root`` is a library's ``.site-build`` directory (or any root
    a ``--skip-freecad`` build is pointed at).
    """

    code_report, output_report = split_combined_report(report)
    code_dir = Path(site_build_root) / "reports" / "code"
    output_dir = Path(site_build_root) / "reports" / "output"
    code_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    code_path = code_dir / f"{report['id']}.json"
    output_path = output_dir / f"{report['id']}.json"
    code_path.write_text(json.dumps(code_report, indent=2) + "\n", encoding="utf-8")
    output_path.write_text(json.dumps(output_report, indent=2) + "\n", encoding="utf-8")
    return code_path, output_path
