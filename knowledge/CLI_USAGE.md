# StackState CLI Usage Guide

This document provides a summary of the StackState CLI (`sts`) usage, including available commands, subcommands, and common flags.

## Global Flags

All commands support the following global flags:

- `--api-token`: Specify the API token of the StackState server.
- `--ca-cert-base64-data`: Base64-encoded private CA or self-signed certificate data to use for SSL verification. Ignored if skip-ssl or ca-cert-path is set.
- `--ca-cert-path`: Path to a private CA or self-signed certificate file. Ignored if skip-ssl is set.
- `--config`: Override the path to the config file.
- `--context (-c)`: Override the context to use.
- `--k8s-sa-token`: Specify the Kubernetes Service Account Token.
- `--k8s-sa-token-path`: Specify the path to the Kubernetes Service Account Token.
- `--no-color`: Disable color when printing to the terminal.
- `--output (-o)`: Specify the output format (`json` or `text`).
- `--service-token`: Specify the Service token of the StackState server.
- `--skip-ssl`: Whether to skip SSL certificate verification when connecting to StackState.
- `--url`: Specify the URL of the StackState server.
- `--verbose (-v)`: Print verbose logging to the terminal to track what the CLI is doing (use multiple times to increase verbosity).
- `--help (-h)`: Show help for a command.

## Commands

### `agent`
Manage StackState agents.
- **list**: List all registered agents.

### `context`
Manage connections to different StackState servers.
- **list**: List available contexts in the config file.
- **show**: Show the current active context.
- **save**: Save a context to the local config file.
  - `--url`: StackState URL.
  - `--api-token`: API Token.
  - `--service-token`: Service Token.
  - `--api-path`: API path (default `/api`).
  - `--skip-validate`: Skip context validation.
  - `--ca-cert-path`: Path to CA certificate.
  - `--ca-cert-base64-data`: Base64 encoded CA certificate data.
  - `--skip-ssl`: Skip SSL verification.
- **set**: Set the current active context.
- **delete**: Delete a context from the local config file.
- **validate**: Validate a context.

### `completion`
Generate the autocompletion script for the specified shell.

### `dashboard` (Experimental)
Manage dashboards. Requires `STS_EXPERIMENTAL_DASHBOARD` environment variable.
- **list**: List all dashboards.
- **describe**: Describe a dashboard in StackState Templated YAML (STY) format.
  - `--id`: Dashboard ID (mutually exclusive with --identifier).
  - `--identifier`: Dashboard identifier (URN) (mutually exclusive with --id).
  - `--file (-f)`: Path to the output file.
- **clone**: Clone a dashboard.
  - `--description`: Description for the new dashboard.
  - `--scope`: Scope (`publicDashboard` or `privateDashboard`).
- **delete**: Delete a dashboard by ID or identifier.
  - `--id`: Dashboard ID (mutually exclusive with --identifier).
  - `--identifier`: Dashboard identifier (URN) (mutually exclusive with --id).
- **apply**: Create or edit a dashboard from a JSON file.
  - `--file (-f)`: Path to the JSON file.
- **edit**: Edit a dashboard.
  - `--id (-i)`: Dashboard ID (mutually exclusive with --identifier).
  - `--identifier`: Dashboard identifier (URN) (mutually exclusive with --id).

### `graph`
Manage the StackState Graph.
- **retention**: Manage data retention (Deprecated).
  - `--schedule-removal`: Schedule removal of expired data.
- **delete-expired-data**: Delete expired data (Deprecated).
  - `--immediate`: Remove immediate and restart StackState.

### `health`
Health synchronization related commands.
- **list**: List all health streams.
- **delete**: Delete a health synchronization stream.
- **clear-error**: Clear errors from a stream.
- **status**: Check status of a stream.
  - `--urn (-u)`: URN of the stream (required).
  - `--sub-stream-urn`: Status of the specific sub stream.
  - `--topology-matches`: List matched/unmatched check states.

### `license`
Manage StackState license.
- **show**: Show license information.
- **update**: Update the license.
  - `--key`: The license key.

### `monitor`
Manage monitors.
- **list**: List all monitors.
- **apply**: Create or edit a monitor from StackState Templated YAML (STY).
  - `--file (-f)`: Path to the STY file.
- **delete**: Delete a monitor.
- **run**: Run a monitor.
  - `--id`: ID of the monitor (mutually exclusive with --identifier).
  - `--identifier`: Identifier of the monitor (mutually exclusive with --id).
  - `--yes (-y)`: Save the state of the monitor run.
- **status**: Get the status of a monitor.
- **edit**: Edit a monitor.
- **disable**: Disable a monitor.
- **enable**: Enable a monitor.
- **describe**: Describe a monitor in STY format.
  - `--id (-i)`: ID of the monitor (required).
  - `--file (-f)`: Path to the output file.
- **clone**: Clone a monitor.

### `otel-component-mapping` (Experimental)
Manage Otel Component Mapping. Requires `STS_EXPERIMENTAL_OTEL_MAPPING` environment variable.
- **list**: List mappings.
- **status**: Show mapping status.

### `otel-relation-mapping` (Experimental)
Manage Otel Relation Mapping. Requires `STS_EXPERIMENTAL_OTEL_MAPPING` environment variable.
- **list**: List mappings.
- **status**: Show mapping status.

