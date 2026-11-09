# SUSE AI outline icon family

All 17 SVGs in this directory are original drawings created for this repository
on 2026-11-05. The editable vector source is each SVG itself. All are licensed
under [Apache-2.0](../../../../LICENSE), the repository licence; each source
also carries an SPDX identifier. No stock artwork, product logo, raster image,
font, external path data or AI Factory asset was copied or traced.

AI Factory supplied the visual direction only: a 40 × 40 tile, consistent
outline and green palette. Every asset, including the original StackPack emblem,
uses a 2-unit round stroke in `#30BA78` on a rounded `#E4F5EB` background.
The emblem is a project icon, not a replacement for SUSE's corporate logo or a
claim of brand approval. Titles and descriptions are included in every source.

| Source (Apache-2.0) | Menu entry / role |
| --- | --- |
| [overview.svg](overview.svg) | Overview |
| [application.svg](application.svg) | Applications; Applications & agents |
| [agent.svg](agent.svg) | Agents |
| [gateway.svg](gateway.svg) | Gateways; model proxy |
| [tool.svg](tool.svg) | Tools; MCP server |
| [inference-server.svg](inference-server.svg) | Inference servers; Inference |
| [model.svg](model.svg) | Models; served model |
| [model-usage.svg](model-usage.svg) | Model usage |
| [data-services.svg](data-services.svg) | Data services |
| [gpu.svg](gpu.svg) | GPUs; GPU infrastructure; physical accelerator |
| [observed-dependencies.svg](observed-dependencies.svg) | Observed dependencies |
| [vector-database.svg](vector-database.svg) | Vector database |
| [search-engine.svg](search-engine.svg) | Search engine |
| [registry.svg](registry.svg) | Model registry |
| [workflow.svg](workflow.svg) | Workflow engine |
| [ui.svg](ui.svg) | AI interface |
| [stackpack-logo.svg](stackpack-logo.svg) | SUSE AI menu group and StackPack logo |

Presentation integration uses `!icon outline/<name>.svg`. The deploying lane
owns that wiring and the manifest's logo reference. These new sources do not
change existing presentation definitions, ComponentType `iconbase64` fields or
the provenance/licence of legacy assets in other directories. The server, cube
and chip motifs continue this repository's original spike sketches, redrawn
here on the same grid; no external asset dependency is required.
