//go:build integration

package integration

import (
	"fmt"
	"os"
	"testing"
	"time"

	"suse-ai-extension-tests/internal/stackstate"
)

var client *stackstate.Client

func TestMain(m *testing.M) {
	// Check if required environment variables are set
	if os.Getenv("STACKSTATE_API_URL") == "" {
		fmt.Println("Skipping integration tests: STACKSTATE_API_URL not set")
		os.Exit(0)
	}

	if os.Getenv("STACKSTATE_API_TOKEN") == "" {
		fmt.Println("Skipping integration tests: STACKSTATE_API_TOKEN not set")
		os.Exit(0)
	}

	// Initialize StackState client
	var err error
	client, err = stackstate.NewClientFromEnv()
	if err != nil {
		fmt.Printf("Failed to create StackState client: %v\n", err)
		os.Exit(1)
	}

	// Wait for StackState to be healthy (max 2 minutes)
	if err := waitForHealthy(client, 2*time.Minute); err != nil {
		fmt.Printf("StackState is not healthy: %v\n", err)
		os.Exit(1)
	}

	// Run tests
	exitCode := m.Run()
	os.Exit(exitCode)
}

func waitForHealthy(c *stackstate.Client, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		if err := c.Healthy(); err == nil {
			return nil
		}

		if time.Now().After(deadline) {
			return fmt.Errorf("timeout waiting for StackState to become healthy")
		}

		<-ticker.C
	}
}
