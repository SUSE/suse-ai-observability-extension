package static

import (
	"encoding/base64"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/parser"
	"suse-ai-extension-tests/internal/testutil"
)

// --- §1: Icon Validation ---

func TestIconBase64HasValidPrefix(t *testing.T) {
	nodes := loadAllNodes(t)

	validPrefixes := []string{
		"data:image/png;base64,",
		"data:image/svg+xml;base64,",
	}

	for _, node := range nodes {
		icon, ok := node.Raw["iconbase64"].(string)
		if !ok || icon == "" {
			continue
		}
		t.Run(node.Type+"/"+node.Name, func(t *testing.T) {
			hasValidPrefix := false
			for _, prefix := range validPrefixes {
				if strings.HasPrefix(icon, prefix) {
					hasValidPrefix = true
					break
				}
			}
			assert.True(t, hasValidPrefix,
				"%s %q has iconbase64 without valid prefix (must start with data:image/png;base64, or data:image/svg+xml;base64,)",
				node.Type, node.Name)
		})
	}
}

func TestIconBase64IsValidEncoding(t *testing.T) {
	nodes := loadAllNodes(t)

	prefixes := []string{
		"data:image/png;base64,",
		"data:image/svg+xml;base64,",
	}

	for _, node := range nodes {
		icon, ok := node.Raw["iconbase64"].(string)
		if !ok || icon == "" {
			continue
		}
		t.Run(node.Type+"/"+node.Name, func(t *testing.T) {
			// Strip the data URI prefix to get raw base64
			b64 := icon
			for _, prefix := range prefixes {
				b64 = strings.TrimPrefix(b64, prefix)
			}
			_, err := base64.StdEncoding.DecodeString(b64)
			assert.NoError(t, err,
				"%s %q has invalid base64 encoding in iconbase64", node.Type, node.Name)
		})
	}
}

func TestIconBase64IsSingleLine(t *testing.T) {
	// Large base64 strings must be single-line — multiline breaks YAML parsing
	// We check this at the raw file level, not via parsed YAML (which would already collapse lines)
	templatesDir := testutil.TemplatesDir()

	err := filepath.Walk(templatesDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || filepath.Ext(path) != ".sty" {
			return err
		}
		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}

		lines := strings.Split(string(content), "\n")
		for i, line := range lines {
			trimmed := strings.TrimSpace(line)
			if !strings.HasPrefix(trimmed, "iconbase64:") {
				continue
			}
			// The value should be on the same line after the key
			// If there's a value, it shouldn't continue onto the next line
			// (next line starting with base64 chars without a YAML key)
			if i+1 < len(lines) {
				nextTrimmed := strings.TrimSpace(lines[i+1])
				// If next line looks like continuation base64 (no YAML key, no list, no comment)
				if nextTrimmed != "" &&
					!strings.HasPrefix(nextTrimmed, "-") &&
					!strings.HasPrefix(nextTrimmed, "#") &&
					!strings.Contains(nextTrimmed, ":") &&
					!strings.HasPrefix(nextTrimmed, "_type") {
					relPath, _ := filepath.Rel(templatesDir, path)
					t.Errorf("iconbase64 at %s:%d appears to span multiple lines — must be single-line",
						relPath, i+1)
				}
			}
		}
		return nil
	})
	require.NoError(t, err)
}

// --- §2: Provisioning Constraints ---

func TestSyncNodesHaveComponentActions(t *testing.T) {
	nodes := loadAllNodes(t)
	syncs := nodesByType(nodes, "Sync")
	require.NotEmpty(t, syncs, "Should find at least one Sync node")

	for _, sync := range syncs {
		t.Run(sync.Name, func(t *testing.T) {
			_, hasField := sync.Raw["componentActions"]
			assert.True(t, hasField,
				"Sync %q must have componentActions field (even if empty)", sync.Name)
		})
	}
}

// --- §3: Include Path Validation ---