### `rbac`
Manage Role-Based Access Control (RBAC).
- **create-subject**: Create a new security subject.
  - `--subject`: Subject name.
  - `--scope`: Subject scope.
  - `--create-only`: Fail if subject exists.
- **delete-subject**: Delete a security subject.
  - `--subject`: Subject name.
- **describe-subjects**: List/describe available subjects.
  - `--subject`: Filter by subject.
- **list-permissions**: List available permissions.
- **describe-permissions**: Show permissions of a subject.
  - `--subject`: Subject name.
  - `--permission`: Filter by permission.
  - `--resource`: Filter by resource.
- **grant**: Grant a permission to a subject.
  - `--subject`: Subject name.
  - `--permission`: Permission to grant.
  - `--resource`: Resource to grant on.
- **revoke**: Revoke a permission from a subject.
  - `--subject`: Subject name.
  - `--permission`: Permission to revoke.
  - `--resource`: Resource to revoke from.

### `script`
Run scripts.
- **run**: Run an STSL script.
  - `--script`: The script content/file.
  - `--arguments-script`: Arguments for the script.
  - `--timeout (-t)`: Timeout in milliseconds.

### `service-token`
Manage service tokens.
- **create**: Create a new service token.
  - `--name (-n)`: Name of the service token (required).
  - `--roles`: Roles assigned to the token (required).
  - `--expiration`: Expiration date of the service token.
  - `--dedicatedSubject`: Create a dedicated subject for this token.
- **delete**: Delete a service token.
- **list**: List all service tokens.

### `settings`
Manage settings (export/import).
- **apply**: Apply settings from a file.
  - `--file (-f)`: Path to .sty or .stj file.
  - `--namespace`: Overwrite specific namespace.
  - `--unlocked-strategy`: Strategy for unlocked settings (`fail`, `skip`, `overwrite`).
  - `--locked-strategy`: Strategy for locked settings (`fail`, `skip`, `overwrite`).
  - `--timeout`: Timeout in seconds.
- **list-types**: List available setting types.
- **list**: List settings.
  - `--type-name`: Filter by type.
  - `--namespace`: Filter by namespace.
  - `--owned-by`: Filter by owner.
- **describe**: Describe settings in STY format.
  - `--ids`: List of IDs.
  - `--namespace`: Filter by namespace.
  - `--type`: Filter by type.
  - `--allowed-namespace-refs`: Whitelist of allowed reference namespaces.
  - `--file (-f)`: Path to the output file.
- **edit**: Edit settings.
  - `--ids`: IDs to edit (mutually exclusive with --type).
  - `--type`: Types to edit (mutually exclusive with --ids).
  - `--allowed-namespace-refs`: Whitelist of allowed reference namespaces.
  - `--locked-strategy`: Strategy for locked settings (`fail`, `skip`, `overwrite`).
  - `--unlocked-strategy`: Strategy for unlocked settings (`fail`, `skip`, `overwrite`).
  - `--timeout`: Timeout in seconds.
- **unlock**: Unlock graph nodes locked by dependencies.
  - `--ids`: IDs to unlock.
- **delete**: Delete graph nodes.
  - `--ids`: IDs to delete.
  - `--timeout`: Timeout.

### `stackpack`
Manage StackPacks.
- **list**: List available StackPacks.
  - `--installed`: Show only installed StackPacks.
- **upload**: Upload a StackPack file.
- **install**: Install a StackPack instance.
  - `--name (-n)`: Name of the StackPack (required).
  - `--parameter (-p)`: Parameters in `key=value` format.
  - `--unlocked-strategy`: Strategy for unlocked settings (`fail`, `skip`, `overwrite`, default `fail`).
  - `--wait`: Wait for installation.
  - `--timeout`: Timeout for waiting.
- **uninstall**: Uninstall a StackPack instance.
  - `--id`: Instance ID.
- **list-instances**: List installed instances.
- **list-parameters**: List required parameters.
  - `--name (-n)`: Name of the StackPack (required).
- **upgrade**: Upgrade a StackPack instance.
  - `--name (-n)`: Name of the StackPack (required).
  - `--unlocked-strategy`: Strategy for unlocked settings (`fail`, `skip`, `overwrite`).
  - `--wait`: Wait for upgrade.
  - `--timeout`: Timeout.
- **confirm-manual-steps**: Confirm manual steps.
- **describe**: Describe a StackPack.
  - `--name`: StackPack name.
Requires `STS_EXPERIMENTAL_STACKPACK` environment variable:
- **scaffold** (Experimental): Create a StackPack skeleton.
- **package** (Experimental): Package a StackPack into a zip.
- **test** (Experimental): Test a StackPack.

### `topic`
Manage Kafka topics.
- **list**: List available topics.
- **describe**: Describe a topic.
  - `--name`: Topic name.
  - `--offset`: Starting offset (default -1).
  - `--limit`: Limit of messages to show (default 10).
  - `--partition`: Kafka partition to query (default -1).
  - `--file (-f)`: The JSON output file to save the messages to.

### `topology-sync`
Manage Topology Synchronization.
- **list**: List active synchronizations.
- **clear-errors**: Clear errors from a synchronization.
  - `--id`: Synchronization ID.
  - `--identifier`: Synchronization identifier.
- **describe**: Show details of a synchronization.
  - `--id`: Synchronization ID.
  - `--identifier`: Synchronization identifier.

### `user-session`
Inspect user session.
- **roles**: Get roles for the current user session.

### `version`
Display version information.
