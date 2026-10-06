# Draft SUSE AI observability strategy and competitive comparison

Assessment date: 2026-10-06. Audience: SUSE AI and SUSE Observability engineering and product teams. This proposal does not supersede the deployed architecture or approve a migration.

Build the next extension around **one operational topology shared with OpenTelemetry and Kubernetes**, with AI-specific mappings, presentations, metrics, and monitors supplied by StackPacks v2. Add an evaluation integration so users can connect application quality to that operational topology. Request reusable execution-inspection, score-correlation, and content-access capabilities from the SUSE Observability team.

The extension should answer both “why is this agent slow or failing?” and “did this version produce a useful, correct result?” Its existing infrastructure coverage provides a useful starting point for the first question. Answering the second requires an evaluation workflow in addition to telemetry collection.

See the [architecture and migration proposal](STACKPACK_V2_ARCHITECTURE.md) and the [draft platform feature requests](OBSERVABILITY_FEATURE_REQUESTS.md).

## Competitive comparison

This is a comparison of documented capabilities, not a performance benchmark. “Current extension” refers to source commit `0708bb91b573a142be35f5fdf15f758970543e98`, declaring extension version `2.2.0`. Product version, extension version, and StackPack schema version are separate version numbers. Competitor capabilities depend on the selected release, hosting arrangement, and edition.

