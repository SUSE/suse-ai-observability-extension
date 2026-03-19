package stackstate

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"
)

// Client provides access to StackState API
type Client struct {
	baseURL    string
	token      string
	tokenType  string
	httpClient *http.Client
}

// NewClientFromEnv creates a new StackState client from environment variables
// Required env vars: STACKSTATE_API_URL, STACKSTATE_API_TOKEN
// Optional: STACKSTATE_TOKEN_TYPE (defaults to "Bearer"), STACKSTATE_SKIP_TLS (defaults to false)
func NewClientFromEnv() (*Client, error) {
	baseURL := os.Getenv("STACKSTATE_API_URL")
	if baseURL == "" {
		return nil, fmt.Errorf("STACKSTATE_API_URL environment variable is required")
	}

	token := os.Getenv("STACKSTATE_API_TOKEN")
	if token == "" {
		return nil, fmt.Errorf("STACKSTATE_API_TOKEN environment variable is required")
	}

	tokenType := os.Getenv("STACKSTATE_TOKEN_TYPE")
	if tokenType == "" {
		tokenType = "Bearer"
	}

	skipTLS := false
	if skipTLSStr := os.Getenv("STACKSTATE_SKIP_TLS"); skipTLSStr != "" {
		var err error
		skipTLS, err = strconv.ParseBool(skipTLSStr)
		if err != nil {
			return nil, fmt.Errorf("invalid STACKSTATE_SKIP_TLS value: %w", err)
		}
	}

	transport := &http.Transport{
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: skipTLS,
		},
	}

	httpClient := &http.Client{
		Timeout:   30 * time.Second,
		Transport: transport,
	}

	return &Client{
		baseURL:    baseURL,
		token:      token,
		tokenType:  tokenType,
		httpClient: httpClient,
	}, nil
}

// Healthy checks if the StackState API is reachable and healthy
func (c *Client) Healthy() error {
	req, err := http.NewRequest("GET", c.baseURL+"/api/server/info", nil)
	if err != nil {
		return fmt.Errorf("failed to create health check request: %w", err)
	}

	req.Header.Set("Authorization", c.tokenType+" "+c.token)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("health check returned status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

// QueryTopology executes a topology query against StackState
func (c *Client) QueryTopology(query string) (*TopologyQueryResult, error) {
	requestBody := map[string]interface{}{
		"query": query,
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal query: %w", err)
	}

	req, err := http.NewRequest("POST", c.baseURL+"/api/topology/query", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create topology query request: %w", err)
	}

	req.Header.Set("Authorization", c.tokenType+" "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("topology query failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("topology query returned status %d: %s", resp.StatusCode, string(body))
	}

	var result TopologyQueryResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode topology query response: %w", err)
	}

	return &result, nil
}
