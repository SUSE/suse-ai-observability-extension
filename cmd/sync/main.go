package main

import (
	"github.com/ravan/stackstate-client/stackstate/receiver"
	"github.com/ravan/stackstate-openlit/internal/config"
	"github.com/ravan/stackstate-openlit/internal/sync"
	"log/slog"
	"os"
)

func main() {
	conf, err := config.GetConfig()

	if err != nil {
		slog.Error("failed to initialize", "error", err)
		os.Exit(1)
	}
	var factory *receiver.Factory
	factory, err = sync.Sync(&conf.Kubernetes)

	if err != nil {
		slog.Error("failed sync with kubernetes", "error", err)
		os.Exit(1)
	}

	sts := receiver.NewClient(&conf.StackState, &conf.Instance)
	err = sts.Send(factory)
	if err != nil {
		slog.Error("failed to send", "error", err)
		os.Exit(1)
	}
}
