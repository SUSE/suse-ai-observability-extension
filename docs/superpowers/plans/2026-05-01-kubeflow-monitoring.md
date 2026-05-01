# Kubeflow Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Kubeflow Pipelines, KServe, and Kubeflow Model Registry into the SUSE AI Observability StackPack as first-class monitored products, and re-enable the previously commented `workflow-engine` and `ml-registry` menu entries.

**Architecture:** Three new product ComponentTypes (`inference-engine.kserve`, `workflow-engine.kubeflow-pipelines`, `ml-registry.kubeflow`), each surfaced via the existing dual-sync (main + product) pipeline. Signals collected by adding three Prometheus scrape jobs and corresponding `transform/<product>` processors to `integrations/otel-collector/otel-values.yaml`, plus new trace transforms for component tagging and `kfp → kserve` / `kfp → model-registry` relations. Model Registry is topology-only in v1 (no metric bindings); a future custom OTel receiver can synthesize metrics.

**Tech Stack:** YAML (.sty Handlebars templates), Groovy (sync extractors / mapping function), npm-groovy-lint, OpenTelemetry Collector OTTL, SUSE Observability `sts` CLI, Taskfile.

**Spec:** `docs/superpowers/specs/2026-05-01-kubeflow-monitoring-design.md`

**ID allocation (verified against MEMORY.md):**
- ComponentTypes: -5015 (kserve), -5016 (kfp), -5017 (model-registry)
- MetricBindings: -630 to -639 (kserve), -640 to -649 (kfp), -650 to -659 reserved (model-registry, future)
- Monitors: -3016 to -3018 (kserve), -3019 to -3022 (kfp)

---

## File Map

### New files
```
stackpack/suse-ai/provisioning/icons/kserve.svg
stackpack/suse-ai/provisioning/icons/kubeflow-pipelines.svg
stackpack/suse-ai/provisioning/icons/kubeflow-model-registry.svg
stackpack/suse-ai/provisioning/templates/metric-bindings/kserve-metrics.sty
stackpack/suse-ai/provisioning/templates/metric-bindings/kubeflow-pipelines-metrics.sty
stackpack/suse-ai/provisioning/templates/monitors/kserve/monitor.sty
stackpack/suse-ai/provisioning/templates/monitors/kserve/remediation-deviating.md.hbs
stackpack/suse-ai/provisioning/templates/monitors/kserve/remediation-critical.md.hbs
stackpack/suse-ai/provisioning/templates/monitors/kubeflow-pipelines/monitor.sty
stackpack/suse-ai/provisioning/templates/monitors/kubeflow-pipelines/remediation-deviating.md.hbs
stackpack/suse-ai/provisioning/templates/monitors/kubeflow-pipelines/remediation-critical.md.hbs
knowledge/KUBEFLOW.md
```

### Modified files
```
stackpack/suse-ai/provisioning/templates/component-types/products.sty   (add 3 ComponentTypes + TraceBindings)
stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy   (3 switch cases)
stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy  (3 switch cases)
stackpack/suse-ai/provisioning/templates/shared.sty                     (uncomment 2 menu entries)
stackpack/suse-ai/provisioning/templates/view-types/workflow-engines.sty (add Run Success Rate column)
stackpack/suse-ai/provisioning/templates/suse-ai.sty                    (4 new {{ include }} lines)
integrations/otel-collector/otel-values.yaml                            (scrape jobs, transforms, trace pipelines, env var)
stackpack/suse-ai/stackpack.conf                                        (version bump via task)
stackpack/suse-ai/resources/configuration.md                            (Kubeflow section)
stackpack/suse-ai/resources/enabled.md                                  (3 new product types)
stackpack/suse-ai/resources/detailed-overview.md                        (Kubeflow in supported list)
stackpack/suse-ai/resources/RELEASE.md                                  (new version entry)
```

---

## Phase 1 — OTel collector additions

These changes go into the test config `integrations/otel-collector/otel-values.yaml` (per project memory, this is the test environment config). Production users override via Helm values.

### Task 1.1: Add `KUBEFLOW_NAMESPACE` env var

**Files:**
- Modify: `integrations/otel-collector/otel-values.yaml:4-8`

- [ ] **Step 1: Read current `extraEnvs` block to confirm location**

Run: `sed -n '4,8p' integrations/otel-collector/otel-values.yaml`
Expected output:
```
extraEnvs:
  - name: K8S_CLUSTER_NAME
    value: "local"  # Update to match your cluster name
  - name: SUSE_AI_NAMESPACE
    value: "suse-private-ai"  # Update to match the SUSE AI namespace
```

- [ ] **Step 2: Add the new env var after `SUSE_AI_NAMESPACE`**

Insert after line 8 (the `value: "suse-private-ai"` line):
```yaml
  - name: KUBEFLOW_NAMESPACE
    value: "kubeflow"  # Update to match the Kubeflow control-plane namespace
```

- [ ] **Step 3: Validate YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('integrations/otel-collector/otel-values.yaml'))"`
Expected: no output (silent success). Any error means YAML is malformed.

- [ ] **Step 4: Commit**

```bash
git add integrations/otel-collector/otel-values.yaml
git commit -m "feat(otel): add KUBEFLOW_NAMESPACE env var"
```

---

### Task 1.2: Add Prometheus scrape jobs for Kubeflow Pipelines, KServe controller, KServe InferenceServices

**Files:**
- Modify: `integrations/otel-collector/otel-values.yaml` — append to `receivers.prometheus.config.scrape_configs:` (currently ends around line 82 with the `vllm` job)

- [ ] **Step 1: Locate end of scrape_configs**

Run: `grep -n "scrape_configs\|^          - job_name" integrations/otel-collector/otel-values.yaml`
Expected: lines listing `gpu-metrics`, `milvus`, `qdrant`, `vllm`. Note the line number of the last `relabel_configs` block under `vllm`.

- [ ] **Step 2: Append the three new scrape jobs**

Append (preserving 10-space indent — the scrape configs are indented under `config.receivers.prometheus.config.scrape_configs:`):
```yaml
          - job_name: 'kubeflow-pipelines'
            scrape_interval: 15s
            metrics_path: '/metrics'
            kubernetes_sd_configs:
              - role: service
                namespaces:
                  names:
                    - ${env:KUBEFLOW_NAMESPACE}
            relabel_configs:
              - source_labels: [__meta_kubernetes_service_name]
                action: keep
                regex: '(ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service)'
          - job_name: 'kserve-controller'
            scrape_interval: 15s
            metrics_path: '/metrics'
            kubernetes_sd_configs:
              - role: pod
                namespaces:
                  names:
                    - kserve
            relabel_configs:
              - source_labels: [__meta_kubernetes_pod_label_control_plane]
                action: keep
                regex: 'kserve-controller-manager'
          - job_name: 'kserve-inferenceservices'
            scrape_interval: 15s
            metrics_path: '/metrics'
            kubernetes_sd_configs:
              - role: pod
            relabel_configs:
              - source_labels: [__meta_kubernetes_pod_label_serving_kserve_io_inferenceservice]
                action: keep
                regex: '.+'
              - source_labels: [__meta_kubernetes_pod_container_port_name]
                action: keep
                regex: 'http-usermetric'
```

- [ ] **Step 3: Validate YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('integrations/otel-collector/otel-values.yaml'))"`
Expected: silent success.

- [ ] **Step 4: Confirm jobs are visible in the parsed config**

Run: `python3 -c "import yaml; cfg=yaml.safe_load(open('integrations/otel-collector/otel-values.yaml')); jobs=[j['job_name'] for j in cfg['config']['receivers']['prometheus']['config']['scrape_configs']]; print(jobs)"`
Expected: list contains `'kubeflow-pipelines'`, `'kserve-controller'`, `'kserve-inferenceservices'` alongside the existing jobs.

- [ ] **Step 5: Commit**

```bash
git add integrations/otel-collector/otel-values.yaml
git commit -m "feat(otel): scrape Kubeflow Pipelines and KServe metrics"
```

---

### Task 1.3: Add resource-tagging transform processors for the three products

**Files:**
- Modify: `integrations/otel-collector/otel-values.yaml` — add three processors alongside the existing `transform/vllm`, `transform/qdrant`, `transform/milvus` blocks (around lines 121-151).

- [ ] **Step 1: Locate the existing `transform/milvus` block**

Run: `grep -n "transform/milvus\|transform/vllm\|transform/qdrant" integrations/otel-collector/otel-values.yaml`
Expected: shows the three blocks. Note the line number where `transform/milvus` ends (the next non-indented `processors:` member).

- [ ] **Step 2: Append three new transform processors after `transform/milvus`**

