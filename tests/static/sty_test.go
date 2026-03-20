package static

import (
	"testing"

	"suse-ai-extension-tests/internal/parser"
)

func TestIDsAreUniqueAcrossAllNodes(t *testing.T) {
	nodes := loadAllNodes(t)

	idMap := make(map[int][]parser.STYNode)
	for _, node := range nodes {
		if node.ID != 0 {
			idMap[node.ID] = append(idMap[node.ID], node)
		}
	}

	for id, nodeList := range idMap {
		if len(nodeList) > 1 {
			t.Errorf("ID %d is used by %d nodes:", id, len(nodeList))
			for _, node := range nodeList {
				t.Errorf("  - Type: %s, Name: %q, File: %s", node.Type, node.Name, node.SourceFile)
			}
		}
	}
}

func TestIdentifiersAreUniqueAcrossAllNodes(t *testing.T) {
	nodes := loadAllNodes(t)

	identifierMap := make(map[string][]parser.STYNode)
	for _, node := range nodes {
		if node.Identifier != "" {
			identifierMap[node.Identifier] = append(identifierMap[node.Identifier], node)
		}
	}

	for identifier, nodeList := range identifierMap {
		if len(nodeList) > 1 {
			t.Errorf("Identifier %q is used by %d nodes:", identifier, len(nodeList))
			for _, node := range nodeList {
				t.Errorf("  - Type: %s, Name: %q, File: %s", node.Type, node.Name, node.SourceFile)
			}
		}
	}
}
