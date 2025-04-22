# SUSE AI Observability Extension

[SUSE Observability](https://docs.stackstate.com) is full-stack observability platform with tons of extension and integration possibilities.

[OpenLIT SDK](https://github.com/openlit/openlit/tree/main/sdk/python) is a monitoring framework built on top of OpenTelemetry that gives you complete Observability for your AI stack, from LLMs to vector databases and GPUs, with just one line of code with tracing and metrics.

## Helm Deployment

Setup a basic genai-values.yaml containing connectivity information about your SUSE Observability instance.

```yaml
serverUrl:  https://xxxx.    # SUSE Observability URL. Installing this Chart along SUSE Observability allows you to use http://suse-observability-router.suse-observability.svc.cluster.local:8080
apiKey: xxx                  # SUSE Observability API Key
apiToken: xxx                # SUSE Observability CLI Token
clusterName: lab             # Cluster name as defined for the Kubernetes StackPack instance in SUSE Observability
```

Then run the following Helm commands,

```bash
helm upgrade --install --namespace so-extensions --create-namespace -f genai_values.yaml suse-ai-observability ./helm

```

## Configuration

### Environment variables

Environment variables can be used to set up the scanner.

| Variable                     | Required | Default | Description                                      |
|------------------------------|----------|---------|--------------------------------------------------|
| STACKSTATE_API_URL           | yes      |         | The URL to the StackState server                 |
| STACKSTATE_API_KEY           | yes      |         | The API key used by the StackState server        |
| KUBERNETES_CLUSTER           | yes      |         | Kubernetes Cluster name as defined in StackState |
| KUBERNETES_QUERYTIMEINTERVAL | yes      | 1h      | Promql interval query over.                      |
| INSTANCE_TYPE                | yes      | openlit | The Custom Sync StackPack instance type.          |
| INSTANCE_URL                 | yes      |         | The Custom Sync StackPack instance url            |


## Development

### Prerequisites

- [Taskfile](https://taskfile.dev/installation/)


### Setup environment variables

Set up a `.env` file for configuring the env.

```
STS_URL=https://myinstance.stackstate.io
STS_API_KEY=xxxx
```
### Build

There are two containers. One, is the runtime (for data sync) and the other one is the setup (for UI).
```shell
task podman-build-runtime
task podman-build-setup
```
