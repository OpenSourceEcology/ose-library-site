# OSE Library Site — Plan

A static site generator that turns any part library built on the
[Schema Canon](https://wiki.opensourceecology.org/wiki/Schema_Canon) entry
contract (reference: [vcs-library](https://github.com/OpenSourceEcology/vcs-library))
into a browsable website: every entry gets a page with its parameters, 3D
view, fabrication drawing, BOM, validation status, and ownership. The site
is regenerated from the library by CI on every change, so it can never say
something the library doesn't. First deployment: vcs-library, on GitHub
Pages from this repo.

Principles:

- Library-agnostic generator; libraries are inputs (`config.yaml` lists
  them). Nothing VCS-specific in generator code.
- Everything on a page is derived from the entry or from pipeline outputs
  (libtools reports, slots). No hand-authored per-entry content in this repo.
- Static output only — no backend, no build-time network beyond cloning the
  configured libraries.
- Visual language: follow the drafting-table vernacular of
  iconic-cad.goodancestor.com — IBM Plex Sans/Mono, paper/ink palette,
  title-block footers. The library should read like a drawer of shop
  drawings, not a SaaS landing page.

## Build pipeline (CI, FreeCAD required)

For each configured library (git url + ref):

1. Clone; `pip install` libtools; discover entries via libtools registry.
2. Run `validate-code` and `validate-output` (freecadcmd; system python —
   see vcs-library's output-validate.yml for the known CI pitfalls) —
   reports feed the badges. A failing entry still gets a page, marked
   failing; the site build itself only fails on generator errors.
3. Export meshes: in the same freecadcmd pass that compiles each entry,
   export binary STL per entry (FreeCAD Mesh; sensible tessellation
   tolerance) for the 3D viewer.
4. Run `generate-slots` — fab SVG embedded on the page, BOM CSV rendered as
   a table and downloadable.
5. `export-json` — the parameters table and machine-readable download.
6. Generate HTML: entry pages, one index per layer, a library home (title,
   owner stats, entry counts, validation summary, links to the library's
   GOVERNANCE/ONTOLOGY/CONTRIBUTING), and a site home listing configured
   libraries. Also emit `site-index.json` (all entries, for client-side
   search later).

## Entry page contents

- Header: title, id, layer badge, status (active/wip), validation badges
  (code / output: pass, fail, or report-only), owner, version.
- 3D view: three.js STLLoader (import-map CDN, same pattern iconic-cad
  uses), orbit controls, dimension readout from the entry envelope.
- Parameters: table from the exported schema JSON (grouped by nested
  sections); download links for schema.py, compiler.py, exported JSON, STL,
  FCStd is NOT hosted (large; link to CI artifacts instead is v1 — omit).
- Fabrication drawing: the generated SVG inline.
- BOM: rendered table + CSV download.
- Provenance and known_issues from meta.yaml, verbatim.
- "Contribute" box: links to the entry directory on GitHub and the
  library's CONTRIBUTING.md; entry owner named as reviewer.

## Repo layout

```
generator/            # python package: build.py, render.py, templates/, assets/
config.yaml           # libraries: [{name, git, ref, subtitle}]
tests/                # pure-logic tests + a fixture library (entry contract, fake outputs)
.github/workflows/
  build-and-deploy.yml  # FreeCAD PPA; build all libraries; deploy-pages
                        # triggers: push, workflow_dispatch, and daily cron
                        # (rebuild picks up library changes without webhooks; v1: repository_dispatch from library repos)
```

Templating: jinja2. Rendering logic that computes page data (badge state,
parameter grouping, BOM table rows, index aggregation) is pure and
unit-tested without FreeCAD; only mesh/slot/report production needs the CI
FreeCAD pass, and the generator consumes those as files, so tests feed it
fixture files.

Done when: Pages serves the site with all 12 vcs-library entries — each page
showing live badges matching the latest CI reports, a rotating 3D model,
the fab drawing, and the BOM; a second fixture library in config proves
multi-library output in tests.
