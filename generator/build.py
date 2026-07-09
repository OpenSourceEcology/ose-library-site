from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from libtools.code_validator import validate_code
from libtools.export_json import export_entry
from libtools.registry import discover
from libtools.report import write_report

from generator import freecad_pass
from generator.render import (
    LAYER_ORDER,
    entry_page_context,
    entry_to_dict,
    library_summary,
    read_json,
    site_index,
)


ROOT = Path(__file__).resolve().parent


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--skip-freecad", action="store_true")
    args = parser.parse_args(argv)

    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    libraries = config.get("libraries") or []
    if not libraries:
        raise SystemExit("config has no libraries")

    args.out.mkdir(parents=True, exist_ok=True)
    _copy_assets(args.out)
    env = _jinja_env()
    built_libraries = []

    with tempfile.TemporaryDirectory(prefix="ose-library-site-") as tmp:
        work_root = Path(tmp)
        for library_config in libraries:
            library_root = _prepare_library(library_config, work_root)
            built = _build_library(env, library_config, library_root, args.out, args.skip_freecad)
            built_libraries.append(built)

    _write_site_home(env, args.out, built_libraries)
    (args.out / "site-index.json").write_text(
        json.dumps(site_index(built_libraries), indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


def _prepare_library(config: dict[str, Any], work_root: Path) -> Path:
    if config.get("path"):
        return Path(config["path"]).resolve()

    name = config["name"]
    dest = work_root / name
    cmd = ["git", "clone", "--depth", "1"]
    if config.get("ref"):
        cmd.extend(["--branch", str(config["ref"])])
    cmd.extend([config["git"], str(dest)])
    subprocess.run(cmd, check=True)
    return dest


def _build_library(
    env: Environment,
    config: dict[str, Any],
    library_root: Path,
    site_root: Path,
    skip_freecad: bool,
) -> dict[str, Any]:
    name = config["name"]
    library_out = site_root / name
    source_data_root = library_root / ".site-build"
    layer_rank = {layer: index for index, layer in enumerate(LAYER_ORDER)}
    entries = sorted(discover(library_root), key=lambda item: (layer_rank.get(item.layer, 99), item.id))

    library = {
        "name": name,
        "subtitle": config.get("subtitle", ""),
        "git": config.get("git", ""),
        "ref": config.get("ref", ""),
        "root": str(library_root),
    }

    with tempfile.TemporaryDirectory(prefix=f"ose-library-site-{name}-data-") as tmp:
        generated_root = Path(tmp)
        exported_dir = generated_root / "exported"
        exported_dir.mkdir(parents=True, exist_ok=True)
        if skip_freecad:
            reports_code = source_data_root / "reports" / "code"
            reports_output = source_data_root / "reports" / "output"
            slots_dir = source_data_root / "slots"
            meshes_dir = source_data_root / "meshes"
        else:
            reports_code = generated_root / "reports" / "code"
            reports_output = generated_root / "reports" / "output"
            slots_dir = generated_root / "slots"
            meshes_dir = generated_root / "meshes"

        for entry in entries:
            exported_path = exported_dir / f"{entry.id}.json"
            exported_path.write_text(
                json.dumps(export_entry(entry), indent=2) + "\n",
                encoding="utf-8",
            )
            if not skip_freecad:
                report = validate_code(entry)
                write_report(report, reports_code)
                _run_freecad(entry, library_root, meshes_dir, reports_output, slots_dir)

        if not skip_freecad and entries:
            produced = list(Path(meshes_dir).glob("*.stl"))
            if not produced:
                raise SystemExit(
                    f"{library['name']}: FreeCAD pass produced no meshes for any of "
                    f"{len(entries)} entries — refusing to publish placeholder pages. "
                    "Check the freecadcmd driver output above."
                )

        rendered_entries = []
        for entry in entries:
            rendered_entries.append(
                _render_entry(
                    env,
                    library,
                    entry,
                    library_root,
                    library_out,
                    exported_dir,
                    reports_code,
                    reports_output,
                    slots_dir,
                    meshes_dir,
                )
            )

    summary = library_summary(library, rendered_entries)
    _write_library_indexes(env, library_out, summary)
    return {**library, "entries": rendered_entries, "summary": summary}


def _run_freecad(entry: Any, root: Path, meshes_dir: Path, reports_dir: Path, slots_dir: Path) -> None:
    freecadcmd = os.environ.get("FREECADCMD", "freecadcmd")
    env = freecad_pass.driver_env(entry, root, meshes_dir, reports_dir, slots_dir)
    result = subprocess.run([freecadcmd, str(Path(freecad_pass.__file__))], env=env)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"freecad pass failed for {entry.id} with exit code {result.returncode}")


def _render_entry(
    env: Environment,
    library: dict[str, Any],
    entry: Any,
    library_root: Path,
    library_out: Path,
    exported_dir: Path,
    reports_code: Path,
    reports_output: Path,
    slots_dir: Path,
    meshes_dir: Path,
) -> dict[str, Any]:
    entry_data = entry_to_dict(entry)
    entry_dir = library_out / entry.layer / entry.id
    files_dir = entry_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    exported_source = exported_dir / f"{entry.id}.json"
    bom_source = slots_dir / f"{entry.id}.bom.csv"
    fab_source = slots_dir / f"{entry.id}.fab.svg"
    stl_source = meshes_dir / f"{entry.id}.stl"

    links = {
        "home": "../../index.html",
        "library": "../../index.html",
        "layer": "../index.html",
        "schema": _copy_file(entry.schema_path, files_dir / "schema.py"),
        "compiler": _copy_file(entry.compiler_path, files_dir / "compiler.py"),
        "json": _copy_file(exported_source, files_dir / f"{entry.id}.json"),
        "bom": _copy_file(bom_source, files_dir / f"{entry.id}.bom.csv"),
        "stl": _copy_file(stl_source, files_dir / f"{entry.id}.stl"),
        "entry_source": _source_url(library, entry_data),
        "contributing": _doc_url(library, "CONTRIBUTING.md"),
    }
    links = {key: value for key, value in links.items() if value}

    reports = {
        "code": read_json(reports_code / f"{entry.id}.json"),
        "output": read_json(reports_output / f"{entry.id}.json")
        or read_json(library_root / "reports" / f"{entry.id}.json"),
    }
    slots = {"bom_path": bom_source, "fab_path": fab_source}
    context = entry_page_context(
        entry_data,
        read_json(exported_source),
        reports,
        slots,
        links,
        library,
    )
    entry_dir.mkdir(parents=True, exist_ok=True)
    _write_template(env, "entry.html", entry_dir / "index.html", context)
    href = f"{entry.layer}/{entry.id}/index.html"
    return {**context, "href": href}


def _write_library_indexes(env: Environment, library_out: Path, summary: dict[str, Any]) -> None:
    library_out.mkdir(parents=True, exist_ok=True)
    _write_template(env, "library.html", library_out / "index.html", summary)

    for layer in summary["layers"]:
        layer_entries = [item for item in summary["entries"] if item["entry"]["layer"] == layer]
        layer_dir = library_out / layer
        layer_dir.mkdir(parents=True, exist_ok=True)
        _write_template(
            env,
            "layer.html",
            layer_dir / "index.html",
            {**summary, "layer": layer, "entries": layer_entries},
        )


def _write_site_home(env: Environment, out: Path, libraries: list[dict[str, Any]]) -> None:
    _write_template(env, "home.html", out / "index.html", {"libraries": libraries, "title": "OSE Library Site"})


def _copy_assets(out: Path) -> None:
    assets_out = out / "assets"
    assets_out.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "assets").iterdir():
        if path.is_file():
            shutil.copy2(path, assets_out / path.name)


def _copy_file(source: Path, dest: Path) -> str | None:
    if not source or not Path(source).is_file():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return f"files/{dest.name}"


def _source_url(library: dict[str, Any], entry: dict[str, Any]) -> str | None:
    git = library.get("git", "")
    if not git.startswith("http"):
        return None
    ref = library.get("ref") or "main"
    return f"{git.rstrip('/')}/tree/{ref}/library/{entry['layer']}s/{entry['id']}"


def _doc_url(library: dict[str, Any], filename: str) -> str | None:
    git = library.get("git", "")
    if not git.startswith("http"):
        return None
    ref = library.get("ref") or "main"
    return f"{git.rstrip('/')}/blob/{ref}/{filename}"


def _jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(("html", "xml")),
    )
    env.filters["value"] = lambda value: "" if value is None else str(value)
    return env


def _write_template(env: Environment, template: str, path: Path, context: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(env.get_template(template).render(**context), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