Insert (preserving 4-space indent — these sit under `processors:`):
```yaml
    transform/kserve:
      error_mode: ignore
      metric_statements:
        - context: resource
          statements:
            - set(attributes["suse.ai.managed"], "true") where IsMatch(attributes["service.name"] ?? "", ".*-predictor-default|.*-transformer-default|.*-explainer-default|kserve-controller-manager")
            - set(attributes["suse.ai.component.name"], "kserve") where IsMatch(attributes["service.name"] ?? "", ".*-predictor-default|.*-transformer-default|.*-explainer-default|kserve-controller-manager")
            - set(attributes["suse.ai.component.type"], "inference-engine") where IsMatch(attributes["service.name"] ?? "", ".*-predictor-default|.*-transformer-default|.*-explainer-default|kserve-controller-manager")
            - set(attributes["service.instance.id"], attributes["service.name"]) where IsMatch(attributes["service.name"] ?? "", ".*-predictor-default|.*-transformer-default|.*-explainer-default|kserve-controller-manager") and attributes["service.instance.id"] == nil
            - set(attributes["k8s.namespace.name"], "${env:SUSE_AI_NAMESPACE}") where IsMatch(attributes["service.name"] ?? "", ".*-predictor-default|.*-transformer-default|.*-explainer-default|kserve-controller-manager") and attributes["k8s.namespace.name"] == nil
    transform/kubeflow-pipelines:
      error_mode: ignore
      metric_statements:
        - context: resource
          statements:
            - set(attributes["suse.ai.managed"], "true") where IsMatch(attributes["service.name"] ?? "", "ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service")
            - set(attributes["suse.ai.component.name"], "kubeflow-pipelines") where IsMatch(attributes["service.name"] ?? "", "ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service")
            - set(attributes["suse.ai.component.type"], "workflow-engine") where IsMatch(attributes["service.name"] ?? "", "ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service")
            - set(attributes["service.instance.id"], attributes["service.name"]) where IsMatch(attributes["service.name"] ?? "", "ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service") and attributes["service.instance.id"] == nil
            - set(attributes["k8s.namespace.name"], "${env:KUBEFLOW_NAMESPACE}") where IsMatch(attributes["service.name"] ?? "", "ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service") and attributes["k8s.namespace.name"] == nil
    transform/kubeflow-model-registry:
      error_mode: ignore
      metric_statements:
        - context: resource
          statements:
            - set(attributes["suse.ai.managed"], "true") where attributes["service.name"] == "model-registry-service"
            - set(attributes["suse.ai.component.name"], "kubeflow-model-registry") where attributes["service.name"] == "model-registry-service"
            - set(attributes["suse.ai.component.type"], "ml-registry") where attributes["service.name"] == "model-registry-service"
            - set(attributes["service.instance.id"], "kubeflow-model-registry") where attributes["service.name"] == "model-registry-service" and attributes["service.instance.id"] == nil
            - set(attributes["k8s.namespace.name"], "${env:KUBEFLOW_NAMESPACE}") where attributes["service.name"] == "model-registry-service" and attributes["k8s.namespace.name"] == nil
```

- [ ] **Step 3: Wire the new processors into the `metrics` pipeline**

Locate the existing pipeline at line ~310:
```
      metrics:
        receivers: [otlp, spanmetrics, prometheus]
        processors: [memory_limiter, transform/qdrant, transform/milvus, transform/vllm, resource, batch]
        exporters: [debug, otlp]
```
Replace the `processors:` line with:
```
        processors: [memory_limiter, transform/qdrant, transform/milvus, transform/vllm, transform/kserve, transform/kubeflow-pipelines, transform/kubeflow-model-registry, resource, batch]
```

- [ ] **Step 4: Validate YAML and processor wiring**

Run:
```
python3 -c "import yaml; cfg=yaml.safe_load(open('integrations/otel-collector/otel-values.yaml')); ps=cfg['config']['service']['pipelines']['metrics']['processors']; assert 'transform/kserve' in ps and 'transform/kubeflow-pipelines' in ps and 'transform/kubeflow-model-registry' in ps; print('OK')"
```
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add integrations/otel-collector/otel-values.yaml
git commit -m "feat(otel): tag Kubeflow metrics with suse.ai resource attributes"
```

---

### Task 1.4: Add trace transforms for component tagging and kfp→kserve/model-registry relations

**Files:**
- Modify: `integrations/otel-collector/otel-values.yaml` — add three processors and one new pipeline.

- [ ] **Step 1: Locate `transform/provider-relations` block (around line 269)**

Run: `grep -n "transform/provider-relations:" integrations/otel-collector/otel-values.yaml`
Note the line where the block ends.

- [ ] **Step 2: Append three new trace transform processors after `transform/provider-relations`**

```yaml
    transform/kserve-traces:
      error_mode: ignore
      trace_statements:
        - context: resource
          statements:
            - set(attributes["suse.ai.managed"], "true") where attributes["serving.kserve.io/inferenceservice"] != nil or IsMatch(attributes["service.name"] ?? "", ".*-predictor-default|.*-transformer-default|.*-explainer-default")
            - set(attributes["suse.ai.component.name"], "kserve") where attributes["serving.kserve.io/inferenceservice"] != nil or IsMatch(attributes["service.name"] ?? "", ".*-predictor-default|.*-transformer-default|.*-explainer-default")
            - set(attributes["suse.ai.component.type"], "inference-engine") where attributes["serving.kserve.io/inferenceservice"] != nil or IsMatch(attributes["service.name"] ?? "", ".*-predictor-default|.*-transformer-default|.*-explainer-default")
    transform/kfp-traces:
      error_mode: ignore
      trace_statements:
        - context: resource
          statements:
            - set(attributes["suse.ai.managed"], "true") where IsMatch(attributes["service.name"] ?? "", "ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service")
            - set(attributes["suse.ai.component.name"], "kubeflow-pipelines") where IsMatch(attributes["service.name"] ?? "", "ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service")
            - set(attributes["suse.ai.component.type"], "workflow-engine") where IsMatch(attributes["service.name"] ?? "", "ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service")
    transform/kubeflow-relations:
      error_mode: ignore
      trace_statements:
        - context: span
          statements:
            - set(attributes["peer.service"], "kserve") where attributes["kserve.inference.service"] != nil
            - set(attributes["peer.service"], "kubeflow-model-registry") where IsMatch(attributes["http.url"] ?? "", ".*model-registry.*")
```

- [ ] **Step 3: Add a new `traces/kubeflow-relations` pipeline**

Locate the `traces/topology` pipeline (around line 349). Append a new pipeline after it:
```yaml
      # Tag KServe and Kubeflow Pipelines spans, then surface
      # kfp -> kserve and kfp -> model-registry relations via peer.service.
      traces/kubeflow-relations:
        receivers: [routing/traces]
        processors: [transform/kserve-traces, transform/kfp-traces, transform/kubeflow-relations, batch]
        exporters: [otlp]
```

- [ ] **Step 4: Add the new pipeline to the `routing/traces` connector table**

Locate the `routing/traces` connector (around line 287). Update its `pipelines:` list:
```yaml
    routing/traces:
      error_mode: ignore
      table:
      - statement: route()
        pipelines: [traces/sampling, traces/spanmetrics, traces/model-relations, traces/provider-relations, traces/topology, traces/kubeflow-relations]
```

- [ ] **Step 5: Validate YAML and pipeline wiring**

Run:
```
python3 -c "
import yaml
cfg = yaml.safe_load(open('integrations/otel-collector/otel-values.yaml'))
pipelines = cfg['config']['service']['pipelines']
assert 'traces/kubeflow-relations' in pipelines, 'pipeline missing'
table = cfg['config']['connectors']['routing/traces']['table'][0]['pipelines']
assert 'traces/kubeflow-relations' in table, 'not in routing'
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add integrations/otel-collector/otel-values.yaml
git commit -m "feat(otel): trace pipelines for Kubeflow component tagging and relations"
```

---

## Phase 2 — Sync wiring (Groovy)

### Task 2.1: Add Kubeflow product cases to `component-mapping-function.groovy`

**Files:**
- Modify: `stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy:89-113`

- [ ] **Step 1: Read the current `productName` switch**

Run: `sed -n '85,115p' stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy`
Expected: shows the `switch(productName)` block with cases for `vllm`, `ollama`, `qdrant`, `milvus`, `opensearch`, `elasticsearch`, `open-webui`, `litellm`, `mlflow`.

- [ ] **Step 2: Add three new cases before the closing `}` of the switch**

Insert before the `case 'mlflow':` block (or after — order doesn't matter functionally):
```groovy
            case 'kserve':
                currentType = "inference-engine.kserve"
                break
            case 'kubeflow-pipelines':
                currentType = "workflow-engine.kubeflow-pipelines"
                break
            case 'kubeflow-model-registry':
                currentType = "ml-registry.kubeflow"
                break
```

- [ ] **Step 3: Update the `aiTypes` whitelist (line ~141) to include the new bare categories — already present**

Confirm the existing `aiTypes` list contains `'workflow-engine'` and `'ml-registry'`:
Run: `grep -n "aiTypes" stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy`
Expected: line containing `def aiTypes = ['application', 'agent', 'ui', 'inference-engine', 'vectordb', 'llm-model', 'model-proxy', 'search-engine', 'mcp-server', 'workflow-engine', 'ml-registry']` — both are present, no edit needed.

- [ ] **Step 4: Lint the Groovy file**

Run: `npm-groovy-lint stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy`
Expected: no errors. Warnings are acceptable.

- [ ] **Step 5: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy
git commit -m "feat(sync): map Kubeflow product names to specialized component types"
```

---

### Task 2.2: Add Kubeflow product cases to `suse-ai-product-id-extractor.groovy`

**Files:**
- Modify: `stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy:58-81`

- [ ] **Step 1: Read the current switch**

Run: `sed -n '55,85p' stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy`
Expected: shows the `switch(productNameLower)` block with the same cases as in `component-mapping-function.groovy`.

- [ ] **Step 2: Add three new cases before the closing `}` of the switch**

Insert (e.g., before the `case 'mlflow':` block):
```groovy
        case 'kserve':
            specificType = "inference-engine.kserve"
            break
        case 'kubeflow-pipelines':
            specificType = "workflow-engine.kubeflow-pipelines"
            break
        case 'kubeflow-model-registry':
            specificType = "ml-registry.kubeflow"
            break
```

- [ ] **Step 3: Lint the Groovy file**

Run: `npm-groovy-lint stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy`
Expected: no errors.

- [ ] **Step 4: Confirm the two switch statements agree**

