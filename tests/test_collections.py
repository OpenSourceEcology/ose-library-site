from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from generator.build import _doc_url, _prepare_library, _source_url, main
from generator.freecad_pass import driver_env


def _collection_config(checkout: Path) -> dict[str, str]:
    return {
        "name": "gvcs-library",
        "path": str(checkout),
        "subdir": "collections/gvcs",
        "git": "https://github.com/OpenSourceEcology/vcs-library",
        "ref": "main",
        "subtitle": "GVCS fixture collection.",
        "workbench_url": "https://opensourceecology.github.io/iconic-cad/machines.html",
    }


def test_subdirectory_collection_uses_collection_root_for_build_sources_and_freecad(tmp_path: Path) -> None:
    checkout = tmp_path / "vcs-library"
    collection = checkout / "collections" / "gvcs"
    shutil.copytree("tests/fixtures/library", collection)
    config = _collection_config(checkout)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"libraries": [config]}), encoding="utf-8")
    out = tmp_path / "site"

    assert _prepare_library(config, tmp_path / "work") == collection.resolve()
    env = driver_env(
        SimpleNamespace(id="alpha_bracket"),
        collection,
        tmp_path / "meshes",
        tmp_path / "reports",
    )
    assert env["OSE_SITE_ROOT"] == str(collection.resolve())
    assert str(collection.resolve()) in env["PYTHONPATH"].split(os.pathsep)

    assert main(["--config", str(config_path), "--out", str(out), "--skip-freecad"]) == 0
    entry_page = (out / "gvcs-library" / "part" / "alpha_bracket" / "index.html").read_text(
        encoding="utf-8"
    )
    library_page = (out / "gvcs-library" / "index.html").read_text(encoding="utf-8")
    assert (
        "https://github.com/OpenSourceEcology/vcs-library/tree/main/collections/gvcs/"
        "library/parts/alpha_bracket"
    ) in entry_page
    assert "https://github.com/OpenSourceEcology/vcs-library/blob/main/CONTRIBUTING.md" in entry_page
    assert "https://opensourceecology.github.io/iconic-cad/machines.html" in entry_page
    assert "https://opensourceecology.github.io/iconic-cad/machines.html" in library_page


def test_collection_document_url_uses_collection_copy_when_present(tmp_path: Path) -> None:
    collection = tmp_path / "collections" / "gvcs"
    collection.mkdir(parents=True)
    (collection / "CONTRIBUTING.md").write_text("Collection guide", encoding="utf-8")
    library = {
        "git": "https://github.com/OpenSourceEcology/vcs-library",
        "ref": "main",
        "subdir": "collections/gvcs",
        "root": str(collection),
    }

    assert _doc_url(library, "CONTRIBUTING.md") == (
        "https://github.com/OpenSourceEcology/vcs-library/blob/main/collections/gvcs/CONTRIBUTING.md"
    )


def test_existing_collection_source_urls_remain_at_repository_root() -> None:
    entry = {"layer": "part", "id": "alpha_bracket"}
    library = {"git": "https://example.invalid/fixture-library", "ref": "main"}

    assert _source_url(library, entry) == (
        "https://example.invalid/fixture-library/tree/main/library/parts/alpha_bracket"
    )


@pytest.mark.parametrize("subdir", ["../outside", "/tmp/outside", 0])
def test_subdirectory_collection_cannot_escape_checkout(tmp_path: Path, subdir: object) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    with pytest.raises(ValueError, match="subdir"):
        _prepare_library({"name": "bad", "path": str(checkout), "subdir": subdir}, tmp_path / "work")
