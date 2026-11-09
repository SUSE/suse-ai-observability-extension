# Design - SUSE AI StackPack 3.0 component model and visual identity

Status: proposed (2026-11-05). Target: StackPack 3.0.0, regenerated. Breaking changes are allowed
because the 3.x Helm chart has not been published. Release rule: GitHub tags may be regenerated until
the Helm chart that references them is published.

Ollama spike results: [S1–S5 report](SPIKE_V3_COMPONENT_MODEL.md). S1 supports D1 with unique highlight IDs; presentations compose field by field, so the single-presentation description below is superseded by the observed merge table. S2 is blocked on the tested native mapping schema. The full redesign remains proposed.

## Problems in 3.0.x

1. **We take over the OpenTelemetry presentation.** Our mappings write into
   `urn:opentelemetry:namespace/<ns>:service/<svc>` (type `otel service`) and 13 presentations bind
   those components at specificity 200-241 with their own icon, name and overview. The platform picks
   one presentation per component, so the Open Telemetry StackPack's own pages change.
2. **The topology has no structure.** One domain and one layer; AI components mix with everything else.
3. **The visual identity is inconsistent.** Five role icons are the same stock-style PNG of unknown
   licence; "inference engine" is the Ollama logo and "vector database" the Milvus logo; three products
   share one placeholder; viewBoxes range from 32 to 646x854; PNG and SVG are mixed.
4. **The install page undersells the StackPack.** `overview.md` has 20 words; `detailed-overview.md` is
   mostly caveats; `configuration.md` starts with attribute rules.
5. **Monitors are generic** and lack operator-oriented remediation.

## Reference designs

Evidence: `~/suse/qa/aif-inspiration/FINDINGS.md` (read-only export) and screenshots of the AI Factory
menu and install page.

| Aspect | SUSE Virtualization (StackVista) | SUSE AI Factory (SA team) |
| --- | --- | --- |
| Own components | `vm`, `vmi`, KubeVirt cluster in `urn:susevirt:/...` | gateway, agent, guard, inference server, model, GPU, sandbox, tenant, tool in `urn:ai-factory:/<cluster>:<kind>/...` |
| Same workload as an existing component | n/a (a VM is not its launcher Pod) | Inference servers and gateways **merge** with their Kubernetes service/deployment and OTel service |
| Distinct concepts | Relations: runs on, launched by, instance of, defined by, controls | Separate components: models, GPUs, tenants, tools |
| Presentations on other StackPacks' components | Overlays: specificity 10, metrics only, no icon/name/overview | n/a |
| Topology | n/a | Own domain and 13 layers, GPU to tenant |
| Menu | n/a | One outline icon family (jungle-green glyph on light-green tile), plain plural nouns, stack order |
| Install page | Components / Relations / Presentations / Data sources contributed; Prerequisites | Value statement, one-line topology chain, bullets per data source with concrete metrics, fit with Kubernetes/OTel |
| Monitors | n/a | Operator-language titles; remediation: Check first / Likely causes / Fix / Verify, with deep links |

## Decisions

### D1. Same workload: one merged component, no presentation takeover
Inference servers, vector databases, search engines, AI gateways, MCP servers, registries and AI
interfaces remain the merged OTel service component (as AI Factory does), so traces, logs, Kubernetes
state and health stay on one node.

