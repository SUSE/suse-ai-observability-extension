package sync

import (
	"github.com/joho/godotenv"
	"github.com/ravan/stackstate-client/stackstate/receiver"
	"github.com/ravan/stackstate-openlit/internal/config"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"os"
	"testing"
)

func TestSync(t *testing.T) {
	conf := getConfig(t)
	factory, err := Sync(conf)
	require.NoError(t, err)
	assert.Equal(t, 15, factory.GetComponentCount())

	sts := receiver.NewClient(&conf.StackState, &conf.Instance)
	err = sts.Send(factory)
	require.NoError(t, err)
}

func getConfig(t *testing.T) *config.Configuration {
	require.NoError(t, os.Setenv("CONFIG_FILE", "../../conf.yaml"))
	require.NoError(t, godotenv.Load("../../.env"))
	require.NoError(t, os.Setenv("stackstate.api_url", os.Getenv("STS_URL")))
	require.NoError(t, os.Setenv("stackstate.api_key", os.Getenv("STS_API_KEY")))
	require.NoError(t, os.Setenv("stackstate.api_token", os.Getenv("STS_API_TOKEN")))
	require.NoError(t, os.Setenv("stackstate.legacy_api", os.Getenv("STS_LEGACY_API")))

	c, err := config.GetConfig()
	require.NoError(t, err)
	return c
}
