package static

import (
	"os"
	"path/filepath"
	"regexp"
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

func TestConfigRequiredFields(t *testing.T) {
	conf := loadConf(t)

	// name, version, displayName, provision, categories must be non-empty
	assert.NotEmpty(t, conf.Name, "name must not be empty")
	assert.NotEmpty(t, conf.Version, "version must not be empty")
	assert.NotEmpty(t, conf.DisplayName, "displayName must not be empty")
	assert.NotEmpty(t, conf.Provision, "provision must not be empty")
	assert.NotEmpty(t, conf.Categories, "categories must not be empty")
}

func TestConfigVersionFormat(t *testing.T) {
	conf := loadConf(t)

	// version matches ^\d+\.\d+\.\d+$
	versionPattern := regexp.MustCompile(`^\d+\.\d+\.\d+$`)
	assert.Regexp(t, versionPattern, conf.Version, "version must match semver format (e.g., 1.2.3)")
}

func TestConfigProvisionClassExists(t *testing.T) {
	conf := loadConf(t)

	// provisioning/<Provision>.groovy file must exist
	provisionFile := filepath.Join(testutil.ProvisioningDir(), conf.Provision+".groovy")
	_, err := os.Stat(provisionFile)
	assert.NoError(t, err, "provisioning file %s must exist", provisionFile)
}

func TestConfigurationURLsReferenceExistingFiles(t *testing.T) {
	conf := loadConf(t)

	// All 6 states must have URLs that resolve to files under resources/
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

		// Verify the file exists in resources/
		resourcePath := filepath.Join(testutil.ResourcesDir(), url)
		_, err := os.Stat(resourcePath)
		assert.NoError(t, err, "configuration URL for state %s (%s) must reference an existing file", state, url)
	}
}

func TestConfigOverviewFilesExist(t *testing.T) {
	conf := loadConf(t)

	// overviewUrl, detailedOverviewUrl, releaseNotes, logoUrl must reference existing files under resources/
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
