# Draft SUSE Observability requests for AI applications

Assessment date: 2026-10-06. These are discussion-ready request drafts, not submitted upstream issues or committed roadmap items. The [strategy](AI_OBSERVABILITY_STRATEGY.md) explains the competitive context; the [architecture proposal](STACKPACK_V2_ARCHITECTURE.md) defines the extension work.

Ask the SUSE Observability team for reusable platform primitives. The AI team should own AI-specific telemetry, classification, dashboards, monitors and evaluation criteria. Confirm existing capabilities before opening implementation requests; a documented feature that already meets an acceptance criterion should be reused.

| Priority | Request | Why it matters | Lead owner |
| --- | --- | --- | --- |
| P0 migration gate | FR0: supported topology composition and sampling contract | Determines whether the custom topology exporter can be retired | Joint verification; Observability resolves platform gaps |
| P1 | FR1: structured AI execution inspection | Makes ordinary AI telemetry usable for agent debugging | Observability UI; AI supplies profiles/fixtures |
| P1 | FR2: asynchronous evaluation and feedback correlation | Connects quality outcomes to operational causes | Observability storage/query; AI owns evaluation |
| P1 with content capture | FR3: content-specific access and lifecycle controls | Permits useful debugging without giving all operators access to prompts | Observability enforcement; AI owns collection policy |
| P2 | FR4: conversation and agent execution analysis | Handles multi-turn, multi-agent and asynchronous workflows | Observability query/UI; AI owns instrumentation |
| P2 | FR5: supported evaluation workflow integration | Turns production failures into repeatable regression tests | Joint integration contract |
| Optional later product investment | FR6: native evaluation workspace | Closes the remaining specialist-tool workflow gap | Observability product/platform with AI domain ownership |

## FR0 Supported topology composition and sampling contract

**User story:** As the AI extension maintainer, I can enrich an OTel service and connect it to model/tool infrastructure without a second topology implementation in the Collector.

**Request:** Confirm a versioned compatibility contract for shared entity identifiers, independently owned settings, merge precedence, lifecycle and upgrade/rollback. Demonstrate how complete topology can be maintained when stored traces are sampled. This is primarily an integration qualification request: mappings, presentations, ranks and status commands already exist.

**Acceptance:** An AI presentation and mapping coexist with base OTel/Kubernetes contributions; ordinary metrics, links and monitors continue working. Removing or upgrading the AI StackPack preserves base components. Same-named entities in separate intended scopes do not collapse. Legacy external-topology precedence is covered by a cutover test. A low-traffic dependency remains discoverable under the supported sampling strategy, with specified expiration and refresh behavior. Mapping errors and missing-input cases can be diagnosed through existing tools or a documented extension to them.

