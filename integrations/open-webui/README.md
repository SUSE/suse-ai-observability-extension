# Open WebUI Ollama observability

`suse_ai_ollama.py` is an in-process Open WebUI Filter Function. It observes each
actual Ollama `/api/chat` provider invocation after model and backend selection.
It reuses Open WebUI's native OpenTelemetry providers, service identity and
request context. The GenAI CLIENT span contains the native aiohttp CLIENT span;
it does not invent an Ollama SERVER span.

The supported integration boundaries are:

- **0.6.41**: `open_webui.routers.ollama.send_post_request`, tested with its
  OTel Python SDK **1.33.1** baseline.
- **0.13.0**: `open_webui.routers.ollama.send_request`, tested with its OTel
  Python SDK **1.42.1**.

This is a version-specific adapter to internal functions, not a promise that
newer Open WebUI releases preserve those interfaces. Re-run the provider
lifecycle tests and a real chat before changing application versions.

Open WebUI 0.13.0 changed both response lifecycles. Its `send_request` takes
keyword-only `payload`, `stream`, `passthrough`, `api_config`, `request` and
related arguments, returns the parsed JSON object for nonstreaming chat, and
returns a `StreamingResponse` backed by `stream_wrapper` for streaming chat.
The upstream session pool releases the response when the stream ends or is
closed. Open WebUI 0.6.41 returns the parsed JSON object or a
`StreamingResponse` backed by the upstream `aiohttp` content with a background
cleanup task. The adapter observes both shapes without changing status,
headers, body bytes, stream framing or cancellation.

At install time the adapter verifies that each candidate is an async function
with an explicit required `url` and an explicit `payload` parameter. A name that
does not match is left untouched and produces one bounded diagnostic. If two
names alias the same callable, both names receive the same wrapper instead of
leaving one silently uninstrumented. If no candidate is usable, chat continues
without telemetry. Instrumentation failures never fail a chat request; they
only suppress telemetry for that call. Check the Open WebUI version against
this document, update the integration, then restart every worker.

## Installation

1. Enable native Open WebUI traces and metrics (`ENABLE_OTEL_TRACES` and
   `ENABLE_OTEL_METRICS`) and configure its OTLP exporter. Set the real
   `service.namespace` and service instance resource attributes. Kubernetes
   enrichment must use actual pod/cluster metadata.
2. In Admin Settings → Functions, create a Filter Function using the complete
   contents of `suse_ai_ollama.py`, then enable it globally or for the intended
   models. The Function depends on the application's existing OTel and Pydantic
   packages; it does not install another SDK or exporter.
3. Disable the old SUSE Pipelines filter for these same calls. If its metric
   reader is already running, changing model matches alone does not stop
   cumulative exports. Save its source/valves, remove that filter from its
   startup configuration and restart that Pipelines worker. Retain unrelated
   Pipeline filters. Check that its old telemetry stops refreshing.
4. For dependencies, configure the valves below and use a Collector containing
   the `count/suse_ai_clients` observation pipeline from the SUSE AI Collector or
   StackPack example. Without it, GenAI traces and metrics still work.

Example valves, after verifying these identities in the running cluster and
Observability topology:

```json
{
  "caller_cluster": "my-cluster",
  "caller_namespace": "frontend",
  "endpoints": [{
    "cluster": "my-cluster",
    "kubernetes_namespace": "models",
    "kubernetes_service": "ollama",
    "port": 11434,
    "service_namespace": "models",
    "service_name": "inference"
  }]
}
```

This resolves `ollama.models`, `ollama.models.svc` and
`ollama.models.svc.cluster.local` to the already discovered OTel service
`models/inference`. `dns_domain` can override `cluster.local`. A short `ollama`
name resolves only from the target's actual Kubernetes namespace. The address
and port come from the selected provider URL, not from requested model metadata.
Unknown, ambiguous or cross-cluster registry matches emit no peer identity.
The registry does not create target services, instances or Kubernetes metadata.

