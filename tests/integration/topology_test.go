//go:build integration

package integration

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestStackStateIsReachable(t *testing.T) {
	err := client.Healthy()
	assert.NoError(t, err)
}
