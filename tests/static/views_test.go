package static

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Test 1: ViewType entries exist for all expected views

func TestViewTypesExist(t *testing.T) {
	nodes := loadAllNodes(t)
	viewTypes := nodesByType(nodes, "ViewType")
	require.NotEmpty(t, viewTypes, "Should find at least one ViewType")

	// Build a map of view type names
	viewTypeNames := make(map[string]bool)
	for _, vt := range viewTypes {
		if vt.Name != "" {
			viewTypeNames[vt.Name] = true
		}
	}

	// Expected view type names
	expectedViewTypes := []string{
		"AI Applications",
		"All GenAI Components",
		"Inference Engines",
		"Vector Databases",
		"Model Proxies",
		"Search Engines",
		"MCP Servers",
		"Workflow Engines",
		"ML Registries",
		"LLM Models",
		"GPU Nodes",
	}

	// Check that all expected view types exist
	for _, expected := range expectedViewTypes {
		assert.True(t, viewTypeNames[expected],
			"Expected ViewType with name %q to exist", expected)
	}

	t.Logf("Found %d ViewTypes: %v", len(viewTypeNames), viewTypeNames)
}

// Test 2: ViewType IDs are in the expected range (<= -6000)

func TestViewTypeIDsAreInExpectedRange(t *testing.T) {
	nodes := loadAllNodes(t)
	viewTypes := nodesByType(nodes, "ViewType")
	require.NotEmpty(t, viewTypes, "Should find at least one ViewType")

	for _, vt := range viewTypes {
		// Skip ViewTypes with ID 0 (unset or default)
		if vt.ID == 0 {
			continue
		}
		assert.LessOrEqual(t, vt.ID, -6000,
			"ViewType %q (ID: %d) should have ID <= -6000 in %s",
			vt.Name, vt.ID, vt.SourceFile)
	}
}

// Test 3: QueryViews have required fields

func TestQueryViewsHaveRequiredFields(t *testing.T) {
	nodes := loadAllNodes(t)
	queryViews := nodesByType(nodes, "QueryView")
	require.NotEmpty(t, queryViews, "Should find at least one QueryView")

	for _, qv := range queryViews {
		// Check name field
		assert.NotEmpty(t, qv.Name,
			"QueryView should have a name field in %s", qv.SourceFile)

		// Check identifier field
		assert.NotEmpty(t, qv.Identifier,
			"QueryView should have an identifier field in %s", qv.SourceFile)

		// Check non-zero ID
		assert.NotZero(t, qv.ID,
			"QueryView %q should have a non-zero ID in %s", qv.Name, qv.SourceFile)

		// Check query field in Raw map
		queryField, exists := qv.Raw["query"]
		assert.True(t, exists,
			"QueryView %q should have a query field in %s", qv.Name, qv.SourceFile)

		if exists {
			queryStr, ok := queryField.(string)
			assert.True(t, ok,
				"QueryView %q query field should be a string in %s", qv.Name, qv.SourceFile)
			assert.NotEmpty(t, queryStr,
				"QueryView %q query field should not be empty in %s", qv.Name, qv.SourceFile)
		}
	}
}

// Test 4: QueryViews with viewType reference valid ViewType identifiers

func TestQueryViewsReferenceViewTypes(t *testing.T) {
	nodes := loadAllNodes(t)
	queryViews := nodesByType(nodes, "QueryView")
	viewTypes := nodesByType(nodes, "ViewType")

	require.NotEmpty(t, queryViews, "Should find at least one QueryView")
	require.NotEmpty(t, viewTypes, "Should find at least one ViewType")

	// Build a map of valid ViewType identifiers
	viewTypeIdentifiers := make(map[string]bool)
	for _, vt := range viewTypes {
		if vt.Identifier != "" {
			viewTypeIdentifiers[vt.Identifier] = true
		}
	}

	// Check each QueryView's viewType reference
	for _, qv := range queryViews {
		viewTypeRef, exists := qv.Raw["viewType"]
		if exists {
			viewTypeStr, ok := viewTypeRef.(string)
			assert.True(t, ok,
				"QueryView %q viewType field should be a string in %s",
				qv.Name, qv.SourceFile)

			if ok && viewTypeStr != "" {
				assert.True(t, viewTypeIdentifiers[viewTypeStr],
					"QueryView %q references viewType %q which should exist in ViewType nodes (file: %s)",
					qv.Name, viewTypeStr, qv.SourceFile)
			}
		}
	}
}

// Test 5: MainMenuGroup items reference existing QueryView identifiers

func TestMainMenuGroupReferencesExistingViews(t *testing.T) {
	nodes := loadAllNodes(t)
	mainMenuGroups := nodesByType(nodes, "MainMenuGroup")
	queryViews := nodesByType(nodes, "QueryView")

	require.NotEmpty(t, mainMenuGroups, "Should find at least one MainMenuGroup")
	require.NotEmpty(t, queryViews, "Should find at least one QueryView")

	// Build a map of valid QueryView identifiers
	queryViewIdentifiers := make(map[string]bool)
	for _, qv := range queryViews {
		if qv.Identifier != "" {
			queryViewIdentifiers[qv.Identifier] = true
		}
	}

	// Check each MainMenuGroup's items
	for _, mmg := range mainMenuGroups {
		itemsRaw, exists := mmg.Raw["items"]
		if !exists {
			continue
		}

		items, ok := itemsRaw.([]interface{})
		assert.True(t, ok,
			"MainMenuGroup %q items should be an array in %s",
			mmg.Name, mmg.SourceFile)

		if !ok {
			continue
		}

		// Check each item in the array
		for i, itemRaw := range items {
			itemMap, ok := itemRaw.(map[string]interface{})
			assert.True(t, ok,
				"MainMenuGroup %q item[%d] should be a map in %s",
				mmg.Name, i, mmg.SourceFile)

			if !ok {
				continue
			}

			// Check for viewIdentifier key
			viewIdentifierRaw, exists := itemMap["viewIdentifier"]
			if exists {
				viewIdentifier, ok := viewIdentifierRaw.(string)
				assert.True(t, ok,
					"MainMenuGroup %q item[%d].viewIdentifier should be a string in %s",
					mmg.Name, i, mmg.SourceFile)

				if ok && viewIdentifier != "" {
					assert.True(t, queryViewIdentifiers[viewIdentifier],
						"MainMenuGroup %q item[%d] references viewIdentifier %q which should exist in QueryView nodes (file: %s)",
						mmg.Name, i, viewIdentifier, mmg.SourceFile)
				}
			}
		}
	}
}