Run:
```
diff <(grep -E "case '[a-z-]+':" stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy | sort -u) \
     <(grep -E "case '[a-z-]+':" stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy | sort -u)
```
Expected: empty output (both files have the same set of `case '<name>':` lines).

- [ ] **Step 5: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy
git commit -m "feat(sync): emit specialized Kubeflow types from product extractor"
```

---

## Phase 3 — Icons

The three SVG icons sit under `provisioning/icons/` and are referenced from `products.sty` via Handlebars `{{ include }}`. Icons must be valid SVG; the StackPack importer base64-encodes them. Per CERTAINS.md §1, the resulting iconbase64 string must include the `data:image/svg+xml;base64,` prefix.

### Task 3.1: Add KServe icon

**Files:**
- Create: `stackpack/suse-ai/provisioning/icons/kserve.svg`

- [ ] **Step 1: Write a minimal valid KServe-themed SVG**

Create the file with this content (a generic serving icon — a horizontal stacked-rectangles shape):
```xml
<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="14" width="48" height="10" rx="2" fill="#326CE5"/>
  <rect x="8" y="28" width="48" height="10" rx="2" fill="#5C7CFA"/>
  <rect x="8" y="42" width="48" height="10" rx="2" fill="#91A7FF"/>
  <circle cx="14" cy="19" r="2" fill="white"/>
  <circle cx="14" cy="33" r="2" fill="white"/>
  <circle cx="14" cy="47" r="2" fill="white"/>
</svg>
```

- [ ] **Step 2: Validate the SVG parses**

Run: `python3 -c "import xml.etree.ElementTree as ET; ET.parse('stackpack/suse-ai/provisioning/icons/kserve.svg'); print('OK')"`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add stackpack/suse-ai/provisioning/icons/kserve.svg
git commit -m "feat(icons): add KServe icon"
```

---

### Task 3.2: Add Kubeflow Pipelines icon

**Files:**
- Create: `stackpack/suse-ai/provisioning/icons/kubeflow-pipelines.svg`

- [ ] **Step 1: Write the SVG (workflow/DAG-themed)**

```xml
<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <circle cx="14" cy="14" r="6" fill="#326DE6"/>
  <circle cx="14" cy="50" r="6" fill="#326DE6"/>
  <circle cx="32" cy="32" r="6" fill="#FB8C00"/>
  <circle cx="50" cy="14" r="6" fill="#326DE6"/>
  <circle cx="50" cy="50" r="6" fill="#326DE6"/>
  <line x1="20" y1="14" x2="26" y2="32" stroke="#326DE6" stroke-width="2"/>
  <line x1="20" y1="50" x2="26" y2="32" stroke="#326DE6" stroke-width="2"/>
  <line x1="38" y1="32" x2="44" y2="14" stroke="#FB8C00" stroke-width="2"/>
  <line x1="38" y1="32" x2="44" y2="50" stroke="#FB8C00" stroke-width="2"/>
</svg>
```

- [ ] **Step 2: Validate**

Run: `python3 -c "import xml.etree.ElementTree as ET; ET.parse('stackpack/suse-ai/provisioning/icons/kubeflow-pipelines.svg'); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add stackpack/suse-ai/provisioning/icons/kubeflow-pipelines.svg
git commit -m "feat(icons): add Kubeflow Pipelines icon"
```

---

### Task 3.3: Add Kubeflow Model Registry icon

**Files:**
- Create: `stackpack/suse-ai/provisioning/icons/kubeflow-model-registry.svg`

- [ ] **Step 1: Write the SVG (registry/library shelf)**

```xml
<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="12" width="44" height="40" rx="3" fill="none" stroke="#326DE6" stroke-width="2"/>
  <rect x="14" y="18" width="36" height="6" rx="1" fill="#326DE6"/>
  <rect x="14" y="28" width="28" height="6" rx="1" fill="#5C7CFA"/>
  <rect x="14" y="38" width="32" height="6" rx="1" fill="#91A7FF"/>
  <circle cx="48" cy="42" r="3" fill="#FB8C00"/>
</svg>
```

- [ ] **Step 2: Validate**

Run: `python3 -c "import xml.etree.ElementTree as ET; ET.parse('stackpack/suse-ai/provisioning/icons/kubeflow-model-registry.svg'); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add stackpack/suse-ai/provisioning/icons/kubeflow-model-registry.svg
git commit -m "feat(icons): add Kubeflow Model Registry icon"
```

---

## Phase 4 — Component types

Per `COMPONENT_TYPE_GUIDE.md` §2, every ComponentType needs the full `highlights` block (events, metrics, relatedResources, externalComponent, about) — missing any field fails provisioning. Use the existing `ml-registry.mlflow` block in `products.sty` (around line 600) as a structural template.

### Task 4.1: Add `inference-engine.kserve` ComponentType

**Files:**
- Modify: `stackpack/suse-ai/provisioning/templates/component-types/products.sty` — append after the existing `ml-registry.mlflow` block (around line 660 of the current file, just before the `llm-model` block).

- [ ] **Step 1: Find the insertion point**

Run: `grep -n 'ml-registry.mlflow\|"llm-model"' stackpack/suse-ai/provisioning/templates/component-types/products.sty | head -5`
Note the line numbers — insert the new ComponentType between the end of `ml-registry.mlflow` and the start of `llm-model`.

- [ ] **Step 2: Append the ComponentType**

```yaml
  - _type: "ComponentType"
    id: -5015
    identifier: "urn:stackpack:suse-ai:shared:component-type:inference-engine.kserve"
    name: "inference-engine.kserve"
    iconbase64: "data:image/svg+xml;base64,{{ include "icons/kserve.svg" "base64" }}"
    viewTypeIdentifier: "urn:stackpack:suse-ai:shared:view-type:inference-engines"
    highlights:
      _type: "ComponentTypeHighlights"
      namePlural: "kserve"
      fields:
        - _type: "ComponentTypeField"
          fieldId: "health"
          label:
            title: "Health"
          valueExtractor:
            _type: "HealthSource"
          display:
            _type: "HealthBadgeDisplay"
        - _type: "ComponentTypeField"
          fieldId: "type"
          label:
            title: "Type"
          valueExtractor:
            _type: "ComponentTypeSource"
          display:
            _type: "TagDisplay"
        - _type: "ComponentTypeField"
          fieldId: "labels"
          label:
            title: "Labels"
          valueExtractor:
            _type: "TagsSource"
          display:
            _type: "TagDisplay"
            singular: "label"
      about:
        _type: "ComponentTypeAbout"
        fields: ["health", "type", "labels"]
      events:
        _type: "ComponentTypeEvents"
        showEvents: true
      showLogs: false
      showLastChange: false
      externalComponent:
        _type: "ComponentTypeExternalComponent"
        showConfiguration: false
        showStatus: false
        externalIdSelector: ""
      relatedResources:
        - _type: "ComponentTypeRelatedResources"
          resourceType: "InferenceServices"
          title: "InferenceServices"
          stql: 'type = "otel service" and label = "suse.ai.component.name:kserve"'
        - _type: "ComponentTypeRelatedResources"
          resourceType: "service instance"
          title: "Instances"
          stql: 'type = "otel service instance" and label = "suse.ai.component.name:kserve"'
        - _type: "ComponentTypeRelatedResources"
          resourceType: "service"
          title: "Services"
          stql: 'withNeighborsOf(direction = "up", components = (type = "otel service instance" and label = "suse.ai.component.name:kserve"), levels = "1") and type = "otel service"'
      metrics:
        - _type: "ComponentTypeMetricCategory"
          name: "Performance"
          description: "Request rate, latency, and error metrics across all InferenceServices."
          bindings:
            - "urn:stackpack:suse-ai:shared:metric-binding:kserve:request-rate"
            - "urn:stackpack:suse-ai:shared:metric-binding:kserve:latency-p95"
            - "urn:stackpack:suse-ai:shared:metric-binding:kserve:error-ratio"
          defaultExpanded: true
        - _type: "ComponentTypeMetricCategory"
          name: "Runtime"
          description: "Per-step latency, queue depth, and model loading."
          bindings:
            - "urn:stackpack:suse-ai:shared:metric-binding:kserve:step-latency"
            - "urn:stackpack:suse-ai:shared:metric-binding:kserve:queue-depth"
            - "urn:stackpack:suse-ai:shared:metric-binding:kserve:model-load-duration"
          defaultExpanded: false
```

- [ ] **Step 3: Validate YAML structure**

Run: `python3 -c "import yaml; list(yaml.safe_load_all(open('stackpack/suse-ai/provisioning/templates/component-types/products.sty')))" 2>&1 | head -5`
Expected: silent success or only warnings about Handlebars `{{ }}` (these are pre-render — use `# noqa` style verification: load with custom tag handler if needed, or just confirm no structural YAML errors in the surrounding context by running):
```
python3 -c "
import re
content = open('stackpack/suse-ai/provisioning/templates/component-types/products.sty').read()
# strip handlebars before yaml.load
stripped = re.sub(r'\{\{[^}]*\}\}', '\"\"', content)
import yaml
list(yaml.safe_load_all(stripped))
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 4: Confirm ID -5015 is unique across .sty files**

Run: `grep -rn "id: -5015" stackpack/suse-ai/provisioning/templates/`
Expected: exactly one match (the line you just added).

- [ ] **Step 5: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/component-types/products.sty
git commit -m "feat(types): add inference-engine.kserve ComponentType"
```

---

### Task 4.2: Add `workflow-engine.kubeflow-pipelines` ComponentType

**Files:**
- Modify: `stackpack/suse-ai/provisioning/templates/component-types/products.sty` — append after the kserve ComponentType from Task 4.1.

