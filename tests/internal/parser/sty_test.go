package parser

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/testutil"
)

func TestExtractIncludes(t *testing.T) {
	content := `nodes:
{{ include "templates/shared.sty" "yaml" }}
{{ include "templates/component-types/genai-app.sty" "yaml" }}
`
	includes := ExtractIncludes(content)
	require.Len(t, includes, 2)
	assert.Equal(t, "templates/shared.sty", includes[0].Path)
	assert.Equal(t, "yaml", includes[0].Format)
	assert.Equal(t, "templates/component-types/genai-app.sty", includes[1].Path)
	assert.Equal(t, "yaml", includes[1].Format)
}

func TestExtractIncludes_WithIdentityFormat(t *testing.T) {
	content := `{{ include "templates/monitors/vllm/remediation-gpu-cache.md.hbs" "identity" }}`
	includes := ExtractIncludes(content)
	require.Len(t, includes, 1)
	assert.Equal(t, "templates/monitors/vllm/remediation-gpu-cache.md.hbs", includes[0].Path)
	assert.Equal(t, "identity", includes[0].Format)
}

func TestExtractIncludes_WithGroovyScript(t *testing.T) {
	content := `{{ include "templates/path.groovy" }}`
	includes := ExtractIncludes(content)
	require.Len(t, includes, 1)
	assert.Equal(t, "templates/path.groovy", includes[0].Path)
	assert.Equal(t, "", includes[0].Format)
}

func TestParseSTYNodes(t *testing.T) {
	content := `- _type: ComponentType
  identifier: "urn:stackpack:suse-ai:shared:component-type:application"
  name: "application"
  iconbase64: "data:image/svg+xml;base64,abc123"

- _type: MetricBinding
  id: -501
  name: End-to-End Request Latency
  identifier: urn:stackpack:suse-ai:shared:metric-binding:vllm:e2e-latency
  scope: type = "inference-engine.vllm"
`
	nodes, err := ParseSTYNodes(content)
	require.NoError(t, err)
	require.Len(t, nodes, 2)

	assert.Equal(t, "ComponentType", nodes[0].Type)
	assert.Equal(t, "application", nodes[0].Name)
	assert.Equal(t, "urn:stackpack:suse-ai:shared:component-type:application", nodes[0].Identifier)
	assert.Equal(t, 0, nodes[0].ID)
	assert.Equal(t, "", nodes[0].Scope)

	assert.Equal(t, "MetricBinding", nodes[1].Type)
	assert.Equal(t, "End-to-End Request Latency", nodes[1].Name)
	assert.Equal(t, -501, nodes[1].ID)
	assert.Equal(t, `type = "inference-engine.vllm"`, nodes[1].Scope)
}

func TestParseSTYNodes_WithDirectives(t *testing.T) {
	// Test that directives are properly stripped, including ones with } in strings
	content := `- _type: Monitor
  id: -3007
  name: vLLM High GPU Cache Usage
  function: {{ get "urn:stackpack:common:monitor-function:threshold" }}
  remediationHint: {{ include "templates/monitors/vllm/remediation-gpu-cache.md.hbs" "identity" }}
`
	nodes, err := ParseSTYNodes(content)
	require.NoError(t, err)
	require.Len(t, nodes, 1)

	assert.Equal(t, "Monitor", nodes[0].Type)
	assert.Equal(t, "vLLM High GPU Cache Usage", nodes[0].Name)
	assert.Equal(t, -3007, nodes[0].ID)
}

func TestParseSTYNodes_WithNodesPrefix(t *testing.T) {
	// Test that "nodes:" prefix is stripped
	content := `nodes:
- _type: ComponentType
  name: "test"
`
	nodes, err := ParseSTYNodes(content)
	require.NoError(t, err)
	require.Len(t, nodes, 1)
	assert.Equal(t, "ComponentType", nodes[0].Type)
	assert.Equal(t, "test", nodes[0].Name)
}

func TestLoadAllSTYNodes(t *testing.T) {
	templatesDir := testutil.TemplatesDir()
	nodes, err := LoadAllSTYNodes(templatesDir)
	require.NoError(t, err)
	assert.NotEmpty(t, nodes)

	// Should find known types
	types := make(map[string]int)
	for _, n := range nodes {
		types[n.Type]++
	}

	t.Logf("Found %d nodes across %d types", len(nodes), len(types))
	for typeName, count := range types {
		t.Logf("  %s: %d", typeName, count)
	}

	assert.True(t, types["ComponentType"] > 0, "Should find ComponentType nodes")
	assert.True(t, types["MetricBinding"] > 0, "Should find MetricBinding nodes")
	assert.True(t, types["Monitor"] > 0, "Should find Monitor nodes")

	// Verify that each node has a SourceFile set
	for _, n := range nodes {
		assert.NotEmpty(t, n.SourceFile, "Node should have SourceFile set")
	}

	// Verify we're not parsing the master file (suse-ai.sty)
	for _, n := range nodes {
		assert.NotContains(t, n.SourceFile, "suse-ai.sty", "Should not parse master file")
	}
}

func TestLoadAllSTYNodes_SkipsInvalidYAML(t *testing.T) {
	// This test verifies that files that fail YAML parsing are silently skipped
	// (some files are primarily include containers)
	templatesDir := testutil.TemplatesDir()
	nodes, err := LoadAllSTYNodes(templatesDir)
	require.NoError(t, err)
	// Should succeed even if some files can't be parsed
	assert.NotEmpty(t, nodes)
}
