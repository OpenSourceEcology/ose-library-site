"""End-to-end slice: an entry authored in ose-library-workbench format is
validated headlessly (no FreeCAD) via the workbench's own core module, and
the resulting report is fed into this repo's site builder to render a real
entry page — proving the author -> validate -> publish pipeline shape the
two repos were designed around.

Skipped when the workbench repo isn't checked out as a sibling of this repo
(the normal local dev layout, not assumed in CI for this repo).
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from generator.build import main as build_main
from generator.workbench_bridge import write_split_reports


WORKBENCH_ROOT = Path(__file__).resolve().parents[2] / "ose-library-workbench"
WORKBENCH_FIXTURE = WORKBENCH_ROOT / "tests" / "fixtures" / "min_library"

pytestmark = pytest.mark.skipif(
    not WORKBENCH_FIXTURE.is_dir(),
    reason="ose-library-workbench sibling checkout not found",
)


class DummyDoc:
    """Mirrors ose-library-workbench/tests/test_core.py's DummyDoc — a
    FreeCAD-free stand-in for a compiled document."""

    def __init__(self):
        self.Objects = []

    def addObject(self, type_name, label):
        obj = DummyObject(type_name, label)
        self.Objects.append(obj)
        return obj


class DummyObject:
    def __init__(self, type_name, label):
        self.Type = type_name
        self.Label = label


@pytest.fixture()
def workbench_core():
    workbench_str = str(WORKBENCH_ROOT)
    inserted = workbench_str not in sys.path
    if inserted:
        sys.path.insert(0, workbench_str)
    try:
        from ose_library_wb import core  # noqa: PLC0415

        yield core
    finally:
        if inserted:
            sys.path.remove(workbench_str)
        sys.modules.pop("ose_library_wb.core", None)
        sys.modules.pop("ose_library_wb", None)


def test_workbench_authored_entry_flows_to_a_published_page(tmp_path, workbench_core):
    # 1. Author: use the workbench's own fixture entry (Schema Canon layout:
    #    schema.py/compiler.py/meta.yaml/expect.yaml under library/<layer>s/<id>/).
    library_root = tmp_path / "authored-library"
    shutil.copytree(WORKBENCH_FIXTURE, library_root)

    entry = workbench_core.open_library(library_root)[0]
    assert entry.id == "mini_box"

    # 2. Compile + validate: headless, exactly as a workbench user's "Compile
    #    Entry" + "Validate Entry" commands would (DummyDoc stands in for a
    #    real FreeCAD document — no freecadcmd available here).
    doc = DummyDoc()
    workbench_core.compile_entry_into(entry, doc)
    report = workbench_core.validate_live(entry, doc)
    assert report.tier == "code+output"

    # 3. Bridge: adapt the workbench's combined report into this generator's
    #    --skip-freecad data-root convention (reports/code/, reports/output/).
    site_build_root = library_root / ".site-build"
    write_split_reports(asdict(report), site_build_root)

    # 4. Publish: run the real site generator against the authored+validated
    #    library, skipping the FreeCAD mesh/slot pass (not available here).
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "libraries": [
                    {
                        "name": "workbench-demo",
                        "path": str(library_root),
                        "git": "https://example.invalid/workbench-demo",
                        "ref": "main",
                        "subtitle": "Authored via ose-library-workbench, no FreeCAD.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "site"
    code = build_main(["--config", str(config_path), "--out", str(out_dir), "--skip-freecad"])
    assert code == 0

    entry_page = out_dir / "workbench-demo" / "module" / "mini_box" / "index.html"
    assert entry_page.is_file()
    html = entry_page.read_text(encoding="utf-8")

    assert "Mini Box" in html
    assert "width_in" in html
    # Code tier passed (schema is well-formed); output tier failed (no real
    # FreeCAD shapes exist under a DummyDoc, so the completeness check
    # against expect.yaml's solids.min_count fails) — both badges should
    # reflect that split accurately, not fall back to "not yet validated".
    assert "code pass" in html
    assert "output fail" in html

    library_home = (out_dir / "workbench-demo" / "index.html").read_text(encoding="utf-8")
    assert "mini_box" in library_home or "Mini Box" in library_home
