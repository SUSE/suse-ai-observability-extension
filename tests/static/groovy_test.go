package static

import (
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/parser"
	"suse-ai-extension-tests/internal/testutil"
)

// syncDir returns the path to the templates/sync directory.
func syncDir() string {
	return filepath.Join(testutil.TemplatesDir(), "sync")
}

func TestIDExtractorHasPrefix(t *testing.T) {
	scriptPath := filepath.Join(syncDir(), "suse-ai-id-extractor.groovy")
	script, err := parser.LoadGroovyScript(scriptPath)
	require.NoError(t, err)

	assert.True(t, script.ContainsPattern(`suse-ai:`), "ID extractor must contain suse-ai: prefix")
	assert.True(t, script.ContainsPattern(`Sts\.createId`), "ID extractor must use Sts.createId")
}

func TestIDExtractorHandlesBothComponentsAndRelations(t *testing.T) {
	scriptPath := filepath.Join(syncDir(), "suse-ai-id-extractor.groovy")
	script, err := parser.LoadGroovyScript(scriptPath)
	require.NoError(t, err)

	assert.True(t, script.ContainsPattern(`sourceExternalId`), "ID extractor must handle sourceExternalId for relations")
	assert.True(t, script.ContainsPattern(`isRelation`), "ID extractor must check isRelation")
}

func TestIDExtractorFiltersOnAITags(t *testing.T) {
	scriptPath := filepath.Join(syncDir(), "suse-ai-id-extractor.groovy")
	script, err := parser.LoadGroovyScript(scriptPath)
	require.NoError(t, err)

	assert.True(t, script.ContainsPattern(`suse\.ai`), "ID extractor must filter on suse.ai tags")
	assert.True(t, script.ContainsPattern(`gen_ai\.`), "ID extractor must filter on gen_ai. tags")
}

func TestIDExtractorSkipsProductComponents(t *testing.T) {
	scriptPath := filepath.Join(syncDir(), "suse-ai-id-extractor.groovy")
	script, err := parser.LoadGroovyScript(scriptPath)
	require.NoError(t, err)

	assert.True(t, script.ContainsPattern(`suse\.ai\.component\.name`), "ID extractor must check suse.ai.component.name to skip products")
}

func TestProductIDExtractorPattern(t *testing.T) {
	scriptPath := filepath.Join(syncDir(), "suse-ai-product-id-extractor.groovy")
	script, err := parser.LoadGroovyScript(scriptPath)
	require.NoError(t, err)

	assert.True(t, script.ContainsPattern(`suse-ai:product:`), "Product ID extractor must contain suse-ai:product: prefix")
	assert.True(t, script.ContainsPattern(`suse\.ai\.component\.name`), "Product ID extractor must use suse.ai.component.name")
	assert.True(t, script.ContainsPattern(`suse\.ai\.component\.type`), "Product ID extractor must use suse.ai.component.type")
}

func TestProductIDExtractorKnownProducts(t *testing.T) {
	scriptPath := filepath.Join(syncDir(), "suse-ai-product-id-extractor.groovy")
	script, err := parser.LoadGroovyScript(scriptPath)
	require.NoError(t, err)

	switchCases := script.ExtractSwitchCases()
	expectedProducts := []string{"vllm", "ollama", "qdrant", "milvus", "opensearch", "elasticsearch", "litellm", "mlflow"}

	for _, product := range expectedProducts {
		assert.Contains(t, switchCases, product, "Product ID extractor must handle known product: %s", product)
	}
}

func TestComponentMappingKnownTypes(t *testing.T) {
	scriptPath := filepath.Join(syncDir(), "component-mapping-function.groovy")
	script, err := parser.LoadGroovyScript(scriptPath)
	require.NoError(t, err)

	switchCases := script.ExtractSwitchCases()
	expectedTypes := []string{"ui", "frontend", "app", "application", "agent", "llm-model", "vectordb"}

	for _, componentType := range expectedTypes {
		assert.Contains(t, switchCases, componentType, "Component mapping must handle known type: %s", componentType)
	}
}

func TestComponentMappingLayerAssignment(t *testing.T) {
	scriptPath := filepath.Join(syncDir(), "component-mapping-function.groovy")
	script, err := parser.LoadGroovyScript(scriptPath)
	require.NoError(t, err)

	assert.True(t, script.ContainsPattern(`isApplicationLayer`), "Component mapping must assign isApplicationLayer")
	assert.True(t, script.ContainsPattern(`isModelLayer`), "Component mapping must assign isModelLayer")
}

func TestComponentMappingCategoryLabelOnlyOnProducts(t *testing.T) {
	scriptPath := filepath.Join(syncDir(), "component-mapping-function.groovy")
	script, err := parser.LoadGroovyScript(scriptPath)
	require.NoError(t, err)

	assert.True(t, script.ContainsPattern(`suse-ai:product:`), "Component mapping must check for suse-ai:product: prefix")
	assert.True(t, script.ContainsPattern(`suse\.ai\.category`), "Component mapping must use suse.ai.category for products")
}

func TestAllGroovyScriptsUseToStringOnExternalId(t *testing.T) {
	scripts := []string{
		"suse-ai-id-extractor.groovy",
		"suse-ai-product-id-extractor.groovy",
		"component-mapping-function.groovy",
	}

	for _, scriptName := range scripts {
		t.Run(scriptName, func(t *testing.T) {
			scriptPath := filepath.Join(syncDir(), scriptName)
			script, err := parser.LoadGroovyScript(scriptPath)
			require.NoError(t, err)

			missingToString := script.FindMissingToString()
			assert.Empty(t, missingToString, "Script %s must use .toString() on all externalId assignments. Found issues:\n%v", scriptName, missingToString)
		})
	}
}
