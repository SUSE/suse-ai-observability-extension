package static

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/parser"
	"suse-ai-extension-tests/internal/testutil"
)

func loadConf(t *testing.T) *parser.StackPackConf {
	t.Helper()
	confPath := filepath.Join(testutil.StackPackRoot(), "stackpack.conf")
	conf, err := parser.ParseStackPackConf(confPath)
	require.NoError(t, err)
	return conf
}

func TestConfigProvisionClassExists(t *testing.T) {
	conf := loadConf(t)

	provisionFile := filepath.Join(testutil.ProvisioningDir(), conf.Provision+".groovy")
	_, err := os.Stat(provisionFile)
	assert.NoError(t, err, "provisioning file %s must exist", provisionFile)
}

func TestConfigurationURLsReferenceExistingFiles(t *testing.T) {
	conf := loadConf(t)

	requiredStates := []string{
		"NOT_INSTALLED",
		"PROVISIONING",
		"WAITING_FOR_DATA",
		"INSTALLED",
		"DEPROVISIONING",
		"ERROR",
	}

	for _, state := range requiredStates {
		url, exists := conf.ConfigurationURLs[state]
		require.True(t, exists, "configurationUrls must contain state %s", state)
		require.NotEmpty(t, url, "configurationUrls[%s] must not be empty", state)

		resourcePath := filepath.Join(testutil.ResourcesDir(), url)
		_, err := os.Stat(resourcePath)
		assert.NoError(t, err, "configuration URL for state %s (%s) must reference an existing file", state, url)
	}
}

func TestConfigOverviewFilesExist(t *testing.T) {
	conf := loadConf(t)

	testCases := []struct {
		name string
		url  string
	}{
		{"overviewUrl", conf.OverviewURL},
		{"detailedOverviewUrl", conf.DetailedOverviewURL},
		{"releaseNotes", conf.ReleaseNotes},
		{"logoUrl", conf.LogoURL},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			require.NotEmpty(t, tc.url, "%s must not be empty", tc.name)

			resourcePath := filepath.Join(testutil.ResourcesDir(), tc.url)
			_, err := os.Stat(resourcePath)
			assert.NoError(t, err, "%s (%s) must reference an existing file", tc.name, tc.url)
		})
	}
}
