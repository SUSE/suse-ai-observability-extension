package stackstate

import (
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"os"
)

// CreateTLSConfig creates a TLS configuration based on the provided StackState config
func CreateTLSConfig(conf *StackState) (*tls.Config, error) {
	tlsConfig := &tls.Config{
		InsecureSkipVerify: conf.TLSSkipVerify,
	}

	// Load CA certificate if provided
	if conf.TLSCAFile != "" {
		caCert, err := os.ReadFile(conf.TLSCAFile)
		if err != nil {
			return nil, fmt.Errorf("failed to read CA certificate from %s: %w", conf.TLSCAFile, err)
		}
		caCertPool := x509.NewCertPool()
		if !caCertPool.AppendCertsFromPEM(caCert) {
			return nil, fmt.Errorf("failed to parse CA certificate from %s", conf.TLSCAFile)
		}
		tlsConfig.RootCAs = caCertPool
	}

	// Load client certificate and key if both provided
	if conf.TLSCertFile != "" && conf.TLSKeyFile != "" {
		cert, err := tls.LoadX509KeyPair(conf.TLSCertFile, conf.TLSKeyFile)
		if err != nil {
			return nil, fmt.Errorf("failed to load client certificate: cert=%s, key=%s, error: %w", conf.TLSCertFile, conf.TLSKeyFile, err)
		}
		tlsConfig.Certificates = []tls.Certificate{cert}
	} else if conf.TLSCertFile != "" || conf.TLSKeyFile != "" {
		return nil, errors.New("both tls_cert_file and tls_key_file must be provided together")
	}

	return tlsConfig, nil
}
