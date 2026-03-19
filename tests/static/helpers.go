package static

import (
	"testing"

	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/parser"
	"suse-ai-extension-tests/internal/testutil"
)

// loadAllNodes loads all STY nodes from the templates directory.
func loadAllNodes(t *testing.T) []parser.STYNode {
	t.Helper()
	nodes, err := parser.LoadAllSTYNodes(testutil.TemplatesDir())
	require.NoError(t, err)
	require.NotEmpty(t, nodes)
	return nodes
}

// nodesByType filters nodes by their _type field.
func nodesByType(nodes []parser.STYNode, typeName string) []parser.STYNode {
	var result []parser.STYNode
	for _, n := range nodes {
		if n.Type == typeName {
			result = append(result, n)
		}
	}
	return result
}