| Offering | Runtime investigation | Evaluation and improvement workflow | Implication for SUSE |
| --- | --- | --- | --- |
| **SUSE Observability with the current AI extension** | AI/product topology; generic traces; token, latency and cost metric bindings; inference engine, vector database, Kubernetes and GPU views; monitors; Kubeflow lifecycle and demo agent/RAG metrics. | Can display externally produced quality metrics, including demo model accuracy. A general evaluation runner, dataset/experiment store, prompt registry, and annotation workflow were not found in the reviewed extension. | Preserve operational coverage while replacing topology duplication. Displaying accuracy or a quality gauge is only one part of an evaluation workflow. See [current architecture](ARCH.md), [metric bindings](../stackpack/suse-ai/provisioning/templates/metric-bindings/), and [monitors](../stackpack/suse-ai/provisioning/templates/monitors/). |
| **Langfuse** | Nested AI observations, inputs/outputs, token/cost analysis, scores and dashboards. | Online scoring, datasets, experiments, human review, prompt versions and deployment labels. | A useful benchmark for the production-trace → evaluation → experiment → prompt-improvement workflow. See [observability](https://langfuse.com/docs/observability/overview), [evaluation concepts](https://langfuse.com/docs/evaluation/core-concepts), and [prompt management](https://langfuse.com/docs/prompt-management/overview). |
| **Opik** | Span trees for LLM calls, tools and retrieval, with input/output inspection and cost/latency investigation. | Test suites, datasets, evaluation metrics, experiment comparisons and annotation queues. Its separate optimizer SDK can tune prompts, tools and agent workflows. | A useful benchmark for agent regression tests and optimization. See [tracing](https://www.comet.com/docs/opik/tracing/overview), [evaluation](https://www.comet.com/docs/opik/evaluation/overview/), and [optimizer](https://www.comet.com/docs/opik/development/optimization-runs/overview). |
| **Arize Phoenix** | AI tracing using OpenTelemetry/OpenInference, with annotations and prompt tooling. | Versioned datasets, experiments, code and LLM evaluators; client-side evaluation and server-side evaluation of experiments. | A candidate evaluation companion. Distinguish Phoenix from Arize AX: Phoenix documentation directs continuous production evaluation with alerting to AX. See [Phoenix](https://arize.com/docs/phoenix/), [evaluation](https://arize.com/docs/phoenix/evaluation/llm-evals), and [datasets](https://arize.com/docs/phoenix/datasets-and-experiments/concepts-datasets). |
| **LangSmith** | Agent execution tracing and investigation, with integration into its development tooling. | Online and offline evaluators, datasets, experiments, annotation queues, prompt engineering and Studio. | A benchmark for turning production failures into repeatable tests and comparing agent versions. See [observability](https://docs.langchain.com/langsmith/observability) and [evaluation](https://docs.langchain.com/langsmith/evaluation). |
| **Datadog Agent Observability** | Agent/LLM traces, token/cost monitoring and correlation with APM. | Managed/custom evaluations, external scores, end-user feedback and annotation queues; evaluation tooling also supports experiments. | A direct benchmark for integrating AI quality with application operations. See [investigation](https://docs.datadoghq.com/llm_observability/investigate/), [evaluations](https://docs.datadoghq.com/llm_observability/investigate/evaluations/), [developer guide](https://docs.datadoghq.com/llm_observability/investigate/evaluations/evaluation_developer_guide/), and [APM correlation](https://docs.datadoghq.com/llm_observability/instrument/agent_observability_and_apm/). |
| **Grafana Cloud Agent Observability** | Conversations, generations, agent versions, workflow steps, dependency views, tokens and cost alongside OTel telemetry. | Online evaluators and quality alerts; APIs for saved conversations, versioned test suites, experiment runs and external scores. | Compare against this product, not only a hand-built Grafana/Tempo dashboard. Its structured generation ingestion is separate from OTLP. See [introduction](https://grafana.com/docs/grafana-cloud/observe-and-act/agent-observability/introduction/) and [evaluation API](https://grafana.com/docs/grafana-cloud/observe-and-act/agent-observability/reference/evaluation-api/). |

The strategic inference is that AI tracing, token charts and a dependency graph are insufficient for broad feature parity. The specialist tools connect an observed failure to a scored example, a dataset and a repeatable experiment. General observability vendors increasingly offer that workflow too.

SUSE's proposed differentiation should be the connection between **agent behavior, quality, serving infrastructure and the Kubernetes/GPU estate**, including customer-operated installations. Self-hosting alone is not unique: Langfuse, Opik, Phoenix and LangSmith all offer it in some form. Langfuse documents enterprise restrictions for capabilities such as project roles, retention policies and server-side masking; Opik's community self-hosting documentation excludes user management; LangSmith self-hosting is an Enterprise add-on. Assess the required edition and operational burden when selecting an integration. See [Langfuse editions](https://langfuse.com/self-hosting/license-key), [Opik self-hosting](https://www.comet.com/docs/opik/self-host/overview), [Phoenix](https://arize.com/docs/phoenix/), and [LangSmith self-hosting](https://docs.langchain.com/langsmith/self-hosted).

## Feature gaps and ownership

“Platform request” below means a capability beyond the reviewed StackPack schema, or an existing platform capability whose adequacy must be confirmed. It does not assert that every SUSE Observability installation lacks it.

| User need | Current extension evidence | Work the AI team can own | Platform boundary |
| --- | --- | --- | --- |
| One AI-to-infrastructure topology | Separate AI product identities and legacy syncs | V2 mappings and presentations over canonical OTel identities; distinct identities for genuinely new entities | Confirm merge, lifecycle and upgrade behavior on the target release |
| LLM performance and serving capacity | Existing latency, token, engine and GPU metric bindings | TTFT, throughput, queues, cache utilization, errors and saturation dashboards/monitors | No new platform feature required for ordinary supplied metrics |
| Agent/tool/RAG operations | Demo tool, iteration and retrieval metrics; generic traces | Framework instrumentation, bounded tool/agent dimensions, tool failures, iteration limits and retrieval indicators | Rich run/conversation rendering and cross-trace execution queries |
| Cost investigation | Cost-series chart bindings | Versioned pricing logic, external cost calculation, budget alerts and price-source metadata | Native per-run aggregation/correlation if the existing query APIs cannot provide it |
| Online answer quality | Externally supplied quality metrics can be charted | Evaluators, criteria, sampling, aggregate quality metrics and remediation | Durable late-arriving scores linked to spans/runs, searchable alongside telemetry |
| Offline model/agent comparison | Kubeflow demo accuracy and lifecycle metrics | Evaluation jobs, fixed test sets, CI thresholds; link results from StackPack pages | Native dataset/experiment objects and comparison UI only if SUSE chooses to own that workflow |
| Prompt and release lineage | Service/product metadata and chart filtering | Record prompt/model/application versions; link to an external prompt registry or Git | Generic joins and comparison across versions; prompt authoring is a separate product decision |
| Human feedback | No general review queue found in the extension | Integrate an annotation tool and define review rubrics | Native feedback persistence, reviewer workflow and permissions if a unified SUSE experience is required |
| Sensitive prompts and responses | Collector configuration is the collection point | Opt-in capture, redaction and destination routing | Enforced content-level access, retention and auditing across UI, API and MCP |

A `ComponentPresentation` can supply overview columns, metrics, related resources, links and a filtered trace perspective. That is enough for operational pages and integration links. The documented schema does not establish a general application framework for dataset editors, annotation queues, prompt playgrounds or arbitrary AI trace renderers. See the [presentation reference](https://documentation.suse.com/cloudnative/suse-observability/latest/en/setup/custom-integrations/presentation/schemas-ref.html).

Also distinguish the platform's own AI Assistant/MCP access from monitoring customer agents. Exposing observability data to an assistant does not, by itself, implement customer-agent instrumentation or output evaluation. The [2.11.1 release notes](https://rancher.github.io/product-docs-playbook/suse-observability/latest/en/setup/release-notes/v2.11.1.html) describe the former alongside StackPacks v2.

## Recommended product direction

| Option | Benefit | Cost or limitation |
| --- | --- | --- |
| Operational extension only | Smallest scope; strong alignment with current ownership | Leaves model/agent evaluation workflows in other tools without a supported connection |
| **Operational extension plus an evaluation integration** | Delivers quality-to-infrastructure investigation sooner; keeps telemetry portable | Two systems to operate; score synchronization, access policy and navigation need explicit contracts |
| Complete native AI engineering suite | Potentially one product for tracing, prompts, datasets, experiments and review | Requires platform services and sustained product investment well beyond a StackPack |

Start with the middle option and design the interfaces so native capabilities can replace the companion later. Run a small integration trial with Langfuse or Opik; consider Phoenix where its evaluation model fits. Make the choice using the same representative workload, with attention to inference content, framework coverage, export fidelity, access controls, disconnected operation and maintenance effort. This recommendation is an implementation strategy, not a claim that one vendor wins every evaluation workload.

OTLP helps share traces, but does not standardize all evaluation objects or product behavior. Langfuse and Opik both document OTLP/HTTP ingestion and product-specific attribute mapping; neither cited endpoint supports OTLP/gRPC. Use separate exporter configuration, preserve trace/span IDs, and test semantic translation. Evaluation scores and datasets may still require the companion's API. See [Langfuse OTel](https://langfuse.com/integrations/native/opentelemetry) and [Opik OTel](https://www.comet.com/docs/opik/integrations/opentelemetry).

## What the first release should let a user do

1. **Investigate slow inference.** Move from an agent/application latency alert to its model endpoint, queue/cache metrics and associated GPU/pod. Distinguish provider latency from application orchestration and retrieval latency.
2. **Investigate a fast but incorrect RAG answer.** Inspect retrieved evidence and output where permitted, see a groundedness/relevance score, identify the prompt/model/retrieval version, and open the failed example in the evaluation system.
3. **Investigate a failing agent.** See tool choice, tool arguments/results where permitted, retries, handoffs, timeouts and loop length. Technical success and user-task completion must remain separate measures.
4. **Compare a candidate release.** Run a versioned dataset against a baseline and candidate; compare quality, latency, token use and cost with identical evaluator definitions. Keep a CI failure linked to the experiment and representative traces.

Evaluation design belongs to the AI team. Use deterministic checks for schemas, tool contracts and known outcomes; use labeled examples and calibrated judges where semantic judgment is necessary. Record evaluator versions, sample counts, skipped/failed evaluations and coverage. A falling judge score can reflect evaluator changes or a changed traffic mix; it is not automatically model degradation. Do not turn an HTTP-success monitor into a task-success measure.

For classical models served through KServe, serving telemetry also does not establish predictive accuracy or drift. Delayed ground truth, feature/output distributions and evaluation jobs are additional inputs; quality metrics can then be displayed and monitored by the extension. Training and model-registry lifecycle tracking remain useful but are separate from measuring production predictive quality.

## Decision sequence

First agree on canonical identity, v2 compatibility and the topology-exporter retirement gates. Then prove the four user workflows above with one agent/RAG application and one inference backend. Request platform score correlation and AI-aware execution inspection in parallel; expand product and framework coverage once the shared contracts work.

The [feature-request drafts](OBSERVABILITY_FEATURE_REQUESTS.md) separate immediate capability confirmation from new product work, and specify acceptance criteria. The [migration proposal](STACKPACK_V2_ARCHITECTURE.md) explains why the custom exporter is a candidate for retirement rather than an immediate deletion.

## Evidence and validation boundary

The existing repository, its `knowledge/` files, current Collector examples and StackPack templates were inspected. The user-specified [SUSE StackPacks examples](https://github.com/StackVista/suse-stackpacks/tree/be6d22d6541e9c2eb098777b8a282b8fc3012fb0) were retrieved through `gh`, at commit `be6d22d6541e9c2eb098777b8a282b8fc3012fb0`. The [official scaffold](https://github.com/StackVista/stackpack-templates/tree/6e8d035ca5d666c48a8b323798ef540e425c0e4e) was also inspected. Web references describe the documentation available on the assessment date; `latest` pages may include behavior beyond the target installed patch.

`task stackpack-sync-status` attempted `sts topology-sync list` and `describe` for all three AI sync identifiers. Each failed because the configured `http://localhost:8081/api` endpoint refused the connection. The local CLI reported `3.3.7`; the 2.11.1 release notes list CLI `3.9.0`. No v2 deployment, collector replacement or competitor benchmark was performed. Deployment compatibility and feature parity remain acceptance tests, not outcomes of this assessment.
