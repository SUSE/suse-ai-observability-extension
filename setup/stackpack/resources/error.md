## Error

An error occurred while installing or configuring the StackPack.

### Common Issues

1. **Missing Dependencies**: Ensure the `common` StackPack (v3.4.2 or later) is installed
2. **Invalid Cluster Name**: The Kubernetes cluster name must contain only lowercase letters, numbers, dots, and dashes
3. **Dependency Installation Failed**: Check if the `open-telemetry` or `kubernetes-v2` StackPacks can be installed independently
4. **Resource Conflicts**: Another StackPack may have conflicting resource identifiers

