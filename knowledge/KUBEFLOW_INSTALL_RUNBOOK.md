# Kubeflow + Observability Install Runbook

Straightforward, ordered steps to install SUSE Kubeflow and validate the
observability extension against it. Updated from the 2026-08-11 live run on the
demo cluster (RKE2 `v1.32.4+rke2r1`).

> **Credentials:** never print them. Read from
> `/home/thbertoldi/suse/suse-ai-stack/extra_vars.yml` via python (pattern in
> `/tmp/upgrade-otel.sh`). Registry keys: `application_collection_user_email` /
> `application_collection_user_token` (AppCo); SUSE registry user is `regcode`
> with a registration code as the token.

Paths on this workstation:
- Kubeflow chart + installer: `/home/thbertoldi/suse/suse-ai-charts/kubeflow/`
- Observability collector values: `integrations/otel-collector/otel-values.yaml`
  in this repository.
- Demo apps: `/home/thbertoldi/suse/suse-ai-demo-apps`.
- Kubeconfig: `/home/thbertoldi/Downloads/local - *.yaml` (quote the path).

---

## 0. Prerequisites (per cluster, do FIRST)

**Default StorageClass** — Kubeflow PVCs (`data-mysql-0`, `katib-mysql`,
`seaweedfs-pvc`) ship with no `storageClassName` and stay `Pending` forever
without a cluster default. k8s ≥1.28 binds existing Pending PVCs retroactively
once a default exists.

```bash
kubectl patch storageclass local-path \
  -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
kubectl get storageclass   # confirm local-path (default)
```

**Slow apiserver note:** the single control-plane apiserver is slow under install
load. Always pass `--request-timeout` to read-only `kubectl` calls, and expect
`helm --wait` to occasionally hang past its timeout even when all pods are
already Running (check pods directly rather than trusting the helm exit).

---

## 1. Install Kubeflow

`runMe.sh` does: helm registry logins → create `istio-system`/`kubeflow`/`knative-serving`
namespaces + pull secrets → cert-manager (optional) → Istio → External Secrets
Operator (+ CRD wait) → `helm dependency update` → Kubeflow umbrella. The final
step alone can take 15 min (~30 subcharts).

```bash
cd /home/thbertoldi/suse/suse-ai-charts/kubeflow
export KUBECONFIG="/home/thbertoldi/Downloads/local - <today>.yaml"

# Load creds from extra_vars.yml WITHOUT printing them.
eval "$(python3 - /home/thbertoldi/suse/suse-ai-stack/extra_vars.yml <<'PY'
import sys, yaml, shlex
d = yaml.safe_load(open(sys.argv[1]))
print("APPCO_USER="  + shlex.quote(str(d["application_collection_user_email"])))
print("APPCO_TOKEN=" + shlex.quote(str(d["application_collection_user_token"])))
print("SUSE_AI_TOKEN=" + shlex.quote(str(d["suse_ai_registration_code"])))
PY
)"

# --disable-cert-manager if the cluster already has cert-manager (Rancher does).
./runMe.sh "$APPCO_USER" "$APPCO_TOKEN" regcode "$SUSE_AI_TOKEN" \
  -f demo-overrides.yaml \
  --disable-cert-manager
```

- `demo-overrides.yaml` sets `global.demoMode: true` (skips credential validation)
  and demo auth/seaweedfs secrets. **Demo only** — never production.
- Default login after install: `user@example.com` / `12341234`.
- **Expected outcome:** ~41 pods Running in `kubeflow` + 6 in `knative-serving`.

### 1a. Knative version gate (WILL hit this on k8s < 1.34)

Knative Serving v1.22.0 hard-requires k8s ≥1.34; this cluster is 1.32.4, so the
`controller`/`webhook`/`activator` pods crashloop on a version check. The chart
exposes **no** values knob for it. Apply the documented override live:

```bash
kubectl set env deployment --all -n knative-serving KUBERNETES_MIN_VERSION=1.28.0
kubectl rollout status deploy -n knative-serving --timeout=180s
# all knative-serving pods should go 2/2 Running
```

