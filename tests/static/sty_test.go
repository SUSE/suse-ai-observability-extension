package static

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/parser"
)

// Test 1: ComponentTypes have required fields

func TestComponentTypesHaveRequiredFields(t *testing.T) {
	nodes := loadAllNodes(t)
	componentTypes := nodesByType(nodes, "ComponentType")
	require.NotEmpty(t, componentTypes, "Should find at least one ComponentType")

	// Compatibility OTel types (minimal definitions without icons)
	compatibilityTypes := map[string]bool{
		"service":          true,
		"service-instance": true,
		"pod":              true,
		"namespace":        true,
		"node":             true,
	}

	for _, ct := range componentTypes {
		// Check name field
		assert.NotEmpty(t, ct.Name, "ComponentType should have a name field in %s", ct.SourceFile)

		// Check identifier field
		assert.NotEmpty(t, ct.Identifier, "ComponentType should have an identifier field in %s", ct.SourceFile)

		// Check iconbase64 field in Raw map (skip compatibility types)
		if !compatibilityTypes[ct.Name] {
			iconbase64, exists := ct.Raw["iconbase64"]
			assert.True(t, exists, "ComponentType %q should have iconbase64 field in %s", ct.Name, ct.SourceFile)
			if exists {
				iconStr, ok := iconbase64.(string)
				assert.True(t, ok, "ComponentType %q iconbase64 should be a string in %s", ct.Name, ct.SourceFile)
				assert.NotEmpty(t, iconStr, "ComponentType %q iconbase64 should not be empty in %s", ct.Name, ct.SourceFile)
			}
		}
	}
}

// Test 2: ComponentType identifiers follow pattern

func TestComponentTypeIdentifiersFollowPattern(t *testing.T) {
	nodes := loadAllNodes(t)
	componentTypes := nodesByType(nodes, "ComponentType")
	require.NotEmpty(t, componentTypes, "Should find at least one ComponentType")

	expectedPrefix := "urn:stackpack:suse-ai:shared:component-type:"

	for _, ct := range componentTypes {
		assert.NotEmpty(t, ct.Identifier, "ComponentType should have an identifier in %s", ct.SourceFile)
		if ct.Identifier != "" {
			assert.Contains(t, ct.Identifier, expectedPrefix,
				"ComponentType %q identifier should start with %q in %s",
				ct.Name, expectedPrefix, ct.SourceFile)
		}
	}
}

// Test 3: IDs are unique across all nodes

func TestIDsAreUniqueAcrossAllNodes(t *testing.T) {
	nodes := loadAllNodes(t)

	idMap := make(map[int][]parser.STYNode)
	for _, node := range nodes {
		// Only track non-zero IDs (zero is default/unset)
		if node.ID != 0 {
			idMap[node.ID] = append(idMap[node.ID], node)
		}
	}

	// Check for duplicates
	for id, nodeList := range idMap {
		if len(nodeList) > 1 {
			t.Errorf("ID %d is used by %d nodes:", id, len(nodeList))
			for _, node := range nodeList {
				t.Errorf("  - Type: %s, Name: %q, File: %s", node.Type, node.Name, node.SourceFile)
			}
		}
	}
}

// Test 4: Identifiers are unique across all nodes

func TestIdentifiersAreUniqueAcrossAllNodes(t *testing.T) {
	nodes := loadAllNodes(t)

	identifierMap := make(map[string][]parser.STYNode)
	for _, node := range nodes {
		// Only track non-empty identifiers
		if node.Identifier != "" {
			identifierMap[node.Identifier] = append(identifierMap[node.Identifier], node)
		}
	}

	// Check for duplicates
	for identifier, nodeList := range identifierMap {
		if len(nodeList) > 1 {
			t.Errorf("Identifier %q is used by %d nodes:", identifier, len(nodeList))
			for _, node := range nodeList {
				t.Errorf("  - Type: %s, Name: %q, File: %s", node.Type, node.Name, node.SourceFile)
			}
		}
	}
}

// Test 5: Expected ComponentTypes exist

func TestExpectedComponentTypesExist(t *testing.T) {
	nodes := loadAllNodes(t)
	componentTypes := nodesByType(nodes, "ComponentType")
	require.NotEmpty(t, componentTypes, "Should find at least one ComponentType")

	// Build a map of component type names
	componentTypeNames := make(map[string]bool)
	for _, ct := range componentTypes {
		if ct.Name != "" {
			componentTypeNames[ct.Name] = true
		}
	}

	// Expected component types
	expectedTypes := []string{
		"application",
		"agent",
		"ui",
		"inference-engine",
		"vectordb",
		"model-proxy",
		"search-engine",
		"mcp-server",
		"workflow-engine",
		"ml-registry",
	}

	// Check that all expected types exist
	for _, expected := range expectedTypes {
		assert.True(t, componentTypeNames[expected],
			"Expected ComponentType with name %q to exist", expected)
	}

	t.Logf("Found %d component types: %v", len(componentTypeNames), componentTypeNames)
}
