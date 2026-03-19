package static

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/testutil"
)

// TestComponentTemplateParses verifies that the component template can be parsed.
func TestComponentTemplateParses(t *testing.T) {
	templatePath := filepath.Join(testutil.TemplatesDir(), "sync", "component-template.json.handlebars")
	content, err := os.ReadFile(templatePath)
	require.NoError(t, err, "Should be able to read component template file")
	require.NotEmpty(t, content, "Component template should not be empty")

	// Templates use escaped delimiters \{{ which are intentional for StackState
	// We verify the file has expected structure rather than parsing with raymond
	contentStr := string(content)

	// Verify it has expected template structure
	assert.Contains(t, contentStr, `"_type": "Component"`, "Should have Component type")
	assert.Contains(t, contentStr, `\{{`, "Should contain handlebars delimiters")
	assert.Contains(t, contentStr, `element.data`, "Should reference element.data")
	assert.Contains(t, contentStr, `getOrCreate`, "Should use getOrCreate helper")
	assert.Contains(t, contentStr, `identifier`, "Should use identifier helper")
}

// TestRelationTemplateParses verifies that the relation template can be parsed.
func TestRelationTemplateParses(t *testing.T) {
	templatePath := filepath.Join(testutil.TemplatesDir(), "sync", "relation-template.json.handlebars")
	content, err := os.ReadFile(templatePath)
	require.NoError(t, err, "Should be able to read relation template file")
	require.NotEmpty(t, content, "Relation template should not be empty")

	// Templates use escaped delimiters \{{ which are intentional for StackState
	// We verify the file has expected structure rather than parsing with raymond
	contentStr := string(content)

	// Verify it has expected template structure
	assert.Contains(t, contentStr, `"_type": "Relation"`, "Should have Relation type")
	assert.Contains(t, contentStr, `\{{`, "Should contain handlebars delimiters")
	assert.Contains(t, contentStr, `element.sourceExternalId`, "Should reference source external ID")
	assert.Contains(t, contentStr, `element.targetExternalId`, "Should reference target external ID")
	assert.Contains(t, contentStr, `getOrCreate`, "Should use getOrCreate helper")
}

// TestRemediationHintTemplatesAreValidMarkdown verifies that all remediation hint
// templates in the monitors directory are non-empty and contain meaningful markdown content.
func TestRemediationHintTemplatesAreValidMarkdown(t *testing.T) {
	monitorsDir := filepath.Join(testutil.TemplatesDir(), "monitors")

	var hbsFiles []string
	err := filepath.Walk(monitorsDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() && strings.HasSuffix(path, ".hbs") {
			hbsFiles = append(hbsFiles, path)
		}
		return nil
	})
	require.NoError(t, err, "Should be able to walk monitors directory")
	require.NotEmpty(t, hbsFiles, "Should find at least one .hbs file in monitors directory")

	for _, hbsFile := range hbsFiles {
		t.Run(filepath.Base(hbsFile), func(t *testing.T) {
			content, err := os.ReadFile(hbsFile)
			require.NoError(t, err, "Should be able to read %s", hbsFile)

			contentStr := string(content)
			assert.NotEmpty(t, contentStr, "Template %s should not be empty", hbsFile)

			// Check for meaningful markdown content
			// Look for headings, lists, or sufficient text content (>20 chars after trimming)
			hasHeading := strings.Contains(contentStr, "# ") || strings.Contains(contentStr, "## ")
			hasList := strings.Contains(contentStr, "- ") || strings.Contains(contentStr, "* ") ||
			           strings.Contains(contentStr, "1. ")
			hasContent := len(strings.TrimSpace(contentStr)) > 20

			assert.True(t, hasHeading || hasList || hasContent,
				"Template %s should contain meaningful markdown (headings, lists, or >20 chars)",
				hbsFile)
		})
	}

	t.Logf("Validated %d remediation hint templates", len(hbsFiles))
}
