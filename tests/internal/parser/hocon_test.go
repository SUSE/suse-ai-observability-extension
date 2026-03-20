package parser

import (
	"path/filepath"
	"testing"

	"suse-ai-extension-tests/internal/testutil"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestParseStackPackConf(t *testing.T) {
	confPath := filepath.Join(testutil.StackPackRoot(), "stackpack.conf")
	conf, err := ParseStackPackConf(confPath)
	require.NoError(t, err)

	assert.Equal(t, "suse-ai", conf.Name)
	assert.Equal(t, "SUSE AI Observability", conf.DisplayName)
	assert.NotEmpty(t, conf.Version)
	assert.Equal(t, "SuseAiProvision", conf.Provision)
	assert.Contains(t, conf.Categories, "AI")
	assert.Contains(t, conf.Categories, "GenAI")
	assert.NotEmpty(t, conf.ConfigurationURLs)
	assert.Equal(t, "configuration.md", conf.ConfigurationURLs["NOT_INSTALLED"])
	assert.Equal(t, "overview.md", conf.OverviewURL)
	assert.Equal(t, "detailed-overview.md", conf.DetailedOverviewURL)
	assert.Equal(t, "RELEASE.md", conf.ReleaseNotes)
	assert.Equal(t, "logo.png", conf.LogoURL)
	assert.Equal(t, "3.4.2", conf.Dependencies["common"])
}