func TestIncludePathsNotDoublePrefixed(t *testing.T) {
	templatesDir := testutil.TemplatesDir()

	err := filepath.Walk(testutil.ProvisioningDir(), func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return err
		}
		ext := filepath.Ext(path)
		if ext != ".sty" && ext != ".handlebars" {
			return nil
		}

		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}

		includes := parser.ExtractIncludes(string(content))
		for _, inc := range includes {
			if strings.HasPrefix(inc.Path, "provisioning/") {
				relPath, _ := filepath.Rel(templatesDir, path)
				t.Errorf("%s: include path %q starts with 'provisioning/' — this causes NoSuchFileException (paths resolve from provisioning/ already)",
					relPath, inc.Path)
			}
		}
		return nil
	})
	require.NoError(t, err)
}

// --- §4: Component Schema ---

func TestQueryViewsHaveQueryVersion(t *testing.T) {
	nodes := loadAllNodes(t)
	queryViews := nodesByType(nodes, "QueryView")
	require.NotEmpty(t, queryViews, "Should find at least one QueryView")

	for _, qv := range queryViews {
		t.Run(qv.Name, func(t *testing.T) {
			version, ok := qv.Raw["queryVersion"].(string)
			assert.True(t, ok && version != "",
				"QueryView %q must have a queryVersion field", qv.Name)
		})
	}
}

func TestComponentTypeHighlightsHaveAbout(t *testing.T) {
	nodes := loadAllNodes(t)
	componentTypes := nodesByType(nodes, "ComponentType")

	// OTel compatibility types don't have highlights
	compatTypes := map[string]bool{
		"service": true, "service-instance": true,
		"pod": true, "namespace": true, "node": true,
	}

	for _, ct := range componentTypes {
		if compatTypes[ct.Name] {
			continue
		}
		t.Run(ct.Name, func(t *testing.T) {
			highlights, ok := ct.Raw["highlights"].(map[string]interface{})
			if !ok {
				return // no highlights = tested elsewhere
			}
			_, hasAbout := highlights["about"]
			assert.True(t, hasAbout,
				"ComponentType %q highlights must have an 'about' section", ct.Name)
		})
	}
}

// --- §7: STY Indentation ---

func TestSTYTopLevelItemsIndentedWithTwoSpaces(t *testing.T) {
	// CERTAINS §7: Top-level list items in included STY files MUST be indented
	// with exactly 2 spaces ("  - _type: ..."). Nested _type fields (inside
	// highlights, fields, etc.) have deeper indentation and are not top-level.
	//
	// We identify top-level items by checking for "  - _type:" at the start of
	// the line. Any "- _type:" with different indentation is either nested
	// (more indentation) or incorrectly formatted (less indentation).
	templatesDir := testutil.TemplatesDir()

	// Known top-level _type values that appear as root-level STY nodes
	topLevelTypes := map[string]bool{
		"ComponentType": true, "MetricBinding": true, "Monitor": true,
		"QueryView": true, "ViewType": true, "Sync": true,
		"DataSource": true, "Layer": true, "Domain": true,
		"MainMenuGroup": true, "RelationType": true,
		"IdExtractorFunction": true, "ComponentMappingFunction": true,
		"ComponentTemplateFunction": true, "RelationTemplateFunction": true,
		"TraceBinding": true, "SpanToComponentBinding": true,
	}

	err := filepath.Walk(templatesDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || filepath.Ext(path) != ".sty" {
			return err
		}
		if filepath.Base(path) == "suse-ai.sty" {
			return nil
		}

		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}

		lines := strings.Split(string(content), "\n")
		for i, line := range lines {
			trimmed := strings.TrimSpace(line)
			if !strings.HasPrefix(trimmed, "- _type:") {
				continue
			}
			// Extract the type value
			typePart := strings.TrimPrefix(trimmed, "- _type:")
			typePart = strings.TrimSpace(typePart)
			typePart = strings.Trim(typePart, `"' `)

			if !topLevelTypes[typePart] {
				continue // nested _type, skip
			}

			if !strings.HasPrefix(line, "  - ") {
				relPath, _ := filepath.Rel(templatesDir, path)
				t.Errorf("%s:%d: top-level %s must be indented with exactly 2 spaces",
					relPath, i+1, typePart)
			}
		}
		return nil
	})
	require.NoError(t, err)
}