- [ ] **Step 1: Append the ComponentType**

```yaml
  - _type: "ComponentType"
    id: -5016
    identifier: "urn:stackpack:suse-ai:shared:component-type:workflow-engine.kubeflow-pipelines"
    name: "workflow-engine.kubeflow-pipelines"
    iconbase64: "data:image/svg+xml;base64,{{ include "icons/kubeflow-pipelines.svg" "base64" }}"
    viewTypeIdentifier: "urn:stackpack:suse-ai:shared:view-type:workflow-engines"
    highlights:
      _type: "ComponentTypeHighlights"
      namePlural: "kubeflow-pipelines"
      fields:
        - _type: "ComponentTypeField"
          fieldId: "health"
          label:
            title: "Health"
          valueExtractor:
            _type: "HealthSource"
          display:
            _type: "HealthBadgeDisplay"
        - _type: "ComponentTypeField"
          fieldId: "type"
          label:
            title: "Type"
          valueExtractor:
            _type: "ComponentTypeSource"
          display:
            _type: "TagDisplay"
        - _type: "ComponentTypeField"
          fieldId: "labels"
          label:
            title: "Labels"
          valueExtractor:
            _type: "TagsSource"
          display:
            _type: "TagDisplay"
            singular: "label"
      about:
        _type: "ComponentTypeAbout"
        fields: ["health", "type", "labels"]
      events:
        _type: "ComponentTypeEvents"
        showEvents: true
      showLogs: false
      showLastChange: false
      externalComponent:
        _type: "ComponentTypeExternalComponent"
        showConfiguration: false
        showStatus: false
        externalIdSelector: ""
      relatedResources:
        - _type: "ComponentTypeRelatedResources"
          resourceType: "service instance"
          title: "Instances"
          stql: 'type = "otel service instance" and label = "suse.ai.component.name:kubeflow-pipelines"'
        - _type: "ComponentTypeRelatedResources"
          resourceType: "service"
          title: "Services"
          stql: 'withNeighborsOf(direction = "up", components = (type = "otel service instance" and label = "suse.ai.component.name:kubeflow-pipelines"), levels = "1") and type = "otel service"'
      metrics:
        - _type: "ComponentTypeMetricCategory"
          name: "Pipeline Runs"
          description: "Run success and failure rates."
          bindings:
            - "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:run-success-rate"
            - "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:run-failure-rate"
          defaultExpanded: true
        - _type: "ComponentTypeMetricCategory"
          name: "Control Plane"
          description: "API server, reconciler, and MLMD health metrics."
          bindings:
            - "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:api-request-rate"
            - "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:api-latency-p95"
            - "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:reconcile-lag"
            - "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:mlmd-op-rate"
          defaultExpanded: false
```

- [ ] **Step 2: Confirm ID -5016 is unique**

Run: `grep -rn "id: -5016" stackpack/suse-ai/provisioning/templates/`
Expected: exactly one match.

- [ ] **Step 3: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/component-types/products.sty
git commit -m "feat(types): add workflow-engine.kubeflow-pipelines ComponentType"
```

---

### Task 4.3: Add `ml-registry.kubeflow` ComponentType

**Files:**
- Modify: `stackpack/suse-ai/provisioning/templates/component-types/products.sty` — append after the kfp ComponentType from Task 4.2.

- [ ] **Step 1: Append the ComponentType (no metric bindings in v1)**

```yaml
  - _type: "ComponentType"
    id: -5017
    identifier: "urn:stackpack:suse-ai:shared:component-type:ml-registry.kubeflow"
    name: "ml-registry.kubeflow"
    iconbase64: "data:image/svg+xml;base64,{{ include "icons/kubeflow-model-registry.svg" "base64" }}"
    viewTypeIdentifier: "urn:stackpack:suse-ai:shared:view-type:ml-registries"
    highlights:
      _type: "ComponentTypeHighlights"
      namePlural: "kubeflow-model-registry"
      fields:
        - _type: "ComponentTypeField"
          fieldId: "health"
          label:
            title: "Health"
          valueExtractor:
            _type: "HealthSource"
          display:
            _type: "HealthBadgeDisplay"
        - _type: "ComponentTypeField"
          fieldId: "type"
          label:
            title: "Type"
          valueExtractor:
            _type: "ComponentTypeSource"
          display:
            _type: "TagDisplay"
        - _type: "ComponentTypeField"
          fieldId: "labels"
          label:
            title: "Labels"
          valueExtractor:
            _type: "TagsSource"
          display:
            _type: "TagDisplay"
            singular: "label"
      about:
        _type: "ComponentTypeAbout"
        fields: ["health", "type", "labels"]
      events:
        _type: "ComponentTypeEvents"
        showEvents: true
      showLogs: false
      showLastChange: false
      externalComponent:
        _type: "ComponentTypeExternalComponent"
        showConfiguration: false
        showStatus: false
        externalIdSelector: ""
      relatedResources:
        - _type: "ComponentTypeRelatedResources"
          resourceType: "service instance"
          title: "Instances"
          stql: 'type = "otel service instance" and label = "suse.ai.component.name:kubeflow-model-registry"'
        - _type: "ComponentTypeRelatedResources"
          resourceType: "service"
          title: "Services"
          stql: 'withNeighborsOf(direction = "up", components = (type = "otel service instance" and label = "suse.ai.component.name:kubeflow-model-registry"), levels = "1") and type = "otel service"'
      metrics: []
```

- [ ] **Step 2: Confirm ID -5017 is unique**

Run: `grep -rn "id: -5017" stackpack/suse-ai/provisioning/templates/`
Expected: exactly one match.

- [ ] **Step 3: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/component-types/products.sty
git commit -m "feat(types): add ml-registry.kubeflow ComponentType (topology-only v1)"
```

---

### Task 4.4: Add TraceBindings + SpanToComponentBindings for kserve and kfp

**Files:**
- Modify: `stackpack/suse-ai/provisioning/templates/component-types/products.sty` — append at the end of the file (after the open-webui span binding, around line 900).

Per `OPENWEBUI.md`, hardcoded URNs are acceptable when there's exactly one logical instance per cluster — which is the case for both kserve and kfp.

- [ ] **Step 1: Find the insertion point**

Run: `tail -20 stackpack/suse-ai/provisioning/templates/component-types/products.sty`
Expected: the last block is the open-webui SpanToComponentBinding. Insert after it.

- [ ] **Step 2: Append the four new bindings**

```yaml
  - _type: TraceBinding
    name: Traces for KServe
    identifier: urn:stackpack:suse-ai:shared:trace-binding:inference-engine.kserve
    filter:
      attributes:
        suse.ai.component.name: ["kserve"]
    scope: '(type = "inference-engine.kserve")'

  - _type: SpanToComponentBinding
    name: Span binding to KServe
    identifier: urn:stackpack:suse-ai:shared:span-to-component-binding:inference-engine.kserve
    urnTemplate: "urn:suse-ai:product:inference-engine:kserve"

  - _type: TraceBinding
    name: Traces for Kubeflow Pipelines
    identifier: urn:stackpack:suse-ai:shared:trace-binding:workflow-engine.kubeflow-pipelines
    filter:
      attributes:
        suse.ai.component.name: ["kubeflow-pipelines"]
    scope: '(type = "workflow-engine.kubeflow-pipelines")'

  - _type: SpanToComponentBinding
    name: Span binding to Kubeflow Pipelines
    identifier: urn:stackpack:suse-ai:shared:span-to-component-binding:workflow-engine.kubeflow-pipelines
    urnTemplate: "urn:suse-ai:product:workflow-engine:kubeflow-pipelines"
```

- [ ] **Step 3: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/component-types/products.sty
git commit -m "feat(types): add Kubeflow trace and span-to-component bindings"
```

---

## Phase 5 — Metric bindings

### Task 5.1: Create `kserve-metrics.sty`

**Files:**
- Create: `stackpack/suse-ai/provisioning/templates/metric-bindings/kserve-metrics.sty`

Per `METRIC_BINDINGS_GUIDE.md`, top-level list items in any included `.sty` file MUST start with exactly two spaces (`  - _type: ...`) so they slot under the master `nodes:` key. Do not include `nodes:` here.

- [ ] **Step 1: Write the bindings file**

```yaml
  - _type: MetricBinding
    id: -630
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kserve:request-rate"
    name: "Request Rate"
    description: "Inference requests per second per InferenceService."
    queries:
      - expression: 'sum by (service_name) (rate(revision_request_count{namespace=~".+"}[${__rate_interval}]))'
        alias: "${service_name}"
        primary: true
        unit: reqps
    chartType: line
    scope: 'type = "inference-engine.kserve"'

  - _type: MetricBinding
    id: -631
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kserve:latency-p95"
    name: "Request Latency"
    description: "P50/P95/P99 of end-to-end request latency per InferenceService."
    queries:
      - expression: 'histogram_quantile(0.99, sum by (service_name, le) (rate(revision_app_request_latencies_bucket[5m])))'
        alias: "P99"
      - expression: 'histogram_quantile(0.95, sum by (service_name, le) (rate(revision_app_request_latencies_bucket[5m])))'
        alias: "P95"
        primary: true
      - expression: 'histogram_quantile(0.50, sum by (service_name, le) (rate(revision_app_request_latencies_bucket[5m])))'
        alias: "P50"
    unit: ms
    chartType: line
    scope: 'type = "inference-engine.kserve"'

  - _type: MetricBinding
    id: -632
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kserve:step-latency"
    name: "Per-Step Latency P95"
    description: "P95 of preprocess, predict, and postprocess steps."
    queries:
      - expression: 'histogram_quantile(0.95, sum by (le) (rate(request_preprocess_seconds_bucket[5m])))'
        alias: "preprocess P95"
      - expression: 'histogram_quantile(0.95, sum by (le) (rate(request_predict_seconds_bucket[5m])))'
        alias: "predict P95"
        primary: true
      - expression: 'histogram_quantile(0.95, sum by (le) (rate(request_postprocess_seconds_bucket[5m])))'
        alias: "postprocess P95"
    unit: s
    chartType: line
    scope: 'type = "inference-engine.kserve"'

  - _type: MetricBinding
    id: -633
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kserve:queue-depth"
    name: "Queue Depth"
    description: "Maximum queue depth across InferenceService pods."
    queries:
      - expression: 'max by (service_name) (queue_depth)'
        alias: "${service_name}"
        primary: true
        unit: short
    chartType: line
    scope: 'type = "inference-engine.kserve"'

  - _type: MetricBinding
    id: -634
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kserve:model-load-duration"
    name: "Model Load Duration"
    description: "Latest model load duration in seconds."
    queries:
      - expression: 'max by (service_name) (model_load_seconds)'
        alias: "${service_name}"
        primary: true
        unit: s
    chartType: line
    scope: 'type = "inference-engine.kserve"'

  - _type: MetricBinding
    id: -635
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kserve:error-ratio"
    name: "Error Ratio"
    description: "Ratio of 5xx responses to total requests per InferenceService."
    queries:
      - expression: '(sum by (service_name) (rate(revision_request_count{response_code_class="5xx"}[5m])) or 0) / sum by (service_name) (rate(revision_request_count[5m]))'
        alias: "${service_name}"
        primary: true
        unit: percentunit
    chartType: line
    scope: 'type = "inference-engine.kserve"'
