package static

import (
	"fmt"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/parser"
)

func TestMetricBindingIDRanges(t *testing.T) {
	nodes := loadAllNodes(t)
	bindings := nodesByType(nodes, "MetricBinding")
	require.NotEmpty(t, bindings, "Should find at least one MetricBinding")

	for _, binding := range bindings {
		assert.Less(t, binding.ID, 0,
			"MetricBinding %q (identifier: %s, file: %s) should have negative ID, got %d",
			binding.Name, binding.Identifier, binding.SourceFile, binding.ID)
	}
}

func TestMetricBindingIDsDoNotOverlap(t *testing.T) {
	nodes := loadAllNodes(t)
	bindings := nodesByType(nodes, "MetricBinding")
	require.NotEmpty(t, bindings, "Should find at least one MetricBinding")

	idMap := make(map[int][]parser.STYNode)
	for _, binding := range bindings {
		idMap[binding.ID] = append(idMap[binding.ID], binding)
	}

	var duplicates []string
	for id, nodes := range idMap {
		if len(nodes) > 1 {
			var files []string
			for _, node := range nodes {
				files = append(files, fmt.Sprintf("%s (%s)", node.Name, node.SourceFile))
			}
			duplicates = append(duplicates, fmt.Sprintf("ID %d: %s", id, strings.Join(files, ", ")))
		}
	}

	assert.Empty(t, duplicates, "Found duplicate MetricBinding IDs:\n%s", strings.Join(duplicates, "\n"))
}

func TestMetricBindingsHaveRequiredFields(t *testing.T) {
	nodes := loadAllNodes(t)
	bindings := nodesByType(nodes, "MetricBinding")
	require.NotEmpty(t, bindings, "Should find at least one MetricBinding")

	for _, binding := range bindings {
		// Check name
		assert.NotEmpty(t, binding.Name,
			"MetricBinding (identifier: %s, file: %s) should have a name",
			binding.Identifier, binding.SourceFile)

		// Check identifier
		assert.NotEmpty(t, binding.Identifier,
			"MetricBinding %q (file: %s) should have an identifier",
			binding.Name, binding.SourceFile)

		// Check ID is non-zero
		assert.NotZero(t, binding.ID,
			"MetricBinding %q (identifier: %s, file: %s) should have a non-zero ID",
			binding.Name, binding.Identifier, binding.SourceFile)

		// Check queries field exists in Raw
		queries, hasQueries := binding.Raw["queries"]
		assert.True(t, hasQueries,
			"MetricBinding %q (identifier: %s, file: %s) should have queries field",
			binding.Name, binding.Identifier, binding.SourceFile)

		if hasQueries {
			assert.NotNil(t, queries,
				"MetricBinding %q (identifier: %s, file: %s) queries field should not be nil",
				binding.Name, binding.Identifier, binding.SourceFile)
		}
	}
}

func TestMetricBindingIdentifiersFollowPattern(t *testing.T) {
	nodes := loadAllNodes(t)
	bindings := nodesByType(nodes, "MetricBinding")
	require.NotEmpty(t, bindings, "Should find at least one MetricBinding")

	expectedPrefix := "urn:stackpack:suse-ai:shared:metric-binding:"

	for _, binding := range bindings {
		assert.True(t,
			strings.HasPrefix(binding.Identifier, expectedPrefix),
			"MetricBinding %q (file: %s) identifier %q should start with %q",
			binding.Name, binding.SourceFile, binding.Identifier, expectedPrefix)
	}
}

func TestMetricBindingScopesReferenceValidTypes(t *testing.T) {
	nodes := loadAllNodes(t)
	bindings := nodesByType(nodes, "MetricBinding")
	require.NotEmpty(t, bindings, "Should find at least one MetricBinding")

	for _, binding := range bindings {
		// Only check bindings that have a non-empty scope
		if binding.Scope != "" {
			// Verify scope has some valid format (not just whitespace)
			trimmedScope := strings.TrimSpace(binding.Scope)
			assert.NotEmpty(t, trimmedScope,
				"MetricBinding %q (identifier: %s, file: %s) has scope but it's empty after trimming",
				binding.Name, binding.Identifier, binding.SourceFile)

			// Basic sanity check: scope should contain a valid operator (=, in, IN, AND, and, OR, or)
			// This is a light validation to ensure the scope has some structure
			upperScope := strings.ToUpper(trimmedScope)
			hasValidOperator := strings.Contains(trimmedScope, "=") ||
				strings.Contains(upperScope, "IN") ||
				strings.Contains(upperScope, "AND") ||
				strings.Contains(upperScope, "OR")

			assert.True(t, hasValidOperator,
				"MetricBinding %q (identifier: %s, file: %s) scope %q should contain a valid operator (=, in/IN, and/AND, or/OR)",
				binding.Name, binding.Identifier, binding.SourceFile, binding.Scope)
		}
	}
}
