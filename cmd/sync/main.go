package main

import (
	"genai-observability/stackstate/receiver"
	"genai-observability/internal/config"
	"genai-observability/internal/sync"
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
	factory, err = sync.Sync(conf)

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
