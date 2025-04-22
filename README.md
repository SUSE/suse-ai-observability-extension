# SUSE AI Observability Extension

[SUSE Observability](https://docs.stackstate.com) is full-stack observability platform with tons of extension and integration possibilities.

[OpenLIT SDK](https://github.com/openlit/openlit/tree/main/sdk/python) is a monitoring framework built on top of OpenTelemetry that gives you complete Observability for your AI stack, from LLMs to vector databases and GPUs, with just one line of code with tracing and metrics.

This extension expands the capabilities of SUSE Observability regarding GenAI applications. Applications instrumented with the OpenLIT SDK generate metrics and traces, that are handle by the extension to generate topology views and observability over time.

## Helm Deployment

Setup a basic genai-values.yaml containing basic information about your SUSE Observability instance.

```yaml
serverUrl:  https://xxxx.    # SUSE Observability URL. Installing this Chart within the same cluster from SUSE Observability allows you to use http://suse-observability-router.suse-observability.svc.cluster.local:8080
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

### Requirements

- [Taskfile](https://taskfile.dev/installation/)

### Build

There are two main containers in the application. One, is the runtime that handles data synchronization, while the other manages the extension's lifecycle.

```shell
task podman-build-runtime
task podman-build-setup
```