- Our contribution to `otel service` / `otel service instance` components becomes an **overlay**:
  low specificity (below the Open Telemetry StackPack's), adding metric sections and highlight fields
  only. No `icon`, `name` or `overview` on presentations bound to OTel components.
- Our menu pages list those components through **our own presentations' overviews**, scoped by our
  labels (`stackpack:suse-ai`, `suse.ai.category:*`, `suse.ai.product:*`).
- Spike question S1 decides whether an overview on our presentation can coexist with the Open
  Telemetry presentation without changing the Open Telemetry pages. If not, fall back to D1b.

**D1b (fallback):** a separate `genai <role>` component per workload in `urn:suse-ai:/<cluster>:<kind>/...`,
related to the OTel service (`observed as`) and, through it, to the Kubernetes workload. Health is
attached to our component by our monitors.

### D2. Distinct concepts: own components and relations
Served model, model usage, agent, tool, database dependency (exist today) and **GPU device** (new,
between pod and node, as in AI Factory) are first-class components in `urn:suse-ai:/...`, related with
explicit relation types: `serves` (inference server -> served model), `uses` (application -> model
usage), `runs on`, `allocated to` (GPU -> pod), `calls` (application -> tool/MCP server).

### D3. Own domain and layers
Domain `SUSE AI`. Layers, top to bottom: AI Applications, AI Agents, AI Gateways, MCP Tools, Inference
Servers, Models, Data Services, GPUs. Generic: no tenant, guard or sandbox layers unless a supported
integration produces them.

### D4. Menu
Plural plain nouns in stack order: Overview, Applications, Agents, Gateways, Tools, Inference servers,
Models, Model usage, Data services, GPUs. One icon per entry.

### D5. Icon family
- One style: outline glyph, single stroke weight, 40x40 grid, SUSE palette (jungle green #30BA78 glyph
  on a light-green tile for menu/role icons; pine #0C322C tile for the StackPack logo).
- Role icons are generic glyphs. Product logos appear only where the vendor's trademark guidelines allow
  it; otherwise a neutral product badge on the role icon.
- Remove the stock PNG of unknown licence. Record source and licence for every icon in
  `stackpack/suse-ai/icons/LICENSES.md`.
- Ask SUSE brand/design for an existing icon library before drawing new glyphs.

### D6. Monitors
Operator-language titles naming the component ("Inference server X: requests queueing"). Remediation in
four parts, Check first / Likely causes / Fix / Verify, with deep links to the component page.
Monitors target our components (D2) or the merged service (D1).

### D7. Install page
- `overview.md`: one value sentence and the topology chain, for example
  `application -> agent -> gateway -> model -> inference server -> pod -> GPU -> node`.
- `detailed-overview.md`: bullets per data source with product and concrete signals; Components /
  Relations / Presentations contributed; how it fits with Kubernetes and Open Telemetry.
- `configuration.md`: Prerequisites (Open Telemetry StackPack, Collector version, Agent version),
  three-step quick start, link to the monitoring guide. Caveats move to the documentation.
- Test whether StackPack resources can embed screenshots.

## Spike (one product before the full change)

Product: Ollama. Deliverables on a pre-release version (`3.0.0-spike.N`; never reuse an uploaded version):
1. **S1** Overlay merge: an overlay presentation on `otel service` (specificity below Open Telemetry,
   metrics only) plus our own list page. Verify the Open Telemetry Services page and component page are
   byte-for-byte unchanged in layout, icon and columns, and our page lists Ollama with AI columns.
2. **S2** Domain/layer: Ollama in layer Inference Servers, its served models in Models, GPU devices in GPUs.
3. **S3** GPU device component with `allocated to` (pod) and `runs on` (node) relations from DCGM labels.
4. **S4** One monitor in the D6 style on the Ollama inference server.
5. **S5** Upgrade from 3.0.x: what happens to existing component identities, monitors and saved links.
Exit criteria: S1 proven (else D1b), no topology-sync errors, screenshots of Open Telemetry pages before
and after.

## Versioning and migration
- Ship as a regenerated 3.0.0 (new GitHub tag, new IBS build). The earlier setup image `3.0.0-8.2` on
  Application Collection keeps the old content; the `recipes` chart must pin the new build's digest.
- Development builds use pre-release versions (`3.0.0-spike.N`), which sort below 3.0.0.
- Servers that already received a 3.0.x upload: `init.sh` skips uploading a version present in the
  catalog and refuses downgrades, so clean the old `suse-ai` 3.0.x versions and instance from demo and
  test instances before validating the final 3.0.0.
- Document identifier and view changes in the release notes and the monitoring guide.
- Keep the Collector contract unchanged where possible; new attributes (for example GPU device identity)
  are added in a Collector release before the StackPack depends on them.

## Decision update — shared product icons (2026-11-09)

The user superseded D1's prohibition on custom icons for merged OpenTelemetry
services and instances, then clarified that overrides apply only when a supported
product is identified. Generic services and instances retain their native icons,
including components with an AI category but no recognized product. Dedicated
product-specific, icon-only presentations outrank native icons; the namespaced fields, native layout and
separate inventory tables retain the existing composition rules. Direct
ComponentType icon mutations are not needed. Product SVGs use 16×16 intrinsic
dimensions, preserving their original drawing viewBoxes within a light-green
backing tile for contrast on both light and dark UI surfaces.

A separately named, isolated copy of the published GitHub v3.0.0 is used for live
comparison, rather than changing the installed development instance back to an
older version. Its settings and component identities are namespaced, including
its OTel companion contributions. The release comparison is demo tooling, not a
second shipping product or a change to the published GitHub tag.
