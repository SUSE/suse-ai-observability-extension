package otel

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// Sender provides functionality to send metrics to an OpenTelemetry endpoint
type Sender struct {
	endpoint   string
	httpClient *http.Client
}

// NewSenderFromEnv creates a new OTel sender from environment variables
// Required env var: OTEL_ENDPOINT
func NewSenderFromEnv() (*Sender, error) {
	endpoint := os.Getenv("OTEL_ENDPOINT")
	if endpoint == "" {
		return nil, fmt.Errorf("OTEL_ENDPOINT environment variable is required")
	}

	httpClient := &http.Client{
		Timeout: 30 * time.Second,
	}

	return &Sender{
		endpoint:   endpoint,
		httpClient: httpClient,
	}, nil
}

// SendMetrics sends a metrics payload to the OpenTelemetry endpoint
func (s *Sender) SendMetrics(payload []byte) error {
	url := s.endpoint + "/v1/metrics"

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(payload))
	if err != nil {
		return fmt.Errorf("failed to create metrics request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send metrics: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("metrics request returned status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}
