package static

import (
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/parser"
	"suse-ai-extension-tests/internal/testutil"
)

func syncDir() string {
	return filepath.Join(testutil.TemplatesDir(), "sync")
}

func TestProductIDExtractorKnownProducts(t *testing.T) {
	script, err := parser.LoadGroovyScript(filepath.Join(syncDir(), "suse-ai-product-id-extractor.groovy"))
	require.NoError(t, err)

	switchCases := script.ExtractSwitchCases()
	expectedProducts := []string{"vllm", "ollama", "qdrant", "milvus", "opensearch", "elasticsearch", "litellm", "mlflow"}

	for _, product := range expectedProducts {
		assert.Contains(t, switchCases, product, "Product ID extractor must handle known product: %s", product)
	}
}

func TestComponentMappingKnownTypes(t *testing.T) {
	script, err := parser.LoadGroovyScript(filepath.Join(syncDir(), "component-mapping-function.groovy"))
	require.NoError(t, err)

	switchCases := script.ExtractSwitchCases()
	expectedTypes := []string{"ui", "frontend", "app", "application", "agent", "llm-model", "vectordb"}

	for _, componentType := range expectedTypes {
		assert.Contains(t, switchCases, componentType, "Component mapping must handle known type: %s", componentType)
	}
}

func TestAllGroovyScriptsUseToStringOnExternalId(t *testing.T) {
	scripts := []string{
		"suse-ai-id-extractor.groovy",
		"suse-ai-product-id-extractor.groovy",
		"component-mapping-function.groovy",
	}

	for _, scriptName := range scripts {
		t.Run(scriptName, func(t *testing.T) {
			script, err := parser.LoadGroovyScript(filepath.Join(syncDir(), scriptName))
			require.NoError(t, err)

			missingToString := script.FindMissingToString()
			assert.Empty(t, missingToString, "Script %s must use .toString() on all externalId assignments. Found issues:\n%v", scriptName, missingToString)
		})
	}
}
