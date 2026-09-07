from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


LAYER_ORDER = ("part", "module", "assembly", "structure")
_SCHEMA_METADATA_KEYS = frozenset({"schema_name", "document_name", "source_parts"})


def entry_to_dict(entry: Any) -> dict[str, Any]:
    if is_dataclass(entry):
        data = asdict(entry)
    elif isinstance(entry, dict):
        data = dict(entry)
    else:
        data = {
            "id": entry.id,
            "layer": entry.layer,
            "path": entry.path,
            "meta": entry.meta,
            "expect": entry.expect,
            "schema_path": entry.schema_path,
            "compiler_path": entry.compiler_path,
            "status": entry.status,
        }
    data["path"] = str(data.get("path", ""))
    data["schema_path"] = str(data.get("schema_path", ""))
    data["compiler_path"] = str(data.get("compiler_path", ""))
    return data


def read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def badge_state(report: dict[str, Any] | None, entry_status: str) -> dict[str, str]:
    if not report:
        return {
            "state": "not-validated",
            "label": "not yet validated",
            "detail": "No validation report was found.",
        }
    failed = [check for check in report.get("checks", []) if not check.get("passed")]
    if report.get("passed") is True:
        return {"state": "pass", "label": "pass", "detail": "All checks passed."}
    if report.get("passed") is not False and not failed:
        return {"state": "pass", "label": "pass", "detail": "All checks passed."}
    count = len(failed)
    detail = (
        "Validation report declares failure."
        if not count
        else f"{count} failing check(s)."
    )
    if entry_status == "wip":
        return {
            "state": "report-only",
            "label": "report-only",
            "detail": f"{detail} WIP entries do not fail the library.",
        }
    return {
        "state": "fail",
        "label": "fail",
        "detail": detail,
    }


def report_checks(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not report:
        return []
    return list(report.get("checks", []))


def parameter_groups(exported: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not exported:
        return []
    schema = exported.get("schema") or {}
    groups: list[dict[str, Any]] = []
    general_rows: list[dict[str, str]] = []

    for key, value in schema.items():
        if key in _SCHEMA_METADATA_KEYS:
            continue
        if isinstance(value, dict):
            groups.append({"name": _label(key), "rows": _flatten_mapping(value)})
        else:
            general_rows.append({"key": key, "label": _label(key), "value": format_value(value)})

    if general_rows:
        groups.insert(0, {"name": "General", "rows": general_rows})
    return [group for group in groups if group["rows"]]


def source_components(exported: dict[str, Any] | None) -> list[dict[str, str]]:
    """Return concise source-component records without exposing their hashes inline."""
    schema = (exported or {}).get("schema") or {}
    parts = schema.get("source_parts")
    if not isinstance(parts, list):
        return []

    rows = []
    for index, part in enumerate(parts, start=1):
        if not isinstance(part, dict):
            continue
        rows.append(
            {
                "label": str(part.get("label") or part.get("id") or f"Component {index}"),
                "solid_count": format_value(part.get("solid_count")) or "—",
                "source_object": str(part.get("source_object") or "—"),
                "file": str(part.get("file") or "—"),
            }
        )
    return rows


def bom_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def envelope_dimensions(expect: dict[str, Any] | None) -> dict[str, Any]:
    bbox = ((expect or {}).get("envelope") or {}).get("bbox_in") or {}
    dims: dict[str, Any] = {}
    for axis in ("x", "y", "z"):
        value = bbox.get(axis)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            dims[axis] = float(value)
        elif isinstance(value, list) and len(value) == 2:
            dims[axis] = round(float(value[1]) - float(value[0]), 4)
    return dims


def entry_page_context(
    entry: dict[str, Any],
    exported: dict[str, Any] | None,
    reports: dict[str, dict[str, Any] | None],
    slots: dict[str, Any],
    links: dict[str, str],
    library: dict[str, Any],
) -> dict[str, Any]:
    meta = entry.get("meta", {})
    expect = entry.get("expect", {})
    code_badge = badge_state(reports.get("code"), entry.get("status", meta.get("status", "")))
    output_badge = badge_state(reports.get("output"), entry.get("status", meta.get("status", "")))
    geometry_mode = str(meta.get("geometry_mode") or "")
    components = source_components(exported)
    return {
        "library": library,
        "entry": entry,
        "meta": meta,
        "expect": expect,
        "exported": exported,
        "title": meta.get("title") or entry.get("id"),
        "parameters": parameter_groups(exported),
        "source_components": components,
        "source_component_count": len(components),
        "fixed_source_geometry": geometry_mode.casefold().startswith("fixed_source"),
        "bom_rows": bom_rows(slots.get("bom_path")),
        "fab_svg": read_text(slots.get("fab_path")),
        "known_issues": meta.get("known_issues") or [],
        "provenance": meta.get("provenance") or {},
        "interface": meta.get("interface") or {},
        "dimensions": envelope_dimensions(expect),
        "badges": {
            "code": code_badge,
            "output": output_badge,
            "status": meta.get("status") or entry.get("status"),
            "layer": meta.get("layer") or entry.get("layer"),
        },
        "checks": {
            "code": report_checks(reports.get("code")),
            "output": report_checks(reports.get("output")),
        },
        "files": {
            "schema": links.get("schema"),
            "compiler": links.get("compiler"),
            "json": links.get("json"),
            "stl": links.get("stl"),
            "bom": links.get("bom"),
        },
        "mesh_available": bool(links.get("stl")),
        "links": links,
    }


def library_summary(library: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {layer: 0 for layer in LAYER_ORDER}
    owners: dict[str, int] = {}
    validation = {"pass": 0, "fail": 0, "report-only": 0, "not-validated": 0}
    for item in entries:
        layer = item["entry"].get("layer")
        counts[layer] = counts.get(layer, 0) + 1
        owner = item["entry"].get("meta", {}).get("owner") or "Unassigned"
        owners[owner] = owners.get(owner, 0) + 1
        for tier in ("code", "output"):
            state = item["badges"][tier]["state"]
            validation[state] = validation.get(state, 0) + 1
    return {
        "library": library,
        "entries": entries,
        "counts": counts,
        "owners": owners,
        "validation": validation,
        "total": len(entries),
        "layers": [layer for layer in LAYER_ORDER if counts.get(layer)],
    }


def site_index(libraries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": 1,
        "libraries": [
            {
                "name": library["name"],
                "subtitle": library.get("subtitle", ""),
                "entry_count": len(library["entries"]),
                "entries": [
                    {
                        "id": item["entry"]["id"],
                        "title": item["entry"]["meta"].get("title", item["entry"]["id"]),
                        "layer": item["entry"]["layer"],
                        "status": item["entry"].get("status"),
                        "owner": item["entry"]["meta"].get("owner"),
                        "href": item["href"],
                        "badges": {
                            "code": item["badges"]["code"]["state"],
                            "output": item["badges"]["output"]["state"],
                        },
                    }
                    for item in library["entries"]
                ],
            }
            for library in libraries
        ],
    }


def _flatten_mapping(mapping: dict[str, Any], prefix: str = "") -> list[dict[str, str]]:
    rows = []
    for key, value in mapping.items():
        row_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            rows.extend(_flatten_mapping(value, row_key))
        else:
            rows.append({"key": row_key, "label": _label(row_key), "value": format_value(value)})
    return rows


def _label(key: str) -> str:
    return key.replace("_", " ").replace(".", " / ").title()


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(format_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)