```

- [ ] **Step 2: Validate YAML and indentation**

Run:
```
python3 -c "
import yaml
content = open('stackpack/suse-ai/provisioning/templates/metric-bindings/kserve-metrics.sty').read()
# Wrap in nodes: to make it parseable as the include site sees it
wrapped = 'nodes:\n' + content
parsed = yaml.safe_load(wrapped)
assert len(parsed['nodes']) == 6, f'expected 6 bindings, got {len(parsed[\"nodes\"])}'
ids = sorted(n['id'] for n in parsed['nodes'])
assert ids == [-635, -634, -633, -632, -631, -630][::-1], f'unexpected IDs: {ids}'
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 3: Confirm IDs are unique across the project**

Run: `for id in -630 -631 -632 -633 -634 -635; do count=$(grep -rln "id: $id\b" stackpack/suse-ai/provisioning/templates/ | wc -l); echo "$id: $count"; done`
Expected: every line shows `1`.

- [ ] **Step 4: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/metric-bindings/kserve-metrics.sty
git commit -m "feat(metrics): add KServe metric bindings"
```

---

### Task 5.2: Create `kubeflow-pipelines-metrics.sty`

**Files:**
- Create: `stackpack/suse-ai/provisioning/templates/metric-bindings/kubeflow-pipelines-metrics.sty`

- [ ] **Step 1: Write the bindings file**

```yaml
  - _type: MetricBinding
    id: -640
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:api-request-rate"
    name: "API Request Rate"
    description: "HTTP/gRPC requests per second across the KFP control plane."
    queries:
      - expression: 'sum by (service) (rate(rest_client_requests_total[${__rate_interval}]))'
        alias: "${service}"
        primary: true
        unit: reqps
    chartType: line
    scope: 'type = "workflow-engine.kubeflow-pipelines"'

  - _type: MetricBinding
    id: -641
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:api-latency-p95"
    name: "API Latency P95"
    description: "P95 of REST client request duration."
    queries:
      - expression: 'histogram_quantile(0.95, sum by (verb, le) (rate(rest_client_request_duration_seconds_bucket[5m])))'
        alias: "${verb}"
        primary: true
        unit: s
    chartType: line
    scope: 'type = "workflow-engine.kubeflow-pipelines"'

  - _type: MetricBinding
    id: -642
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:run-success-rate"
    name: "Run Success Rate"
    description: "Fraction of pipeline runs that completed successfully over 15m."
    queries:
      - expression: '(sum(rate(run_server_run_count{status="Succeeded"}[15m])) or 0) / sum(rate(run_server_run_count[15m]))'
        alias: "Success ratio"
        primary: true
        unit: percentunit
    chartType: line
    scope: 'type = "workflow-engine.kubeflow-pipelines"'

  - _type: MetricBinding
    id: -643
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:run-failure-rate"
    name: "Run Failure Rate"
    description: "Pipeline runs failing per second over 15m."
    queries:
      - expression: 'sum(rate(run_server_run_count{status="Failed"}[15m]))'
        alias: "Failures/s"
        primary: true
        unit: short
    chartType: line
    scope: 'type = "workflow-engine.kubeflow-pipelines"'

  - _type: MetricBinding
    id: -644
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:reconcile-lag"
    name: "Reconcile Lag"
    description: "Maximum unfinished work age in the controller workqueue."
    queries:
      - expression: 'max(workqueue_unfinished_work_seconds)'
        alias: "Lag (s)"
        primary: true
        unit: s
    chartType: line
    scope: 'type = "workflow-engine.kubeflow-pipelines"'

  - _type: MetricBinding
    id: -645
    identifier: "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:mlmd-op-rate"
    name: "MLMD Operation Rate"
    description: "gRPC calls per second to the metadata-grpc-service."
    queries:
      - expression: 'sum by (grpc_method) (rate(grpc_server_handled_total{job=~".*metadata-grpc.*"}[5m]))'
        alias: "${grpc_method}"
        primary: true
        unit: reqps
    chartType: line
    scope: 'type = "workflow-engine.kubeflow-pipelines"'
```

- [ ] **Step 2: Validate**

Run:
```
python3 -c "
import yaml
content = open('stackpack/suse-ai/provisioning/templates/metric-bindings/kubeflow-pipelines-metrics.sty').read()
parsed = yaml.safe_load('nodes:\n' + content)
assert len(parsed['nodes']) == 6
ids = sorted(n['id'] for n in parsed['nodes'])
assert ids == [-645, -644, -643, -642, -641, -640][::-1]
print('OK')
"
```

- [ ] **Step 3: Confirm IDs are unique**

Run: `for id in -640 -641 -642 -643 -644 -645; do count=$(grep -rln "id: $id\b" stackpack/suse-ai/provisioning/templates/ | wc -l); echo "$id: $count"; done`
Expected: every line shows `1`.

- [ ] **Step 4: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/metric-bindings/kubeflow-pipelines-metrics.sty
git commit -m "feat(metrics): add Kubeflow Pipelines metric bindings"
```

---

## Phase 6 — Monitors

### Task 6.1: Create KServe monitor file and remediation hints

**Files:**
- Create: `stackpack/suse-ai/provisioning/templates/monitors/kserve/monitor.sty`
- Create: `stackpack/suse-ai/provisioning/templates/monitors/kserve/remediation-deviating.md.hbs`
- Create: `stackpack/suse-ai/provisioning/templates/monitors/kserve/remediation-critical.md.hbs`

Use the existing `templates/monitors/vllm/monitor.sty` as a structural template if needed (not shown here — the patterns below are self-contained).

- [ ] **Step 1: Create `remediation-deviating.md.hbs`**

```handlebars
**KServe inference health is deviating ({{healthState}}) on {{componentName}}.**

Current value: `{{currentValue}}` (threshold `{{threshold}}`).

Quick checks:

1. `kubectl get inferenceservice -A` — confirm services are `Ready=True`.
2. `kubectl get pods -A -l serving.kserve.io/inferenceservice` — look for restarts or `CrashLoopBackOff`.
3. Tail the runtime container of the affected service:
   `kubectl logs -n <ns> -l serving.kserve.io/inferenceservice=<name> -c kserve-container --tail=100`
4. Check the queue-proxy: `kubectl logs -n <ns> -l serving.kserve.io/inferenceservice=<name> -c queue-proxy --tail=100`.

If latency is climbing, validate that no traffic spike or model warm-up is underway.
```

- [ ] **Step 2: Create `remediation-critical.md.hbs`**

```handlebars
**KServe inference health is CRITICAL on {{componentName}}.**

Current value: `{{currentValue}}` (threshold `{{threshold}}`). Failed-request rate exceeds the critical bound.

Immediate actions:

1. `kubectl get inferenceservice <name> -n <ns> -o yaml` — inspect `status.conditions` for the failing predictor.
2. Tail kserve-container logs for stack traces.
3. If a recent deployment is at fault, roll back: `kubectl rollout undo deploy/<predictor-deployment> -n <ns>`.
4. Confirm upstream dependencies (model storage, OpenSearch/Milvus, GPU availability) are healthy.

See the full triage playbook at `knowledge/KUBEFLOW.md`.
```

- [ ] **Step 3: Create `monitor.sty`**