⚠️ This is a live `kubectl set env` patch — a `helm upgrade`/reconcile of the
kubeflow release **reverts it**. If you re-run `runMe.sh`, re-apply this after.
(Skip entirely if tomorrow's cluster is k8s ≥1.34.)

### 1b. Helm release may show `failed`

If the last `helm upgrade` timed out (slow apiserver) the `kubeflow` release can
read `failed` / `pending-install` while every resource is actually healthy. It's
cosmetic. To reconcile to `deployed`, re-run `runMe.sh` (idempotent) — but then
redo step **1a**.

---

## 2. Deploy / upgrade the observability collector

Production path: the suse-ai-stack ansible role `opentelemetry-collector`
templates `otel-values.yaml.j2` → `helm upgrade --install`. For branch validation
use the helm upgrade directly with the branch values (`/tmp/upgrade-otel.sh`):

```bash
# Helm v4 registry login wants the HOSTNAME only (not /charts):
printf '%s' "$APPCO_TOKEN" | helm registry login dp.apps.rancher.io -u "$APPCO_USER" --password-stdin

helm upgrade opentelemetry-collector \
  oci://dp.apps.rancher.io/charts/opentelemetry-collector \
  -n observability --version 0.149.0 \
  -f integrations/otel-collector/otel-values.yaml \
  -f /tmp/otel-nopull.yaml       # see below
```

`/tmp/otel-nopull.yaml` must contain BOTH:
```yaml
global:
  imagePullSecrets: []   # ghcr image is public
image:
  registry: ""           # clear productized-chart default (see below)
```

**Image requirement:** the branch config uses `cluster_name` in the topology
exporter and needs the newer collector image. `otel-values.yaml` now pins
`ghcr.io/suse/suse-ai-opentelemetry-collector:0.156.0` (standard topology Kafka
topic name) as the **full path in `image.repository`**. ⚠️ The productized OCI
chart (`oci://dp.apps.rancher.io/charts/opentelemetry-collector` 0.149.0) **DOES
have `image.registry`, defaulting to `dp.apps.rancher.io`** — it prepends to the
repository, giving `dp.apps.rancher.io/ghcr.io/suse/...` → `ErrImagePull` ("no
basic auth credentials"). You **must** set `image.registry: ""` (as above) so
only the ghcr path is used. (Verified 2026-08-10. The upstream
`open-telemetry/opentelemetry-collector` chart has no such field.) The productized
`registry.suse.com/ai/containers/...` is not published at 0.156.0 yet, and its
`:0.149.0` is **too old** (rejects `cluster_name`) — don't pin to it.

Confirm health:
```bash
kubectl get pods -n observability -l app.kubernetes.io/name=opentelemetry-collector
# must be 1/1 Running; a CrashLoop means a config parse error (see logs)
```

The values file's `MODEL_REGISTRY_BEARER_TOKEN=demo` is only for this demo
AuthorizationPolicy. Supply it from a Secret outside a disposable demo cluster.

---

## 3. KServe namespace & scrape facts (already fixed in the branch)

The SUSE chart puts **KServe in the `kubeflow` namespace** (not `kserve`), and:

- `kserve-controller` job: pods labeled `control-plane=kserve-controller-manager`,
  cluster-wide (no ns filter). Metrics are behind **kube-rbac-proxy** on
  HTTPS `:8443` — the job uses `scheme: https` + `insecure_skip_verify` + SA-token
  `credentials_file`, and the collector clusterRole grants
  `nonResourceURLs: ["/metrics"]`.
- `kubeflow-pipelines` job: only `ml-pipeline:8888` (`http`) serves Prometheus;
  `grpc:8887`→415 and gRPC-only `metadata-grpc-service:8080`→503 are dropped by a
  `__meta_kubernetes_service_port_name` keep filter.
- `kubeflow-workflow-controller` job: discovers the Argo controller pod and
  scrapes its self-signed HTTPS metrics endpoint on port 9090. This adds workflow
  phases, operation latency, queue state, pod outcomes, retries, and errors.
- `kserve-inferenceservices` job: scrapes the **model container's own** `/metrics`
  (port 8080, via `prometheus.kserve.io/{port,path}`), **not** the
  `http-usermetric`/`aggr-metric:9088` port. Aggregation never binds on this chart
  (stock Knative queue-proxy, no qpext image).
- `http_check/model-registry`: calls the authenticated v1alpha3
  `registered_models` endpoint every 30 seconds and exports availability,
  latency, response-size, validation, and error signals.
- OTTL here must **not** use `??` (lexer rejects it). Prometheus regex is RE2 — no
  backreferences (`\1`).

---

## 4. Validate

**Layer 1 — sources serve** (`kubectl exec <pod> -- wget -qO- localhost:<port>/metrics`):
`ml-pipeline:8888`, workflow-controller `https://localhost:9090/metrics`,
kserve-controller `:8443` (needs token), and predictor `:8080`. Also call the
Model Registry v1alpha3 route with its Authorization header and expect a body
containing `"items"`.

**Layer 2 — collector scrapes clean:**
```bash
CPOD=$(kubectl get pods -n observability -l app.kubernetes.io/name=opentelemetry-collector -o jsonpath='{.items[-1].metadata.name}')
kubectl logs "$CPOD" -n observability --since=5m | grep -i 'Failed to scrape' | grep -iE 'kubeflow|kserve'
# silence = healthy. (suse-private-ai elasticsearch/qdrant DNS errors are unrelated test-env noise.)
```

**Layer 3 — metrics in SUSE Observability UI:** metrics explorer → query e.g.
`run_server_run_count`, `argo_workflows_gauge`,
`argo_workflows_pods_count_total`, `httpcheck_status`,
`controller_runtime_reconcile_total`, and `request_predict_seconds_count`.

**Layer 4 — topology/UI:** components `inference-engine.kserve`,
`workflow-engine.kubeflow-pipelines`, `ml-registry.kubeflow` render with charts.

### 4a. Run the real model lifecycle

Use the KFP profile namespace rather than the `kubeflow` control-plane namespace.
The companion demo creates the Iris dataset, trains and evaluates a model,
registers the exact KFP Model artifact, deploys that artifact to KServe, and
smoke-tests the ready revision.

```bash
cd /home/thbertoldi/suse/suse-ai-demo-apps/demo/kubeflow
python -m venv .venv
.venv/bin/pip install -r requirements.txt

export PIPELINE_TAG=demo-$(date -u +%Y%m%d-%H%M%S)
docker buildx build --platform linux/amd64 \
  -t ghcr.io/thbertoldi/suse-ai-demo-iris-pipeline:${PIPELINE_TAG} \
  --push .

kubectl -n kubeflow port-forward svc/ml-pipeline 18889:8888
```

In another terminal, set `PIPELINE_TAG` to the same value and submit:

```bash
cd /home/thbertoldi/suse/suse-ai-demo-apps/demo/kubeflow
export PIPELINE_TAG=demo-YYYYMMDD-HHMMSS  # same value as the build terminal
IRIS_PIPELINE_IMAGE=ghcr.io/thbertoldi/suse-ai-demo-iris-pipeline:${PIPELINE_TAG} \
KFP_HOST=http://127.0.0.1:18889 \
  .venv/bin/python submit.py
```

Verify the InferenceService storage URI contains the new KFP run ID, its
latest-created revision equals its latest-ready revision, and the
`suse-ai-sklearn-iris` Service selects only that revision. The predictor
ServiceAccount must retain both the S3 credential Secret and
`imagePullSecrets: [suse-ai-registry]`.

---

## 5. StackPack (upload to test the UI)

```bash
cd /home/thbertoldi/suse/suse-ai-observability-extension
task stackpack-validate
task version-up
task stackpack-upload
```
`stackpack-upload` validates IDs and Groovy, creates a version-specific archive,
uploads it, and upgrades with `--unlocked-strategy overwrite`. Never reuse a
version number.
Prereq stackpacks in the backend: `kubernetes-v2` (per cluster), `open-telemetry`,
and the declared `common` dependency.

Before declaring success:

```bash
sts topology-sync list
sts topology-sync describe --id <suse-ai-sync-id>
```

The list's error field is cumulative; the describe output is the source of
truth for current error details.

---

## Quick gotcha checklist
1. Default StorageClass set? (else PVCs Pending)
2. Knative `KUBERNETES_MIN_VERSION=1.28.0` applied? (k8s < 1.34) — re-apply after any helm reconcile
3. Collector image is `ghcr.io/suse/...:0.156.0` (full path in `image.repository` **plus `image.registry: ""`** — the productized OCI chart otherwise prepends `dp.apps.rancher.io`), not the productized `:0.149.0`
4. Workflow controller HTTPS 9090 and Model Registry HTTP check are both active
5. Real lifecycle runs in a profile namespace, not the `kubeflow` control plane
6. Predictor SA has the S3 Secret and `suse-ai-registry` pull secret
7. Stable prediction Service selects latest-created == latest-ready revision
8. `--request-timeout` on read-only kubectl when the apiserver is slow
