package stackstate

import (
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"testing"
)

func TestCreateTLSConfig(t *testing.T) {
	t.Run("default configuration", func(t *testing.T) {
		conf := &StackState{
			TLSSkipVerify: true,
		}

		tlsConfig, err := CreateTLSConfig(conf)
		require.NoError(t, err)
		assert.True(t, tlsConfig.InsecureSkipVerify)
		assert.Nil(t, tlsConfig.RootCAs)
		assert.Empty(t, tlsConfig.Certificates)
	})

	t.Run("secure configuration", func(t *testing.T) {
		conf := &StackState{
			TLSSkipVerify: false,
		}

		tlsConfig, err := CreateTLSConfig(conf)
		require.NoError(t, err)
		assert.False(t, tlsConfig.InsecureSkipVerify)
		assert.Nil(t, tlsConfig.RootCAs)
		assert.Empty(t, tlsConfig.Certificates)
	})

	t.Run("missing cert files", func(t *testing.T) {
		conf := &StackState{
			TLSSkipVerify: false,
			TLSCertFile:   "/nonexistent/cert.pem",
			TLSKeyFile:    "/nonexistent/key.pem",
		}

		_, err := CreateTLSConfig(conf)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "failed to load client certificate")
	})

	t.Run("mismatched cert and key", func(t *testing.T) {
		conf := &StackState{
			TLSSkipVerify: false,
			TLSCertFile:   "/nonexistent/cert.pem",
		}

		_, err := CreateTLSConfig(conf)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "both tls_cert_file and tls_key_file must be provided together")
	})
}
