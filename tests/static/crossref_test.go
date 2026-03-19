package static

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// walkForBindingRefs recursively walks through nested maps and slices to find
// strings containing "metric-binding".
func walkForBindingRefs(data interface{}, refs map[string]bool) {
	switch v := data.(type) {
	case map[string]interface{}:
		for _, val := range v {
			walkForBindingRefs(val, refs)
		}
	case []interface{}:
		for _, item := range v {
			if s, ok := item.(string); ok && strings.Contains(s, "metric-binding") {
				refs[s] = true
			}
			walkForBindingRefs(item, refs)
		}
	case string:
		if strings.Contains(v, "metric-binding") {
			refs[v] = true
		}
	}
}

// TestMetricBindingIdentifiersReferencedByComponentTypes verifies that
// MetricBinding identifiers are actually referenced by ComponentType definitions.
func TestMetricBindingIdentifiersReferencedByComponentTypes(t *testing.T) {
	nodes := loadAllNodes(t)

	// Collect all MetricBinding identifiers
	metricBindings := nodesByType(nodes, "MetricBinding")
	require.NotEmpty(t, metricBindings, "Should find at least one MetricBinding")

	metricBindingIdentifiers := make(map[string]bool)
	for _, mb := range metricBindings {
		if mb.Identifier != "" {
			metricBindingIdentifiers[mb.Identifier] = true
		}
	}
	require.NotEmpty(t, metricBindingIdentifiers, "MetricBindings should have identifiers")

	// Collect references from ComponentTypes
	componentTypes := nodesByType(nodes, "ComponentType")
	require.NotEmpty(t, componentTypes, "Should find at least one ComponentType")

	bindingRefs := make(map[string]bool)
	for _, ct := range componentTypes {
		walkForBindingRefs(ct.Raw, bindingRefs)
	}

	// Verify that at least some MetricBinding identifiers are referenced
	referencedCount := 0
	for ref := range bindingRefs {
		if metricBindingIdentifiers[ref] {
			referencedCount++
		}
	}

	assert.Greater(t, referencedCount, 0,
		"At least some MetricBinding identifiers should be referenced by ComponentTypes")

	t.Logf("Found %d MetricBindings, %d binding references in ComponentTypes, %d matched",
		len(metricBindingIdentifiers), len(bindingRefs), referencedCount)
}

// TestSyncNodeIDsAreInExpectedRange verifies that sync-related nodes have IDs
// between -1200 and -10 (inclusive).
func TestSyncNodeIDsAreInExpectedRange(t *testing.T) {
	nodes := loadAllNodes(t)

	// Define the types to check and their expected ID range
	syncTypes := []string{
		"DataSource",
		"Sync",
		"IdExtractorFunction",
		"ComponentMappingFunction",
		"ComponentTemplateFunction",
		"RelationTemplateFunction",
	}

	minID := -1200
	maxID := -10

	for _, typeName := range syncTypes {
		typeNodes := nodesByType(nodes, typeName)
		if len(typeNodes) == 0 {
			t.Logf("No nodes found for type %s (skipping)", typeName)
			continue
		}

		for _, node := range typeNodes {
			assert.LessOrEqual(t, node.ID, maxID,
				"%s %q (file: %s) ID should be <= %d, got %d",
				typeName, node.Name, node.SourceFile, maxID, node.ID)

			assert.GreaterOrEqual(t, node.ID, minID,
				"%s %q (file: %s) ID should be >= %d, got %d",
				typeName, node.Name, node.SourceFile, minID, node.ID)
		}

		t.Logf("Verified %d %s nodes have IDs in range [%d, %d]",
			len(typeNodes), typeName, minID, maxID)
	}
}