```yaml
  - _type: Monitor
    id: -3016
    name: "KServe High Error Rate"
    identifier: urn:stackpack:suse-ai:shared:monitor:kserve-error-rate
    description: |
      Triggers when more than 5% of requests to a KServe InferenceService
      return a 5xx response, averaged over 5 minutes.
    status: ENABLED
    intervalSeconds: 60
    tags: ["kserve", "error"]
    function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
    arguments:
      comparator: GT
      failureState: CRITICAL
      threshold: 0.05
      metric:
        query: '(sum by (service_name) (rate(revision_request_count{response_code_class="5xx"}[5m])) or 0) / sum by (service_name) (rate(revision_request_count[5m]))'
        aliasTemplate: "Error ratio"
        unit: percentunit
      titleTemplate: "KServe ${service_name} error rate exceeds 5%"
      urnTemplate: "urn:suse-ai:product:inference-engine:kserve"
    remediationHint: '{{ include "templates/monitors/kserve/remediation-critical.md.hbs" "identity" }}'

  - _type: Monitor
    id: -3017
    name: "KServe Latency P95 High"
    identifier: urn:stackpack:suse-ai:shared:monitor:kserve-latency-p95
    description: |
      Triggers when the P95 end-to-end request latency exceeds 2 seconds
      over 5 minutes.
    status: ENABLED
    intervalSeconds: 60
    tags: ["kserve", "latency"]
    function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
    arguments:
      comparator: GT
      failureState: DEVIATING
      threshold: 2.0
      metric:
        query: 'histogram_quantile(0.95, sum by (service_name, le) (rate(revision_app_request_latencies_bucket[5m])))'
        aliasTemplate: "P95 latency"
        unit: s
      titleTemplate: "KServe ${service_name} P95 latency above 2s"
      urnTemplate: "urn:suse-ai:product:inference-engine:kserve"
    remediationHint: '{{ include "templates/monitors/kserve/remediation-deviating.md.hbs" "identity" }}'

  - _type: Monitor
    id: -3018
    name: "KServe Model Load Failures"
    identifier: urn:stackpack:suse-ai:shared:monitor:kserve-model-load-failures
    description: |
      Triggers when a model load attempt fails for a KServe InferenceService.
    status: ENABLED
    intervalSeconds: 60
    tags: ["kserve", "model-load"]
    function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
    arguments:
      comparator: GT
      failureState: DEVIATING
      threshold: 0
      metric:
        query: 'sum by (service_name) (increase(model_load_seconds_count{success="false"}[5m]))'
        aliasTemplate: "Failed loads"
        unit: short
      titleTemplate: "KServe ${service_name} failed to load a model"
      urnTemplate: "urn:suse-ai:product:inference-engine:kserve"
    remediationHint: '{{ include "templates/monitors/kserve/remediation-deviating.md.hbs" "identity" }}'
```

- [ ] **Step 4: Confirm IDs are unique and includes resolve**

Run: `for id in -3016 -3017 -3018; do count=$(grep -rln "id: $id\b" stackpack/suse-ai/provisioning/templates/ | wc -l); echo "$id: $count"; done`
Expected: every line shows `1`.

Run: `ls stackpack/suse-ai/provisioning/templates/monitors/kserve/`
Expected: `monitor.sty`, `remediation-critical.md.hbs`, `remediation-deviating.md.hbs`.

- [ ] **Step 5: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/monitors/kserve/
git commit -m "feat(monitors): add KServe error, latency, and model-load monitors"
```

---

### Task 6.2: Create Kubeflow Pipelines monitor file and remediation hints

**Files:**
- Create: `stackpack/suse-ai/provisioning/templates/monitors/kubeflow-pipelines/monitor.sty`
- Create: `stackpack/suse-ai/provisioning/templates/monitors/kubeflow-pipelines/remediation-deviating.md.hbs`
- Create: `stackpack/suse-ai/provisioning/templates/monitors/kubeflow-pipelines/remediation-critical.md.hbs`

- [ ] **Step 1: Create `remediation-deviating.md.hbs`**

```handlebars
**Kubeflow Pipelines health is deviating ({{healthState}}) on {{componentName}}.**

Current value: `{{currentValue}}` (threshold `{{threshold}}`).

Quick checks:

1. `kubectl get pods -n <kubeflow-namespace> -l app.kubernetes.io/part-of=kubeflow-pipelines` — control-plane pod status.
2. Inspect the persistence agent and scheduledworkflow controller:
   `kubectl logs -n <kubeflow-namespace> deploy/ml-pipeline-persistenceagent --tail=100`
   `kubectl logs -n <kubeflow-namespace> deploy/ml-pipeline-scheduledworkflow --tail=100`
3. List recent runs: `kfp run list --max-size 20`
4. If the failure rate is climbing, look for a common pipeline definition that started failing.
```

- [ ] **Step 2: Create `remediation-critical.md.hbs`**

```handlebars
**Kubeflow Pipelines API server is CRITICAL on {{componentName}}.**

Current value: `{{currentValue}}` (threshold `{{threshold}}`).

Immediate actions:

1. `kubectl get pods -n <kubeflow-namespace> -l app=ml-pipeline` — confirm `Ready` state.
2. `kubectl describe pod -n <kubeflow-namespace> -l app=ml-pipeline` — look for OOMKilled, CrashLoopBackOff.
3. Check the database backend (MySQL/MariaDB) referenced by the api-server pod's environment.
4. Restart if hung: `kubectl rollout restart deploy/ml-pipeline -n <kubeflow-namespace>`.
```

- [ ] **Step 3: Create `monitor.sty`**

```yaml
  - _type: Monitor
    id: -3019
    name: "Kubeflow Pipelines Run Failure Rate High"
    identifier: urn:stackpack:suse-ai:shared:monitor:kfp-run-failure-rate
    description: |
      Triggers when more than 10% of pipeline runs fail over a 15-minute window.
    status: ENABLED
    intervalSeconds: 60
    tags: ["kubeflow-pipelines", "runs"]
    function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
    arguments:
      comparator: GT
      failureState: DEVIATING
      threshold: 0.10
      metric:
        query: '(sum(rate(run_server_run_count{status="Failed"}[15m])) or 0) / sum(rate(run_server_run_count[15m]))'
        aliasTemplate: "Failure ratio"
        unit: percentunit
      titleTemplate: "Kubeflow Pipelines run failure rate above 10%"
      urnTemplate: "urn:suse-ai:product:workflow-engine:kubeflow-pipelines"
    remediationHint: '{{ include "templates/monitors/kubeflow-pipelines/remediation-deviating.md.hbs" "identity" }}'

  - _type: Monitor
    id: -3020
    name: "Kubeflow Pipelines Reconcile Lag"
    identifier: urn:stackpack:suse-ai:shared:monitor:kfp-reconcile-lag
    description: |
      Triggers when the controller workqueue has unfinished work older than
      60 seconds, indicating reconciliation is falling behind.
    status: ENABLED
    intervalSeconds: 60
    tags: ["kubeflow-pipelines", "controller"]
    function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
    arguments:
      comparator: GT
      failureState: DEVIATING
      threshold: 60
      metric:
        query: 'max(workqueue_unfinished_work_seconds)'
        aliasTemplate: "Lag (s)"
        unit: s
      titleTemplate: "Kubeflow Pipelines reconcile lag above 60s"
      urnTemplate: "urn:suse-ai:product:workflow-engine:kubeflow-pipelines"
    remediationHint: '{{ include "templates/monitors/kubeflow-pipelines/remediation-deviating.md.hbs" "identity" }}'

  - _type: Monitor
    id: -3021
    name: "Kubeflow Pipelines API Server Down"
    identifier: urn:stackpack:suse-ai:shared:monitor:kfp-api-down
    description: |
      Triggers when the ml-pipeline API server scrape target is down for 5 minutes.
    status: ENABLED
    intervalSeconds: 60
    tags: ["kubeflow-pipelines", "availability"]
    function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
    arguments:
      comparator: LT
      failureState: CRITICAL
      threshold: 1
      metric:
        query: 'min(up{job="kubeflow-pipelines",service=~".*ml-pipeline.*"})'
        aliasTemplate: "up"
        unit: short
      titleTemplate: "Kubeflow Pipelines API server is down"
      urnTemplate: "urn:suse-ai:product:workflow-engine:kubeflow-pipelines"
    remediationHint: '{{ include "templates/monitors/kubeflow-pipelines/remediation-critical.md.hbs" "identity" }}'

  - _type: Monitor
    id: -3022
    name: "Kubeflow Pipelines MLMD gRPC Errors"
    identifier: urn:stackpack:suse-ai:shared:monitor:kfp-mlmd-errors
    description: |
      Triggers when the metadata-grpc-service is returning errors at a sustained rate.
    status: ENABLED
    intervalSeconds: 60
    tags: ["kubeflow-pipelines", "mlmd"]
    function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
    arguments:
      comparator: GT
      failureState: DEVIATING
      threshold: 1
      metric:
        query: 'sum(rate(grpc_server_handled_total{grpc_code!="OK",job=~".*metadata-grpc.*"}[5m]))'
        aliasTemplate: "errors/s"
        unit: short
      titleTemplate: "Kubeflow Pipelines MLMD gRPC errors elevated"
      urnTemplate: "urn:suse-ai:product:workflow-engine:kubeflow-pipelines"
    remediationHint: '{{ include "templates/monitors/kubeflow-pipelines/remediation-deviating.md.hbs" "identity" }}'
```

- [ ] **Step 4: Confirm IDs are unique**

Run: `for id in -3019 -3020 -3021 -3022; do count=$(grep -rln "id: $id\b" stackpack/suse-ai/provisioning/templates/ | wc -l); echo "$id: $count"; done`
Expected: every line shows `1`.

- [ ] **Step 5: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/monitors/kubeflow-pipelines/
git commit -m "feat(monitors): add Kubeflow Pipelines run/control-plane monitors"
```

---

## Phase 7 — Menus, view-types, and master include

### Task 7.1: Re-enable workflow-engine and ml-registry menu entries

**Files:**
- Modify: `stackpack/suse-ai/provisioning/templates/shared.sty:28,30`

- [ ] **Step 1: Read current state**