The three `suse.ai.peer.service.name`, `suse.ai.peer.service.namespace` and
`suse.ai.peer.cluster` attributes appear only on the provider CLIENT span. The
Collector verifies the caller cluster, emits a per-batch delta observation and
normalizes it to `suse.ai.service.calls`. The existing relation mapping handles
both resolved calls and paired servicegraph observations, so a paired trace does
not create another logical edge. These gauges are topology observations, not a
request-volume metric: both sources can observe the same call. Use the GenAI
duration histogram count for provider-operation counts.

Native OTel service identifiers remain `namespace + service name`; they do not
include cluster. Equal logical names/namespaces across clusters can merge before
this adapter runs. Use distinct logical namespaces where isolation is required;
the endpoint resolver does not repair that platform identity limitation.

## Lifecycle and data

Each provider invocation owns its own state, independent of chat IDs and
completion callbacks. Duration is measured in seconds from provider request to
nonstreaming response, stream exhaustion, failure or cancellation. HTTP errors,
truncated streams and cancellation produce error outcomes. Only reported token
usage is recorded; missing usage is omitted. Streaming content is forwarded
unchanged, with a bounded buffer for reading final Ollama NDJSON usage. On
0.13.0, nonstreaming responses are parsed before the adapter finalizes the
operation; on both surfaces, a stream that is never consumed is finalized as a
cancellation by the response background cleanup.

The adapter records model, provider, endpoint, operation, outcome and reported
usage. It does not capture prompts, generated content, credentials, chat/message
IDs or arbitrary prices. Local models do not receive invented cost metrics.
Open WebUI background title/tag requests are separate provider operations when
they invoke this boundary, and are counted separately from the visible turn.

Changing valves affects subsequent requests immediately. **Changing Function
source requires restarting every Open WebUI worker**: module reload intentionally
retains the first installed wrapper to avoid stacked instrumentation. Save the
Function update, drain/pause demo traffic, restart the workers using the existing
deployment procedure, then resume traffic and verify a fresh trace. The native
service ID stays stable; a replacement pod must use its real new instance ID.
Disabling the Function stops new observations; restart workers to remove the
patch and stop the SDK exporting its existing cumulative metric series.

For removal, disable/delete this Function, restart Open WebUI, then remove the
optional Collector count connector from both pipeline references. Restore the
saved Pipelines filter only if that earlier integration is required. Avoid
enabling both exporters for the same calls.

## Validation

Run the same lifecycle suite against both supported SDK baselines:

```bash
python3 -m venv /tmp/webui-integration-tests-0.6
/tmp/webui-integration-tests-0.6/bin/pip install -r integrations/open-webui/tests/requirements.txt
PATH=/tmp/webui-integration-tests-0.6/bin:$PATH task open-webui-test

python3 -m venv /tmp/webui-integration-tests-0.13
/tmp/webui-integration-tests-0.13/bin/pip install -r integrations/open-webui/tests/requirements-0.13.0.txt
PATH=/tmp/webui-integration-tests-0.13/bin:$PATH task open-webui-test-0.13
```

CI runs the same test suite in both pinned environments through
`.github/workflows/open-webui-integration.yml` when this integration changes.

The tests use real OTel SDKs, native aiohttp instrumentation and streaming
responses. They cover both `send_post_request` and `send_request`: exact
operation/token totals, nonstreaming and streaming success, native parent-child
spans, overlap, cancellation, repeated cleanup, unconsumed and truncated
streams, HTTP errors, optional future keyword arguments, unsupported routers,
invalid/unknown endpoints and scoped resolution. Live acceptance additionally
requires backend relation composition, idle expiry, actual monitor evaluation
and browser/API chats. Client telemetry does not populate Ollama's own server
metrics or create its missing instance.

For a 0.13.0 acceptance check, send one nonstreaming and one streaming chat,
then cancel a streaming answer and trigger one provider error (for example,
stop the Ollama backend or request an unknown model). Verify one
`chat <model>` CLIENT span and one duration count per real `/api/chat` call,
token attributes only when Ollama reports them, no prompt/completion/credential
attributes, and unchanged client-visible status, body and stream. Repeat after
a worker restart and with one background title/tag request. Instrumentation is
scoped to POST `/api/chat`; other Ollama endpoints and methods are untouched.
