package main

import (
	"genai-observability/internal/config"
	"genai-observability/internal/sync"
	"genai-observability/stackstate/receiver"
	"log/slog"
	"os"
)

func main() {
	conf, err := config.GetConfig()

	if err != nil {
		slog.Error("failed to initialize", "error", err)
		os.Exit(1)
	}

	cIdFactory := new(identifier.ComponentIdentifierFactory)
	cId, err := cIdFactory.Build(conf)
	cId.Sync()

	sts := receiver.NewClient(&conf.StackState, &conf.Instance)
	err = sts.Send(cId.GetBuilder())
	if err != nil {
		slog.Error("failed to send", "error", err)
		os.Exit(1)
	}
}
