from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import traceback
from pathlib import Path
from types import ModuleType


_PACKAGE_PARENT = str(Path(__file__).resolve().parent.parent)
if _PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, _PACKAGE_PARENT)

# freecadcmd ignores PYTHONPATH, so the parent process passes the libtools
# install location explicitly and it is bootstrapped here before import.
_LIBTOOLS_PATH = os.environ.get("OSE_SITE_LIBTOOLS_PATH")
if _LIBTOOLS_PATH and _LIBTOOLS_PATH not in sys.path:
    sys.path.insert(0, _LIBTOOLS_PATH)

from libtools import compile_entry
from libtools.output_validator import failure_report, validate_output
from libtools.registry import Entry, discover, load_schema
from libtools.report import write_report


_HOSTILE_ENV_VARS = (
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "pythonLocation",
    "Python_ROOT_DIR",
    "Python2_ROOT_DIR",
    "Python3_ROOT_DIR",
    "LD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
    "VIRTUAL_ENV",
)


def driver_env(
    entry: Entry,
    root: Path,
    out_dir: Path,
    reports_dir: Path,
    slots_dir: Path | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    for name in _HOSTILE_ENV_VARS:
        env.pop(name, None)

    package_parent = Path(compile_entry.__file__).resolve().parent.parent
    site_parent = Path(__file__).resolve().parent.parent
    # ``root`` is the configured collection root, which may be a subdirectory
    # of a shared repository checkout. Put it on both FreeCAD's bootstrap path
    # and the driver environment so collection-local compiler helpers import.
    collection_root = Path(root).resolve()
    pythonpath_parts = [str(package_parent), str(site_parent), str(collection_root)]
    env.update(
        {
            "OSE_SITE_LIBTOOLS_PATH": str(package_parent),
            "OSE_SITE_ROOT": str(collection_root),
            "OSE_SITE_ENTRY": entry.id,
            "OSE_SITE_OUT": str(out_dir),
            "OSE_SITE_REPORTS": str(reports_dir),
            "PYTHONPATH": os.pathsep.join(dict.fromkeys(pythonpath_parts)),
        }
    )
    if slots_dir is not None:
        env["OSE_SITE_SLOTS"] = str(slots_dir)
    return env


def run(root: str, entry_id: str, out_dir: str, reports_dir: str, slots_dir: str | None) -> int:
    entry: Entry | None = None
    try:
        root_path = Path(root)
        root_resolved = str(root_path.resolve())
        if root_resolved not in sys.path:
            sys.path.insert(0, root_resolved)

        entries = discover(root_path)
        entry = {candidate.id: candidate for candidate in entries}[entry_id]
        schema = load_schema(entry)
        compiler = _load_compiler(entry.compiler_path)

        import FreeCAD as App
        import Mesh

        doc = App.newDocument(schema["document_name"])
        compiler.compile(schema, doc)
        doc.recompute()

        shapes, common_volume_fn = compile_entry.extract_shapes(doc)
        report = validate_output(entry, shapes, common_volume_fn)
        write_report(report, Path(reports_dir))

        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        mesh_objects = [obj for obj in doc.Objects if getattr(obj, "Shape", None) is not None]
        if mesh_objects:
            Mesh.export(mesh_objects, str(out_path / f"{entry.id}.stl"))

        if slots_dir and report.passed:
            from libtools.bom import write_bom_csv
            from libtools.fab_drawing import write_fab_drawing

            slots_path = Path(slots_dir)
            slots_path.mkdir(parents=True, exist_ok=True)
            write_bom_csv(shapes, slots_path / f"{entry.id}.bom.csv")
            write_fab_drawing(entry, shapes, doc, slots_path / f"{entry.id}.fab.svg")

        return 0 if report.passed or entry.status == "wip" else 1
    except Exception:
        detail = traceback.format_exc()
        report_key: Entry | tuple[str, str, str]
        report_key = entry if entry is not None else (entry_id, "unknown", "active")
        write_report(failure_report(report_key, detail), Path(reports_dir))
        status = entry.status if entry is not None else "active"
        return 0 if status == "wip" else 1


def _load_compiler(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_ose_site_compiler_{path.parent.name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load compiler from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    return run(
        os.environ["OSE_SITE_ROOT"],
        os.environ["OSE_SITE_ENTRY"],
        os.environ["OSE_SITE_OUT"],
        os.environ["OSE_SITE_REPORTS"],
        os.environ.get("OSE_SITE_SLOTS"),
    )


if __name__ != "generator.freecad_pass" and os.environ.get("OSE_SITE_ENTRY"):
    sys.exit(main())
elif __name__ == "__main__":
    sys.exit(main())
