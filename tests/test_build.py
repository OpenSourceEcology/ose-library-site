from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlparse

from generator.build import main


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_names = {"a": "href", "link": "href", "script": "src"}
        wanted = attr_names.get(tag)
        if not wanted:
            return
        for name, value in attrs:
            if name == wanted and value:
                self.links.append(value)


def build_fixture(tmp_path: Path) -> Path:
    out = tmp_path / "site"
    code = main(["--config", "tests/fixtures/config.yaml", "--out", str(out), "--skip-freecad"])
    assert code == 0
    return out


def test_fixture_site_pages_and_badges(tmp_path: Path) -> None:
    site = build_fixture(tmp_path)
    alpha = (site / "fixture-library/part/alpha_bracket/index.html").read_text(encoding="utf-8")
    beta = (site / "fixture-library/module/beta_wall/index.html").read_text(encoding="utf-8")
    gamma = (site / "second-library/part/gamma_plate/index.html").read_text(encoding="utf-8")

    assert "code pass" in alpha
    assert "output fail" in alpha
    assert "Needs fixture review before shop use." in alpha
    assert "<td>2x4</td>" in alpha
    assert "Nested" in alpha
    assert "fastener_count" in alpha
    assert "viewer" in alpha

    assert "code report-only" in beta
    assert "output report-only" in beta
    assert "Door rough opening is intentionally omitted in fixture." in beta
    assert "mesh pending" in beta

    assert "code not yet validated" in gamma
    assert "output not yet validated" in gamma
    assert "not yet validated" in gamma


def test_index_counts_site_index_and_layout(tmp_path: Path) -> None:
    site = build_fixture(tmp_path)
    library_home = (site / "fixture-library/index.html").read_text(encoding="utf-8")
    layer_home = site / "fixture-library/part/index.html"
    entry_page = site / "fixture-library/part/alpha_bracket/index.html"
    index = json.loads((site / "site-index.json").read_text(encoding="utf-8"))

    assert layer_home.is_file()
    assert entry_page.is_file()
    assert "<strong>2</strong>" in library_home
    assert "part</a><span>1 entries" in library_home
    assert "module</a><span>1 entries" in library_home

    assert index["version"] == 1
    assert [library["name"] for library in index["libraries"]] == [
        "fixture-library",
        "second-library",
    ]
    first_entry = index["libraries"][0]["entries"][0]
    assert set(first_entry) == {"id", "title", "layer", "status", "owner", "href", "badges"}
    assert first_entry["href"] == "part/alpha_bracket/index.html"


def test_all_internal_links_resolve(tmp_path: Path) -> None:
    site = build_fixture(tmp_path)
    html_files = list(site.rglob("*.html"))
    assert html_files

    missing: list[str] = []
    for html_file in html_files:
        parser = LinkParser()
        parser.feed(html_file.read_text(encoding="utf-8"))
        for link in parser.links:
            parsed = urlparse(link)
            if parsed.scheme in {"http", "https", "mailto"} or link.startswith("#"):
                continue
            path_part = urldefrag(link)[0]
            if not path_part:
                continue
            target = (html_file.parent / path_part).resolve()
            if not target.exists():
                missing.append(f"{html_file.relative_to(site)} -> {link}")

    assert missing == []