Run: `sed -n '24,33p' stackpack/suse-ai/provisioning/templates/shared.sty`
Expected: shows commented lines for `model-proxy`, `mcp-server`, `workflow-engine`, `ml-registry`.

- [ ] **Step 2: Uncomment the workflow-engine and ml-registry lines**

Replace:
```
      #- viewIdentifier: "urn:stackpack:suse-ai:shared:query-view:workflow-engine"
      #- viewIdentifier: "urn:stackpack:suse-ai:shared:query-view:ml-registry"
```
With:
```
      - viewIdentifier: "urn:stackpack:suse-ai:shared:query-view:workflow-engine"
      - viewIdentifier: "urn:stackpack:suse-ai:shared:query-view:ml-registry"
```

Leave `model-proxy` and `mcp-server` commented (out of scope per the spec).

- [ ] **Step 3: Validate YAML**

Run: `python3 -c "import yaml; list(yaml.safe_load_all(open('stackpack/suse-ai/provisioning/templates/shared.sty').read().replace('{{', 'XX').replace('}}', 'YY'))); print('OK')"`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/shared.sty
git commit -m "feat(menu): re-enable workflow-engine and ml-registry menu entries"
```

---

### Task 7.2: Add a Run Success Rate column to the workflow-engines view

**Files:**
- Modify: `stackpack/suse-ai/provisioning/templates/view-types/workflow-engines.sty`

- [ ] **Step 1: Read current `overview.columns` block**

Run: `cat stackpack/suse-ai/provisioning/templates/view-types/workflow-engines.sty`
Expected: a single ViewType (id -6008) with columns Health/Component/Service Name/Namespace/Cluster.

- [ ] **Step 2: Insert the new column between `Component` and `Service Name`**

The columns are listed under `overview.columns:`. Insert before the existing `_type: ViewTypeTableColText` for Service Name:
```yaml
        - title: "Run Success Rate"
          width: 145
          metricBindingIdentifier: "urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:run-success-rate"
          _type: ViewTypeTableColMetricBinding
```

- [ ] **Step 3: Confirm the file still parses**

Run:
```
python3 -c "
import yaml
content = open('stackpack/suse-ai/provisioning/templates/view-types/workflow-engines.sty').read()
parsed = yaml.safe_load('nodes:\n' + content)
cols = parsed['nodes'][0]['overview']['columns']
titles = [c.get('title') or c['_type'] for c in cols]
assert 'Run Success Rate' in titles, titles
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/view-types/workflow-engines.sty
git commit -m "feat(views): add Run Success Rate column to workflow-engines view"
```

---

### Task 7.3: Wire the new metric-binding and monitor files into `suse-ai.sty`

**Files:**
- Modify: `stackpack/suse-ai/provisioning/templates/suse-ai.sty:33-49`

- [ ] **Step 1: Read current includes**

Run: `cat stackpack/suse-ai/provisioning/templates/suse-ai.sty`
Expected: shows the full include list under `# Metric Bindings` and `# Monitors`.

- [ ] **Step 2: Add the new metric-binding includes**

Append to the `# Metric Bindings` section (after line 42, the last `common-metrics.sty` line):
```
{{ include "templates/metric-bindings/kserve-metrics.sty" "yaml" }}
{{ include "templates/metric-bindings/kubeflow-pipelines-metrics.sty" "yaml" }}
```

- [ ] **Step 3: Add the new monitor includes**

Append to the `# Monitors` section (after the last existing monitor include):
```
{{ include "templates/monitors/kserve/monitor.sty" "yaml" }}
{{ include "templates/monitors/kubeflow-pipelines/monitor.sty" "yaml" }}
```

- [ ] **Step 4: Confirm includes look right**

Run: `grep -E 'kserve|kubeflow' stackpack/suse-ai/provisioning/templates/suse-ai.sty`
Expected: 4 lines (2 metric-binding includes, 2 monitor includes).

- [ ] **Step 5: Commit**

```bash
git add stackpack/suse-ai/provisioning/templates/suse-ai.sty
git commit -m "feat(stackpack): wire Kubeflow metric bindings and monitors into master template"
```

---

## Phase 8 — Documentation

### Task 8.1: Add knowledge file for Kubeflow integration

**Files:**
- Create: `knowledge/KUBEFLOW.md`

- [ ] **Step 1: Write the knowledge file (mirrors `knowledge/OPENWEBUI.md` structure)**

```markdown
# Kubeflow Integration

**Current Status**: v1 — KServe and Pipelines fully integrated with metrics + traces; Model Registry topology-only.

## Overview

Kubeflow is monitored via three product components:

- `inference-engine.kserve` — aggregates all KServe InferenceServices in the cluster.
- `workflow-engine.kubeflow-pipelines` — aggregates the KFP control plane (api-server, scheduledworkflow controller, persistence agent, MLMD).
- `ml-registry.kubeflow` — Kubeflow Model Registry (topology only in v1).

## Architecture

### Discovery

Signals are collected via the SUSE AI custom OTel collector. Three new Prometheus scrape jobs in `integrations/otel-collector/otel-values.yaml`:

- `kubeflow-pipelines` — Kubernetes service discovery in `${KUBEFLOW_NAMESPACE}` (default `kubeflow`).
- `kserve-controller` — pods labeled `control-plane=kserve-controller-manager` in the `kserve` namespace.
- `kserve-inferenceservices` — pods carrying `serving.kserve.io/inferenceservice` label, port `http-usermetric` (the qpext aggregated endpoint).

### Required customer configuration

KServe InferenceServices must enable metric aggregation:

```yaml
metadata:
  annotations:
    serving.kserve.io/enable-metric-aggregation: "true"
    serving.kserve.io/enable-prometheus-scraping: "true"
```

Without these, the queue-proxy emits its own metrics on a port we don't scrape.

### Resource attribute tagging

`transform/kserve`, `transform/kubeflow-pipelines`, and `transform/kubeflow-model-registry` add:

| Key | Value |
|---|---|
| `suse.ai.managed` | `true` |
| `suse.ai.component.name` | `kserve` / `kubeflow-pipelines` / `kubeflow-model-registry` |
| `suse.ai.component.type` | `inference-engine` / `workflow-engine` / `ml-registry` |

### Topology relations

| Edge | Mechanism |
|---|---|
| `kserve → llm-model.<x>` | Existing `traces/model-relations` (auto-discovers from `gen_ai.*` spans when KServe runs vLLM/Ollama) |
| `application → kserve` | Existing `traces/provider-relations` (when app sets `gen_ai.provider.name=kserve`) |
| `kubeflow-pipelines → kserve` | New `transform/kubeflow-relations`: spans with `kserve.inference.service` attribute → `peer.service=kserve` |
| `kubeflow-pipelines → kubeflow-model-registry` | New `transform/kubeflow-relations`: spans hitting registry API → `peer.service=kubeflow-model-registry` |

## Metric bindings

Documented in `stackpack/suse-ai/provisioning/templates/metric-bindings/kserve-metrics.sty` and `kubeflow-pipelines-metrics.sty`. Highlights:

- KServe: request rate, P50/P95/P99 latency, per-step latency, queue depth, model load duration, error ratio.
- Pipelines: API request rate, API latency P95, run success ratio, run failure rate, reconcile lag, MLMD operation rate.

## Monitors

`templates/monitors/kserve/monitor.sty` and `templates/monitors/kubeflow-pipelines/monitor.sty`. The cross-cutting `-3001 GenAI Application Metric Stream Active` monitor automatically covers all three new products via `suse.ai.component.name`.

## Future work

- Custom OTel receiver in the SUSE AI collector image to poll the Kubeflow Model Registry REST API and synthesize metrics (registered_models, model_versions, registrations_total). IDs -650..-659 reserved for the resulting bindings; -3023 reserved for the registration-error-rate monitor.
- Kubeflow Notebooks, Central Dashboard, Training Operator, Katib coverage.

## Troubleshooting

### KServe InferenceService doesn't appear under "Inference Engines"

- Confirm the `serving.kserve.io/enable-metric-aggregation: "true"` annotation is set on the InferenceService.
- Confirm the qpext port name is `http-usermetric` (default for KServe ≥ v0.10).
- Check the OTel collector logs for `kserve-inferenceservices` scrape errors.

### Pipelines control plane shows no data

- Verify `KUBEFLOW_NAMESPACE` matches your install (some distributions use `kubeflow-system`).
- Confirm the four control-plane services exist: `kubectl get svc -n <namespace> | grep -E 'ml-pipeline|metadata-grpc'`.
- Some KFP versions don't expose all controller-runtime metrics — empty charts are expected then.

### Model Registry shows no metrics

This is expected in v1 — Model Registry is topology-only. K8s pod-level health comes through the K8s StackPack.
```

- [ ] **Step 2: Commit**

```bash
git add knowledge/KUBEFLOW.md
git commit -m "docs: add Kubeflow integration knowledge file"
```

---

### Task 8.2: Update customer-facing resources

**Files:**
- Modify: `stackpack/suse-ai/resources/configuration.md`
- Modify: `stackpack/suse-ai/resources/enabled.md`
- Modify: `stackpack/suse-ai/resources/detailed-overview.md`

- [ ] **Step 1: Append a Kubeflow setup section to `configuration.md`**

Append at end of file:
```markdown

## Kubeflow

To monitor Kubeflow components (Pipelines, KServe, Model Registry), update your OTel collector Helm values:

```yaml
extraEnvs:
  - name: KUBEFLOW_NAMESPACE
    value: "kubeflow"   # change if your install uses a different namespace
