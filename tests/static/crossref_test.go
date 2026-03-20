package static

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

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

func TestMetricBindingIdentifiersReferencedByComponentTypes(t *testing.T) {
	nodes := loadAllNodes(t)

	metricBindings := nodesByType(nodes, "MetricBinding")
	require.NotEmpty(t, metricBindings, "Should find at least one MetricBinding")

	metricBindingIdentifiers := make(map[string]bool)
	for _, mb := range metricBindings {
		if mb.Identifier != "" {
			metricBindingIdentifiers[mb.Identifier] = true
		}
	}

	componentTypes := nodesByType(nodes, "ComponentType")
	require.NotEmpty(t, componentTypes, "Should find at least one ComponentType")

	bindingRefs := make(map[string]bool)
	for _, ct := range componentTypes {
		walkForBindingRefs(ct.Raw, bindingRefs)
	}

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