**AI team contribution:** Paired old/new telemetry fixtures, proposed entity IDs, mapping/presentation source, monitor selectors and the exporter-retirement test matrix. Keep the exporter until those tests pass. See the [official scaffold](https://github.com/StackVista/stackpack-templates/blob/6e8d035ca5d666c48a8b323798ef540e425c0e4e/templates/generic/settings/component-mappings/microservices.sty) and [existing mapping diagnostics](https://documentation.suse.com/cloudnative/suse-observability/latest/en/setup/custom-integrations/otelmappings/troubleshooting.html).

## FR1 Structured AI execution inspection

**User story:** When an agent gives a wrong answer, I can inspect its model calls, tool invocations and retrieved evidence alongside the infrastructure involved.

**Request:** Provide a native AI-aware span/run renderer or a supported declarative span-presentation extension. Recognize standard/profiled GenAI operations and display messages by role, structured tool arguments/results, retrieval metadata, usage, latency and streaming timing. The AI team supplies semantic mappings and terminology; the platform supplies safe rendering, navigation and query integration.

**Acceptance:** A trace with an agent, retrieval, two model calls and a tool call is understandable without reading flattened attribute JSON. Requested and actual model are distinct. Redacted, absent and truncated content are distinguishable. The user can navigate to the corresponding service/model/pod where identity is known. An ordinary OTel source works without an obligatory SUSE application SDK; a compatibility profile covers another commonly used instrumentation format. Large or malformed content is bounded and rendered safely.

**StackPack boundary:** Component fields, metric panels and filtered trace perspectives already belong in our StackPack. They do not establish a custom renderer for individual trace records. Validate that distinction with the platform team before choosing the extension mechanism. [Existing presentation schema](https://documentation.suse.com/cloudnative/suse-observability/latest/en/setup/custom-integrations/presentation/schemas-ref.html).

**Competitive reference:** [Langfuse trace investigation](https://langfuse.com/docs/observability/overview) and [Opik tracing](https://www.comet.com/docs/opik/tracing/overview).

## FR2 Asynchronous evaluation and feedback correlation

**User story:** A quality score arriving after a request completes appears on the right operation and can be investigated alongside errors, latency and deployment changes.

**Request:** Support durable ingest and retrieval of evaluation/feedback records, joined by tenant plus trace/span identity or an explicitly scoped run/conversation key. Accept a documented OTel Logs event representation where applicable and/or a stable API for external evaluators. Retain score type/value/label, evaluator identity/version, provenance, evaluated-at time and operation time. Keep detailed results searchable without putting per-request identities in metric labels.

**Acceptance:** A score submitted after its target span is stored joins correctly. Retries are idempotent; two evaluators and two evaluator versions do not overwrite each other. Results arriving before the trace can join later. A sampled-out, expired or unauthorized target is handled explicitly. Numeric, categorical and human-feedback results retain provenance. Queries can select low-quality executions and return authorized trace links; aggregate quality metrics include eligible/evaluated/failed counts. Tenant boundaries apply to both ingestion and retrieval.

**AI team contribution:** Evaluator adapters, scoring rubrics, calibration and judge/model/dataset version metadata. Initially, the companion owns detailed records and the StackPack consumes aggregate quality metrics. No LLM judge should execute inside topology synchronization or a normal health-monitor evaluation.

**Competitive reference:** [Datadog evaluation intake](https://docs.datadoghq.com/llm_observability/instrument/api/) and [Grafana external score ingest](https://grafana.com/docs/grafana-cloud/observe-and-act/agent-observability/reference/evaluation-api/). The OTel [evaluation event](https://github.com/open-telemetry/semantic-conventions-genai/blob/4f85037ef86e92c510d2ef881a58f1076f6fc0e4/docs/gen-ai/gen-ai-events.md) remains Development; do not advertise a stable cross-vendor score schema prematurely.

## FR3 Content-specific access and lifecycle controls

**User story:** An operator can diagnose latency and infrastructure issues, while only an authorized application reviewer can inspect retained prompts, responses or tool payloads.

**Request:** Confirm or add content-level permissions and retention controls for AI payloads, distinct from permission to read operational metadata. Apply them consistently to native UI, query/export APIs, external links and MCP/assistant access. Support independent retention of sensitive content and aggregate operational/quality measures, with auditable content access and deletion behavior.

**Acceptance:** Two roles can see the same permitted operational metadata but different content. API/export/MCP paths enforce the same restriction. Changing a role or expiring content does not leave a readable cached copy or unrestricted attachment. Redaction and retention behavior are testable on nested messages and tool payloads, including logs if logs carry the content. Existing generic RBAC is reused wherever it already satisfies these requirements.

**AI team contribution:** Opt-in capture defaults, source/Collector redaction, tenant routing, payload limits and test fixtures. Collection-time redaction is essential but cannot implement backend authorization after ingestion.

**Competitive reference:** [Langfuse enterprise content and governance features](https://langfuse.com/self-hosting/license-key) and [Datadog evaluation/content controls](https://docs.datadoghq.com/llm_observability/investigate/evaluations/).

## FR4 Conversation and agent execution analysis

**User story:** I can follow a user task through several traces, agent handoffs and resumed jobs, and understand where time, tokens, errors and poor outcomes accumulated.

**Request:** Add or document an execution query model for conversations/runs spanning multiple traces, including OTel span links where emitted. Provide a workflow view and aggregated measures with explicit attribution rules. Support comparisons by agent/application/prompt/model version and quality cohort. This concerns high-cardinality execution records, not the stable topology graph.

**Acceptance:** A two-turn conversation with a queued tool job and a second agent can be followed across its trace boundaries. Missing/late spans are visible. Retry attempts can be counted separately from logical operations. Parent/child rollups do not count the same model usage twice. Users can compare baseline and candidate populations using fixed time windows and evaluator versions, inspect sample counts, and navigate to examples. Normal attribute filtering should reuse the existing trace API.

**AI team contribution:** Trace propagation, explicit run/conversation correlation, bounded agent/tool identities, completion signals and usage attribution fixtures. A Collector cannot recover a relationship that the application never emitted.

**Competitive reference:** [Grafana conversations and workflow dependencies](https://grafana.com/docs/grafana-cloud/observe-and-act/agent-observability/introduction/) and [Datadog session evaluation](https://docs.datadoghq.com/llm_observability/evaluations/managed_evaluations/session_level_evaluations).

## FR5 Supported evaluation workflow integration

**User story:** I can select a failed production execution, use it in a regression dataset, and return from an experiment result to the operational evidence.

**Request:** Agree on a supported integration contract for authorized trace retrieval/export, stable deep links, version metadata and score ingest. Reuse existing APIs and `ComponentPresentation` links first; request only missing guarantees. Detailed datasets, experiments and annotation queues may remain in a companion for the first release.

**Acceptance:** One representative failure is exported with its provenance and permitted content, added to a versioned dataset, evaluated against two application versions, and linked back to the original trace. The workflow has documented tenant/authentication boundaries, pagination/volume limits and behavior after retention expiry. Ingesting scores follows FR2. At least one companion path is supported end to end; OTLP trace ingestion alone is not counted as completion.

**AI team contribution:** The companion adapter, evaluator jobs, CI gates, dataset criteria and StackPack links/monitors. Preserve original trace/span IDs when routing traces; test any backend-specific ID mapping rather than assuming UI identifiers are identical.

**Competitive reference:** [Langfuse offline evaluation](https://langfuse.com/docs/evaluation/get-started/offline) and [LangSmith evaluation workflow](https://docs.langchain.com/langsmith/evaluation).

## FR6 Optional native evaluation workspace

**User story:** AI engineers and domain reviewers can run the full improvement workflow inside SUSE Observability when an external companion is unsuitable.

**Request:** Make an explicit product decision about native versioned datasets, experiment comparison, human annotation queues, evaluator orchestration and prompt management. These require persistent application objects, worker execution, APIs and UI beyond the current StackPack setting types. Prioritize datasets/experiment comparison and human feedback before automatic prompt optimization.

**Acceptance:** Production examples can be promoted to immutable dataset versions; a baseline/candidate experiment records the application, model, prompt, dataset and evaluator versions; reviewers can annotate examples with provenance; jobs have budgets, retries and failure states; deterministic and LLM evaluators can run with customer-provided models. Evaluation traffic and failures are separately observable. Disconnected installations can use locally available judges and dependencies where that deployment mode is promised.

**AI team contribution:** Domain-specific evaluators, reference datasets, model/provider integrations and calibration. The Observability team owns the shared service/storage/UI primitives. A simple chart over evaluation scores is not acceptance for this request.

**Competitive reference:** [Opik evaluation workflows](https://www.comet.com/docs/opik/evaluation/overview/), [Phoenix datasets](https://arize.com/docs/phoenix/datasets-and-experiments/concepts-datasets), and [Langfuse prompt management](https://langfuse.com/docs/prompt-management/overview).

## Work to keep in the AI extension

Do not open platform requests for functionality already expressible through supplied telemetry and supported StackPack configuration: AI service classification, model/endpoint topology, engine/vector/GPU dashboards, PromQL health monitors, quality threshold alerts, menu organization, related-resource links and technology-specific remediation.

Instrumentation, semantic-version adapters, cost calculation/pricing policy, guardrail instrumentation and evaluator criteria also belong with the AI team or its selected integration. Synchronous guardrail enforcement belongs in the application/gateway execution path; Observability can receive the decisions and monitor their outcomes. Revisit platform ownership only when a reusable storage, query, authorization or UI primitive is actually missing.
