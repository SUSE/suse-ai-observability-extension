# Kubeflow + Observability Install Runbook

Straightforward, ordered steps to install SUSE Kubeflow and validate the
observability extension against it. Distilled from the 2026-08-04 live run on the
demo cluster (RKE2 `v1.32.4+rke2r1`). Every gotcha below actually bit us — follow
the order and they won't.

> **Credentials:** never print them. Read from
> `/home/thbertoldi/suse/suse-ai-stack/extra_vars.yml` via python (pattern in
> `/tmp/upgrade-otel.sh`). Registry keys: `application_collection_user_email` /
> `application_collection_user_token` (AppCo); SUSE registry user is `regcode`
> with a registration code as the token.

Paths on this workstation:
- Kubeflow chart + installer: `/home/thbertoldi/suse/suse-ai-charts/kubeflow/`
- Observability collector values: `integrations/otel-collector/otel-values.yaml` (this repo, branch `feat/kubeflow-monitoring`)
- Kubeconfig: `~/Downloads/local - *.yaml` (export `KUBECONFIG`)

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
  -f /tmp/otel-nopull.yaml       # global.imagePullSecrets: [] (ghcr image is public)
```

**Image requirement:** the branch config uses `cluster_name` in the topology
exporter and needs the newer collector image. `otel-values.yaml` now pins
`ghcr.io/suse/suse-ai-opentelemetry-collector:0.156.0` (standard topology Kafka
topic name). Put the **full path in `image.repository`** — the upstream chart
has no `image.registry` field, so `registry: ghcr.io` is ignored and the image
defaults to `docker.io` (→ `ImagePullBackOff`). The productized
`registry.suse.com/ai/containers/...` is not published at 0.156.0 yet, and its
`:0.149.0` is **too old** (rejects `cluster_name`) — don't pin to it.

Confirm health:
```bash
kubectl get pods -n observability -l app.kubernetes.io/name=opentelemetry-collector
# must be 1/1 Running; a CrashLoop means a config parse error (see logs)
```

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
- `kserve-inferenceservices` job: scrapes the **model container's own** `/metrics`
  (port 8080, via `prometheus.kserve.io/{port,path}`), **not** the
  `http-usermetric`/`aggr-metric:9088` port. Aggregation never binds on this chart
  (stock Knative queue-proxy, no qpext image).
- OTTL here must **not** use `??` (lexer rejects it). Prometheus regex is RE2 — no
  backreferences (`\1`).

---

## 4. Validate

**Layer 1 — sources serve** (`kubectl exec <pod> -- wget -qO- localhost:<port>/metrics`):
`ml-pipeline:8888`, kserve-controller `:8443` (needs token), predictor `:8080`.

**Layer 2 — collector scrapes clean:**
```bash
CPOD=$(kubectl get pods -n observability -l app.kubernetes.io/name=opentelemetry-collector -o jsonpath='{.items[-1].metadata.name}')
kubectl logs "$CPOD" -n observability --since=5m | grep -i 'Failed to scrape' | grep -iE 'kubeflow|kserve'
# silence = healthy. (suse-private-ai elasticsearch/qdrant DNS errors are unrelated test-env noise.)
```

**Layer 3 — metrics in SUSE Observability UI:** metrics explorer → query e.g.
`run_server_run_count`, `controller_runtime_reconcile_total`, `request_predict_seconds_count`.

**Layer 4 — topology/UI:** components `inference-engine.kserve`,
`workflow-engine.kubeflow-pipelines`, `ml-registry.kubeflow` render with charts.

### 4a. Sample InferenceService (to exercise serving metrics)

The KServe pod-mutator webhook skips namespaces labeled `control-plane`
(the `kubeflow` ns is one) — so the storage-initializer is NOT injected there.
**Deploy the sample in a fresh namespace** (e.g. `kserve-test`), and add the
`suse-ai-registry` pull secret to the predictor ServiceAccount if you hit
`ImagePullBackOff`.

```yaml
# /tmp/sklearn-iris-sl.yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: sklearn-iris
  namespace: kserve-test
  annotations:
    serving.kserve.io/enable-prometheus-scraping: "true"
    autoscaling.knative.dev/min-scale: "1"
spec:
  predictor:
    model:
      modelFormat: {name: sklearn}
      storageUri: gs://kfserving-examples/models/sklearn/1.0/model
```

Drive traffic, then confirm `request_predict_seconds_count` climbs on the
predictor's `:8080/metrics`. **Cleanup:** `kubectl delete ns kserve-test`.

---

## 5. Stackpack (upload to test the UI)

```bash
cd stackpack/suse-ai
# task version-up   # bump patch first if the UI rejects a duplicate version
zip -r /tmp/suse-ai.sts stackpack.conf provisioning resources
# then upload /tmp/suse-ai.sts via the SUSE Observability UI (StackPacks → SUSE AI Observability → Upload)
```
Run `python3 scripts/check-id-conflicts.py` first — IDs must be unique.
Prereq stackpacks in the backend: `kubernetes-v2` (per cluster), `open-telemetry`,
and the declared `common` dependency.

---

## Quick gotcha checklist
1. Default StorageClass set? (else PVCs Pending)
2. Knative `KUBERNETES_MIN_VERSION=1.28.0` applied? (k8s < 1.34) — re-apply after any helm reconcile
3. Collector image is `ghcr.io/suse/...:0.156.0` (full path in `image.repository`; chart has no `registry` field), not the productized `:0.149.0`
4. Sample InferenceService in a NON-`kubeflow` namespace (webhook skips `control-plane` ns)
5. Predictor SA has `suse-ai-registry` pull secret if ImagePullBackOff
6. `--request-timeout` on all read-only kubectl (slow apiserver)
