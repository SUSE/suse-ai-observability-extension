package static

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestQueryViewsReferenceViewTypes(t *testing.T) {
	nodes := loadAllNodes(t)
	queryViews := nodesByType(nodes, "QueryView")
	viewTypes := nodesByType(nodes, "ViewType")

	require.NotEmpty(t, queryViews, "Should find at least one QueryView")
	require.NotEmpty(t, viewTypes, "Should find at least one ViewType")

	viewTypeIdentifiers := make(map[string]bool)
	for _, vt := range viewTypes {
		if vt.Identifier != "" {
			viewTypeIdentifiers[vt.Identifier] = true
		}
	}

	for _, qv := range queryViews {
		viewTypeRef, exists := qv.Raw["viewType"]
		if !exists {
			continue
		}
		viewTypeStr, ok := viewTypeRef.(string)
		if !ok || viewTypeStr == "" {
			continue
		}
		assert.True(t, viewTypeIdentifiers[viewTypeStr],
			"QueryView %q references viewType %q which doesn't exist (file: %s)",
			qv.Name, viewTypeStr, qv.SourceFile)
	}
}

func TestMainMenuGroupReferencesExistingViews(t *testing.T) {
	nodes := loadAllNodes(t)
	mainMenuGroups := nodesByType(nodes, "MainMenuGroup")
	queryViews := nodesByType(nodes, "QueryView")

	require.NotEmpty(t, mainMenuGroups, "Should find at least one MainMenuGroup")
	require.NotEmpty(t, queryViews, "Should find at least one QueryView")

	queryViewIdentifiers := make(map[string]bool)
	for _, qv := range queryViews {
		if qv.Identifier != "" {
			queryViewIdentifiers[qv.Identifier] = true
		}
	}

	for _, mmg := range mainMenuGroups {
		itemsRaw, exists := mmg.Raw["items"]
		if !exists {
			continue
		}
		items, ok := itemsRaw.([]interface{})
		if !ok {
			continue
		}
		for i, itemRaw := range items {
			itemMap, ok := itemRaw.(map[string]interface{})
			if !ok {
				continue
			}
			viewIdentifier, ok := itemMap["viewIdentifier"].(string)
			if !ok || viewIdentifier == "" {
				continue
			}
			assert.True(t, queryViewIdentifiers[viewIdentifier],
				"MainMenuGroup %q item[%d] references viewIdentifier %q which doesn't exist (file: %s)",
				mmg.Name, i, viewIdentifier, mmg.SourceFile)
		}
	}
}