```

For KServe InferenceServices, enable metric aggregation on each one:

```yaml
metadata:
  annotations:
    serving.kserve.io/enable-metric-aggregation: "true"
    serving.kserve.io/enable-prometheus-scraping: "true"
```

Once aggregation is enabled, the OTel collector picks up KServe metrics through Kubernetes pod discovery on the `http-usermetric` port. No further per-InferenceService configuration is required.
```

- [ ] **Step 2: Append three product types to `enabled.md`**

Append (under whatever existing list of products is there — read the file first to match style):
```markdown
- **KServe** (`inference-engine.kserve`) — request rate, P95/P99 latency, queue depth, model-load failures across all InferenceServices.
- **Kubeflow Pipelines** (`workflow-engine.kubeflow-pipelines`) — pipeline run success/failure rates, API server latency, reconcile lag, MLMD operations.
- **Kubeflow Model Registry** (`ml-registry.kubeflow`) — topology and Kubernetes pod health (no native metrics in v1).
```

- [ ] **Step 3: Add Kubeflow to the supported-products list in `detailed-overview.md`**

Read first: `cat stackpack/suse-ai/resources/detailed-overview.md`
Then append a section in the same style (do not invent headings — match the existing structure). Likely format:
```markdown
### Kubeflow

The StackPack monitors three Kubeflow components:

- **KServe**: per-InferenceService request volume, latency percentiles, error ratio, and model-load failures.
- **Kubeflow Pipelines**: pipeline run health, control-plane API latency, MLMD operation rate.
- **Kubeflow Model Registry**: topology presence and Kubernetes-level pod health.
```

- [ ] **Step 4: Commit**

```bash
git add stackpack/suse-ai/resources/configuration.md stackpack/suse-ai/resources/enabled.md stackpack/suse-ai/resources/detailed-overview.md
git commit -m "docs(resources): document Kubeflow setup and surfaced products"
```

---

### Task 8.3: Add a release-notes entry

**Files:**
- Modify: `stackpack/suse-ai/resources/RELEASE.md`

- [ ] **Step 1: Read current RELEASE.md**

Run: `head -30 stackpack/suse-ai/resources/RELEASE.md`
Note the format used by previous entries.

- [ ] **Step 2: Prepend a new entry matching the existing format**

The version will be assigned by `task version-up` in Task 9.1, so use the placeholder string `<NEW_VERSION>` here and replace it after running `task version-up`.

Example entry to prepend:
```markdown
## <NEW_VERSION>

### Added

- Kubeflow integration: KServe (inference-engine.kserve), Kubeflow Pipelines (workflow-engine.kubeflow-pipelines), Kubeflow Model Registry (ml-registry.kubeflow).
- Re-enabled the **Workflow Engines** and **ML Registries** sidebar menu entries.
- New OTel collector scrape jobs and transforms for Kubeflow metrics and traces.
- New monitors for KServe (error rate, latency, model-load failures) and Kubeflow Pipelines (run failures, reconcile lag, API down, MLMD errors).
```

- [ ] **Step 3: Don't commit yet** — version replacement happens in the next task.

---

## Phase 9 — Version bump and final verification

### Task 9.1: Bump the StackPack version

**Files:**
- Modify: `stackpack/suse-ai/stackpack.conf` (via Taskfile)
- Modify: `stackpack/suse-ai/resources/RELEASE.md` (replace placeholder)

- [ ] **Step 1: Read current version**

Run: `grep version stackpack/suse-ai/stackpack.conf`
Expected: `version = "2.0.0"` (or similar — note exact value).

- [ ] **Step 2: Run the version-up task**

Run: `task version-up`
Expected output: `StackPack version updated to 2.0.1` (or `2.0.<n+1>` from previous).

- [ ] **Step 3: Capture the new version and replace the placeholder in RELEASE.md**

```
NEW_VERSION=$(grep 'version =' stackpack/suse-ai/stackpack.conf | cut -d'"' -f2)
sed -i "s/<NEW_VERSION>/${NEW_VERSION}/" stackpack/suse-ai/resources/RELEASE.md
grep "## ${NEW_VERSION}" stackpack/suse-ai/resources/RELEASE.md
```
Expected: prints the heading line for the new version.

- [ ] **Step 4: Commit version bump**

```bash
git add stackpack/suse-ai/stackpack.conf stackpack/suse-ai/resources/RELEASE.md
git commit -m "chore: bump stackpack version for Kubeflow integration"
```

---

### Task 9.2: ID-collision sweep across all `.sty` files

**Files:** read-only sweep — no edits expected.

- [ ] **Step 1: Run the sweep**

Run:
```
grep -rh "id: -" stackpack/suse-ai/provisioning/templates/ | grep -oE "id: -[0-9]+" | sort | uniq -d
```
Expected: empty output. Any printed ID is a duplicate that must be reassigned.

- [ ] **Step 2: If duplicates appear, resolve them and re-run** — pick a free ID from the appropriate range per `MEMORY.md`, update the `.sty` file, and update any references (component types referencing the binding URN don't change since they reference identifiers, not IDs — but other `.sty` files referencing the same numeric ID would need to change).

- [ ] **Step 3: Lint all touched Groovy files**

Run: `npm-groovy-lint stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy`
Expected: no errors.

- [ ] **Step 4: No commit needed if everything is clean.**

---

### Task 9.3: Upload, verify provisioning, and check sync output

**Files:** none — this is the integration test against a live SUSE Observability instance.

This task assumes the engineer has `sts` CLI configured against a test cluster.

- [ ] **Step 1: Upload the StackPack**

Run: `task stackpack-upload`
Expected: zip succeeds, upload succeeds, `sts stackpack upgrade` returns success. Any provisioning error here points to a malformed ComponentType or duplicate ID.

- [ ] **Step 2: Verify both syncs are running without errors**

Run: `sts topology-sync list | head -10` then `sts topology-sync describe --name "SUSE AI"` and `sts topology-sync describe --name "SUSE AI Products"`.
Expected: no error messages for either.

- [ ] **Step 3: Confirm the new ComponentTypes are registered**

Run:
```
for type in inference-engine.kserve workflow-engine.kubeflow-pipelines ml-registry.kubeflow; do
  sts component-type list -o json | jq -r '.[] | select(.name=="'"$type"'") | .name'
done
```
Expected: prints all three type names.

- [ ] **Step 4: With a test InferenceService deployed, confirm the kserve product appears**

Run (assumes kubectl context against the test cluster):
```
kubectl apply -f - <<'EOF'
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: sklearn-iris-test
  namespace: default
  annotations:
    serving.kserve.io/enable-metric-aggregation: "true"
    serving.kserve.io/enable-prometheus-scraping: "true"
spec:
  predictor:
    sklearn:
      protocolVersion: v2
      storageUri: "gs://kfserving-examples/models/sklearn/1.0/model"
EOF
```

Wait ~2 minutes, then in the SUSE Observability UI navigate to **SUSE AI → Inference Engines**.
Expected: a `kserve` product component appears. Click into it; Performance and Runtime metric categories render (data may be empty until traffic is sent).

- [ ] **Step 5: Send sample traffic and confirm metrics flow**

Send a few prediction requests and verify the Request Rate chart updates within ~30 seconds.

- [ ] **Step 6: If the test cluster has Kubeflow Pipelines installed, confirm the kfp product appears under Workflow Engines.**

- [ ] **Step 7: Take down the test InferenceService**

Run: `kubectl delete inferenceservice sklearn-iris-test -n default`

- [ ] **Step 8: Update `knowledge/CERTAINS.md` with any new verified facts learned during validation**

Per AGENTS.md §2.3: "Update this file at the end of every successful loop with **verifiable** facts only." If this loop revealed any non-obvious behavior (e.g., metric name surprises, label name differences from what the spec assumed), document them now.

- [ ] **Step 9: Commit any CERTAINS.md updates**

```bash
git add knowledge/CERTAINS.md
git commit -m "docs(knowledge): record verified Kubeflow integration facts"
```

---

## Self-Review Notes

After plan execution, the implementer should verify against the design spec:

- [ ] §3.1 (component model) — three ComponentTypes added (Tasks 4.1–4.3). ✓
- [ ] §3.3 (relations) — kserve→llm-model handled by existing pipelines, kfp→kserve and kfp→model-registry by Task 1.4. ✓
- [ ] §4.1 (env var) — Task 1.1. ✓
- [ ] §4.2 (scrape jobs) — Task 1.2. ✓
- [ ] §4.3 (transforms) — Task 1.3. ✓
- [ ] §4.4 (trace transforms) — Task 1.4. ✓
- [ ] §4.5 (customer doc) — Task 8.2 step 1. ✓
- [ ] §5.2 (sync wiring) — Tasks 2.1, 2.2. ✓
- [ ] §5.2 (icons) — Tasks 3.1–3.3. ✓
- [ ] §6 (metric bindings) — Tasks 5.1, 5.2. ✓
- [ ] §7 (monitors) — Tasks 6.1, 6.2. ✓
- [ ] §3.3 (TraceBindings/SpanToComponentBindings) — Task 4.4. ✓
- [ ] Menu re-enable — Task 7.1. ✓
- [ ] ViewType column — Task 7.2. ✓
- [ ] Master include wiring — Task 7.3. ✓
- [ ] Knowledge file — Task 8.1. ✓
- [ ] Customer docs — Task 8.2. ✓
- [ ] Release notes + version bump — Tasks 8.3, 9.1. ✓
- [ ] ID collision sweep — Task 9.2. ✓
- [ ] Live verification — Task 9.3. ✓

Spec §8 (Model Registry custom receiver) is intentionally deferred — out of scope for this plan, captured as future work.
